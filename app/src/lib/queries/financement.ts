/**
 * Requêtes du module Financement de la vie politique :
 * - S25 : comptes des partis déposés à la CNCCFP (exercices 2021-2024) ;
 * - S29 : comptes de campagne des législatives 2024 ;
 * - S37 : décrets annuels d'aide publique aux partis (enveloppes NATIONALES,
 *   une ligne par décret consulté — 2024 et 2026).
 *
 * ATTENTION, deux grandeurs distinctes coexistent ici et ne se comparent pas :
 * l'ENVELOPPE fixée par décret (partis_aide_annuelle) et la somme des aides
 * INSCRITES AUX COMPTES par les partis (partis_comptes / v_partis_aide_publique_evolution,
 * un cumul de déclarations). Les deux séries coïncident en 2021-2022 puis
 * divergent à partir de 2023.
 *
 * Chaque requête a été rejouée telle quelle via
 * `sqlite3 "file:data/france.db?mode=ro"` le 20/08/2026 (valeurs de
 * contrôle : 575 dépôts 2024, produits totaux 208 620 190,81 €, aide
 * inscrite aux comptes F1+F2 2024 = 70 275 372,28 €, enveloppes des décrets
 * 2024 = 66 438 848,34 € et 2026 = 64 262 871,05 €, 4 010 candidats,
 * taux de rejet 0,0271, 85 alertes rejet).
 *
 * Convention « base absente » : `getDonneesFinancement()` renvoie `null`
 * tant que `make ingest` n'a pas produit la base.
 */
import { getDb, type MetaSource } from "@/lib/db";

/** KPI de tête (exercice 2024, comptes en euros pour les montants). */
export type FinancementKpi = {
  /** Nb de partis ayant déposé leurs comptes 2024 (toutes unités). */
  depots2024: number;
  /** Somme des produits totaux 2024 (comptes en euros uniquement). */
  produits2024: number;
};

/** Ligne de la vue v_partis_top_produits (dernier exercice = 2024). */
export type PartiTopProduits = {
  parti_id: string;
  nom: string;
  sigle: string | null;
  exercice: number;
  produits_total: number | null;
  aide_publique: number;
  dons: number | null;
  cotisations: number;
};

/** Ligne de v_partis_ressources_par_type pour un exercice. */
export type RessourcesParType = {
  exercice: number;
  dons: number;
  cotisations_adherents: number;
  cotisations_elus: number;
  aide_publique: number;
  contributions_recues: number;
  autres_produits: number;
  produits_total: number;
};

/** Ligne de v_partis_aide_publique_evolution (2021 → 2024). */
export type AidePubliqueAnnee = {
  exercice: number;
  aide_f1: number;
  aide_f2: number;
  autres_aides_publiques: number;
  aide_f1_f2: number;
  nb_partis_aides: number;
};

/**
 * Ligne de `partis_aide_annuelle` : l'ENVELOPPE nationale d'une année, telle
 * que fixée par un décret réellement consulté. À ne pas confondre avec
 * `AidePubliqueAnnee`, qui agrège des déclarations de partis.
 */
export type DecretAidePublique = {
  annee: number;
  montant_total_eur: number;
  /** NULL tant que le décret n'a pas été dépouillé fraction par fraction. */
  fraction1_eur: number | null;
  fraction2_eur: number | null;
  perimetre: string;
  reference: string;
  source_url: string;
  note: string | null;
};

/** Agrégats des comptes de campagne (v_campagnes_2024_agregats). */
export type CampagnesAgregats = {
  nb_candidats: number;
  depenses_declarees: number;
  depenses_retenues: number;
  recettes_declarees: number;
  recettes_retenues: number;
  remboursement_etat: number;
  nb_approuves: number;
  nb_reformes: number;
  nb_rejetes: number;
  nb_absences_depot: number;
  nb_hors_delai: number;
  nb_dispenses_depot: number;
  taux_rejet_comptes_deposes: number;
};

/** Répartition par famille de décision CNCCFP (agrégée en SQL). */
export type DecisionFamille = {
  decision_famille: string;
  nb: number;
  depenses_retenues: number;
  remboursement_etat: number;
};

/** Ligne brute de v_campagnes_2024_par_decision (codes natifs). */
export type DecisionDetail = {
  decision: string;
  decision_famille: string;
  nb: number;
  depenses_retenues: number;
  remboursement_etat: number;
};

