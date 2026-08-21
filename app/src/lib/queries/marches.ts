/**
 * Requêtes de la page « Marchés publics » (/marches) — module DECP (S1),
 * BOAMP (S2) et APProch (S9). Lecture seule sur data/france.db via getDb().
 *
 * Datation d'un marché (pipelines/ingest_decp.py) : `date_notification` est
 * la date de la notification INITIALE du marché — un avenant ultérieur ne
 * le redate pas. TOUTES les fenêtres de ce fichier portent sur elle : le
 * 12 mois des agrégats, le 36 mois de la série, le « 30 derniers jours »
 * calculé ici sur decp_marches. Les ATTRIBUTS (montant, titulaires, objet,
 * procédure) sont ceux de la version courante du marché.
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
 * - decp_agg_departement.montant_total NULL = aucun montant connu (≠ 0) ;
 * - decp_qualite_montants (1 ligne) dit ce que vaut le total 12 mois : part
 *   plafonnée, part marquée suspecte, total sans écrêtage. La borne basse
 *   « hors suspects » n'est PAS « le vrai montant » (drapeau non audité
 *   ligne à ligne) ; le drapeau lui-même est décomposé ici en trois classes
 *   (corrigé à la source / signalé non corrigé / écrêté seul), sur la même
 *   fenêtre, cf. `chargerDecompositionSuspects`.
 *
 * Qualité de PUBLICATION (decp_publication_qualite / _annees / _acheteurs) :
 * délai entre la notification initiale et la PREMIÈRE publication des
 * données du marché, et respect du délai légal. Les trois tables sont
 * produites par le pipeline ; `chargerQualitePublication` renvoie `null`
 * quand elles ne sont pas en base, et la page n'affiche alors pas la
 * section. Tout taux de respect du délai qui en sort est une BORNE HAUTE :
 * un marché jamais publié n'a pas de délai mesurable, il ne pèse donc dans
 * aucun dénominateur.
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

/**
 * Qualité du montant agrégé 12 mois (table `decp_qualite_montants`, une
 * seule ligne, calculée DANS le pipeline sur la même fenêtre que
 * `decp_repartition` — la coupe des 12 mois n'est stockée nulle part en
 * base et `MAX(date_notification)` la retrouverait décalée).
 *
 * `montant_hors_suspects` est une BORNE BASSE, pas « le vrai montant » :
 * le drapeau `montant_suspect` n'a pas été audité ligne à ligne.
 */
export type QualiteMontants = {
  nb_marches: number;
  /** Total écrêté — la valeur du KPI héros. */
  montant_total: number | null;
  /** Marchés au-delà du plafond, TOUS acheteurs (≠ decp_agg_departement). */
  nb_ecretes: number;
  /** Ce que ces marchés apportent au total, au plafond (montant réel inconnu). */
  montant_ecretes: number | null;
  nb_suspects: number;
  montant_suspects: number | null;
  /** Borne basse : total hors marchés à montant marqué suspect. */
  montant_hors_suspects: number | null;
  /** Somme des montants retenus sans aucun écrêtage. */
  montant_brut: number | null;
  nb_sans_montant: number;
  plafond: number;
};

/**
 * Décomposition du drapeau `montant_suspect` sur la MÊME fenêtre 12 mois que
 * `decp_qualite_montants`. Le drapeau agrège trois situations que le
 * compteur unique confond, alors qu'elles n'ont pas la même valeur :
 *
 * - `aberrant` : la source a elle-même repéré ET corrigé la saisie
 *   (montant_rationalise) — le montant affiché est déjà le montant redressé,
 *   le drapeau ne signale plus qu'une trace d'historique ;
 * - `suspect` : la source signale l'anomalie mais ne corrige rien — le
 *   montant déclaré est conservé tel quel, c'est là que porte l'incertitude ;
 * - non classé au-delà du plafond : aucune anomalie signalée à la source,
 *   c'est NOTRE écrêtage à 100 M€ qui lève le drapeau.
 *
 * Les montants sont écrêtés comme dans les agrégats (`least`, NULL préservé),
 * donc directement comparables au total affiché.
 */
