/**
 * Requêtes du module Lobbying (source S4 — répertoire HATVP des
 * représentants d'intérêts, vues AGORA). Lecture seule sur data/france.db.
 *
 * Chaque requête a été rejouée telle quelle via
 * `sqlite3 "file:data/france.db?mode=ro"` le 19/08/2026 (valeurs de
 * contrôle : 4 067 entités / 3 692 actives, 112 450 activités historiques,
 * 41 601 activités sur 24 mois, 316 entités en défaut de déclaration).
 *
 * Convention « base absente » : `getDonneesLobbying()` renvoie `null` tant
 * que `make ingest` n'a pas produit la base — la page affiche alors un
 * message honnête au lieu de planter.
 */
import { getDb, type MetaSource } from "@/lib/db";

/** KPI du bandeau (tous depuis lobby_entites + lobby_activites). */
export type LobbyKpi = {
  entites: number;
  actives: number;
  activitesTotal: number;
  /** Détail 24 mois réellement présent dans lobby_activites. */
  activites24m: number;
};

/** Activités par groupe d'institutions visées (lobby_agg_institutions). */
export type InstitutionGroupe = {
  groupe: string;
  nb_activites_total: number;
  nb_activites_12m: number;
};

/** Ligne brute de lobby_agg_institutions (vue tableau jumelle). */
export type InstitutionDetail = {
  institution: string;
  groupe: string;
  nb_activites_total: number;
  nb_activites_12m: number;
  nb_entites: number;
};

/** Top entités par activités publiées sur 12 mois (+ lien fiche HATVP). */
export type TopEntite = {
  rang: number;
  denomination: string;
  categorie: string | null;
  nb_activites_12m: number;
  url_fiche: string | null;
};

/** Fourchette de budget native HATVP (`borne_max` NULL = non bornée). */
export type FourchetteBudget = {
  fourchette: string;
  borne_min: number | null;
  borne_max: number | null;
  nb_entites: number;
};

/** Activités et entités par trimestre de publication. */
export type TrimestreActivites = {
  trimestre: string;
  nb_activites: number;
  nb_entites: number;
};

/** Ministère/institution visé (libellé tel que déclaré). */
export type MinistereVise = {
  ministere: string;
  nb_activites_total: number;
  nb_activites_12m: number;
  nb_entites: number;
};

/** Alerte telle qu'en base (table partagée `alertes`). */
export type AlerteLigne = {
  id: string;
  type: string;
  gravite: string;
  titre: string;
  detail: string | null;
  regle: string | null;
  base_legale: string | null;
  source_url: string | null;
  date_calcul: string;
};

/** Entité flaggée « défaut de déclaration » (flag public officiel HATVP). */
export type EntiteEnDefaut = {
  id: string;
  denomination: string;
  categorie: string | null;
  ville: string | null;
  url_fiche: string | null;
};

export type DonneesLobbying = {
  /** Fraîcheur S4 (HATVP AGORA). */
  meta: MetaSource;
  kpi: LobbyKpi;
  /** Groupes d'institutions, activités décroissantes (7 groupes). */
  institutions: InstitutionGroupe[];
  /** Les 9 lignes natives (vue tableau jumelle du BarList). */
  institutionsDetail: InstitutionDetail[];
  topEntites: TopEntite[];
  budgets: FourchetteBudget[];
  /** Nb d'entités couvertes par une fourchette (somme des nb_entites). */
  budgetsCouverture: { dansFourchettes: number; total: number };
  trimestres: TrimestreActivites[];
  ministeres: MinistereVise[];
  /** Alerte agrégée native du pipeline (type lobbying_declaration_incomplete). */
  alerteDefauts: AlerteLigne | null;
  /** Nb d'alertes individuelles `lobbying_defaut_declaration` (= 316). */
  nbAlertesDefaut: number;
  entitesEnDefaut: EntiteEnDefaut[];
};

/**
 * Liste COMPLÈTE des entités en défaut de déclaration (316 au 19/08/2026),
 * tri alphabétique — consommée par le fragment statique
 * /data/lobbying/defauts.json (la page n'embarque que les 50 premières).
 * `null` si la base n'existe pas encore.
 */