/** Ligne de v_campagnes_2024_top_depenses — sans nuance politique. */
export type CampagneTopDepense = {
  candidat_id: string;
  nom: string;
  circonscription: string;
  departement: string | null;
  depenses_declarees: number | null;
  depenses_retenues: number | null;
  remboursement_etat: number | null;
  decision: string;
};

/** Enveloppe ouverte par décret — pas l’aide inscrite aux comptes. */
export function perimetreEnveloppeDecret(d: Pick<DecretAidePublique, "perimetre">): string {
  return `${d.perimetre.toLowerCase()} — ouverture par décret, pas les comptes des partis`;
}

/** Somme des déclarations F1+F2 — pas l’enveloppe du décret. */
export const PERIMETRE_AIDE_INSCRITE =
  "cumul de déclarations F1+F2, exercice 2024 — pas l’enveloppe du décret";

/** Effectif de dépôts — un stock, pas un flux d’argent. */
export const PERIMETRE_DEPOTS_PARTIS =
  "effectif de dépôts, toutes unités — un stock, pas un flux d’argent";

/** Produits = flux d’exercice, comptes en euros. */
export const PERIMETRE_PRODUITS_PARTIS =
  "flux de l’exercice 2024, comptes en euros — pas un patrimoine";

/** Fichier CNCCFP des législatives 2024 — pas le recensement ministériel. */
export const PERIMETRE_CANDIDATS_CAMPAGNE =
  "législatives 2024, fichier CNCCFP — ce n’est pas le recensement ministériel des candidats";

/** Taux sur les comptes déposés seulement. */
export const PERIMETRE_TAUX_REJET =
  "rejets / comptes déposés — dispensés et absences de dépôt exclus du dénominateur";

/** Montant retenu, flux du scrutin. */
export const PERIMETRE_DEPENSES_RETENUES =
  "flux du scrutin 2024, montants retenus par la CNCCFP — pas le déclaré";

/** Remboursement : comptes approuvés seulement. */
export const PERIMETRE_REMBOURSEMENT =
  "flux du scrutin 2024 — dans les données, seuls les comptes approuvés portent un remboursement";

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

/** Synthèse des 85 alertes de rejet (règle/base légale communes). */
export type AlertesRejetsSynthese = {
  nb: number;
  gravite: string;
  regle: string | null;
  base_legale: string | null;
  source_url: string | null;
};

export type DonneesFinancement = {
  /** Fraîcheur S25 (comptes des partis), S29 (campagnes), S37 (décret). */
  metaPartis: MetaSource;
  metaCampagnes: MetaSource;
  metaDecret: MetaSource | null;
  kpi: FinancementKpi;
  /** Comptes 2023 déposés hors euros (2 XPF + 1 sans unité), exclus des agrégats €. */
  comptesHorsEuros: { nb: number; exercice_min: number | null; exercice_max: number | null };
  topProduits: PartiTopProduits[];
  ressources2024: RessourcesParType | null;
  /** Aide INSCRITE AUX COMPTES par les partis, par exercice (déclarations). */
  aideEvolution: AidePubliqueAnnee[];
  /** Enveloppes légales, une par décret consulté, année croissante. */
  decretsAide: DecretAidePublique[];
  campagnes: CampagnesAgregats;
  decisionsFamilles: DecisionFamille[];
  decisionsDetail: DecisionDetail[];
  topDepenses: CampagneTopDepense[];
  /** Comptes approuvés après réformation dont le retenu dépasse le déclaré. */
  nbReformationHausse: number;
  alertesRejets: AlertesRejetsSynthese;
  /** Les 5 alertes « dépendance aide publique ≥ 75 % » (ratio décroissant). */
  alertesDependance: AlerteLigne[];
  /** Alerte documentaire « partis privés d'aide » (liste JO en PDF seulement). */
  alerteDocumentaire: AlerteLigne | null;
};

/**
 * Charge toutes les données de la page Financement en une passe.
 * `null` si la base (ou une source obligatoire S25/S29) est absente.
 */
