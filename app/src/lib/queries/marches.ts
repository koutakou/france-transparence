/**
 * Requêtes de la page « Marchés publics » (/marches) — module DECP (S1),
 * BOAMP (S2) et APProch (S9). Lecture seule sur data/france.db via getDb().
 *
 * Sémantique des montants (pipelines/ingest_decp.py, fiche S1) :
 * - montant_retenu = montant_rationalise si présent, sinon montant (valeur
 *   à afficher) ; les AGRÉGATS (decp_agg_*, decp_top_*, decp_repartition)
 *   somment least(montant_retenu, 100 M€) — écrêtage anti-saisie aberrante ;
 *   le détail (decp_derniers_marches) conserve les montants NON écrêtés
 *   avec le drapeau montant_suspect ;
 * - montants d'accords-cadres = MAXIMUMS notifiés, pas du dépensé ;
 * - latence légale de publication ≤ 2 mois : fenêtres récentes incomplètes ;
 * - top titulaires : montant divisé par le nombre de co-titulaires ;
 * - decp_agg_departement.montant_total NULL = aucun montant connu (≠ 0).
 *
 * BOAMP : ao_en_cours est un instantané quotidien — on re-filtre TOUJOURS
 * annulee = 0 ET date_limite_reponse > datetime('now') à la requête.
 * APProch : acheteur = SIREN seul (nom récupéré via entites quand connu),
 * montants en tranches TEXTE non sommables.
 *
 * Toutes les requêtes de ce fichier ont été éprouvées sur la base réelle
 * (sqlite3 mode ro) le 19/08/2026.
 */
import fs from "node:fs";
import path from "node:path";
import type { FeatureCollection, Geometry } from "geojson";
import { getDb, type MetaSource } from "@/lib/db";

/* ------------------------------------------------------------------ */
/* Types de lignes                                                     */
/* ------------------------------------------------------------------ */

export type DepartementAgg = {
  departement_code: string;
  departement_nom: string | null;
  nb_marches: number;
  /** Somme des montants retenus écrêtés — NULL = aucun montant connu (≠ 0). */
  montant_total: number | null;
  nb_marches_ecretes: number;
};

export type MoisAgg = {
  mois: string; // 'YYYY-MM'
  nb_marches: number;
  montant_total: number | null; // écrêté
};

export type TopAcheteur = {
  rang: number;
  siret: string | null;
  nom: string | null;
  nb_marches: number;
  montant_total: number | null; // écrêté
};

export type TopTitulaire = TopAcheteur & {
  /** PME / ETI / GE quand connue. */
  categorie: string | null;
};

export type RepartitionProcedure = {
  /** NULL = procédure non renseignée à la source (catégorie à afficher). */
  valeur: string | null;
  nb_marches: number;
  montant_total: number | null; // écrêté
};

export type DernierMarche = {
  rang: number;
  uid: string;
  date_notification: string;
  acheteur_nom: string | null;
  objet: string | null;
  titulaire_nom: string | null;
  nb_titulaires: number;
  /** NON écrêté (détail) — le drapeau montant_suspect l'étiquette. */
  montant_retenu: number | null;
  montant_suspect: number; // 0/1
  techniques: string | null; // contient « Accord-cadre » → montant = maximum
};

export type FamilleAO = {
  famille: string;
  famille_libelle: string | null;
  nb: number;
};

export type AoEnCours = {
  idweb: string;
  objet: string | null;
  acheteur: string | null;
  /** NULL = montant non publié dans l'annonce (~70 % des cas). */
  montant_estime: number | null;
  date_limite_reponse: string; // ISO datetime UTC
  url_avis: string | null;
};

export type AnnoncesJour = {
  jour: string; // ISO date
  nb: number;
  nb_appels_offre: number;
  nb_attributions: number;
};

export type MarcheAVenir = {
  code: string;
  intitule: string | null;
  acheteur_siren: string | null;
  /** Nom résolu via entites (référentiel) — NULL si SIREN inconnu du référentiel. */
  acheteur_nom: string | null;
  categorie_achat: string | null;
  montant_estime_tranche: string | null; // tranche texte non sommable
  date_prev_publication: string;
  lien_consultation: string | null;
};

export type AlerteMarches = {
  id: string;
  type: string;
  gravite: string; // haute / moyenne / info
  titre: string;
  detail: string | null;
  regle: string | null;
  base_legale: string | null;
  source_url: string | null;
  date_calcul: string;
};

