/**
 * Croisement LOBBYING × MARCHÉS PUBLICS — répertoire HATVP des
 * représentants d'intérêts (source S4) × DECP consolidées (source S1).
 *
 * Pourquoi un fichier à part et pas `lobbying.ts` : ce module lit DEUX
 * sources et porte la sémantique des montants DECP (écrêtage, accords-
 * cadres, drapeau « suspect ») que `lobbying.ts` n'a aucune raison de
 * connaître. Il est décrit en entier dans docs/CROISEMENT-LOBBYING-MARCHES.md.
 *
 * ── La clé de jointure ────────────────────────────────────────────────
 * `lobby_entites.identifiant_national` porte un SIREN quand
 * `type_identifiant = 'SIREN'` (3 747 entités sur 4 068 au 18/08/2026 ;
 * les 321 autres sont identifiées par un numéro RNA d'association ou un
 * identifiant interne HATVP, non raccordable aux DECP). Les 9 premiers
 * caractères d'un SIRET de titulaire sont son SIREN : la jointure est
 * EXACTE, sans rapprochement de noms donc sans homonymie.
 *
 * ── Tous les titulaires, pas seulement le premier ─────────────────────
 * `decp_marches.titulaire_siret` ne contient PAS « le » titulaire mais le
 * plus petit SIRET du marché (`min(titulaire_id)` dans
 * pipelines/ingest_decp.py) : s'y limiter perdrait tout co-titulaire dont
 * le SIRET n'est pas le plus petit — ~1 100 marchés. On déplie donc
 * `titulaires_json` (la liste complète, [{siret, nom}, …]) avec json_each.
 *
 * ── Sémantique des montants (identique au module /marches) ────────────
 * - montant = `montant_retenu` ÉCRÊTÉ à 100 M€/marché (plafond du pipeline,
 *   anti-saisie aberrante), puis DIVISÉ par le nombre de co-titulaires —
 *   la convention déjà appliquée par `decp_top_titulaires` : le montant
 *   DECP est celui du marché entier, la source ne le ventile pas ;
 * - les ACCORDS-CADRES sont sortis du périmètre de référence : leur montant
 *   notifié est un MAXIMUM contractuel, pas une dépense. Ils sont comptés à
 *   part, jamais additionnés au reste sans le dire ;
 * - le drapeau `montant_suspect` (anomalie signalée à la source, ou montant
 *   au-delà du plafond) donne une BORNE BASSE, pas « le vrai montant » : il
 *   n'a pas été audité marché par marché, il écarte donc aussi des montants
 *   exacts ;
 * - un marché sans montant renseigné est compté dans le nombre de marchés
 *   et exclu de toutes les sommes — aucune valeur n'est inventée.
 *
 * ── Ce que le croisement N'EST PAS ────────────────────────────────────
 * Être inscrit au répertoire des représentants d'intérêts ET titulaire d'un
 * marché public n'est ni interdit ni anormal : les deux obligations sont
 * distinctes et se cumulent légalement. Le module ne produit AUCUNE alerte
 * et ne qualifie personne. Le seul constat d'irrégularité qu'il relaie est
 * le flag natif `defaut_declaration` de la HATVP, déjà exploité tel quel
 * par le module Lobbying.
 *
 * ── Performance ───────────────────────────────────────────────────────
 * Le build pré-rend 1 000+ pages : ces requêtes sont jouées UNE fois, pour
 * /lobbying et pour /api/lobbying-marches.json. Mesuré sur la base réelle
 * (469 Mo, 585 503 marchés, 662 340 lignes titulaires) : ~2,4 s au total.
 * Deux pièges de plan de requête, tous deux vérifiés en EXPLAIN QUERY PLAN :
 * 1. la liste des SIREN du répertoire doit être une SOUS-REQUÊTE et non la
 *    table `lobby_entites` (qui n'a pas d'index sur `identifiant_national`) :
 *    SQLite ne matérialise et n'auto-indexe que la sous-requête — sans elle,
 *    la même requête passe de 1 s à ~5 min ;
 * 2. l'ordre des boucles doit être forcé par CROSS JOIN (decp_marches en
 *    tête) : laissé libre, SQLite met la liste des SIREN en boucle externe
 *    et rejoue json_each 3 746 fois.
 *
 * Requêtes rejouées telles quelles via `sqlite3 mode=ro` le 20/08/2026
 * (valeurs de contrôle : 3 746 SIREN distincts au répertoire, 435 d'entre
 * eux titulaires de 11 174 marchés hors accords-cadres pour 18,32 Md€,
 * borne basse hors montants suspects 12,04 Md€, 27 en défaut de déclaration).
 */
