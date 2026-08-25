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
 * - tops titulaires et acheteurs : l'unité classée est l'ENTREPRISE
 *   (SIREN), pas l'établissement (SIRET) — cf. `SQL_TOP_TITULAIRES`. Un
 *   identifiant dont aucun SIREN ne peut être extrait est écarté des DEUX
 *   classements et compté à part : decp_titulaires_qualite (unité : le
 *   couple marché x titulaire) et decp_acheteurs_qualite (unité : le
 *   marché, un marché n'ayant qu'un acheteur) ;
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
 * annulee = 0 ET datetime(date_limite_reponse) > datetime('now') à la
 * requête (`datetime()` normalise l'ISO `T` / `+00:00` : une comparaison
 * chaîne laisse passer toutes les clôtures du jour, `T` > espace).
 * Même prédicat que accueil.ts — les deux tuiles doivent dire le même
 * stock.
 * APProch : acheteur = SIREN seul (nom résolu à la requête sur entites puis
 * sur le référentiel Sirene), montants en tranches TEXTE non sommables.
 *
 * Toutes les requêtes de ce fichier ont été éprouvées sur la base réelle
 * (sqlite3 mode ro) le 19/08/2026, sauf celles des tops et de
 * `decp_titulaires_qualite` : elles portent sur le schéma par ENTREPRISE et
 * sont éprouvées sur une base bâtie à ce schéma, remplie depuis la base
 * réelle en lecture seule (21/08/2026).
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

/**
 * Une ligne des classements 12 mois. L'unité classée est l'ENTREPRISE
 * (personne morale, SIREN) : les marchés de tous ses établissements sont
 * regroupés sur une seule ligne, et `nb_etablissements` dit combien
 * d'établissements distincts ce regroupement recouvre.
 *
 * `nom` est le libellé de référence : la `denomination` de Sirene quand le
 * SIREN y figure, sinon le nom déclaré dans le DECP (cf. `SQL_TOP_*`).
 */
export type TopAcheteur = {
  rang: number;
  siren: string | null;
  nom: string | null;
  /** Établissements distincts regroupés sous ce SIREN sur la fenêtre. */
  nb_etablissements: number;
  nb_marches: number;
  montant_total: number | null; // écrêté
  /** 1 si le SIREN figure dans `sirene_unites_legales` (S18) — sinon pas d'annuaire. */
  dans_sirene: number;
};

export type TopTitulaire = TopAcheteur & {
  /** PME / ETI / GE quand connue (Sirene, sinon catégorie déclarée au DECP). */
  categorie: string | null;
};

/**
 * Ce que le classement des titulaires couvre et ce qu'il écarte
 * (`decp_titulaires_qualite`, une seule ligne, même fenêtre 12 mois que
 * `decp_top_titulaires`). Une « ligne » est un couple marché × titulaire :
 * un marché à trois co-titulaires en produit trois.
 *
 * Un identifiant de titulaire non conforme (rien dont on puisse extraire un
 * SIREN : identifiant tronqué, chaîne de remplissage type `00001`, valeur non
 * numérique) ne se rattache à aucune entreprise. Sa ligne est écartée du
 * classement et comptée ici, avec son montant : rien n'est deviné, et rien
 * ne disparaît silencieusement du décompte.
 */
export type QualiteTitulaires = {
  /** Marchés de la fenêtre. */
  nb_marches: number;
  /** Dont au moins un titulaire déclaré. */
  nb_marches_avec_titulaire: number;
  /** Couples marché × titulaire. */
  nb_lignes: number;
  /** Lignes rattachées à un SIREN : celles que le classement agrège. */
  nb_lignes_identifiables: number;
  /** Lignes à identifiant non conforme : hors du classement. */
  nb_lignes_ecartees: number;
  montant_identifiable: number | null;
  /** Montant porté par les lignes écartées — absent de tout classement. */
  montant_ecarte: number | null;
  /** Valeurs d'identifiant distinctes parmi les lignes écartées. */
  nb_identifiants_ecartes: number;
  /** Établissements distincts des lignes identifiables. */
  nb_sirets: number;
  /** Entreprises distinctes : le nombre de lignes possibles du classement. */
  nb_sirens: number;
  /** Entreprises présentes par plus d'un établissement. */
  nb_sirens_multi_etab: number;
};