export type DonneesMarches = {
  /** Fraîcheur par source — absentes de meta_sources = undefined. */
  meta: { s1?: MetaSource; s2?: MetaSource; s9?: MetaSource };
  kpis: {
    nbMarches12m: number;
    montant12m: number | null; // écrêté
    nbMarches30j: number;
    aoEnCours: number;
    marchesAVenir: number;
    /** Marchés > 100 M€ écrêtés dans les agrégats 12 mois (acheteurs à département connu). */
    nbEcretes12m: number;
  };
  departements: DepartementAgg[];
  serieMensuelle: MoisAgg[]; // 36 mois, ordre chronologique
  topAcheteurs: TopAcheteur[];
  topTitulaires: TopTitulaire[];
  repartitionProcedure: RepartitionProcedure[]; // ordre nb_marches décroissant
  derniersMarches: DernierMarche[];
  familles: FamilleAO[]; // familles BOAMP réellement en cours, nb décroissant
  familleActive: string | null; // famille demandée, validée contre la liste
  ao: AoEnCours[]; // 20 échéances les plus proches (filtre appliqué)
  aoTotalFiltre: number; // total d'AO en cours pour le filtre courant
  aoSansMontantFiltre: number; // dont montant non publié
  annoncesParJour: AnnoncesJour[]; // 31 jours, ordre chronologique
  marchesAVenir: MarcheAVenir[]; // 20 publications prévues les plus proches
  alertes: AlerteMarches[]; // alertes du domaine (vide aujourd'hui)
};

/* ------------------------------------------------------------------ */
/* Chargement                                                          */
/* ------------------------------------------------------------------ */

/**
 * Charge tout le nécessaire de la page /marches en une passe.
 * `null` tant que la base n'existe pas (message honnête côté page).
 * `familleDemandee` (searchParam) est validée contre les familles réelles.
 */