import { getDb, type MetaSource } from "@/lib/db";

/** Plafond d'écrêtage par marché — même valeur que le pipeline DECP. */
export const PLAFOND_ECRETAGE = 100_000_000;

/** Couverture de la clé de jointure dans le répertoire HATVP. */
export type CouvertureSiren = {
  /** Toutes les entités inscrites au répertoire. */
  entites: number;
  /** Entités dont l'identifiant national est un SIREN. */
  entitesSiren: number;
  /** SIREN DISTINCTS (une entité peut être inscrite deux fois). */
  sirensDistincts: number;
  /** Entités identifiées par un numéro RNA d'association. */
  entitesRna: number;
  /** Entités portant un identifiant interne HATVP (non raccordable). */
  entitesHatvp: number;
};

/**
 * Agrégats du croisement. Trois périmètres cohabitent et ne se
 * confondent jamais dans l'affichage :
 * - `*Tous` : tous les marchés, accords-cadres compris (montants notionnels) ;
 * - `*HorsAc` : PÉRIMÈTRE DE RÉFÉRENCE — accords-cadres exclus ;
 * - `*HorsAcHorsSuspects` : borne basse, marchés à montant suspect exclus.
 */
export type AgregatsCroisement = {
  marchesTous: number;
  sirensTous: number;
  montantTous: number | null;
  /** Accords-cadres écartés du périmètre de référence (montant = maximum). */
  marchesAccordsCadres: number;
  montantAccordsCadres: number | null;
  marchesHorsAc: number;
  sirensHorsAc: number;
  montantHorsAc: number | null;
  /** Somme sans aucun écrêtage — ce que le plafond sert à ne pas afficher. */
  montantHorsAcBrut: number | null;
  /** Marchés au-delà du plafond, comptés au plafond (montant réel inconnu). */
  ecretesHorsAc: number;
  /** Ce que ces marchés écrêtés apportent au total, au plafond. */
  montantEcretesHorsAc: number | null;
  suspectsHorsAc: number;
  montantSuspectsHorsAc: number | null;
  marchesHorsAcHorsSuspects: number;
  sirensHorsAcHorsSuspects: number;
  montantHorsAcHorsSuspects: number | null;
  /** Notifiés sans montant : comptés en marchés, exclus des sommes. */
  sansMontantHorsAc: number;
  /** Sous-ensemble « en défaut de déclaration » (flag officiel HATVP). */
  defautSirensTous: number;
  defautMarchesTous: number;
  defautMontantTous: number | null;
  defautMarchesTousHorsSuspects: number;
  defautMontantTousHorsSuspects: number | null;
  defautSirensHorsAc: number;
  defautMarchesHorsAc: number;
  defautMontantHorsAc: number | null;
};

/** Dénominateurs DECP, pour situer le croisement dans l'ensemble. */
export type EnsembleDecp = {
  /** Marchés hors accords-cadres ayant au moins un titulaire identifié. */
  marchesHorsAc: number;
  /** Montant écrêté correspondant (même convention de ventilation). */
  montantHorsAc: number | null;
  /** SIREN distincts titulaires d'au moins un marché, toutes techniques. */
  sirensTitulaires: number;
};

/** Un représentant d'intérêts titulaire, avec ses deux facettes. */
export type TitulaireLobbyiste = {
  siren: string;
  denomination: string;
  categorie: string | null;
  url_fiche: string | null;
  /** Flag natif HATVP repris tel quel (0/1) — constat officiel, pas un calcul. */
  defaut_declaration: number;
  /** Activités de représentation d'intérêts publiées sur 12 mois. */
  activites_12m: number;
  nb_marches_hors_ac: number;
  montant_hors_ac: number | null;
  nb_suspects_hors_ac: number;
  nb_marches_tous: number;
  montant_tous: number | null;
};

