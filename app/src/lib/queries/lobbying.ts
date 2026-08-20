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

/**
 * Libellés du champ « département ministériel » de la HATVP qui ne désignent
 * NI un ministère NI une institution : ce sont des TYPES D'INTERLOCUTEUR
 * (« un agent d'administration centrale », « autres »). Le formulaire AGORA
 * les propose dans la même liste que les portefeuilles ministériels, les
 * autorités indépendantes et les collectivités, et l'agrégat les mélange donc
 * à des institutions nommées.
 *
 * Les laisser dans le classement faisait dire au tableau quelque chose de
 * faux : « Agent d'administration centrale de l'État » y arrivait au 4ᵉ rang
 * d'un classement intitulé « ministères et institutions », alors que ce
 * libellé ne nomme aucun destinataire. Ils sont donc présentés à part —
 * jamais retirés : qu'une activité de représentation d'intérêts soit
 * déclarée en visant « un agent d'administration centrale » sans nommer
 * l'administration est une information sur la précision du répertoire.
 *
 * Liste FERMÉE, écrite en dur, sur le même principe que la table de
 * recomposition des portefeuilles du pipeline : aucune heuristique ne
 * saurait distinguer un type d'interlocuteur d'une institution réelle sans
 * se tromper (« Défenseur des droits » est une institution, « Agent de
 * l'État » n'en est pas une). Un libellé hors de cette liste est traité comme
 * une institution — dégradation propre, jamais une erreur.
 */
const LIBELLES_TYPES_INTERLOCUTEUR: ReadonlySet<string> = new Set([
  "Agent d'administration centrale de l'État",
  "Agent d'un service déconcentré de l'État",
  "Agent d'un établissement public administratif de l'État",
  "Autres : à préciser",
]);

/**
 * Vrai si le libellé désigne un type d'interlocuteur et non une institution.
 * Les apostrophes typographiques de la donnée réelle (U+2019) sont unifiées
 * avant comparaison, comme le fait le pipeline pour les catégories.
 */
export function estTypeInterlocuteur(libelle: string): boolean {
  return LIBELLES_TYPES_INTERLOCUTEUR.has(libelle.replace(/’/g, "'").trim());
}

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
  /** Top 12 des ministères et institutions RÉELLEMENT nommés. */
  ministeres: MinistereVise[];
  /** Types d'interlocuteur déclarés sans nommer d'institution (présentés à part). */
  typesInterlocuteur: MinistereVise[];
  /** Part des activités déclarées sur un type d'interlocuteur, en %. */
  partTypesInterlocuteur: number | null;
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

  // L'agrégat entier (quelques centaines de lignes) est lu pour être TRIÉ ici
  // en deux ensembles : les institutions nommées d'un côté, les types
  // d'interlocuteur de l'autre. Un `LIMIT 12` en SQL mêlait les deux, et la
  // part des seconds ne pouvait plus être calculée honnêtement.
  const ministeresTous = db
    .prepare(
      `SELECT ministere, nb_activites_total, nb_activites_12m, nb_entites
       FROM lobby_agg_ministeres
       ORDER BY nb_activites_total DESC`,
    )
    .all() as MinistereVise[];

  const typesInterlocuteur = ministeresTous.filter((m) =>
    estTypeInterlocuteur(m.ministere),
  );
  const ministeres = ministeresTous
    .filter((m) => !estTypeInterlocuteur(m.ministere))
    .slice(0, 12);

  const totalActivitesVisees = ministeresTous.reduce(
    (somme, m) => somme + m.nb_activites_total,
    0,
  );
  const partTypesInterlocuteur =
    totalActivitesVisees === 0
      ? null
      : (100 *
          typesInterlocuteur.reduce((somme, m) => somme + m.nb_activites_total, 0)) /
        totalActivitesVisees;

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
    typesInterlocuteur,
    partTypesInterlocuteur,
    alerteDefauts,
    nbAlertesDefaut,
    entitesEnDefaut,
  };
}
