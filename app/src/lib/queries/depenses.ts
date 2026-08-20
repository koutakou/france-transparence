/**
 * Requêtes du module « Dépenses de l'État » (/depenses).
 *
 * Sources lues (data/france.db, lecture seule) :
 * - S13 `budget_mensuel` — situations mensuelles budgétaires DGFiP :
 *   montants = CUMULS depuis le 1er janvier, dernier mois = max(date_fin_mois)
 *   (= 2026-06-30 à l'ingestion du 19/08/2026), colonnes `*_n1` pour N−1 ;
 * - S20 `budget_vert` — crédits PLF 2026 (≠ LFI promulguée, jamais publiée
 *   en données) : afficher `etiquette_2026`, filtrer
 *   `type_depense = 'Crédits budgétaires'` (total CP 479,5 Md€) ;
 * - S21 `budget_destination_2025` — CP BRUTS du PLF 2025 (projet), non
 *   comparables aux dépenses nettes de S13 ;
 * - S23 `subventions_associations` — versements 2023 (décalage structurel
 *   de deux ans, à dire à l'écran).
 *
 * Valeurs de contrôle (sqlite3, 19/08/2026) : dépenses nettes cumulées au
 * 30/06/2026 = 240 537 726 398,70 € (N−1 : 228 120 512 879,50 €, soit
 * +5,44 %) ; solde budgétaire −106 773 214 550,73 € ; recettes nettes
 * 184 552 567 623,22 € ; subventions 2023 = 11,77 Md€ sur 112 722 versements.
 *
 * Chaque fonction renvoie `null` tant que la base n'est pas construite
 * (`getDb()` null) — la page affiche alors son message honnête.
 */
import { getDb, type MetaSource } from "@/lib/db";

/* Lignes de synthèse de budget_mensuel (identifiants stables du pipeline). */
const LIGNE_DEPENSES_NETTES =
  "depenses/budget-general/total-depenses-nettes-du-budget-general";
const LIGNE_RECETTES_NETTES =
  "recettes/budget-general/total-recettes-nettes-du-budget-general";
const LIGNE_SOLDE = "solde-budgetaire/solde-budgetaire/solde-budgetaire";

/** Identifiants meta_sources du module. */
export type SourceBudgetId = "S13" | "S20" | "S21" | "S23";

/**
 * Lignes de fraîcheur des quatre sources du module (FreshnessBadge par bloc).
 * Une clé peut manquer si la source n'a pas été ingérée : la page ne rend
 * alors pas le badge correspondant.
 */
export function getSourcesBudget(): Partial<Record<SourceBudgetId, MetaSource>> | null {
  const db = getDb();
  if (!db) return null;
  const lignes = db
    .prepare(
      "SELECT * FROM meta_sources WHERE source_id IN ('S13','S20','S21','S23')",
    )
    .all() as MetaSource[];
  const parId: Partial<Record<SourceBudgetId, MetaSource>> = {};
  for (const ligne of lignes) parId[ligne.source_id as SourceBudgetId] = ligne;
  return parId;
}

export interface KpisBudgetMensuel {
  /** Dernier mois publié (ISO, ex. « 2026-06-30 »). */
  dateFinMois: string;
  /** Année du dernier mois publié (2026). */
  annee: number;
  /** Cumul des dépenses nettes du budget général depuis le 1er janvier (€). */
  depensesNettes: number;
  /** Même cumul à la même date l'année précédente (€), si publié. */
  depensesNettesN1: number | null;
  recettesNettes: number | null;
  recettesNettesN1: number | null;
  /** Solde budgétaire cumulé (négatif = déficit). */
  solde: number | null;
  soldeN1: number | null;
}

interface LigneMensuelleRow {
  ligne_id: string;
  date_fin_mois: string;
  annee: number;
  montant_cumul: number;
  montant_cumul_n1: number | null;
}

/**
 * KPI du bandeau : dépenses nettes, recettes nettes et solde budgétaire
 * cumulés au dernier mois publié (S13). Testé : au 2026-06-30, dépenses
 * 240 537 726 398,70 € / recettes 184 552 567 623,22 € / solde
 * −106 773 214 550,73 €.
 */
