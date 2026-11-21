/**
 * Définition des exports CSV statiques (/api/*.csv) : nom de fichier, sens,
 * sources amont et colonnes. Module pur (les imports sont des types), testé
 * par tests/exports-csv.test.mjs. Les routes `app/api/<nom>.csv/route.ts`
 * lisent la base et passent les lignes à `reponseCsv`, les routes
 * `app/api/<nom>.provenance.txt/route.ts` publient la provenance.
 *
 * Règle de contenu : un CSV ne porte AUCUNE colonne de plus que l'export JSON
 * ou le tableau de page dont il est la version tableur. Même règle de
 * données personnelles que l'affichage : rien n'est ajouté, seuls les champs
 * déjà publiés sont repris. Seuls les en-têtes qui diraient « suspect » sont
 * renommés en « signale » (montant_signales, nb_marches_signales par exemple).
 */
import type { ColonneCsv } from "@/lib/csv";
import type { MetaSource } from "@/lib/db";
import type { Alerte } from "@/lib/queries/alertes";
import type { TitulaireLobbyiste } from "@/lib/queries/croisement-lobbying-marches";
import type { BudgetMensuelLigne, DecpAggDepartement, DecpAggMois, EluExport } from "@/lib/queries/donnees";
import type { RupturePerimetreApi } from "@/lib/queries/budget-ruptures";
import type { TopAcheteur, TopTitulaire } from "@/lib/queries/marches";

export type DefinitionCsv<T> = {
  /** Nom du fichier publié sous /api/, ex. `elus.csv`. */
  fichier: string;
  titre: string;
  description: string;
  mentions?: string[];
  /** Identifiants `meta_sources` amont, repris de la route JSON ou de la page équivalente. */
  sources: string[];
  sansSource?: string;
  /** Chemins du site (page ou export JSON) qui publient les mêmes données. */
  voirAussi: string[];
  colonnes: ColonneCsv<T>[];
};

/** Chemin du site où un CSV est publié (`elus.csv` : `/api/elus.csv`). */
export function cheminCsv(fichier: string): string {
  return `/api/${fichier}`;
}

/** Chemin du fichier de provenance publié à côté d'un CSV. */
export function cheminProvenance(fichier: string): string {
  return `/api/${fichier.replace(/\.csv$/, "")}.provenance.txt`;
}

const CREDIT_DECP =
  "Crédit : consolidation communautaire decp-processing (Colin Maudry), à créditer en cas de réutilisation.";

const NOTIFICATION_INITIALE =
  "Chaque marché est compté à la date de sa notification initiale (un avenant ne le redate pas), avec les montants de sa version courante. Marchés notifiés = engagements contractuels, pas des paiements. Montant d'un accord-cadre = maximum contractuel. Latence légale de publication jusqu'à 2 mois.";

/* ------------------------------------------------------------------ */

export const CSV_META: DefinitionCsv<MetaSource> = {
  fichier: "meta.csv",
  titre: "Catalogue des sources de France Transparence (meta_sources)",
  description:
    "Une ligne par source tracée : nom, URL amont, licence, fréquence déclarée, date des données, date d'ingestion, volumétrie et notes. La fraîcheur calculée de chaque source est sur la page Données et dans /api/meta.json.",
  sources: [],
  sansSource:
    "Le fichier est lui-même le catalogue : chaque ligne porte la licence, la date des données et l'URL amont de sa source.",
  voirAussi: ["/api/meta.json", "/donnees/"],
  colonnes: [
    { cle: "source_id", description: "identifiant de la source", valeur: (s) => s.source_id },
    { cle: "nom", description: "nom de la source et de son producteur", valeur: (s) => s.nom },
    { cle: "url", description: "URL amont", valeur: (s) => s.url },
    { cle: "licence", description: "licence de la source", valeur: (s) => s.licence },
    { cle: "frequence", description: "fréquence de publication déclarée", valeur: (s) => s.frequence },
    { cle: "date_donnees", description: "date des données selon la source", valeur: (s) => s.date_donnees },
    { cle: "date_ingestion", description: "instant de la dernière ingestion", valeur: (s) => s.date_ingestion },
    { cle: "lignes", description: "lignes ingérées", valeur: (s) => s.lignes },
    { cle: "notes", description: "notes de méthode", valeur: (s) => s.notes },
  ],
};