export type DecompositionSuspects = {
  /** Corrigés à la source : le montant retenu est déjà le montant redressé. */
  nbAberrants: number;
  montantAberrants: number | null;
  /** Signalés à la source mais NON corrigés : incertitude réelle. */
  nbSuspectsSource: number;
  montantSuspectsSource: number | null;
  /** Non signalés par la source, drapeau levé par l'écrêtage seul. */
  nbHorsPlafond: number;
  montantHorsPlafond: number | null;
};

/**
 * Qualité de publication, ligne de synthèse (`decp_publication_qualite`,
 * une seule ligne). Toutes les définitions sont arrêtées DANS le pipeline,
 * jamais recalculées ici :
 *
 * - notification = la plus ancienne date de notification du marché
 *   (notification INITIALE) ; publication = la plus ancienne date de
 *   publication de ses données (PREMIÈRE publication) ;
 * - un marché est RETENU quand les deux dates existent, tiennent dans des
 *   bornes plausibles, et que la publication ne précède pas la notification ;
 * - les marchés à publication ANTÉRIEURE à la notification sont écartés du
 *   calcul et comptés à part (`nb_publication_anterieure`) : un délai
 *   négatif n'est jamais ramené à 0.
 *
 * Ce que ces compteurs ne disent pas : un marché jamais publié n'a pas de
 * délai, il est absent du numérateur COMME du dénominateur. Tout taux de
 * respect du délai bâti là-dessus est une BORNE HAUTE.
 */
export type SynthesePublication = {
  /** Marchés distincts présents dans la source. */
  nb_marches_source: number;
  /** Marchés dont le délai a pu être mesuré. */
  nb_retenus: number;
  nb_sans_notification: number;
  /** Marchés sans aucune date de première publication : hors de tout taux. */
  nb_sans_publication: number;
  /** Dates sentinelles ou hors bornes plausibles. */
  nb_dates_hors_bornes: number;
  /** Publication antérieure à la notification : écartés, comptés à part. */
  nb_publication_anterieure: number;
  /** Retenus des cohortes CLOSES sans catégorie d'acheteur renseignée. */
  nb_sans_categorie: number;
  delai_q1: number | null;
  delai_median: number | null;
  delai_q3: number | null;
  /** 9e décile du délai — c'est lui qui impose d'attendre pour clore une cohorte. */
  delai_d9: number | null;
  /** Délai légal de publication, en MOIS (pas en jours). */
  delai_legal_mois: number;
  /** Première année de notification de la ventilation par acheteur. */
  cohorte_min: number;
  /** Dernière année de notification considérée comme CLOSE. */
  cohorte_max: number;
  /** Publication retenue la plus récente, ISO — `null` si aucune. */
  date_observation_max: string | null;
};

/**
 * Respect du délai légal par année de NOTIFICATION
 * (`decp_publication_annees`, ordre chronologique).
 *
 * `cohorte_close = 0` : le dénominateur de l'année est incomplet — les
 * marchés notifiés cette année-là et restés non publiés à ce jour n'y
 * figurent pas, ce qui rend le taux optimiste par construction. La page doit
 * distinguer ces années et les dire provisoires.
 */
export type PublicationAnnee = {
  annee: number;
  nb_marches: number;
  nb_dans_delai: number;
  /** Pourcentage 0-100 (pas une fraction) — `null` si l'année est vide. */
  taux_dans_delai: number | null;
  delai_median: number | null;
  /** Délai supérieur à un an. */
  nb_plus_un_an: number;
  /** 1 = cohorte close, 0 = provisoire (dénominateur incomplet). */
  cohorte_close: number;
};

/**
 * Respect du délai légal par catégorie d'acheteur
 * (`decp_publication_acheteurs`), sur les seules cohortes CLOSES
 * `cohorte_min..cohorte_max`.
 *
 * Les marchés sans catégorie renseignée ne sont PAS une catégorie : ils sont
 * absents de cette table et comptés dans `SynthesePublication.nb_sans_categorie`.
 * La ventilation ne couvre donc pas tout, et la page le dit.
 */