export function getKpisBudgetMensuel(): KpisBudgetMensuel | null {
  const db = getDb();
  if (!db) return null;
  const lignes = db
    .prepare(
      `SELECT ligne_id, date_fin_mois, annee, montant_cumul, montant_cumul_n1
         FROM budget_mensuel
        WHERE date_fin_mois = (SELECT MAX(date_fin_mois) FROM budget_mensuel)
          AND ligne_id IN (?, ?, ?)`,
    )
    .all(LIGNE_DEPENSES_NETTES, LIGNE_RECETTES_NETTES, LIGNE_SOLDE) as LigneMensuelleRow[];
  const depenses = lignes.find((l) => l.ligne_id === LIGNE_DEPENSES_NETTES);
  if (!depenses) return null;
  const recettes = lignes.find((l) => l.ligne_id === LIGNE_RECETTES_NETTES);
  const solde = lignes.find((l) => l.ligne_id === LIGNE_SOLDE);
  return {
    dateFinMois: depenses.date_fin_mois,
    annee: depenses.annee,
    depensesNettes: depenses.montant_cumul,
    depensesNettesN1: depenses.montant_cumul_n1,
    recettesNettes: recettes?.montant_cumul ?? null,
    recettesNettesN1: recettes?.montant_cumul_n1 ?? null,
    solde: solde?.montant_cumul ?? null,
    soldeN1: solde?.montant_cumul_n1 ?? null,
  };
}

export interface SerieAnnuelleDepenses {
  annee: number;
  /** 12 positions (janvier → décembre), en euros ; `null` = mois non publié. */
  valeurs: (number | null)[];
}

/**
 * Série mensuelle des dépenses nettes CUMULÉES du budget général, pour les
 * `nbAnnees` dernières années (la plus récente d'abord — c'est elle que la
 * page trace en série 1). Testé : juin 2026 = 240,54 Md€, juin 2025 =
 * 228,12 Md€, juin 2024 = 230,57 Md€ ; 2026 s'arrête au mois 6.
 */
export function getSerieDepensesNettes(nbAnnees = 3): SerieAnnuelleDepenses[] | null {
  const db = getDb();
  if (!db) return null;
  const lignes = db
    .prepare(
      `SELECT annee, mois, montant_cumul
         FROM budget_mensuel
        WHERE ligne_id = ?
          AND annee > (SELECT MAX(annee) FROM budget_mensuel) - ?
        ORDER BY annee DESC, mois ASC`,
    )
    .all(LIGNE_DEPENSES_NETTES, nbAnnees) as {
    annee: number;
    mois: number;
    montant_cumul: number;
  }[];
  if (lignes.length === 0) return null;
  const parAnnee = new Map<number, (number | null)[]>();
  for (const l of lignes) {
    if (!parAnnee.has(l.annee)) parAnnee.set(l.annee, Array<number | null>(12).fill(null));
    const valeurs = parAnnee.get(l.annee);
    if (valeurs && l.mois >= 1 && l.mois <= 12) valeurs[l.mois - 1] = l.montant_cumul;
  }
  return [...parAnnee.entries()]
    .sort((a, b) => b[0] - a[0])
    .map(([annee, valeurs]) => ({ annee, valeurs }));
}

export interface TitreDepense {
  /** Libellé du titre tel que publié (« Dépenses de personnel »…). */
  ligne: string;
  /** Cumul depuis le 1er janvier au dernier mois publié (€). */
  montantCumul: number;
  /** Même cumul à la même date N−1 (€), si publié. */
  montantCumulN1: number | null;
}

export interface DepensesParTitre {
  dateFinMois: string;
  titres: TitreDepense[];
}

/**
 * Décomposition des dépenses nettes du budget général par titre (niveau 2,
 * catégorie « Dépenses », sous-catégorie « Budget général ») au dernier mois
 * publié. Testé au 2026-06-30 : personnel 81,03 Md€, intervention 73,24,
 * fonctionnement 37,18, charges de la dette 34,53, investissement 13,04,
 * dotation des pouvoirs publics 1,14, opérations financières 0,37.
 */