export function chargerDonneesMarches(
  familleDemandee: string | null,
): DonneesMarches | null {
  const db = getDb();
  if (!db) return null;

  const meta = db
    .prepare("SELECT * FROM meta_sources WHERE source_id IN ('S1','S2','S9')")
    .all() as MetaSource[];
  const metaPar = (id: string) => meta.find((m) => m.source_id === id);

  // KPI 12 mois : totaux des agrégats précalculés (fenêtre 12 mois du
  // pipeline, écrêtés) — dimension 'procedure' couvre 100 % des marchés.
  // Vérifié : 298 065 marchés / 271,31 Md€ le 19/08/2026.
  const total12m = db
    .prepare(
      `SELECT SUM(nb_marches) AS nb, SUM(montant_total) AS montant
       FROM decp_repartition WHERE dimension = 'procedure'`,
    )
    .get() as { nb: number | null; montant: number | null };

  // Vérifié : 19 619 marchés notifiés sur les 30 derniers jours (19/08/2026).
  const nb30j = db
    .prepare(
      `SELECT COUNT(*) AS nb FROM decp_marches
       WHERE date_notification >= date('now', '-30 days')`,
    )
    .get() as { nb: number };

  // Instantané BOAMP re-filtré au moment de la requête (annulations +
  // dates limites passées écartées). Vérifié : 9 005 le 19/08/2026.
  const aoEnCours = db
    .prepare(
      `SELECT COUNT(*) AS nb FROM ao_en_cours
       WHERE annulee = 0 AND date_limite_reponse > datetime('now')`,
    )
    .get() as { nb: number };

  // Vérifié : 4 060 projets APProch (tous à publication future).
  const aVenir = db
    .prepare("SELECT COUNT(*) AS nb FROM marches_a_venir")
    .get() as { nb: number };

  // Vérifié : 402 marchés écrêtés (12 mois, acheteurs à département connu).
  const ecretes = db
    .prepare(
      "SELECT SUM(nb_marches_ecretes) AS nb FROM decp_agg_departement",
    )
    .get() as { nb: number | null };

  // Carte : 107 départements, montants déjà écrêtés, NULL = aucun montant
  // connu. Vérifié : Paris (75) 37,55 Md€ / 15 838 marchés.
  const departements = db
    .prepare(
      `SELECT departement_code, departement_nom, nb_marches, montant_total,
              nb_marches_ecretes
       FROM decp_agg_departement ORDER BY departement_code`,
    )
    .all() as DepartementAgg[];

  // Série mensuelle 36 mois. Vérifié : 2023-09 → 2026-08,
  // juillet 2026 = 27 185 marchés / 29,64 Md€.
  const serieMensuelle = db
    .prepare(
      "SELECT mois, nb_marches, montant_total FROM decp_agg_mois ORDER BY mois",
    )
    .all() as MoisAgg[];

  // Tops 12 mois. Vérifiés : Réseau des acheteurs hospitaliers 12,33 Md€ ;
  // SFR 2,70 Md€ (montants répartis entre co-titulaires côté titulaires).
  const topAcheteurs = db
    .prepare(
      `SELECT rang, siret, nom, nb_marches, montant_total
       FROM decp_top_acheteurs ORDER BY rang LIMIT 10`,
    )
    .all() as TopAcheteur[];
  const topTitulaires = db
    .prepare(
      `SELECT rang, siret, nom, categorie, nb_marches, montant_total
       FROM decp_top_titulaires ORDER BY rang LIMIT 10`,
    )
    .all() as TopTitulaire[];

  // Répartition par procédure (12 mois) — valeur NULL = non renseigné.
  // Vérifié : Procédure adaptée 160 375 ; NULL 507.
  const repartitionProcedure = db
    .prepare(
      `SELECT valeur, nb_marches, montant_total FROM decp_repartition
       WHERE dimension = 'procedure' ORDER BY nb_marches DESC`,
    )
    .all() as RepartitionProcedure[];

  // Flux « derniers marchés notifiés » (J-1) — montants NON écrêtés,
  // drapeau montant_suspect à étiqueter.
  const derniersMarches = db
    .prepare(
      `SELECT rang, uid, date_notification, acheteur_nom, objet,
              titulaire_nom, nb_titulaires, montant_retenu, montant_suspect,
              techniques
       FROM decp_derniers_marches ORDER BY rang LIMIT 20`,
    )
    .all() as DernierMarche[];

  // Familles BOAMP réellement en cours (mêmes filtres que le tableau).
  // Vérifié : JOUE 5 478, FNS 2 935, MAPA 536, DSP 48, DIVERS 8.
  const familles = (
    db
      .prepare(
        `SELECT famille, famille_libelle, COUNT(*) AS nb FROM ao_en_cours
         WHERE annulee = 0 AND date_limite_reponse > datetime('now')
           AND famille IS NOT NULL
         GROUP BY famille, famille_libelle ORDER BY nb DESC`,
      )
      .all() as FamilleAO[]
  );

  // searchParam validé contre les familles réelles (sinon ignoré).
  const familleActive =
    familleDemandee !== null &&
    familles.some((f) => f.famille === familleDemandee)
      ? familleDemandee
      : null;

  // Compteur du filtre courant + part sans montant publié.
  // Vérifié : global 9 005 dont 69,8 % sans montant ; MAPA 536 dont 536.
  const compteFiltre = db
    .prepare(
      `SELECT COUNT(*) AS nb, COALESCE(SUM(montant_estime IS NULL), 0) AS sans
       FROM ao_en_cours
       WHERE annulee = 0 AND date_limite_reponse > datetime('now')
         AND (? IS NULL OR famille = ?)`,
    )
    .get(familleActive, familleActive) as { nb: number; sans: number };

  // 20 échéances les plus proches pour le filtre courant.
  const ao = db
    .prepare(
      `SELECT idweb, objet, acheteur, montant_estime, date_limite_reponse,
              url_avis
       FROM ao_en_cours
       WHERE annulee = 0 AND date_limite_reponse > datetime('now')
         AND (? IS NULL OR famille = ?)
       ORDER BY date_limite_reponse ASC LIMIT 20`,
    )
    .all(familleActive, familleActive) as AoEnCours[];

  // 31 jours d'annonces (toutes natures). Vérifié : 9 426 annonces,
  // 2026-07-20 → 2026-08-19.
  const annoncesParJour = db
    .prepare(
      `SELECT jour, nb, nb_appels_offre, nb_attributions
       FROM annonces_par_jour ORDER BY jour`,
    )
    .all() as AnnoncesJour[];

  // APProch : nom d'acheteur via entites quand le SIREN y figure
  // (sous-requête scalaire : un SIREN peut porter 2 entités — vérifié).
  // Vérifié : 606 projets sur 4 060 avec nom résolu.
  const marchesAVenir = db
    .prepare(
      `SELECT m.code, m.intitule, m.acheteur_siren,
              (SELECT e.nom FROM entites e
                WHERE e.siren = m.acheteur_siren
                ORDER BY e.nom LIMIT 1) AS acheteur_nom,
              m.categorie_achat, m.montant_estime_tranche,
              m.date_prev_publication, m.lien_consultation
       FROM marches_a_venir m
       ORDER BY m.date_prev_publication ASC, m.code LIMIT 20`,
    )
    .all() as MarcheAVenir[];

  // Alertes du domaine marchés — aucune à ce jour (vérifié : 0 ligne),
  // la page ne rend la section que si des lignes existent.
  const alertes = db
    .prepare(
      `SELECT id, type, gravite, titre, detail, regle, base_legale,
              source_url, date_calcul
       FROM alertes
       WHERE type LIKE 'marche%' OR type LIKE 'decp%'
          OR type LIKE 'boamp%' OR type LIKE 'commande%'
          OR type LIKE 'approch%'
       ORDER BY CASE gravite WHEN 'haute' THEN 0 WHEN 'moyenne' THEN 1 ELSE 2 END,
                date_calcul DESC`,
    )
    .all() as AlerteMarches[];

  return {
    meta: { s1: metaPar("S1"), s2: metaPar("S2"), s9: metaPar("S9") },
    kpis: {
      nbMarches12m: total12m.nb ?? 0,
      montant12m: total12m.montant,
      nbMarches30j: nb30j.nb,
      aoEnCours: aoEnCours.nb,
      marchesAVenir: aVenir.nb,
      nbEcretes12m: ecretes.nb ?? 0,
    },
    departements,
    serieMensuelle,
    topAcheteurs,
    topTitulaires,
    repartitionProcedure,
    derniersMarches,
    familles,
    familleActive,
    ao,
    aoTotalFiltre: compteFiltre.nb,
    aoSansMontantFiltre: compteFiltre.sans,
    annoncesParJour,
    marchesAVenir,
    alertes,
  };
}