export function getDonneesFinancement(): DonneesFinancement | null {
  const db = getDb();
  if (!db) return null;

  const metas = db
    .prepare("SELECT * FROM meta_sources WHERE source_id IN ('S25','S29','S37')")
    .all() as MetaSource[];
  const metaPartis = metas.find((m) => m.source_id === "S25");
  const metaCampagnes = metas.find((m) => m.source_id === "S29");
  const metaDecret = metas.find((m) => m.source_id === "S37") ?? null;
  if (!metaPartis || !metaCampagnes) return null;

  const kpi = db
    .prepare(
      `SELECT COUNT(*) AS depots2024,
              ROUND(SUM(CASE WHEN unite = 'EUR' THEN COALESCE(produits_total, 0) ELSE 0 END), 2)
                AS produits2024
       FROM partis_comptes
       WHERE exercice = 2024`,
    )
    .get() as FinancementKpi;

  const comptesHorsEuros = db
    .prepare(
      `SELECT COUNT(*) AS nb, MIN(exercice) AS exercice_min, MAX(exercice) AS exercice_max
       FROM partis_comptes
       WHERE unite <> 'EUR'`,
    )
    .get() as { nb: number; exercice_min: number | null; exercice_max: number | null };

  const topProduits = db
    .prepare(
      `SELECT parti_id, nom, sigle, exercice, produits_total, aide_publique, dons, cotisations
       FROM v_partis_top_produits
       LIMIT 10`,
    )
    .all() as PartiTopProduits[];

  const ressources2024 =
    (db
      .prepare("SELECT * FROM v_partis_ressources_par_type WHERE exercice = 2024")
      .get() as RessourcesParType | undefined) ?? null;

  const aideEvolution = db
    .prepare("SELECT * FROM v_partis_aide_publique_evolution")
    .all() as AidePubliqueAnnee[];

  // Tous les décrets sourcés, et eux seuls : la table n'est jamais complétée
  // par interpolation, la série est volontairement trouée.
  const decretsAide = db
    .prepare("SELECT * FROM partis_aide_annuelle ORDER BY annee")
    .all() as DecretAidePublique[];

  const campagnes = db
    .prepare("SELECT * FROM v_campagnes_2024_agregats")
    .get() as CampagnesAgregats;

  const decisionsFamilles = db
    .prepare(
      `SELECT decision_famille,
              SUM(nb) AS nb,
              ROUND(SUM(depenses_retenues), 2)  AS depenses_retenues,
              ROUND(SUM(remboursement_etat), 2) AS remboursement_etat
       FROM v_campagnes_2024_par_decision
       GROUP BY decision_famille
       ORDER BY nb DESC`,
    )
    .all() as DecisionFamille[];

  const decisionsDetail = db
    .prepare("SELECT * FROM v_campagnes_2024_par_decision")
    .all() as DecisionDetail[];

  const topDepenses = db
    .prepare(
      `SELECT candidat_id, nom, circonscription, departement,
              depenses_declarees, depenses_retenues, remboursement_etat, decision
       FROM v_campagnes_2024_top_depenses
       LIMIT 10`,
    )
    .all() as CampagneTopDepense[];

  const nbReformationHausse = (
    db
      .prepare(
        `SELECT COUNT(*) AS nb
         FROM campagnes_2024
         WHERE decision_famille = 'approuve_apres_reformation'
           AND depenses_retenues > depenses_declarees`,
      )
      .get() as { nb: number }
  ).nb;

  // Les 85 alertes de rejet partagent une même règle et base légale
  // (vérifié : COUNT(DISTINCT regle) = COUNT(DISTINCT base_legale) = 1).
  const alertesRejets = db
    .prepare(
      `SELECT COUNT(*) AS nb,
              MIN(gravite)     AS gravite,
              MIN(regle)       AS regle,
              MIN(base_legale) AS base_legale,
              MIN(source_url)  AS source_url
       FROM alertes
       WHERE type = 'financement_campagne_rejetee'`,
    )
    .get() as AlertesRejetsSynthese;

  const alertesDependance = db
    .prepare(
      `SELECT id, type, gravite, titre, detail, regle, base_legale, source_url, date_calcul
       FROM alertes
       WHERE type = 'financement_parti_dependance_aide'
       ORDER BY CAST(substr(detail, instr(detail, '(ratio ') + 7) AS REAL) DESC, id`,
    )
    .all() as AlerteLigne[];

  const alerteDocumentaire =
    (db
      .prepare(
        `SELECT id, type, gravite, titre, detail, regle, base_legale, source_url, date_calcul
         FROM alertes
         WHERE type = 'financement_parti_prive_aide'
         ORDER BY id
         LIMIT 1`,
      )
      .get() as AlerteLigne | undefined) ?? null;

  return {
    metaPartis,
    metaCampagnes,
    metaDecret,
    kpi,
    comptesHorsEuros,
    topProduits,
    ressources2024,
    aideEvolution,
    decretsAide,
    campagnes,
    decisionsFamilles,
    decisionsDetail,
    topDepenses,
    nbReformationHausse,
    alertesRejets,
    alertesDependance,
    alerteDocumentaire,
  };
}