export function getDepensesParTitre(): DepensesParTitre | null {
  const db = getDb();
  if (!db) return null;
  const lignes = db
    .prepare(
      `SELECT ligne, date_fin_mois, montant_cumul, montant_cumul_n1
         FROM budget_mensuel
        WHERE date_fin_mois = (SELECT MAX(date_fin_mois) FROM budget_mensuel)
          AND categorie = 'Dépenses'
          AND sous_categorie = 'Budget général'
          AND niveau = 2
        ORDER BY montant_cumul DESC`,
    )
    .all() as {
    ligne: string;
    date_fin_mois: string;
    montant_cumul: number;
    montant_cumul_n1: number | null;
  }[];
  if (lignes.length === 0) return null;
  return {
    dateFinMois: lignes[0].date_fin_mois,
    titres: lignes.map((l) => ({
      ligne: l.ligne,
      montantCumul: l.montant_cumul,
      montantCumulN1: l.montant_cumul_n1,
    })),
  };
}

export interface MissionPlf2026 {
  mission: string;
  /** Exécution 2024 en CP (€) — `null` si aucune ligne renseignée. */
  exec2024Cp: number | null;
  /** LFI 2025 en CP (€) — `null` si aucune ligne renseignée. */
  lfi2025Cp: number | null;
  /** PLF 2026 en CP (€). */
  plf2026Cp: number | null;
}

export interface MissionsPlf2026 {
  /** Étiquette publiée par le pipeline (PLF déposé ≠ LFI promulguée). */
  etiquette: string;
  /** Total CP des crédits budgétaires du PLF 2026 (€) — testé : 479,5 Md€. */
  totalPlf2026Cp: number;
  /** Top missions par CP PLF 2026 décroissant. */
  missions: MissionPlf2026[];
}

/**
 * Top missions du PLF 2026 en crédits de paiement (S20 `budget_vert`,
 * `type_depense = 'Crédits budgétaires'` uniquement — hors dépenses fiscales
 * et taxes affectées), avec la comparaison exécution 2024 / LFI 2025 /
 * PLF 2026. Testé : Pensions 68,16 Md€, Enseignement scolaire 64,48,
 * Défense 57,15 (exéc 2024 : 47,84) ; total CP 479,5 Md€.
 */
export function getMissionsPlf2026(limite = 10): MissionsPlf2026 | null {
  const db = getDb();
  if (!db) return null;
  const total = db
    .prepare(
      `SELECT SUM(plf_2026_cp) AS total, MAX(etiquette_2026) AS etiquette
         FROM budget_vert
        WHERE type_depense = 'Crédits budgétaires'`,
    )
    .get() as { total: number | null; etiquette: string | null } | undefined;
  if (!total || total.total === null) return null;
  const missions = db
    .prepare(
      `SELECT mission,
              SUM(execution_2024_cp) AS exec_2024,
              SUM(lfi_2025_cp)       AS lfi_2025,
              SUM(plf_2026_cp)       AS plf_2026
         FROM budget_vert
        WHERE type_depense = 'Crédits budgétaires'
        GROUP BY mission
        ORDER BY SUM(plf_2026_cp) DESC
        LIMIT ?`,
    )
    .all(limite) as {
    mission: string;
    exec_2024: number | null;
    lfi_2025: number | null;
    plf_2026: number | null;
  }[];
  return {
    etiquette: total.etiquette ?? "PLF 2026",
    totalPlf2026Cp: total.total,
    missions: missions.map((m) => ({
      mission: m.mission,
      exec2024Cp: m.exec_2024,
      lfi2025Cp: m.lfi_2025,
      plf2026Cp: m.plf_2026,
    })),
  };
}

export interface MinistereDestination2025 {
  ministere: string;
  /** CP bruts, tous budgets confondus (BG + BA + CAS + CCF), en €. */
  cpTotal: number;
  /** CP bruts du seul budget général (typebudget = 'BG'), en €. */
  cpBudgetGeneral: number;
}

export interface MinisteresDestination2025 {
  /** Étiquette publiée (« PLF 2025 déposé… — projet, pas la LFI votée »). */
  etiquette: string;
  /** Total CP bruts tous budgets (€) — testé : 823,0 Md€ (BG seul : 594,0). */
  totalCp: number;
  ministeres: MinistereDestination2025[];
}