export const CSV_ALERTES: DefinitionCsv<Alerte> = {
  fichier: "alertes.csv",
  titre: "Alertes d'intégrité de la vie publique (France Transparence)",
  description:
    "Les alertes affichées sur la page Alertes, calculées à l'ingestion des données publiques. Chaque alerte cite sa règle et sa base légale. Classification de ce site, constats officiels repris : pas une infraction constatée ici.",
  mentions: [
    "Les comptes de campagne rejetés ou approuvés après réformation ne sont pas dans ce fichier : ils sont comptés sans nom sur la page Financement, qui renvoie aux décisions du Conseil constitutionnel.",
    "Les déclarations HATVP au statut « En cours » plus de 2 mois après l'entrée en fonction sont des agrégats non nominatifs, jamais sous 3 personnes.",
  ],
  sources: ["S14", "S17", "S4", "S25", "S29"],
  voirAussi: ["/alertes/", "/api/alertes.json"],
  colonnes: [
    { cle: "id", description: "identifiant stable de l'alerte", valeur: (a) => a.id },
    { cle: "type", description: "type d'alerte", valeur: (a) => a.type },
    { cle: "gravite", description: "classification de ce site (haute, moyenne, info)", valeur: (a) => a.gravite },
    { cle: "titre", description: "intitulé", valeur: (a) => a.titre },
    { cle: "detail", description: "détail", valeur: (a) => a.detail },
    { cle: "regle", description: "règle de calcul", valeur: (a) => a.regle },
    { cle: "base_legale", description: "base légale", valeur: (a) => a.base_legale },
    { cle: "source_url", description: "URL de la donnée officielle", valeur: (a) => a.source_url },
    { cle: "date_calcul", description: "instant du calcul", valeur: (a) => a.date_calcul },
    { cle: "date_fait", description: "date du fait selon la source (vide quand la source ne la donne pas)", valeur: (a) => a.date_fait },
  ],
};

export const CSV_ELUS: DefinitionCsv<EluExport> = {
  fichier: "elus.csv",
  titre: "Répertoire des élus français, champs publics compacts",
  description:
    "Le répertoire des élus (RNE, open data de l'Assemblée nationale et du Sénat, HATVP), mêmes champs que /api/elus.json : identité, identifiants publics, lien HATVP, types des mandats en cours (député ou sénateur seulement si la chambre liste l'élu au jour des données). Le détail des mandats reste sur les fiches élus et dans le RNE amont. Conseillers municipaux non nominatifs.",
  sources: ["S17", "S5-AMO10", "S6-ODSEN", "S14"],
  voirAussi: ["/elus/", "/api/elus.json"],
  colonnes: [
    { cle: "id", description: "identifiant de la fiche élu du site", valeur: (e) => e.id },
    { cle: "nom", description: "nom", valeur: (e) => e.nom },
    { cle: "prenom", description: "prénom", valeur: (e) => e.prenom },
    { cle: "uid_an", description: "identifiant Assemblée nationale", valeur: (e) => e.uid_an },
    { cle: "matricule_senat", description: "matricule Sénat", valeur: (e) => e.matricule_senat },
    { cle: "hatvp_url", description: "page HATVP", valeur: (e) => e.hatvp_url },
    {
      cle: "types_mandats",
      description: "types des mandats en cours, séparés par une virgule",
      valeur: (e) => (e.types_mandats ?? []).join(","),
    },
  ],
};

type LigneBudget = BudgetMensuelLigne & { rupture_perimetre: RupturePerimetreApi | null };