/**
 * Ce que le classement des acheteurs couvre et ce qu'il écarte
 * (`decp_acheteurs_qualite`, une seule ligne, même fenêtre 12 mois que
 * `decp_top_acheteurs`). Le filtre de conformité de l'identifiant vaut pour
 * les acheteurs comme pour les titulaires : un identifiant dont on ne peut
 * extraire aucun SIREN est écarté du classement, et compté ici.
 *
 * POURQUOI cette table est plus COURTE que `decp_titulaires_qualite` et non
 * son décalque : `decp_marches.acheteur_siret` est scalaire — un marché n'a
 * qu'un acheteur. Le couple marché × acheteur n'existe pas, l'unité de
 * compte est donc le MARCHÉ, et il n'y a aucun compteur de « lignes » à
 * publier ici.
 *
 * La partition porte sur `nb_marches_avec_acheteur`, pas sur `nb_marches` :
 * un marché de la fenêtre sans acheteur renseigné n'est pas un identifiant
 * que nous écartons, c'est une absence de saisie à la source. Les confondre
 * ferait porter à notre filtre un défaut qui ne vient pas de lui.
 */
export type QualiteAcheteurs = {
  /** Marchés de la fenêtre — même source que `QualiteTitulaires.nb_marches`. */
  nb_marches: number;
  /** Dont acheteur renseigné : le dénominateur de la partition ci-dessous. */
  nb_marches_avec_acheteur: number;
  /** Marchés rattachés à un SIREN d'acheteur : ceux que le classement agrège. */
  nb_marches_identifiables: number;
  /** Marchés à identifiant d'acheteur non conforme : hors du classement. */
  nb_marches_ecartes: number;
  montant_identifiable: number | null;
  /** Montant porté par les marchés écartés — absent du classement. */
  montant_ecarte: number | null;
  /** Valeurs d'identifiant distinctes parmi les marchés écartés. */
  nb_identifiants_ecartes: number;
  /** Établissements acheteurs distincts des marchés identifiables. */
  nb_sirets: number;
  /** Entités acheteuses distinctes (SIREN). */
  nb_sirens: number;
  /** Entités acheteuses présentes par plus d'un établissement. */
  nb_sirens_multi_etab: number;
};

/**
 * Forme d'un identifiant d'acheteur écarté du classement. La règle d'écart
 * est unique : n'est pas un SIRET (14 chiffres, rien d'autre). Cette table
 * dit CE QU'EST la valeur écartée, sans la publier : un dump d'identifiants
 * illisibles n'apprend rien, un décompte par forme si.
 *
 * Les libellés sont stables ; les comptes dérivent. `null` si la fenêtre
 * 12 mois n'a pas pu être reconstituée à l'unité près.
 */