export type PublicationAcheteur = {
  categorie: string;
  nb_marches: number;
  nb_dans_delai: number;
  /** Pourcentage 0-100. */
  taux_dans_delai: number | null;
  delai_median: number | null;
  nb_plus_un_an: number;
  /** Pourcentage 0-100. */
  taux_plus_un_an: number | null;
};

/** Les trois tables de la qualité de publication, chargées ensemble. */
export type QualitePublication = {
  synthese: SynthesePublication;
  /** Ordre chronologique. */
  annees: PublicationAnnee[];
  /** Taux de respect du délai décroissant. */
  acheteurs: PublicationAcheteur[];
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
  };
  /** Ce que vaut le total 12 mois : parts écrêtée et suspecte. `null` si la
   *  table n'a pas encore été produite par le pipeline. */
  qualiteMontants: QualiteMontants | null;
  /** Ce que le drapeau « suspect » recouvre réellement : corrigé à la
   *  source / signalé non corrigé / écrêté seul. `null` si la fenêtre 12 mois
   *  n'a pas pu être reconstituée à l'unité près (rien n'est alors deviné). */
  decompositionSuspects: DecompositionSuspects | null;
  /** Délai entre notification et première publication, respect du délai
   *  légal par année et par catégorie d'acheteur. `null` tant que les trois
   *  tables ne sont pas en base — la section n'est alors pas rendue. */
  qualitePublication: QualitePublication | null;
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

/** Connexion better-sqlite3 ouverte (getDb() non nul). */
type Db = NonNullable<ReturnType<typeof getDb>>;

/** Décalages de jour essayés pour retrouver la fenêtre (cf. ci-dessous). */
const DECALAGES_FENETRE = ["+0 day", "-1 day", "+1 day"] as const;

/**
 * Décompose le drapeau `montant_suspect` sur la fenêtre 12 mois exacte de
 * `decp_qualite_montants`.
 *
 * POURQUOI ce détour : la coupe des 12 mois n'est stockée nulle part en base
 * (le pipeline la calcule à partir du jour d'ingestion, cf. ingest_decp.py) ;
 * `MAX(date_notification)`, antérieur de quelques jours, la retrouverait
 * décalée. On repart donc du jour d'ingestion de la source S1, à ± 1 jour
 * près (`date_ingestion` est horodaté UTC quand la fenêtre est calculée en
 * heure locale : une ingestion de nuit décale la date d'un jour).
 *
 * Le candidat n'est retenu QUE s'il reconstitue à l'unité près le nombre de
 * marchés ET le nombre de suspects déjà publiés par `decp_qualite_montants`,
 * et que les trois classes recomposent exactement ce total. Sinon la
 * fonction renvoie `null` : la page retombe alors sur le compteur unique
 * plutôt que d'afficher une décomposition portant sur une autre population.
 * On ne réconcilie que des ENTIERS — comparer des sommes de flottants
 * calculées par deux moteurs (DuckDB puis SQLite) n'aurait aucun sens.
 */