export function getEntitesEnDefaut(): EntiteEnDefaut[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT id, denomination, categorie, ville, url_fiche
       FROM lobby_entites
       WHERE defaut_declaration = 1
       ORDER BY denomination`,
    )
    .all() as EntiteEnDefaut[];
}

/**
 * Charge toutes les données de la page Lobbying en une passe.
 * `null` si la base n'existe pas encore (ou si la source S4 n'est pas
 * ingérée) — état « données en cours d'ingestion ».
 */
export function getDonneesLobbying(): DonneesLobbying | null {
  const db = getDb();
  if (!db) return null;

  const meta = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S4'")
    .get() as MetaSource | undefined;
  if (!meta) return null;

  const kpiEntites = db
    .prepare(
      `SELECT COUNT(*) AS entites,
              SUM(active) AS actives,
              SUM(nb_activites_total) AS activites_total
       FROM lobby_entites`,
    )
    .get() as { entites: number; actives: number; activites_total: number };

  const kpiActivites = db
    .prepare("SELECT COUNT(*) AS activites_24m FROM lobby_activites")
    .get() as { activites_24m: number };

  const institutions = db
    .prepare(
      `SELECT groupe,
              SUM(nb_activites_total) AS nb_activites_total,
              SUM(nb_activites_12m)  AS nb_activites_12m
       FROM lobby_agg_institutions
       GROUP BY groupe
       ORDER BY nb_activites_total DESC`,
    )
    .all() as InstitutionGroupe[];

  const institutionsDetail = db
    .prepare(
      `SELECT institution, groupe, nb_activites_total, nb_activites_12m, nb_entites
       FROM lobby_agg_institutions
       ORDER BY nb_activites_total DESC`,
    )
    .all() as InstitutionDetail[];

  const topEntites = db
    .prepare(
      `SELECT t.rang, t.denomination, t.categorie, t.nb_activites_12m, e.url_fiche
       FROM lobby_agg_top_entites t
       LEFT JOIN lobby_entites e ON e.id = t.entite_id
       WHERE t.rang <= 20
       ORDER BY t.rang`,
    )
    .all() as TopEntite[];

  const budgets = db
    .prepare(
      `SELECT fourchette, borne_min, borne_max, nb_entites
       FROM lobby_agg_budgets
       ORDER BY (borne_min IS NULL), borne_min`,
    )
    .all() as FourchetteBudget[];

  const couverture = db
    .prepare(
      `SELECT (SELECT SUM(nb_entites) FROM lobby_agg_budgets) AS dansFourchettes,
              (SELECT COUNT(*) FROM lobby_entites)            AS total`,
    )
    .get() as { dansFourchettes: number; total: number };

  const trimestres = db
    .prepare(
      `SELECT trimestre, nb_activites, nb_entites
       FROM lobby_agg_trimestres
       ORDER BY trimestre`,
    )
    .all() as TrimestreActivites[];

  const ministeres = db
    .prepare(
      `SELECT ministere, nb_activites_total, nb_activites_12m, nb_entites
       FROM lobby_agg_ministeres
       ORDER BY nb_activites_total DESC
       LIMIT 12`,
    )
    .all() as MinistereVise[];

  const alerteDefauts =
    (db
      .prepare(
        `SELECT id, type, gravite, titre, detail, regle, base_legale, source_url, date_calcul
         FROM alertes
         WHERE type = 'lobbying_declaration_incomplete'
         ORDER BY id
         LIMIT 1`,
      )
      .get() as AlerteLigne | undefined) ?? null;

  const nbAlertesDefaut = (
    db
      .prepare(
        "SELECT COUNT(*) AS nb FROM alertes WHERE type = 'lobbying_defaut_declaration'",
      )
      .get() as { nb: number }
  ).nb;

  const entitesEnDefaut = getEntitesEnDefaut() ?? [];

  return {
    meta,
    kpi: {
      entites: kpiEntites.entites,
      actives: kpiEntites.actives,
      activitesTotal: kpiEntites.activites_total,
      activites24m: kpiActivites.activites_24m,
    },
    institutions,
    institutionsDetail,
    topEntites,
    budgets,
    budgetsCouverture: couverture,
    trimestres,
    ministeres,
    alerteDefauts,
    nbAlertesDefaut,
    entitesEnDefaut,
  };
}