export type CroisementLobbyingMarches = {
  /** Fraîcheur des DEUX sources — le module date ses données. */
  metaS1: MetaSource;
  metaS4: MetaSource;
  couverture: CouvertureSiren;
  agregats: AgregatsCroisement;
  ensemble: EnsembleDecp;
  /** Les 566 titulaires, montant hors accords-cadres décroissant. */
  titulaires: TitulaireLobbyiste[];
};

/* ------------------------------------------------------------------ */
/* SQL                                                                 */
/* ------------------------------------------------------------------ */

/**
 * Liste des SIREN du répertoire, dédoublonnée. GROUP BY et non DISTINCT :
 * une entité peut être inscrite DEUX FOIS au répertoire sous le même SIREN
 * (cas réel au 18/08/2026 : « MOUVEMENT DES ENTREPRISES DE FRANCE BFC »,
 * 3 747 inscriptions pour 3 746 SIREN) — sans dédoublonnage, ses marchés
 * seraient comptés deux fois.
 */
const SQL_SIRENS_LOBBY = `SELECT identifiant_national AS siren,
                                 MAX(defaut_declaration) AS defaut
                          FROM lobby_entites
                          WHERE type_identifiant = 'SIREN'
                          GROUP BY identifiant_national`;

/**
 * Une ligne par (marché, titulaire) : `titulaires_json` déplié.
 * `ac` = accord-cadre (le libellé natif peut cumuler plusieurs techniques,
 * « Accord-cadre, Système d'acquisition dynamique » — d'où le LIKE) ;
 * l'apostrophe typographique du libellé source impose de tester
 * « ccord-cadre » plutôt que le mot entier avec sa majuscule.
 */
const SQL_LIGNES_TITULAIRES = `SELECT m.uid                                          AS uid,
                                      m.montant_retenu                               AS montant_retenu,
                                      m.montant_suspect                              AS montant_suspect,
                                      (COALESCE(m.techniques,'') LIKE '%ccord-cadre%') AS ac,
                                      min(m.montant_retenu, ${PLAFOND_ECRETAGE}.0) / m.nb_titulaires AS part,
                                      m.montant_retenu / m.nb_titulaires              AS part_brute,
                                      substr(json_extract(v.value,'$.siret'), 1, 9)   AS siren9
                               FROM decp_marches m
                               CROSS JOIN json_each(m.titulaires_json) v`;

/* ------------------------------------------------------------------ */
/* Chargement                                                          */
/* ------------------------------------------------------------------ */

/**
 * Mémo de build. Deux consommateurs demandent EXACTEMENT le même croisement
 * — la page /lobbying et l'export /api/lobbying-marches.json — et la base
 * est immuable pendant un build (connexion `query_only`, fichier produit par
 * l'ingestion). Sans ce mémo, les 3,1 s de requêtes sont payées deux fois.
 * `undefined` = pas encore calculé ; `null` = calculé et sans données.
 */
let memo: CroisementLobbyingMarches | null | undefined;

/**
 * Charge le croisement complet en quatre passes (~3,1 s, mémoïsées).
 * `null` si la base n'existe pas encore, ou si l'une des deux sources n'est
 * pas ingérée : un croisement à une seule source n'a aucun sens, la page
 * affiche alors son état « données en cours d'ingestion ».
 */