function chargerDecompositionSuspects(
  db: Db,
  qualite: QualiteMontants | null,
  s1: MetaSource | undefined,
): DecompositionSuspects | null {
  const jour = s1?.date_ingestion?.slice(0, 10);
  if (!qualite || !jour) return null;

  const requete = db.prepare(
    `SELECT COUNT(*)                                        AS nb_fenetre,
            SUM(CASE WHEN montant_suspect = 1 THEN 1 ELSE 0 END) AS nb_suspects,
            SUM(CASE WHEN montant_suspect = 1
                      AND montant_anomalie = 'aberrant' THEN 1 ELSE 0 END)
                                                            AS nb_aberrants,
            SUM(CASE WHEN montant_suspect = 1
                      AND montant_anomalie = 'aberrant'
                     THEN min(montant_retenu, :plafond) END) AS montant_aberrants,
            SUM(CASE WHEN montant_suspect = 1
                      AND montant_anomalie = 'suspect' THEN 1 ELSE 0 END)
                                                            AS nb_suspects_source,
            SUM(CASE WHEN montant_suspect = 1
                      AND montant_anomalie = 'suspect'
                     THEN min(montant_retenu, :plafond) END) AS montant_suspects_source,
            SUM(CASE WHEN montant_suspect = 1
                      AND montant_anomalie IS NULL THEN 1 ELSE 0 END)
                                                            AS nb_hors_plafond,
            SUM(CASE WHEN montant_suspect = 1
                      AND montant_anomalie IS NULL
                     THEN min(montant_retenu, :plafond) END) AS montant_hors_plafond
       FROM decp_marches
      WHERE date_notification > date(:jour, :decalage, '-12 months')`,
  );

  for (const decalage of DECALAGES_FENETRE) {
    const l = requete.get({ plafond: qualite.plafond, jour, decalage }) as {
      nb_fenetre: number;
      nb_suspects: number;
      nb_aberrants: number;
      montant_aberrants: number | null;
      nb_suspects_source: number;
      montant_suspects_source: number | null;
      nb_hors_plafond: number;
      montant_hors_plafond: number | null;
    };
    const somme = l.nb_aberrants + l.nb_suspects_source + l.nb_hors_plafond;
    if (
      l.nb_fenetre !== qualite.nb_marches ||
      l.nb_suspects !== qualite.nb_suspects ||
      somme !== qualite.nb_suspects
    ) {
      continue;
    }
    return {
      nbAberrants: l.nb_aberrants,
      montantAberrants: l.montant_aberrants,
      nbSuspectsSource: l.nb_suspects_source,
      montantSuspectsSource: l.montant_suspects_source,
      nbHorsPlafond: l.nb_hors_plafond,
      montantHorsPlafond: l.montant_hors_plafond,
    };
  }
  return null;
}

/** Les trois tables de la qualité de publication — chargées ou aucune. */
const TABLES_PUBLICATION = [
  "decp_publication_qualite",
  "decp_publication_annees",
  "decp_publication_acheteurs",
] as const;

/**
 * Charge la qualité de publication telle quelle : dénominateurs, taux et
 * médianes sont lus en base, aucun n'est recomposé ici. La page met en
 * forme, elle ne refait pas la fenêtre — une fenêtre reconstituée côté front
 * ne retombe pas sur celle du pipeline.
 *
 * `null` (et rien d'affiché) dans deux cas : les tables ne sont pas en base,
 * ou la ligne de synthèse manque. Une section muette vaut mieux qu'une
 * section dont les chiffres viendraient d'ailleurs.
 */
