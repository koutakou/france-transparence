/**
 * Requêtes de la page ACCUEIL (vue d'ensemble) — fichier propre à ce module
 * (NOTES-FRONT « Design system », jamais partagé avec un autre module).
 *
 * Toutes les requêtes ont été rejouées sur data/france.db en lecture seule
 * avant d'être figées ici. Aucun montant n'est affiché sans source : la page
 * consomme aussi `meta_sources` (badges de fraîcheur).
 *
 * Rappels pièges (docs/NOTES-FRONT.md) :
 * - budget_mensuel : montants = CUMULS depuis le 1er janvier ; dernier mois
 *   réel = max(date_fin_mois) (pas de temps réel) ;
 * - budget_vert : montants PLF 2026 (≠ LFI promulguée) → l'étiquette
 *   `etiquette_2026` est remontée telle quelle ;
 * - budget_destination_2025 : CP BRUTS (non comparables aux dépenses nettes) ;
 * - decp_agg_departement : fenêtre 12 mois, montants déjà écrêtés
 *   (plafond 100 M€/marché), NULL = aucun montant connu (≠ 0) ;
 * - ao_en_cours : snapshot → re-filtrer date_limite_reponse au moment de la
 *   requête (`datetime()` pour normaliser l'ISO `+00:00`), annulee = 0 ;
 * - alertes : gravités haute/moyenne/info, règle + base légale à afficher.
 */
import fs from "node:fs";
import path from "node:path";
import type { FeatureCollection, Geometry } from "geojson";
import { getDb, type MetaSource } from "@/lib/db";

/* ------------------------------------------------------------------ */
/* GeoJSON départements (fond de carte, lu côté serveur uniquement)    */
/* ------------------------------------------------------------------ */

/** Chemin résolu comme DB_PATH dans lib/db.ts : ../data relatif à app/. */
export const GEOJSON_DEPARTEMENTS_PATH = path.resolve(
  process.cwd(),
  "..",
  "data",
  "geo",
  "departements.geojson",
);

export type GeojsonDepartements = FeatureCollection<
  Geometry,
  { code?: string; nom?: string } & Record<string, unknown>
>;

let geojsonCache: GeojsonDepartements | null = null;

/**
 * Fond de carte des départements (101 features, `properties.code`).
 * `null` si le fichier n'existe pas encore (même garde honnête que la base).
 * Fichier statique → parsé une seule fois par process.
 */
export function lireDepartementsGeojson(): GeojsonDepartements | null {
  if (geojsonCache) return geojsonCache;
  if (!fs.existsSync(GEOJSON_DEPARTEMENTS_PATH)) return null;
  try {
    geojsonCache = JSON.parse(
      fs.readFileSync(GEOJSON_DEPARTEMENTS_PATH, "utf-8"),
    ) as GeojsonDepartements;
  } catch {
    return null;
  }
  return geojsonCache;
}

/* ------------------------------------------------------------------ */
/* Types des lignes remontées                                          */
/* ------------------------------------------------------------------ */

/** Compteur « exécution » : dépenses nettes du budget général, cumul annuel. */
export type ExecutionEtat = {
  dateFinMois: string; // ISO — dernier mois publié (2026-06-30)
  cumul: number; // € — montant_cumul
  cumulN1: number | null; // € — même mois N−1
  /** Variation vs N−1 en %, null si N−1 absent (delta NEUTRE à l'affichage). */
  deltaPct: number | null;
};

export type PartTitre = { ligne: string; montant: number };

export type MissionPlf = { mission: string; cp: number };

export type DepartementCarte = {
  code: string;
  nom: string | null;
  nbMarches: number;
  /** € écrêtés — NULL = aucun montant connu (ne pas afficher 0). */
  montant: number | null;
};

export type PrefectureCarte = {
  nom: string;
  departement: string; // code zéro-paddé ('01'…'2B') — même format que la carte
  lat: number;
  lon: number;
};