/* ------------------------------------------------------------------ */
/* Fragment statique /data/marches/ao.json (filtre famille côté client) */
/* ------------------------------------------------------------------ */

export type VueAoFamille = {
  /** Total d'AO en cours pour ce filtre (au moment de la construction). */
  total: number;
  /** Dont montant non publié dans l'annonce. */
  sansMontant: number;
  /** Les 20 échéances les plus proches pour ce filtre. */
  lignes: AoEnCours[];
};

export type AoParFamille = {
  familles: FamilleAO[];
  /** Vues par famille — clé `""` = toutes familles confondues. */
  vues: Record<string, VueAoFamille>;
};

/**
 * Pré-calcule, pour CHAQUE famille BOAMP (et « toutes »), la vue servie par
 * le filtre client de /marches : total, part sans montant, 20 échéances les
 * plus proches. Instantané re-filtré (annulations, échéances passées) à la
 * construction du site — même SQL que `chargerDonneesMarches`.
 */
export function getAoParFamille(): AoParFamille | null {
  const db = getDb();
  if (!db) return null;
  const familles = db
    .prepare(
      `SELECT famille, famille_libelle, COUNT(*) AS nb FROM ao_en_cours
       WHERE annulee = 0 AND date_limite_reponse > datetime('now')
         AND famille IS NOT NULL
       GROUP BY famille, famille_libelle ORDER BY nb DESC`,
    )
    .all() as FamilleAO[];

  const vuePour = (famille: string | null): VueAoFamille => {
    const compte = db
      .prepare(
        `SELECT COUNT(*) AS nb, COALESCE(SUM(montant_estime IS NULL), 0) AS sans
         FROM ao_en_cours
         WHERE annulee = 0 AND date_limite_reponse > datetime('now')
           AND (? IS NULL OR famille = ?)`,
      )
      .get(famille, famille) as { nb: number; sans: number };
    const lignes = db
      .prepare(
        `SELECT idweb, objet, acheteur, montant_estime, date_limite_reponse,
                url_avis
         FROM ao_en_cours
         WHERE annulee = 0 AND date_limite_reponse > datetime('now')
           AND (? IS NULL OR famille = ?)
         ORDER BY date_limite_reponse ASC LIMIT 20`,
      )
      .all(famille, famille) as AoEnCours[];
    return { total: compte.nb, sansMontant: compte.sans, lignes };
  };

  const vues: Record<string, VueAoFamille> = { "": vuePour(null) };
  for (const f of familles) vues[f.famille] = vuePour(f.famille);
  return { familles, vues };
}

/* ------------------------------------------------------------------ */
/* Fond de carte                                                       */
/* ------------------------------------------------------------------ */

export type GeoDepartements = FeatureCollection<
  Geometry,
  { code?: string; nom?: string } & Record<string, unknown>
>;

/** Chemin du GeoJSON départements : ../data/geo relatif à app/ (cwd de next). */
const GEOJSON_PATH = path.resolve(
  process.cwd(),
  "..",
  "data",
  "geo",
  "departements.geojson",
);

/**
 * Fond de carte des départements (101 features, properties.code / .nom).
 * `null` si le fichier n'existe pas encore — la page affiche alors le
 * tableau seul, sans carte, avec un message honnête.
 */
export function chargerGeoDepartements(): GeoDepartements | null {
  if (!fs.existsSync(GEOJSON_PATH)) return null;
  try {
    return JSON.parse(fs.readFileSync(GEOJSON_PATH, "utf-8")) as GeoDepartements;
  } catch {
    return null;
  }
}