/**
 * Top ministères (destination) du PLF 2025 en CP BRUTS (S21) — jamais à
 * comparer aux dépenses nettes de S13. Les deux colonnes séparent le budget
 * général des totaux tous budgets (comptes spéciaux inclus) : testé,
 * « Budget et comptes publics » porte 368,84 Md€ tous budgets mais
 * 165,21 Md€ en budget général ; Éducation nationale 87,09 Md€.
 */
export function getMinisteresDestination2025(limite = 10): MinisteresDestination2025 | null {
  const db = getDb();
  if (!db) return null;
  const total = db
    .prepare(
      `SELECT SUM(credit_de_paiement) AS total, MAX(etiquette_montants) AS etiquette
         FROM budget_destination_2025`,
    )
    .get() as { total: number | null; etiquette: string | null } | undefined;
  if (!total || total.total === null) return null;
  const ministeres = db
    .prepare(
      `SELECT libelle_ministere AS ministere,
              SUM(credit_de_paiement) AS cp_total,
              SUM(CASE WHEN typebudget = 'BG' THEN credit_de_paiement ELSE 0 END) AS cp_bg
         FROM budget_destination_2025
        WHERE libelle_ministere IS NOT NULL
        GROUP BY libelle_ministere
        ORDER BY SUM(credit_de_paiement) DESC
        LIMIT ?`,
    )
    .all(limite) as { ministere: string; cp_total: number; cp_bg: number }[];
  return {
    etiquette: total.etiquette ?? "PLF 2025",
    totalCp: total.total,
    ministeres: ministeres.map((m) => ({
      ministere: m.ministere,
      cpTotal: m.cp_total,
      cpBudgetGeneral: m.cp_bg,
    })),
  };
}

export interface BeneficiaireSubventions {
  /** SIREN — `null` dans la source pour certains bénéficiaires (réel). */
  siren: string | null;
  denomination: string;
  /** Somme des versements de l'année (€). */
  montant: number;
  nbVersements: number;
}

export interface SubventionsAssociations {
  /** Année des versements publiés (2023 — décalage structurel de deux ans). */
  annee: number;
  /** Total des versements (€) — testé : 11,77 Md€. */
  total: number;
  /** Nombre de versements — testé : 112 722. */
  nbVersements: number;
  /** Top bénéficiaires par montant décroissant. */
  top: BeneficiaireSubventions[];
}

/**
 * Subventions de l'État aux associations (S23, jaune PLF 2025) : total et
 * top bénéficiaires de la dernière année publiée. Testé (2023) : total
 * 11,77 Md€ / 112 722 versements ; 1er bénéficiaire « ASS INTERNATIONALE DE
 * DEVELOPPEMEN » 1 004,0 M€ (SIREN absent dans la source), puis UNION
 * NATIONALE DES CARPA 597,0 M€ (SIREN 316344233).
 */
export function getSubventionsAssociations(limite = 10): SubventionsAssociations | null {
  const db = getDb();
  if (!db) return null;
  const global = db
    .prepare(
      `SELECT MAX(annee_versement) AS annee, SUM(montant) AS total, COUNT(*) AS nb
         FROM subventions_associations
        WHERE annee_versement = (SELECT MAX(annee_versement) FROM subventions_associations)`,
    )
    .get() as { annee: number | null; total: number | null; nb: number } | undefined;
  if (!global || global.annee === null || global.total === null) return null;
  const top = db
    .prepare(
      `SELECT siren, denomination,
              SUM(montant) AS montant, COUNT(*) AS nb_versements
         FROM subventions_associations
        WHERE annee_versement = ?
        GROUP BY siren, denomination
        ORDER BY SUM(montant) DESC
        LIMIT ?`,
    )
    .all(global.annee, limite) as {
    siren: string | null;
    denomination: string;
    montant: number;
    nb_versements: number;
  }[];
  return {
    annee: global.annee,
    total: global.total,
    nbVersements: global.nb,
    top: top.map((t) => ({
      siren: t.siren,
      denomination: t.denomination,
      montant: t.montant,
      nbVersements: t.nb_versements,
    })),
  };
}