function chargerQualitePublication(db: Db): QualitePublication | null {
  const presentes = (
    db
      .prepare(
        `SELECT COUNT(*) AS n FROM sqlite_master
          WHERE type = 'table' AND name IN (?, ?, ?)`,
      )
      .get(...TABLES_PUBLICATION) as { n: number }
  ).n;
  if (presentes !== TABLES_PUBLICATION.length) return null;

  const synthese =
    (db
      .prepare(
        `SELECT nb_marches_source, nb_retenus, nb_sans_notification,
                nb_sans_publication, nb_dates_hors_bornes,
                nb_publication_anterieure, nb_sans_categorie,
                delai_q1, delai_median, delai_q3, delai_d9,
                delai_legal_mois, cohorte_min, cohorte_max,
                date_observation_max
         FROM decp_publication_qualite WHERE id = 1`,
      )
      .get() as SynthesePublication | undefined) ?? null;
  if (!synthese) return null;

  // Série par année de NOTIFICATION, ordre chronologique. Les années
  // provisoires (cohorte_close = 0) sont chargées comme les autres : c'est
  // la page qui les distingue, jamais une coupe silencieuse ici.
  const annees = db
    .prepare(
      `SELECT annee, nb_marches, nb_dans_delai, taux_dans_delai,
              delai_median, nb_plus_un_an, cohorte_close
       FROM decp_publication_annees ORDER BY annee`,
    )
    .all() as PublicationAnnee[];

  // Ventilation acheteurs, taux décroissant (les taux inconnus en dernier).
  const acheteurs = db
    .prepare(
      `SELECT categorie, nb_marches, nb_dans_delai, taux_dans_delai,
              delai_median, nb_plus_un_an, taux_plus_un_an
       FROM decp_publication_acheteurs
       ORDER BY taux_dans_delai IS NULL, taux_dans_delai DESC, nb_marches DESC`,
    )
    .all() as PublicationAcheteur[];

  return { synthese, annees, acheteurs };
}

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
  // pipeline sur la notification initiale, montants écrêtés) — la
  // dimension 'procedure' couvre 100 % des marchés. Nombre et montant
  // dérivent à chaque ingestion : aucune valeur de contrôle n'est figée
  // ici, celle du jour est celle qu'affiche la page.
  const total12m = db
    .prepare(
      `SELECT SUM(nb_marches) AS nb, SUM(montant_total) AS montant
       FROM decp_repartition WHERE dimension = 'procedure'`,
    )
    .get() as { nb: number | null; montant: number | null };

  // 30 jours glissants sur la date de NOTIFICATION INITIALE : un marché
  // ancien modifié hier n'y entre pas. Fenêtre récente, donc la plus
  // exposée à la latence légale de publication (≤ 2 mois) — elle est
  // structurellement incomplète, et le compte varie d'un jour à l'autre.
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

  // Qualité du total 12 mois. Le compte d'écrêtés vient d'ICI et non de
  // SUM(nb_marches_ecretes) FROM decp_agg_departement, qui n'en couvre que
  // les acheteurs à département connu, et en laisse donc échapper
  // quelques-uns à chaque ingestion.
  // Tous ces compteurs portent sur la même fenêtre 12 mois que
  // decp_repartition et dérivent à chaque ingestion : ils sont lus en
  // base, jamais recopiés ici.
  const qualiteMontants =
    (db
      .prepare(
        `SELECT nb_marches, montant_total, nb_ecretes, montant_ecretes,
                nb_suspects, montant_suspects, montant_hors_suspects,
                montant_brut, nb_sans_montant, plafond
         FROM decp_qualite_montants WHERE id = 1`,
      )
      .get() as QualiteMontants | undefined) ?? null;

  // Ce que le drapeau « suspect » recouvre : la source a-t-elle déjà corrigé
  // (classe 'aberrant'), signalé sans corriger (classe 'suspect'), ou le
  // drapeau vient-il de notre seul écrêtage ? Les trois classes doivent
  // recomposer EXACTEMENT le nb_suspects de decp_qualite_montants —
  // c'est la condition de retenue de la fenêtre (cf. la fonction), et le
  // seul contrôle qui vaille : les effectifs, eux, dérivent.
  const decompositionSuspects = chargerDecompositionSuspects(
    db,
    qualiteMontants,
    metaPar("S1"),
  );

  // Qualité de PUBLICATION : délai notification -> première publication.
  // Les trois tables arrivent ensemble ou pas du tout ; tous les taux et
  // quantiles en sortent tels quels (voir la fonction).
  const qualitePublication = chargerQualitePublication(db);

  // Carte : 107 départements, montants déjà écrêtés, NULL = aucun montant
  // connu.
  const departements = db
    .prepare(
      `SELECT departement_code, departement_nom, nb_marches, montant_total,
              nb_marches_ecretes
       FROM decp_agg_departement ORDER BY departement_code`,
    )
    .all() as DepartementAgg[];

  // Série mensuelle : 36 mois civils, chaque marché rangé au mois de sa
  // notification INITIALE (un avenant ne le déplace pas de mois). Les
  // deux derniers mois sont structurellement incomplets — latence légale
  // de publication ≤ 2 mois.
  const serieMensuelle = db
    .prepare(
      "SELECT mois, nb_marches, montant_total FROM decp_agg_mois ORDER BY mois",
    )
    .all() as MoisAgg[];

  // Tops 12 mois — côté titulaires, le montant du marché est réparti
  // entre co-titulaires (la source ne le ventile pas).
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

  // Répartition par procédure (12 mois) — valeur NULL = non renseigné,
  // catégorie à afficher telle quelle et non à masquer.
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
    },
    qualiteMontants,
    decompositionSuspects,
    qualitePublication,
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