export type KpisAccueil = {
  marches30j: number;
  aoEnCours: number;
  textesJo30j: number;
};

export type CompteursSuivi = {
  marchesSuivis: number;
  entitesPubliques: number;
  elusSuivis: number;
};

export type MinistereCp = {
  ministere: string;
  cp: number; // € (CP bruts PLF 2025)
  partPct: number; // part du total des CP, en %
};

export type DernierMarche = {
  rang: number;
  date: string;
  acheteur: string | null;
  objet: string | null;
  montant: number | null; // montant_rationalise — NULL = non publié
};

export type TexteJo = {
  id: string;
  date: string;
  nature: string | null;
  titre: string;
  lien: string; // lien Légifrance (sortant uniquement, jamais fetché)
};

export type AoProcheCloture = {
  id: string;
  objet: string | null;
  acheteur: string | null;
  dateLimite: string; // ISO datetime UTC
  montantEstime: number | null; // NULL = non publié (≈ 70 % des cas)
  url: string | null;
};

export type AlerteAccueil = {
  id: string;
  type: string;
  gravite: string; // 'haute' | 'moyenne' | 'info'
  titre: string;
  detail: string | null;
  regle: string | null;
  baseLegale: string | null;
  sourceUrl: string | null;
  dateCalcul: string;
};

export type DonneesAccueil = {
  execution: ExecutionEtat | null;
  partsTitres: PartTitre[];
  missionsPlf2026: MissionPlf[];
  /** Étiquette honnête portée par budget_vert (PLF ≠ LFI). */
  etiquettePlf2026: string | null;
  totalCpPlf2026: number | null;
  departementsCarte: DepartementCarte[];
  prefectures: PrefectureCarte[];
  kpis: KpisAccueil;
  suivi: CompteursSuivi;
  ministeres2025: MinistereCp[];
  totalCp2025: number | null;
  derniersMarches: DernierMarche[];
  textesJo: TexteJo[];
  aoCloture: AoProcheCloture[];
  alertes: AlerteAccueil[];
  /** Fraîcheur des sources consommées par la page, indexée par source_id. */
  sources: Record<string, MetaSource>;
};

/* ------------------------------------------------------------------ */
/* Requêtes                                                            */
/* ------------------------------------------------------------------ */

/** Sources meta_sources consommées par l'accueil (badges de fraîcheur). */
const SOURCES_ACCUEIL = [
  "S13", // situations mensuelles budgétaires (compteur, donut)
  "S20", // PLF 2026 budget vert (top missions)
  "S21", // PLF 2025 destination (tableau ministères)
  "S1", // DECP (carte, derniers marchés, KPI 30 j)
  "S2", // BOAMP (AO en cours)
  "S3", // JORF (textes au JO)
  "S17", // RNE (élus suivis)
  "S35-reforga-admin-etat", // entités publiques
] as const;

const LIGNE_DEPENSES_NETTES =
  "depenses/budget-general/total-depenses-nettes-du-budget-general";

/**
 * Toutes les données de l'accueil en un appel (une seule garde base
 * absente). `null` tant que `make ingest` n'a pas construit la base.
 */