export const CSV_BUDGET_MENSUEL: DefinitionCsv<LigneBudget> = {
  fichier: "budget-mensuel.csv",
  titre: "Situations mensuelles budgétaires de l'État français",
  description:
    "Situations mensuelles budgétaires de l'État (26 lignes par grands titres), série complète depuis 2013. Montants en euros : montant_cumul = cumul depuis le 1er janvier, montant_mois = flux du mois, colonnes _n1 = même période N-1. Mois infra-annuels provisoires, environ 5 à 7 semaines de décalage. Les colonnes rupture_perimetre_* signalent une cellule qui ne se compare pas à N-1 : valeur publiée telle quelle, aucune variation à calculer à travers elle.",
  sources: ["S13"],
  voirAussi: ["/depenses/", "/api/budget-mensuel.json"],
  colonnes: [
    { cle: "ligne_id", description: "identifiant de la ligne", valeur: (l) => l.ligne_id },
    { cle: "ordre", description: "ordre d'affichage", valeur: (l) => l.ordre },
    { cle: "niveau", description: "niveau dans l'arbre", valeur: (l) => l.niveau },
    { cle: "categorie", description: "catégorie", valeur: (l) => l.categorie },
    { cle: "sous_categorie", description: "sous-catégorie", valeur: (l) => l.sous_categorie },
    { cle: "ligne", description: "libellé de la ligne", valeur: (l) => l.ligne },
    { cle: "date_fin_mois", description: "dernier jour du mois", valeur: (l) => l.date_fin_mois },
    { cle: "annee", description: "année", valeur: (l) => l.annee },
    { cle: "mois", description: "mois (1 à 12)", valeur: (l) => l.mois },
    { cle: "montant_cumul", description: "cumul depuis le 1er janvier, euros", valeur: (l) => l.montant_cumul },
    { cle: "montant_mois", description: "flux du mois seul, euros", valeur: (l) => l.montant_mois },
    { cle: "montant_cumul_n1", description: "cumul à la même date N-1, euros", valeur: (l) => l.montant_cumul_n1 },
    { cle: "montant_mois_n1", description: "flux du même mois N-1, euros", valeur: (l) => l.montant_mois_n1 },
    {
      cle: "rupture_perimetre_cote",
      description: "« mois » : cette cellule est en rupture, « n1 » : c'est celle de N-1 (vide : aucune rupture)",
      valeur: (l) => l.rupture_perimetre?.cote,
    },
    {
      cle: "rupture_perimetre_date_fin_mois",
      description: "date de la cellule en rupture",
      valeur: (l) => l.rupture_perimetre?.date_fin_mois,
    },
    {
      cle: "rupture_perimetre_identite",
      description: "identité comptable que respectent les autres mois",
      valeur: (l) => l.rupture_perimetre?.identite,
    },
    {
      cle: "rupture_perimetre_definition_constatee",
      description: "autre combinaison de lignes qui redonne exactement la cellule",
      valeur: (l) => l.rupture_perimetre?.definition_constatee,
    },
  ],
};

export const CSV_MARCHES_DEPARTEMENTS: DefinitionCsv<DecpAggDepartement> = {
  fichier: "marches-agregats-departements.csv",
  titre: "Marchés publics notifiés par département, 12 mois (DECP consolidées)",
  description:
    "Agrégats de marchés publics par département de l'acheteur, sur 12 mois glissants, montants écrêtés à 100 M€ par marché (montant_total vide = aucun montant connu). Partie « departements » de /api/marches-agregats.json.",
  mentions: [NOTIFICATION_INITIALE, CREDIT_DECP],
  sources: ["S1"],
  voirAussi: ["/marches/", "/api/marches-agregats.json"],
  colonnes: [
    { cle: "departement_code", description: "code du département", valeur: (d) => d.departement_code },
    { cle: "departement_nom", description: "nom du département", valeur: (d) => d.departement_nom },
    { cle: "nb_marches", description: "marchés notifiés", valeur: (d) => d.nb_marches },
    { cle: "montant_total", description: "somme écrêtée à 100 M€ par marché, euros", valeur: (d) => d.montant_total },
    { cle: "nb_marches_ecretes", description: "marchés dont le montant a été écrêté", valeur: (d) => d.nb_marches_ecretes },
  ],
};

