/**
 * Requêtes du bloc « Registre de transparence de l'Union européenne »
 * (source S40), servi en bas de la page /lobbying. Lecture seule sur
 * data/france.db, tables `ue_registre_*` écrites par le pipeline P16.
 *
 * ────────────────────────────────────────────────────────────────────────
 * CLOISONNEMENT — la règle qui gouverne tout ce fichier
 * ────────────────────────────────────────────────────────────────────────
 * Le registre de l'Union et le répertoire français des représentants
 * d'intérêts (S4, HATVP) sont deux registres distincts, adossés à deux
 * cadres juridiques distincts : accord interinstitutionnel du 20/05/2021
 * pour l'un, loi « Sapin II » du 09/12/2016 pour l'autre. Périmètres
 * d'inscription, obligations déclaratives et unités de coût diffèrent.
 * Conséquences tenues ici :
 *   - aucune requête ne joint `ue_registre_*` à `lobby_*` — et aucune ne le
 *     pourrait : l'export UE ne publie AUCUN identifiant national
 *     d'entreprise, d'aucun pays (ni SIREN, ni TVA, ni registre du
 *     commerce), son seul identifiant est le code du registre lui-même ;
 *   - aucun montant des deux registres n'est additionné ni rapporté à
 *     l'autre ;
 *   - `getCompteursSepares()` est le SEUL endroit où une valeur venue
 *     du répertoire HATVP est lue pour ce bloc, et elle sert à afficher
 *     DEUX COMPTEURS CÔTE À CÔTE — jamais un ratio de l'un sur l'autre, qui
 *     laisserait croire à deux mesures du même objet.
 *
 * Convention « base absente » : les fonctions renvoient `null` tant que la
 * source n'est pas ingérée — le bloc disparaît alors, au lieu d'afficher
 * des compteurs vides.
 */
import { getDb, type MetaSource } from "@/lib/db";

/**
 * Organisation inscrite au registre de l'Union (personne morale).
 *
 * Ce type est la PROJECTION PUBLIÉE : il part tel quel dans le fragment
 * statique /data/registre-ue/organisations.json, que n'importe qui peut
 * télécharger. Il ne doit donc porter que les champs réellement affichés —
 * les colonnes du tableau, plus `id` qui sert de clé de ligne et de lien
 * vers la fiche du registre.
 *
 * `siege_ville` et `exercice_fin` en ont été retirés : la base les porte,
 * mais aucune colonne ne les montrait et aucun chunk JS ne les lisait. Ils
 * voyageaient donc chez chaque visiteur sans rien lui apprendre. Le registre
 * de l'Union exclut les personnes physiques déclarées comme telles, mais son
 * filtre laisse passer des consultants en nom propre classés « cabinets de
 * conseil » — pour eux, la ville du siège est une adresse personnelle. Une
 * donnée qu'on n'affiche pas n'a aucune raison d'être publiée.
 *
 * Si une colonne devait un jour les afficher, les remettre ici est trivial ;
 * l'inverse ne l'est pas, une fois le fragment aspiré.
 */
export type OrganisationUe = {
  id: string;
  nom: string;
  acronyme: string | null;
  categorie: string | null;
  /** Fourchette de coûts annuels telle que publiée (`null` si non déclarée). */
  cout_libelle: string | null;
};

/** Catégorie d'inscription × effectifs (total registre / siège en France). */
export type CategorieUe = {
  categorie: string;
  nb_organisations: number;
  nb_france: number;
};

/** Fourchette de coûts annuels × effectifs. */
export type CoutUe = {
  fourchette: string;
  borne_min: number | null;
  borne_max: number | null;
  nb_organisations: number;
  nb_france: number;
};

/** Domaine d'intérêt déclaré × effectifs. */
export type DomaineUe = {
  domaine: string;
  nb_organisations: number;
  nb_france: number;
};