export function getCroisementLobbyingMarches(): CroisementLobbyingMarches | null {
  if (memo !== undefined) return memo;
  const db = getDb();
  // Base absente : on ne mémoïse PAS ce `null` — dès que l'ingestion crée le
  // fichier, l'appel suivant doit pouvoir aboutir (même règle que getDb()).
  if (!db) return null;

  const metaS1 = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S1'")
    .get() as MetaSource | undefined;
  const metaS4 = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S4'")
    .get() as MetaSource | undefined;
  if (!metaS1 || !metaS4) {
    memo = null;
    return memo;
  }

  // 1. Couverture de la clé — lecture de lobby_entites seule (instantané).
  const couverture = db
    .prepare(
      `SELECT COUNT(*)                                                        AS entites,
              SUM(type_identifiant = 'SIREN')                                 AS entitesSiren,
              COUNT(DISTINCT CASE WHEN type_identifiant = 'SIREN'
                                  THEN identifiant_national END)              AS sirensDistincts,
              SUM(type_identifiant = 'RNA')                                   AS entitesRna,
              SUM(type_identifiant = 'HATVP')                                 AS entitesHatvp
       FROM lobby_entites`,
    )
    .get() as CouvertureSiren;

  // 2. Dénominateurs DECP. Le nombre de marchés et leur montant se lisent
  //    SANS déplier les titulaires (uid est clé primaire, et sommer la part
  //    de chaque co-titulaire revient à sommer le montant du marché) : c'est
  //    30x moins cher. Seul le nombre de SIREN titulaires impose le dépliage.
  const ensembleMarches = db
    .prepare(
      `SELECT COUNT(*)                                     AS marchesHorsAc,
              SUM(min(montant_retenu, ${PLAFOND_ECRETAGE}.0)) AS montantHorsAc
       FROM decp_marches
       WHERE titulaires_json IS NOT NULL
         AND COALESCE(techniques,'') NOT LIKE '%ccord-cadre%'`,
    )
    .get() as { marchesHorsAc: number; montantHorsAc: number | null };

  const ensembleSirens = db
    .prepare(
      `SELECT COUNT(DISTINCT substr(json_extract(v.value,'$.siret'), 1, 9)) AS sirensTitulaires
       FROM decp_marches m
       CROSS JOIN json_each(m.titulaires_json) v`,
    )
    .get() as { sirensTitulaires: number };

  // 3. Agrégats du croisement, une seule passe. COUNT(DISTINCT uid) et non
  //    COUNT(*) : un marché dont DEUX co-titulaires sont au répertoire
  //    produit deux lignes et ne doit compter que pour un marché.
  const agregats = db
    .prepare(
      `SELECT
         COUNT(DISTINCT uid)                                                        AS marchesTous,
         COUNT(DISTINCT siren)                                                      AS sirensTous,
         SUM(part)                                                                  AS montantTous,
         COUNT(DISTINCT CASE WHEN ac = 1 THEN uid END)                              AS marchesAccordsCadres,
         SUM(CASE WHEN ac = 1 THEN part END)                                        AS montantAccordsCadres,
         COUNT(DISTINCT CASE WHEN ac = 0 THEN uid END)                              AS marchesHorsAc,
         COUNT(DISTINCT CASE WHEN ac = 0 THEN siren END)                            AS sirensHorsAc,
         SUM(CASE WHEN ac = 0 THEN part END)                                        AS montantHorsAc,
         SUM(CASE WHEN ac = 0 THEN part_brute END)                                  AS montantHorsAcBrut,
         COUNT(DISTINCT CASE WHEN ac = 0 AND montant_retenu > ${PLAFOND_ECRETAGE}.0
                             THEN uid END)                                          AS ecretesHorsAc,
         SUM(CASE WHEN ac = 0 AND montant_retenu > ${PLAFOND_ECRETAGE}.0
                  THEN part END)                                                    AS montantEcretesHorsAc,
         COUNT(DISTINCT CASE WHEN ac = 0 AND montant_suspect = 1 THEN uid END)      AS suspectsHorsAc,
         SUM(CASE WHEN ac = 0 AND montant_suspect = 1 THEN part END)                AS montantSuspectsHorsAc,
         COUNT(DISTINCT CASE WHEN ac = 0 AND montant_suspect = 0 THEN uid END)      AS marchesHorsAcHorsSuspects,
         COUNT(DISTINCT CASE WHEN ac = 0 AND montant_suspect = 0 THEN siren END)    AS sirensHorsAcHorsSuspects,
         SUM(CASE WHEN ac = 0 AND montant_suspect = 0 THEN part END)                AS montantHorsAcHorsSuspects,
         COUNT(DISTINCT CASE WHEN ac = 0 AND montant_retenu IS NULL THEN uid END)   AS sansMontantHorsAc,
         COUNT(DISTINCT CASE WHEN def = 1 THEN siren END)                           AS defautSirensTous,
         COUNT(DISTINCT CASE WHEN def = 1 THEN uid END)                             AS defautMarchesTous,
         SUM(CASE WHEN def = 1 THEN part END)                                       AS defautMontantTous,
         COUNT(DISTINCT CASE WHEN def = 1 AND montant_suspect = 0 THEN uid END)     AS defautMarchesTousHorsSuspects,
         SUM(CASE WHEN def = 1 AND montant_suspect = 0 THEN part END)               AS defautMontantTousHorsSuspects,
         COUNT(DISTINCT CASE WHEN def = 1 AND ac = 0 THEN siren END)                AS defautSirensHorsAc,
         COUNT(DISTINCT CASE WHEN def = 1 AND ac = 0 THEN uid END)                  AS defautMarchesHorsAc,
         SUM(CASE WHEN def = 1 AND ac = 0 THEN part END)                            AS defautMontantHorsAc
       FROM (
         SELECT m.uid AS uid, m.montant_retenu AS montant_retenu,
                m.montant_suspect AS montant_suspect, m.ac AS ac,
                m.part AS part, m.part_brute AS part_brute,
                e.siren AS siren, e.defaut AS def
         FROM (${SQL_LIGNES_TITULAIRES}) m
         CROSS JOIN (${SQL_SIRENS_LOBBY}) e ON e.siren = m.siren9
       )`,
    )
    .get() as AgregatsCroisement;

  // 4. Une ligne par représentant d'intérêts titulaire (566 lignes) : la
  //    page y découpe son top et sa liste « en défaut », l'export JSON la
  //    publie entière — inutile de rejouer la jointure trois fois.
  const titulaires = db
    .prepare(
      `SELECT a.siren, ent.denomination, ent.categorie, ent.url_fiche,
              ent.defaut_declaration, ent.activites_12m,
              a.nb_marches_hors_ac, a.montant_hors_ac, a.nb_suspects_hors_ac,
              a.nb_marches_tous, a.montant_tous
       FROM (
         SELECT c.siren                                                      AS siren,
                COUNT(DISTINCT CASE WHEN c.ac = 0 THEN c.uid END)            AS nb_marches_hors_ac,
                SUM(CASE WHEN c.ac = 0 THEN c.part END)                      AS montant_hors_ac,
                COUNT(DISTINCT CASE WHEN c.ac = 0 AND c.montant_suspect = 1
                                    THEN c.uid END)                          AS nb_suspects_hors_ac,
                COUNT(DISTINCT c.uid)                                        AS nb_marches_tous,
                SUM(c.part)                                                  AS montant_tous
         FROM (
           SELECT e.siren AS siren, m.uid AS uid, m.ac AS ac,
                  m.montant_suspect AS montant_suspect, m.part AS part
           FROM (${SQL_LIGNES_TITULAIRES}) m
           CROSS JOIN (${SQL_SIRENS_LOBBY}) e ON e.siren = m.siren9
         ) c
         GROUP BY c.siren
       ) a
       JOIN (SELECT identifiant_national     AS siren,
                    MIN(denomination)        AS denomination,
                    MIN(categorie)           AS categorie,
                    MIN(url_fiche)           AS url_fiche,
                    MAX(defaut_declaration)  AS defaut_declaration,
                    MAX(nb_activites_12m)    AS activites_12m
             FROM lobby_entites
             WHERE type_identifiant = 'SIREN'
             GROUP BY identifiant_national) ent ON ent.siren = a.siren
       ORDER BY a.montant_hors_ac DESC, a.nb_marches_hors_ac DESC, a.siren`,
    )
    .all() as TitulaireLobbyiste[];

  memo = {
    metaS1,
    metaS4,
    couverture,
    agregats,
    ensemble: {
      marchesHorsAc: ensembleMarches.marchesHorsAc,
      montantHorsAc: ensembleMarches.montantHorsAc,
      sirensTitulaires: ensembleSirens.sirensTitulaires,
    },
    titulaires,
  };
  return memo;
}