export const CSV_MARCHES_MOIS: DefinitionCsv<DecpAggMois> = {
  fichier: "marches-agregats-mois.csv",
  titre: "Marchés publics notifiés par mois, 36 mois (DECP consolidées)",
  description:
    "Agrégats de marchés publics par mois de notification, sur 36 mois glissants, montants écrêtés à 100 M€ par marché (montant_total vide = aucun montant connu). Partie « mois » de /api/marches-agregats.json.",
  mentions: [NOTIFICATION_INITIALE, CREDIT_DECP],
  sources: ["S1"],
  voirAussi: ["/marches/", "/api/marches-agregats.json"],
  colonnes: [
    { cle: "mois", description: "mois de notification (AAAA-MM)", valeur: (m) => m.mois },
    { cle: "nb_marches", description: "marchés notifiés", valeur: (m) => m.nb_marches },
    { cle: "montant_total", description: "somme écrêtée à 100 M€ par marché, euros", valeur: (m) => m.montant_total },
  ],
};

export const CSV_LOBBYING_MARCHES: DefinitionCsv<TitulaireLobbyiste> = {
  fichier: "lobbying-marches.csv",
  titre: "Représentants d'intérêts titulaires de marchés publics (HATVP × DECP)",
  description:
    "Les représentants d'intérêts inscrits au répertoire HATVP qui sont titulaires de marchés publics, joints sur le SIREN (exact, sans rapprochement de noms) : partie « titulaires » de /api/lobbying-marches.json, dont le bloc meta donne aussi les agrégats et la couverture. Fenêtre de 24 mois sur la notification initiale. Montants écrêtés à 100 M€ par marché puis répartis à parts égales entre co-titulaires. Périmètre de référence hors accords-cadres (montant d'un accord-cadre = maximum, pas une dépense).",
  mentions: [
    "Être inscrit au répertoire des représentants d'intérêts et être titulaire d'un marché public sont deux situations légales qui se cumulent couramment : aucune entité de ce fichier n'est en tort du seul fait d'y figurer. defaut_declaration reprend tel quel le constat officiel de la HATVP, qui ne qualifie que la déclaration de représentation d'intérêts, jamais le marché.",
    "Méthode : docs/CROISEMENT-LOBBYING-MARCHES.md du dépôt du site.",
    CREDIT_DECP,
  ],
  sources: ["S1", "S4"],
  voirAussi: ["/lobbying/", "/api/lobbying-marches.json"],
  colonnes: [
    { cle: "siren", description: "SIREN de l'entité", valeur: (t) => t.siren },
    { cle: "denomination", description: "dénomination au répertoire HATVP", valeur: (t) => t.denomination },
    { cle: "categorie", description: "catégorie déclarée à la HATVP", valeur: (t) => t.categorie },
    { cle: "url_fiche", description: "fiche HATVP de l'entité", valeur: (t) => t.url_fiche },
    { cle: "defaut_declaration", description: "1 = constat officiel HATVP de défaut de déclaration", valeur: (t) => t.defaut_declaration },
    { cle: "activites_12m", description: "activités de représentation d'intérêts publiées sur 12 mois", valeur: (t) => t.activites_12m },
    { cle: "nb_marches_hors_ac", description: "marchés hors accords-cadres", valeur: (t) => t.nb_marches_hors_ac },
    { cle: "montant_hors_ac", description: "montant hors accords-cadres, écrêté et réparti, euros", valeur: (t) => t.montant_hors_ac },
    { cle: "nb_signales_hors_ac", description: "marchés hors accords-cadres au montant signalé", valeur: (t) => t.nb_suspects_hors_ac },
    { cle: "nb_marches_tous", description: "marchés, accords-cadres compris", valeur: (t) => t.nb_marches_tous },
    { cle: "montant_tous", description: "montant, accords-cadres compris, euros", valeur: (t) => t.montant_tous },
  ],
};

/**
 * Colonnes communes aux deux classements, dans l'ordre du tableau de /marches.
 * Les en-têtes publiés disent « signalé » (décision de ton du 20/11) : les
 * champs de la base et les clés du JSON gardent leur nom `*_suspects`.
 */
type LigneTop = Omit<TopAcheteur, "montant_total">;