/** Les deux compteurs affichés côte à côte, chacun avec son périmètre. */
export type CompteursSepares = {
  /** Registre de l'Union : organisations à siège en France. */
  ueSiegeFrance: number;
  /** Registre de l'Union : total des inscrits, tous pays. */
  ueTotal: number;
  /** Répertoire HATVP : entités déclarant un niveau d'action « Européen ». */
  hatvpNiveauEuropeen: number;
  /** Répertoire HATVP : total des entités inscrites. */
  hatvpTotal: number;
};

export type DonneesRegistreUe = {
  /** Fraîcheur S40 — `date_donnees` vient de la balise `<exportDate>`. */
  meta: MetaSource;
  /** Inscrits au registre, toutes catégories et tous pays. */
  totalInscrits: number;
  /** Inscrits à siège en France, dont personnes physiques non nommées. */
  france: {
    total: number;
    personnesPhysiques: number;
    /** Organisations réellement listables (total − personnes physiques). */
    nominatives: number;
    /** Nombre de fourchettes de coûts déclarées par des inscrits français. */
    avecCout: number;
  };
  compteurs: CompteursSepares;
  paysTete: { pays: string; nb_organisations: number }[];
  categoriesFrance: CategorieUe[];
  coutsFrance: CoutUe[];
  domainesFrance: DomaineUe[];
  /** Premières organisations françaises (tri alphabétique) rendues en HTML. */
  organisationsFrance: OrganisationUe[];
};

/**
 * Nombre d'organisations françaises embarquées dans le HTML statique ; le
 * reste vit dans le fragment /data/registre-ue/organisations.json, chargé au
 * clic. /lobbying est la page la plus lourde du site : y rendre la liste
 * entière côté serveur coûterait plusieurs centaines de kilo-octets.
 */
export const APERCU_ORGANISATIONS = 6;

// L'URL de fiche publique du registre est dérivée de l'identifiant par
// `urlFicheRegistreUe()`, définie dans le composant client
// `@/components/client/OrganisationsRegistreUe` — ce module-ci importe
// `better-sqlite3` et ne peut donc pas être chargé côté navigateur.

/** Vrai si les tables du registre de l'Union existent en base. */
function tablesPresentes(): boolean {
  const db = getDb();
  if (!db) return false;
  const ligne = db
    .prepare(
      "SELECT count(*) AS n FROM sqlite_master WHERE type = 'table' AND name = 'ue_registre_organisations'",
    )
    .get() as { n: number };
  return ligne.n > 0;
}

/**
 * Liste COMPLÈTE des organisations à siège en France inscrites au registre
 * de l'Union, tri alphabétique — consommée par le fragment statique
 * /data/registre-ue/organisations.json, que la page charge à la demande.
 *
 * Les travailleurs indépendants (« Self-employed individuals ») ne sont pas
 * dans cette table : ce sont des personnes physiques, le pipeline les compte
 * sans les nommer. L'écart est affiché sur la page, pas dissimulé.
 */
export function getOrganisationsFrance(): OrganisationUe[] | null {
  const db = getDb();
  if (!db || !tablesPresentes()) return null;
  return db
    .prepare(
      `SELECT id, nom, acronyme, categorie, cout_libelle
       FROM ue_registre_organisations
       WHERE siege_pays = 'FRANCE'
       ORDER BY nom`,
    )
    .all() as OrganisationUe[];
}

/**
 * Les deux compteurs, mesurés séparément dans leur registre respectif.
 *
 * Ils ne mesurent PAS la même chose et ne doivent jamais être divisés l'un
 * par l'autre : « déclarer un niveau d'action européen à la HATVP » est une
 * case cochée dans une déclaration française ; « être inscrit au registre de
 * l'Union » est une inscription à Bruxelles, ouverte à des organisations qui
 * n'ont aucune activité de représentation d'intérêts en France et ne
 * figurent donc pas au répertoire HATVP. Une entité peut relever des deux,
 * d'un seul, ou d'aucun.
 */