export function getDonneesAccueil(): DonneesAccueil | null {
  const db = getDb();
  if (!db) return null;

  /* --- Compteur : dépenses nettes du budget général, dernier mois --- */
  const compteur = db
    .prepare(
      `SELECT date_fin_mois AS dateFinMois,
              montant_cumul AS cumul,
              montant_cumul_n1 AS cumulN1
         FROM budget_mensuel
        WHERE ligne_id = ?
        ORDER BY date_fin_mois DESC
        LIMIT 1`,
    )
    .get(LIGNE_DEPENSES_NETTES) as
    | { dateFinMois: string; cumul: number; cumulN1: number | null }
    | undefined;

  const execution: ExecutionEtat | null = compteur
    ? {
        ...compteur,
        deltaPct:
          compteur.cumulN1 !== null && compteur.cumulN1 !== 0
            ? ((compteur.cumul - compteur.cumulN1) / Math.abs(compteur.cumulN1)) * 100
            : null,
      }
    : null;

  /* --- Donut : décomposition par titre (niveau 2), même mois --- */
  const partsTitres = compteur
    ? (db
        .prepare(
          `SELECT ligne, montant_cumul AS montant
             FROM budget_mensuel
            WHERE date_fin_mois = ?
              AND categorie = 'Dépenses'
              AND sous_categorie = 'Budget général'
              AND niveau = 2
            ORDER BY montant_cumul DESC`,
        )
        .all(compteur.dateFinMois) as PartTitre[])
    : [];

  /* --- Top 5 missions PLF 2026 (crédits budgétaires, CP) --- */
  const missionsPlf2026 = db
    .prepare(
      `SELECT mission, SUM(plf_2026_cp) AS cp
         FROM budget_vert
        WHERE type_depense = 'Crédits budgétaires' AND plf_2026_cp IS NOT NULL
        GROUP BY mission
        ORDER BY cp DESC
        LIMIT 5`,
    )
    .all() as MissionPlf[];

  const etiquettePlf2026 =
    (
      db.prepare(`SELECT etiquette_2026 AS e FROM budget_vert LIMIT 1`).get() as
        | { e: string }
        | undefined
    )?.e ?? null;

  const totalCpPlf2026 =
    (
      db
        .prepare(
          `SELECT SUM(plf_2026_cp) AS total
             FROM budget_vert
            WHERE type_depense = 'Crédits budgétaires'`,
        )
        .get() as { total: number | null } | undefined
    )?.total ?? null;

  /* --- Carte : montants DECP 12 mois par département (écrêtés) --- */
  const departementsCarte = db
    .prepare(
      `SELECT departement_code AS code,
              departement_nom AS nom,
              nb_marches AS nbMarches,
              montant_total AS montant
         FROM decp_agg_departement`,
    )
    .all() as DepartementCarte[];

  const prefectures = db
    .prepare(
      `SELECT nom, departement, lat, lon
         FROM ref_villes
        WHERE est_prefecture = 1`,
    )
    .all() as PrefectureCarte[];

  /* --- KPI (fenêtres relatives à la requête ; page force-dynamic) --- */
  const kpis: KpisAccueil = {
    marches30j: (
      db
        .prepare(
          `SELECT COUNT(*) AS n FROM decp_marches
            WHERE date_notification >= date('now', '-30 days')`,
        )
        .get() as { n: number }
    ).n,
    // snapshot BOAMP → re-filtrage de la date limite au moment de la requête
    aoEnCours: (
      db
        .prepare(
          `SELECT COUNT(*) AS n FROM ao_en_cours
            WHERE annulee = 0 AND datetime(date_limite_reponse) > datetime('now')`,
        )
        .get() as { n: number }
    ).n,
    textesJo30j: (
      db
        .prepare(
          `SELECT COUNT(*) AS n FROM jorf_textes
            WHERE date_publi >= date('now', '-30 days')`,
        )
        .get() as { n: number }
    ).n,
  };

  /* --- Bandeau de couverture (counts réels, jamais figés) --- */
  const suivi: CompteursSuivi = {
    marchesSuivis: (
      db.prepare(`SELECT COUNT(*) AS n FROM decp_marches`).get() as { n: number }
    ).n,
    // « publiques » : ministères, institutions, collectivités, organismes —
    // les 718 partis d'`entites` n'en font pas partie
    entitesPubliques: (
      db
        .prepare(
          `SELECT COUNT(*) AS n FROM entites
            WHERE type IN ('ministere','institution','collectivite','organisme')`,
        )
        .get() as { n: number }
    ).n,
    elusSuivis: (
      db.prepare(`SELECT COUNT(*) AS n FROM elus`).get() as { n: number }
    ).n,
  };

  /* --- Tableau : CP bruts PLF 2025 par ministère (top 8) --- */
  const totalCp2025 =
    (
      db
        .prepare(
          `SELECT SUM(credit_de_paiement) AS total FROM budget_destination_2025`,
        )
        .get() as { total: number | null } | undefined
    )?.total ?? null;

  const ministeresBruts = db
    .prepare(
      `SELECT libelle_ministere AS ministere, SUM(credit_de_paiement) AS cp
         FROM budget_destination_2025
        WHERE libelle_ministere IS NOT NULL
        GROUP BY libelle_ministere
        ORDER BY cp DESC
        LIMIT 8`,
    )
    .all() as { ministere: string; cp: number }[];

  const ministeres2025: MinistereCp[] = ministeresBruts.map((m) => ({
    ...m,
    partPct: totalCp2025 ? (m.cp / totalCp2025) * 100 : 0,
  }));

  /* --- Flux : derniers marchés notifiés (agrégat J-1 du pipeline) --- */
  const derniersMarches = db
    .prepare(
      `SELECT rang,
              date_notification AS date,
              acheteur_nom AS acheteur,
              objet,
              montant_rationalise AS montant
         FROM decp_derniers_marches
        ORDER BY rang
        LIMIT 7`,
    )
    .all() as DernierMarche[];

  /* --- Flux : derniers textes au JO --- */
  const textesJo = db
    .prepare(
      `SELECT texte_id AS id,
              date_publi AS date,
              nature,
              titre,
              lien_legifrance AS lien
         FROM jorf_textes
        ORDER BY date_publi DESC, num_sequence
        LIMIT 6`,
    )
    .all() as TexteJo[];

  /* --- Flux : AO proches de la clôture (non annulés, limite future) --- */
  const aoCloture = db
    .prepare(
      `SELECT idweb AS id,
              objet,
              acheteur,
              date_limite_reponse AS dateLimite,
              montant_estime AS montantEstime,
              url_avis AS url
         FROM ao_en_cours
        WHERE annulee = 0 AND datetime(date_limite_reponse) > datetime('now')
        ORDER BY datetime(date_limite_reponse)
        LIMIT 4`,
    )
    .all() as AoProcheCloture[];

  /* --- Alertes : les 4 plus récentes EN MÉLANGEANT les gravités
         (les dernières par date seule seraient 4 alertes identiques du même
         lot de calcul : on prend la plus récente de chaque gravité + la
         2e « haute », ordonnées par gravité décroissante). --- */
  const alertes = db
    .prepare(
      `SELECT id, type, gravite, titre, detail, regle,
              base_legale AS baseLegale,
              source_url AS sourceUrl,
              date_calcul AS dateCalcul
         FROM (
           SELECT a.*, ROW_NUMBER() OVER (
                    PARTITION BY gravite
                    ORDER BY date_calcul DESC, id
                  ) AS rn
             FROM alertes a
         )
        WHERE rn = 1 OR (gravite = 'haute' AND rn = 2)
        ORDER BY CASE gravite
                   WHEN 'haute' THEN 0
                   WHEN 'moyenne' THEN 1
                   ELSE 2
                 END, rn
        LIMIT 4`,
    )
    .all() as AlerteAccueil[];

  /* --- Fraîcheur des sources de la page --- */
  const lignesSources = db
    .prepare(
      `SELECT * FROM meta_sources
        WHERE source_id IN (${SOURCES_ACCUEIL.map(() => "?").join(",")})`,
    )
    .all(...SOURCES_ACCUEIL) as MetaSource[];
  const sources = Object.fromEntries(
    lignesSources.map((s) => [s.source_id, s]),
  ) as Record<string, MetaSource>;

  return {
    execution,
    partsTitres,
    missionsPlf2026,
    etiquettePlf2026,
    totalCpPlf2026,
    departementsCarte,
    prefectures,
    kpis,
    suivi,
    ministeres2025,
    totalCp2025,
    derniersMarches,
    textesJo,
    aoCloture,
    alertes,
    sources,
  };
}