const COLONNES_MONTANT_TOP: ColonneCsv<LigneTop>[] = [
  {
    cle: "montant_hors_signales",
    description: "montant hors montants signalés, euros (fixe le rang)",
    valeur: (a) => a.montant_hors_suspects,
  },
  {
    cle: "montant_signales",
    description: "montants signalés, euros (vide quand aucun marché n'est signalé)",
    valeur: (a) => (a.nb_marches_suspects === 0 ? null : a.montant_suspects),
  },
  {
    cle: "nb_marches_signales",
    description: "marchés au montant signalé",
    valeur: (a) => a.nb_marches_suspects,
  },
];

const MENTIONS_TOP = [
  "Fenêtre de 12 mois glissants sur la notification initiale. Un SIREN regroupe tous les établissements d'une même personne morale. Montants écrêtés à 100 M€ par marché. Le rang est fixé par le montant hors montants signalés, les montants signalés sont publiés à côté, jamais retirés. Nom de référence : dénomination Sirene quand le SIREN y figure, sinon nom déclaré dans les DECP.",
  CREDIT_DECP,
];

export const CSV_TOP_ACHETEURS: DefinitionCsv<LigneTop> = {
  fichier: "marches-top-acheteurs.csv",
  titre: "Top acheteurs publics, 12 mois (DECP consolidées)",
  description:
    "Le tableau « Top acheteurs » de la page Marchés publics, mêmes colonnes : les acheteurs regroupés par SIREN qui ont notifié les montants les plus élevés sur 12 mois.",
  mentions: MENTIONS_TOP,
  sources: ["S1", "S18"],
  voirAussi: ["/marches/"],
  colonnes: [
    { cle: "rang", description: "rang", valeur: (a) => a.rang },
    { cle: "nom", description: "acheteur", valeur: (a) => a.nom },
    { cle: "siren", description: "SIREN", valeur: (a) => a.siren },
    { cle: "nb_etablissements", description: "établissements regroupés sous ce SIREN", valeur: (a) => a.nb_etablissements },
    { cle: "nb_marches", description: "marchés", valeur: (a) => a.nb_marches },
    ...COLONNES_MONTANT_TOP,
  ],
};

export const CSV_TOP_TITULAIRES: DefinitionCsv<Omit<TopTitulaire, "montant_total">> = {
  fichier: "marches-top-titulaires.csv",
  titre: "Top titulaires de marchés publics, 12 mois (DECP consolidées)",
  description:
    "Le tableau « Top titulaires » de la page Marchés publics, mêmes colonnes : les entreprises regroupées par SIREN titulaires des montants les plus élevés sur 12 mois. Montant d'un marché à plusieurs titulaires réparti à parts égales entre co-titulaires.",
  mentions: MENTIONS_TOP,
  sources: ["S1", "S18"],
  voirAussi: ["/marches/"],
  colonnes: [
    { cle: "rang", description: "rang", valeur: (t) => t.rang },
    { cle: "nom", description: "titulaire", valeur: (t) => t.nom },
    { cle: "siren", description: "SIREN", valeur: (t) => t.siren },
    { cle: "categorie", description: "catégorie d'entreprise (PME, ETI, GE)", valeur: (t) => t.categorie },
    { cle: "nb_etablissements", description: "établissements regroupés sous ce SIREN", valeur: (t) => t.nb_etablissements },
    { cle: "nb_marches", description: "marchés", valeur: (t) => t.nb_marches },
    ...COLONNES_MONTANT_TOP,
  ],
};

/** Tous les exports CSV, dans l'ordre de la page Données. */
export const EXPORTS_CSV: Pick<DefinitionCsv<unknown>, "fichier" | "titre" | "description" | "sources">[] = [
  CSV_META,
  CSV_ALERTES,
  CSV_ELUS,
  CSV_BUDGET_MENSUEL,
  CSV_MARCHES_DEPARTEMENTS,
  CSV_MARCHES_MOIS,
  CSV_LOBBYING_MARCHES,
  CSV_TOP_ACHETEURS,
  CSV_TOP_TITULAIRES,
];