export type FormeIdentifiantEcarte = {
  classe:
    | "non_numerique"
    | "lettres"
    | "siren_espaces"
    | "siren_nu"
    | "longueur_13"
    | "autre";
  libelle: string;
  nb_identifiants: number;
  nb_marches: number;
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
  /** Nom résolu à la requête : `entites` d'abord, `sirene_unites_legales`
   *  ensuite — NULL si le SIREN n'est nommé par aucun des deux. */
  acheteur_nom: string | null;
  categorie_achat: string | null;
  montant_estime_tranche: string | null; // tranche texte non sommable
  date_prev_publication: string;
  lien_consultation: string | null;
  /** 1 si l'acheteur figure dans `sirene_unites_legales` (S18). */
  dans_sirene: number;
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
  /** Ce que le classement des titulaires couvre, et ce qu'il écarte faute
   *  d'identifiant exploitable. `null` si la table n'est pas en base — le
   *  paragraphe correspondant n'est alors pas rendu. */
  qualiteTitulaires: QualiteTitulaires | null;
  /** Même chose côté acheteurs, à l'unité du MARCHÉ (un marché n'a qu'un
   *  acheteur). `null` si la table n'est pas en base — la mention
   *  correspondante n'est alors pas rendue. */
  qualiteAcheteurs: QualiteAcheteurs | null;
  /** Forme des identifiants d'acheteur écartés (même fenêtre). `null` si
   *  la fenêtre n'a pas pu être reconstituée : on n'affiche alors que le
   *  compteur, pas une ventilation portant sur une autre population. */
  formesIdentifiantsEcartes: FormeIdentifiantEcarte[] | null;
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

const LIBELLES_FORME_ECARTEE: Record<FormeIdentifiantEcarte["classe"], string> = {
  non_numerique: "valeur sans aucun chiffre",
  lettres: "identifiant portant des lettres",
  siren_espaces: "SIREN de 9 chiffres, avec espaces",
  siren_nu: "SIREN de 9 chiffres, sans le numéro d’établissement",
  longueur_13: "numéro de 13 chiffres — un caractère manque pour un SIRET",
  autre: "autre forme non conforme",
};

/** Classe un identifiant d'acheteur déjà connu non-SIRET. */
function classeIdentifiant(id: string): FormeIdentifiantEcarte["classe"] {
  if (!/\d/.test(id)) return "non_numerique";
  if (/[A-Za-z]/.test(id)) return "lettres";
  const chiffres = id.replace(/\D/g, "");
  if (/\s/.test(id) && chiffres.length === 9) return "siren_espaces";
  if (/^[0-9]+$/.test(id) && id.length === 9) return "siren_nu";
  if (/^[0-9]+$/.test(id) && id.length === 13) return "longueur_13";
  return "autre";
}

/**
 * Ventile les identifiants d'acheteur écartés par FORME, sur la fenêtre
 * 12 mois exacte de `decp_acheteurs_qualite`.
 *
 * POURQUOI ici et pas dans le pipeline : la règle d'écart (14 chiffres) est
 * déjà appliquée à l'ingestion ; ce qui manquait à la page est de dire ce
 * que sont ces valeurs, pas d'en changer le compte. Rejouer le filtre à la
 * lecture évite un `CREATE TABLE` sur la base migrée. On ne retient un
 * candidat QUE s'il reconstitue à l'unité près les trois compteurs déjà
 * publiés (marchés de la fenêtre, marchés écartés, identifiants distincts).
 */
function chargerFormesIdentifiantsEcartes(
  db: Db,
  qualite: QualiteAcheteurs | null,
  s1: MetaSource | undefined,
): FormeIdentifiantEcarte[] | null {
  const jour = s1?.date_ingestion?.slice(0, 10);
  if (!qualite || !jour || qualite.nb_identifiants_ecartes === 0) return null;

  const requete = db.prepare(
    `SELECT acheteur_siret AS id, COUNT(*) AS n
       FROM decp_marches
      WHERE date_notification > date(:jour, :decalage, '-12 months')
        AND acheteur_siret IS NOT NULL
        AND NOT (length(acheteur_siret) = 14 AND acheteur_siret GLOB '[0-9]*')
      GROUP BY acheteur_siret`,
  );
  const compteFenetre = db.prepare(
    `SELECT COUNT(*) AS n FROM decp_marches
      WHERE date_notification > date(:jour, :decalage, '-12 months')`,
  );

  for (const decalage of DECALAGES_FENETRE) {
    const nFenetre = (compteFenetre.get({ jour, decalage }) as { n: number }).n;
    const lignes = requete.all({ jour, decalage }) as { id: string; n: number }[];
    const nbMarches = lignes.reduce((s, l) => s + l.n, 0);
    if (
      nFenetre !== qualite.nb_marches ||
      lignes.length !== qualite.nb_identifiants_ecartes ||
      nbMarches !== qualite.nb_marches_ecartes
    ) {
      continue;
    }
    const parClasse = new Map<FormeIdentifiantEcarte["classe"], FormeIdentifiantEcarte>();
    for (const l of lignes) {
      const classe = classeIdentifiant(l.id);
      const deja = parClasse.get(classe);
      if (deja) {
        deja.nb_identifiants += 1;
        deja.nb_marches += l.n;
      } else {
        parClasse.set(classe, {
          classe,
          libelle: LIBELLES_FORME_ECARTEE[classe],
          nb_identifiants: 1,
          nb_marches: l.n,
        });
      }
    }
    return [...parClasse.values()].sort((a, b) => b.nb_marches - a.nb_marches);
  }
  return null;
}

/* ------------------------------------------------------------------ */
/* Tops 12 mois : le libellé de référence vient de Sirene              */
/* ------------------------------------------------------------------ */

/**
 * `decp_top_titulaires` et `decp_top_acheteurs` classent des ENTREPRISES
 * (SIREN) et stockent, à côté du SIREN, le nom et la catégorie tels que
 * DÉCLARÉS dans le DECP. Le libellé de référence, lui, est celui de Sirene :
 * `denomination` et `categorie_entreprise` de `sirene_unites_legales`.
 *
 * POURQUOI le nommage se fait ICI et non dans le pipeline DECP : écrire un
 * nom issu du référentiel Sirene depuis le pipeline DECP ferait dépendre
 * l'ingestion d'un pipeline de celle d'un autre — un couplage d'écriture
 * entre pipelines que le projet refuse déjà ailleurs (cf. `marches_a_venir`,
 * dont le nom d'acheteur est résolu à la requête via `entites`). La
 * jointure est faite à la lecture, en LEFT JOIN : un SIREN absent du
 * référentiel garde le libellé DECP, un SIREN sans libellé nulle part
 * ressort `nom = NULL` et la page affiche alors le SIREN.
 *
 * RGPD : `sirene_unites_legales.denomination` est NULL pour les personnes
 * physiques, et aucun nom, prénom ni sexe de personne physique n'est lu du
 * fichier Sirene. Le repli sur le libellé DECP est donc le comportement
 * voulu dans ce cas : ce libellé est déjà celui que la source publie et que
 * cette page affiche, la jointure n'ajoute aucune donnée personnelle. Un
 * nom manquant reste manquant — il n'est complété d'aucune autre source.
 *
 * `NULLIF(TRIM(...), '')` : le référentiel porte la chaîne vide au même
 * titre que NULL pour une dénomination absente, les deux doivent replier.
 */
const SQL_TOP_TITULAIRES = `
  SELECT t.rang,
         t.siren,
         COALESCE(NULLIF(TRIM(s.denomination), ''), t.nom)               AS nom,
         COALESCE(NULLIF(TRIM(s.categorie_entreprise), ''), t.categorie) AS categorie,
         t.nb_etablissements,
         t.nb_marches,
         t.montant_total,
         CASE WHEN s.siren IS NOT NULL THEN 1 ELSE 0 END AS dans_sirene
    FROM decp_top_titulaires t
    LEFT JOIN sirene_unites_legales s ON s.siren = t.siren
   ORDER BY t.rang LIMIT 10`;

const SQL_TOP_ACHETEURS = `
  SELECT a.rang,
         a.siren,
         COALESCE(NULLIF(TRIM(s.denomination), ''), a.nom) AS nom,
         a.nb_etablissements,
         a.nb_marches,
         a.montant_total,
         CASE WHEN s.siren IS NOT NULL THEN 1 ELSE 0 END AS dans_sirene
    FROM decp_top_acheteurs a
    LEFT JOIN sirene_unites_legales s ON s.siren = a.siren
   ORDER BY a.rang LIMIT 10`;

/**
 * Mêmes classements sans le référentiel : `sirene_unites_legales` est
 * produite par un AUTRE pipeline que le DECP, elle peut donc manquer alors
 * que les tops sont là. SQLite refuserait la requête entière sur une table
 * absente — on retombe alors sur les libellés DECP, qui sont déjà publiés
 * aujourd'hui. Dégradation propre, jamais une page en erreur.
 */
const SQL_TOP_TITULAIRES_SANS_SIRENE = `
  SELECT rang, siren, nom, categorie, nb_etablissements, nb_marches,
         montant_total, 0 AS dans_sirene
    FROM decp_top_titulaires ORDER BY rang LIMIT 10`;

const SQL_TOP_ACHETEURS_SANS_SIRENE = `
  SELECT rang, siren, nom, nb_etablissements, nb_marches, montant_total,
         0 AS dans_sirene
    FROM decp_top_acheteurs ORDER BY rang LIMIT 10`;

/**
 * Achats annoncés (APProch) : la source ne publie QUE le SIREN de l'acheteur,
 * le schéma le commente lui-même. Le nom est donc résolu à la LECTURE, sur
 * deux référentiels et dans cet ordre :
 *   1. `entites` — vocabulaire maison, mis en forme pour l'affichage
 *      (« Ministère de l'Intérieur »), mais il ne couvre qu'une minorité des
 *      SIREN acheteurs ;
 *   2. `sirene_unites_legales` — dénomination légale en capitales, qui couvre
 *      le reste.
 * `entites` passe en premier délibérément : quand les deux nomment le même
 * SIREN, c'est le libellé lisible qui doit s'afficher, pas la forme légale.
 *
 * POURQUOI À LA REQUÊTE et jamais par un UPDATE depuis le pipeline Sirene :
 * `ingest_approch` fait DELETE+INSERT à chaque ingestion, un nom écrit par un
 * autre pipeline serait effacé à la suivante — et cela créerait entre les deux
 * pipelines un couplage d'écriture que le projet refuse déjà pour les tops
 * (cf. SQL_TOP_TITULAIRES).
 *
 * RGPD, même règle qu'aux tops : `denomination` est NULL pour les personnes
 * physiques, et aucun nom, prénom ni sexe de personne physique n'est lu du
 * fichier Sirene. Un acheteur non nommé le RESTE — la page affiche alors son
 * SIREN, jamais un nom emprunté à une autre source.
 *
 * `NULLIF(TRIM(...), '')` : les deux référentiels portent la chaîne vide au
 * même titre que NULL, les deux doivent replier.
 */
const SQL_MARCHES_A_VENIR = `
  SELECT m.code, m.intitule, m.acheteur_siren,
         COALESCE(
           NULLIF(TRIM((SELECT e.nom FROM entites e
                         WHERE e.siren = m.acheteur_siren
                         ORDER BY e.nom LIMIT 1)), ''),
           NULLIF(TRIM(s.denomination), '')
         ) AS acheteur_nom,
         m.categorie_achat, m.montant_estime_tranche,
         m.date_prev_publication, m.lien_consultation,
         CASE WHEN s.siren IS NOT NULL THEN 1 ELSE 0 END AS dans_sirene
    FROM marches_a_venir m
    LEFT JOIN sirene_unites_legales s ON s.siren = m.acheteur_siren
   ORDER BY m.date_prev_publication ASC, m.code LIMIT 20`;

/**
 * Même liste sans le référentiel Sirene, produit par un AUTRE pipeline et
 * qui peut donc manquer : SQLite refuserait la requête entière sur une table
 * absente. On retombe sur `entites` seul, c'est-à-dire sur le comportement
 * publié jusqu'ici. Dégradation propre, jamais une page en erreur.
 */
const SQL_MARCHES_A_VENIR_SANS_SIRENE = `
  SELECT m.code, m.intitule, m.acheteur_siren,
         NULLIF(TRIM((SELECT e.nom FROM entites e
                       WHERE e.siren = m.acheteur_siren
                       ORDER BY e.nom LIMIT 1)), '') AS acheteur_nom,
         m.categorie_achat, m.montant_estime_tranche,
         m.date_prev_publication, m.lien_consultation,
         0 AS dans_sirene
    FROM marches_a_venir m
   ORDER BY m.date_prev_publication ASC, m.code LIMIT 20`;

/** Une table est-elle présente en base ? (tables produites par d'autres
 *  pipelines : leur absence est un état normal, pas une erreur). */
function tablePresente(db: Db, nom: string): boolean {
  return (
    (
      db
        .prepare(
          `SELECT COUNT(*) AS n FROM sqlite_master
            WHERE type = 'table' AND name = ?`,
        )
        .get(nom) as { n: number }
    ).n === 1
  );
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
       WHERE annulee = 0 AND datetime(date_limite_reponse) > datetime('now')`,
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

  // Tops 12 mois par ENTREPRISE (SIREN) : les établissements d'une même
  // personne morale sont regroupés sur une ligne. Côté titulaires, le
  // montant du marché est réparti entre co-titulaires (la source ne le
  // ventile pas). Le libellé de référence vient de Sirene quand le
  // référentiel est en base, sinon du DECP (cf. SQL_TOP_TITULAIRES).
  const avecSirene = tablePresente(db, "sirene_unites_legales");
  const topAcheteurs = db
    .prepare(avecSirene ? SQL_TOP_ACHETEURS : SQL_TOP_ACHETEURS_SANS_SIRENE)
    .all() as TopAcheteur[];
  const topTitulaires = db
    .prepare(avecSirene ? SQL_TOP_TITULAIRES : SQL_TOP_TITULAIRES_SANS_SIRENE)
    .all() as TopTitulaire[];

  // Ce que le classement des titulaires couvre et ce qu'il écarte. Table
  // produite par le pipeline sur la même fenêtre que le classement ;
  // `null` quand elle n'est pas en base, et la page n'affiche alors pas le
  // paragraphe (même patron que decp_qualite_montants).
  const qualiteTitulaires = tablePresente(db, "decp_titulaires_qualite")
    ? ((db
        .prepare(
          `SELECT nb_marches, nb_marches_avec_titulaire, nb_lignes,
                  nb_lignes_identifiables, nb_lignes_ecartees,
                  montant_identifiable, montant_ecarte,
                  nb_identifiants_ecartes, nb_sirets, nb_sirens,
                  nb_sirens_multi_etab
           FROM decp_titulaires_qualite WHERE id = 1`,
        )
        .get() as QualiteTitulaires | undefined) ?? null)
    : null;

  // Pendant côté acheteurs. Le filtre de conformité de l'identifiant vaut
  // des deux côtés, donc son compteur aussi : un identifiant d'acheteur
  // écarté du classement sans être compté nulle part serait une disparition
  // silencieuse, ce que la page dit ne pas faire. Unité : le MARCHÉ.
  const qualiteAcheteurs = tablePresente(db, "decp_acheteurs_qualite")
    ? ((db
        .prepare(
          `SELECT nb_marches, nb_marches_avec_acheteur,
                  nb_marches_identifiables, nb_marches_ecartes,
                  montant_identifiable, montant_ecarte,
                  nb_identifiants_ecartes, nb_sirets, nb_sirens,
                  nb_sirens_multi_etab
           FROM decp_acheteurs_qualite WHERE id = 1`,
        )
        .get() as QualiteAcheteurs | undefined) ?? null)
    : null;

  const formesIdentifiantsEcartes = chargerFormesIdentifiantsEcartes(
    db,
    qualiteAcheteurs,
    metaPar("S1"),
  );

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
         WHERE annulee = 0 AND datetime(date_limite_reponse) > datetime('now')
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
       WHERE annulee = 0 AND datetime(date_limite_reponse) > datetime('now')
         AND (? IS NULL OR famille = ?)`,
    )
    .get(familleActive, familleActive) as { nb: number; sans: number };

  // 20 échéances les plus proches pour le filtre courant.
  const ao = db
    .prepare(
      `SELECT idweb, objet, acheteur, montant_estime, date_limite_reponse,
              url_avis
       FROM ao_en_cours
       WHERE annulee = 0 AND datetime(date_limite_reponse) > datetime('now')
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

  // APProch : nom d'acheteur résolu à la requête sur `entites` puis Sirene
  // (sous-requête scalaire côté entites : un SIREN peut y porter 2 lignes —
  // vérifié). Cf. SQL_MARCHES_A_VENIR pour l'ordre des référentiels et le
  // refus du couplage d'écriture avec ingest_approch.
  const marchesAVenir = db
    .prepare(avecSirene ? SQL_MARCHES_A_VENIR : SQL_MARCHES_A_VENIR_SANS_SIRENE)
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
    qualiteTitulaires,
    qualiteAcheteurs,
    formesIdentifiantsEcartes,
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
       WHERE annulee = 0 AND datetime(date_limite_reponse) > datetime('now')
         AND famille IS NOT NULL
       GROUP BY famille, famille_libelle ORDER BY nb DESC`,
    )
    .all() as FamilleAO[];

  const vuePour = (famille: string | null): VueAoFamille => {
    const compte = db
      .prepare(
        `SELECT COUNT(*) AS nb, COALESCE(SUM(montant_estime IS NULL), 0) AS sans
         FROM ao_en_cours
         WHERE annulee = 0 AND datetime(date_limite_reponse) > datetime('now')
           AND (? IS NULL OR famille = ?)`,
      )
      .get(famille, famille) as { nb: number; sans: number };
    const lignes = db
      .prepare(
        `SELECT idweb, objet, acheteur, montant_estime, date_limite_reponse,
                url_avis
         FROM ao_en_cours
         WHERE annulee = 0 AND datetime(date_limite_reponse) > datetime('now')
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