function getCompteursSepares(ueSiegeFrance: number, ueTotal: number): CompteursSepares {
  const db = getDb();
  const vide = {
    ueSiegeFrance,
    ueTotal,
    hatvpNiveauEuropeen: 0,
    hatvpTotal: 0,
  };
  if (!db) return vide;
  const ligne = db
    .prepare(
      `SELECT COUNT(*) AS total,
              SUM(CASE WHEN niveaux_intervention LIKE '%Européen%' THEN 1 ELSE 0 END) AS europeen
       FROM lobby_entites`,
    )
    .get() as { total: number; europeen: number | null } | undefined;
  if (!ligne) return vide;
  return {
    ueSiegeFrance,
    ueTotal,
    hatvpNiveauEuropeen: ligne.europeen ?? 0,
    hatvpTotal: ligne.total,
  };
}

/**
 * Charge le bloc « registre de l'Union » en une passe.
 * `null` si la base n'existe pas ou si la source S40 n'est pas ingérée.
 */
export function getDonneesRegistreUe(): DonneesRegistreUe | null {
  const db = getDb();
  if (!db || !tablesPresentes()) return null;

  const meta = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S40'")
    .get() as MetaSource | undefined;
  if (!meta) return null;

  // Le TOTAL vient des agrégats, pas de la table nominative : celle-ci
  // exclut les personnes physiques, et un total qui les oublierait
  // contredirait le compte publié par le registre lui-même.
  const totaux = db
    .prepare(
      `SELECT SUM(nb_organisations) AS total,
              SUM(nb_personnes_physiques) AS physiques
       FROM ue_registre_agg_pays`,
    )
    .get() as { total: number; physiques: number };

  const france = db
    .prepare(
      `SELECT nb_organisations, nb_personnes_physiques
       FROM ue_registre_agg_pays WHERE pays = 'FRANCE'`,
    )
    .get() as
    | { nb_organisations: number; nb_personnes_physiques: number }
    | undefined;
  const franceTotal = france?.nb_organisations ?? 0;
  const francePhysiques = france?.nb_personnes_physiques ?? 0;

  const paysTete = db
    .prepare(
      `SELECT pays, nb_organisations
       FROM ue_registre_agg_pays
       ORDER BY nb_organisations DESC, pays
       LIMIT 5`,
    )
    .all() as { pays: string; nb_organisations: number }[];

  const categoriesFrance = db
    .prepare(
      `SELECT categorie, nb_organisations, nb_france
       FROM ue_registre_agg_categories
       WHERE nb_france > 0
       ORDER BY nb_france DESC, categorie`,
    )
    .all() as CategorieUe[];

  const coutsFrance = db
    .prepare(
      `SELECT fourchette, borne_min, borne_max, nb_organisations, nb_france
       FROM ue_registre_agg_couts
       WHERE nb_france > 0
       ORDER BY (borne_min IS NOT NULL), borne_min`,
    )
    .all() as CoutUe[];

  const domainesFrance = db
    .prepare(
      `SELECT domaine, nb_organisations, nb_france
       FROM ue_registre_agg_interets
       WHERE nb_france > 0
       ORDER BY nb_france DESC, domaine
       LIMIT 5`,
    )
    .all() as DomaineUe[];

  const organisationsFrance = db
    .prepare(
      `SELECT id, nom, acronyme, categorie, cout_libelle
       FROM ue_registre_organisations
       WHERE siege_pays = 'FRANCE'
       ORDER BY nom
       LIMIT ?`,
    )
    .all(APERCU_ORGANISATIONS) as OrganisationUe[];

  return {
    meta,
    totalInscrits: totaux.total,
    france: {
      total: franceTotal,
      personnesPhysiques: francePhysiques,
      nominatives: franceTotal - francePhysiques,
      avecCout: coutsFrance.reduce((somme, c) => somme + c.nb_france, 0),
    },
    compteurs: getCompteursSepares(franceTotal, totaux.total),
    paysTete,
    categoriesFrance,
    coutsFrance,
    domainesFrance,
    organisationsFrance,
  };
}
