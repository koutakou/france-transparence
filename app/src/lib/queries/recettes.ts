/**
 * Requêtes du module « Recettes de l'État » (/recettes).
 *
 * Source unique : S13 `budget_mensuel` — situations mensuelles budgétaires
 * DGFiP (2013-01 → dernier mois publié, cumuls depuis le 1er janvier et
 * colonnes `*_n1` pour la même date N−1). La table porte NEUF lignes de
 * recettes du budget général, et rien d'autre :
 * - total recettes NETTES (nettes des remboursements et dégrèvements) ;
 * - total recettes fiscales nettes, détaillé en cinq lignes (TVA — part
 *   revenant à l'État seulement —, impôt sur le revenu, impôt sur les
 *   sociétés, TICPE, autres recettes fiscales) ;
 * - total recettes non fiscales, SANS détail publié : aucune décomposition
 *   n'est fabriquée ici ;
 * - fonds de concours et attributions de produits.
 *
 * Valeurs de contrôle (sqlite3 -readonly, 20/08/2026, date_fin_mois =
 * 2026-06-30) : recettes nettes cumulées 184 552 567 623,22 €
 * (N−1 : 177 899 298 257,69 €) ; fiscales nettes 168 482 924 169,73 € ;
 * TVA 50 284 692 223,24 € ; non fiscales 16 069 643 453,49 € ; fonds de
 * concours 3 138 207 686,54 €. Années complètes : cumul au 31/12/2025 =
 * 380,39 Md€ de recettes nettes (2013 : 297,72 Md€).
 *
 * Chaque fonction renvoie `null` tant que la base n'est pas construite
 * (`getDb()` null) — la page affiche alors son message honnête. Une valeur
 * absente reste `null`, jamais 0.
 */
import { getDb, type MetaSource } from "@/lib/db";

/* Lignes de recettes de budget_mensuel (identifiants stables du pipeline). */
const LIGNE_TOTAL_NETTES =
  "recettes/budget-general/total-recettes-nettes-du-budget-general";
const LIGNE_FISCALES = "recettes/budget-general/total-recettes-fiscales";
const LIGNE_NON_FISCALES = "recettes/budget-general/total-recettes-non-fiscales";
const LIGNE_FONDS_CONCOURS =
  "recettes/budget-general/fonds-de-concours-et-attribution-de-produits";

/** Les cinq lignes de détail des recettes fiscales nettes (niveau 3). */
const LIGNES_GRANDS_IMPOTS = [
  "recettes/budget-general/taxe-sur-la-valeur-ajoutee",
  "recettes/budget-general/impot-sur-le-revenu",
  "recettes/budget-general/impot-sur-les-societes",
  "recettes/budget-general/taxe-interieure-de-consommation-sur-les-produits-energetiques",
  "recettes/budget-general/autres-recettes-fiscales",
];

/** Ligne de fraîcheur S13 (badge de datation du module). */
export function getSourceRecettes(): MetaSource | null {
  const db = getDb();
  if (!db) return null;
  const ligne = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S13'")
    .get() as MetaSource | undefined;
  return ligne ?? null;
}

export interface KpisRecettes {
  /** Dernier mois publié (ISO, ex. « 2026-06-30 »). */
  dateFinMois: string;
  annee: number;
  /** Numéro du dernier mois publié (1–12) — < 12 ⇒ année en cours, provisoire. */
  mois: number;
  /** Cumul des recettes nettes du budget général depuis le 1er janvier (€). */
  totalNettes: number;
  totalNettesN1: number | null;
  /** Cumul des recettes fiscales nettes (€). */
  fiscalesNettes: number | null;
  fiscalesNettesN1: number | null;
  /** Cumul des recettes non fiscales (€) — la source n'en publie aucun détail. */
  nonFiscales: number | null;
  nonFiscalesN1: number | null;
  /** Cumul des fonds de concours et attributions de produits (€). */
  fondsConcours: number | null;
  fondsConcoursN1: number | null;
}

interface LigneMensuelleRow {
  ligne_id: string;
  date_fin_mois: string;
  annee: number;
  mois: number;
  montant_cumul: number;
  montant_cumul_n1: number | null;
}

/**
 * KPI du bandeau : les quatre agrégats de recettes au dernier mois publié.
 * Testé : au 2026-06-30, nettes 184 552 567 623,22 € / fiscales nettes
 * 168 482 924 169,73 € / non fiscales 16 069 643 453,49 € / fonds de
 * concours 3 138 207 686,54 €.
 */
export function getKpisRecettes(): KpisRecettes | null {
  const db = getDb();
  if (!db) return null;
  const lignes = db
    .prepare(
      `SELECT ligne_id, date_fin_mois, annee, mois, montant_cumul, montant_cumul_n1
         FROM budget_mensuel
        WHERE date_fin_mois = (SELECT MAX(date_fin_mois) FROM budget_mensuel)
          AND ligne_id IN (?, ?, ?, ?)`,
    )
    .all(
      LIGNE_TOTAL_NETTES,
      LIGNE_FISCALES,
      LIGNE_NON_FISCALES,
      LIGNE_FONDS_CONCOURS,
    ) as LigneMensuelleRow[];
  const total = lignes.find((l) => l.ligne_id === LIGNE_TOTAL_NETTES);
  if (!total) return null;
  const fiscales = lignes.find((l) => l.ligne_id === LIGNE_FISCALES);
  const nonFiscales = lignes.find((l) => l.ligne_id === LIGNE_NON_FISCALES);
  const fonds = lignes.find((l) => l.ligne_id === LIGNE_FONDS_CONCOURS);
  return {
    dateFinMois: total.date_fin_mois,
    annee: total.annee,
    mois: total.mois,
    totalNettes: total.montant_cumul,
    totalNettesN1: total.montant_cumul_n1,
    fiscalesNettes: fiscales?.montant_cumul ?? null,
    fiscalesNettesN1: fiscales?.montant_cumul_n1 ?? null,
    nonFiscales: nonFiscales?.montant_cumul ?? null,
    nonFiscalesN1: nonFiscales?.montant_cumul_n1 ?? null,
    fondsConcours: fonds?.montant_cumul ?? null,
    fondsConcoursN1: fonds?.montant_cumul_n1 ?? null,
  };
}

export interface SerieAnnuelleRecettes {
  annee: number;
  /** 12 positions (janvier → décembre), en euros ; `null` = mois non publié. */
  valeurs: (number | null)[];
}

/**
 * Série mensuelle des recettes nettes CUMULÉES du budget général, pour les
 * `nbAnnees` dernières années (la plus récente d'abord — série 1 de la
 * page). Testé : juin 2026 = 184,55 Md€, juin 2025 = 177,90 Md€ ; 2026
 * s'arrête au mois 6, les positions suivantes restent `null` (trou de
 * donnée, jamais un zéro).
 */
export function getSerieRecettesNettes(nbAnnees = 3): SerieAnnuelleRecettes[] | null {
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
    .all(LIGNE_TOTAL_NETTES, nbAnnees) as {
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

export interface AnneeRecettes {
  annee: number;
  /** Recettes nettes du budget général, cumul au 31 décembre (€). */
  totalNettes: number | null;
  /** Recettes fiscales nettes, cumul au 31 décembre (€). */
  fiscalesNettes: number | null;
}

export interface SeriesLonguesRecettes {
  /** Années COMPLÈTES (douze mois publiés), croissantes — testé : 2013–2025. */
  annees: AnneeRecettes[];
  /** Année en cours si elle est incomplète (< 12 mois publiés), sinon null. */
  enCours: {
    annee: number;
    /** Dernier mois publié de l'année en cours (ISO). */
    dateFinMois: string;
    totalNettes: number | null;
  } | null;
}

/**
 * Séries longues : recettes nettes et recettes fiscales nettes de chaque
 * année COMPLÈTE (cumul au 31 décembre), depuis le début de la série S13
 * (2013). L'année en cours, incomplète, n'est jamais mêlée aux années
 * pleines : elle est renvoyée à part, datée de son dernier mois publié.
 * Testé : 2013 = 297,72 Md€ nets, 2025 = 380,39 Md€ ; en cours 2026 =
 * 184,55 Md€ au 30/06.
 */
export function getSeriesLonguesRecettes(): SeriesLonguesRecettes | null {
  const db = getDb();
  if (!db) return null;
  const decembre = db
    .prepare(
      `SELECT ligne_id, annee, montant_cumul
         FROM budget_mensuel
        WHERE mois = 12 AND ligne_id IN (?, ?)
        ORDER BY annee ASC`,
    )
    .all(LIGNE_TOTAL_NETTES, LIGNE_FISCALES) as {
    ligne_id: string;
    annee: number;
    montant_cumul: number;
  }[];
  if (decembre.length === 0) return null;
  const parAnnee = new Map<number, AnneeRecettes>();
  for (const l of decembre) {
    const a =
      parAnnee.get(l.annee) ??
      ({ annee: l.annee, totalNettes: null, fiscalesNettes: null } as AnneeRecettes);
    if (l.ligne_id === LIGNE_TOTAL_NETTES) a.totalNettes = l.montant_cumul;
    else a.fiscalesNettes = l.montant_cumul;
    parAnnee.set(l.annee, a);
  }
  const annees = [...parAnnee.values()].sort((a, b) => a.annee - b.annee);

  const dernier = db
    .prepare(
      `SELECT annee, mois, date_fin_mois, montant_cumul
         FROM budget_mensuel
        WHERE ligne_id = ?
          AND date_fin_mois = (SELECT MAX(date_fin_mois) FROM budget_mensuel)`,
    )
    .get(LIGNE_TOTAL_NETTES) as
    | { annee: number; mois: number; date_fin_mois: string; montant_cumul: number }
    | undefined;
  const enCours =
    dernier && dernier.mois < 12
      ? {
          annee: dernier.annee,
          dateFinMois: dernier.date_fin_mois,
          totalNettes: dernier.montant_cumul,
        }
      : null;
  return { annees, enCours };
}

export interface GrandImpot {
  /** Libellé publié par la DGFiP (« Taxe sur la valeur ajoutée »…). */
  ligne: string;
  /** Identifiant stable (pour repérer la TVA et lui accoler sa mention). */
  ligneId: string;
  /** Cumul depuis le 1er janvier au dernier mois publié (€). */
  montantCumul: number;
  /** Même cumul à la même date N−1 (€), si publié. */
  montantCumulN1: number | null;
}

export interface RecettesFiscalesDetail {
  dateFinMois: string;
  annee: number;
  /** Total recettes fiscales nettes (€), si publié. */
  totalFiscales: number | null;
  /** Les cinq lignes de détail, montant décroissant. */
  impots: GrandImpot[];
}

/** La ligne TVA — part revenant au budget général de l'État seulement. */
export const LIGNE_ID_TVA = "recettes/budget-general/taxe-sur-la-valeur-ajoutee";

/**
 * Décomposition des recettes fiscales nettes par grand impôt au dernier
 * mois publié — les cinq seules lignes que publie la source, aucune n'est
 * inventée. Testé au 2026-06-30 : TVA (part État) 50,28 Md€, IR 44,49,
 * autres recettes fiscales 35,88, IS 30,40, TICPE 7,43.
 */
export function getRecettesFiscalesDetail(): RecettesFiscalesDetail | null {
  const db = getDb();
  if (!db) return null;
  const jetons = LIGNES_GRANDS_IMPOTS.map(() => "?").join(", ");
  const lignes = db
    .prepare(
      `SELECT ligne_id, ligne, date_fin_mois, annee, montant_cumul, montant_cumul_n1
         FROM budget_mensuel
        WHERE date_fin_mois = (SELECT MAX(date_fin_mois) FROM budget_mensuel)
          AND ligne_id IN (${jetons}, ?)
        ORDER BY montant_cumul DESC`,
    )
    .all(...LIGNES_GRANDS_IMPOTS, LIGNE_FISCALES) as (LigneMensuelleRow & {
    ligne: string;
  })[];
  const impots = lignes.filter((l) => l.ligne_id !== LIGNE_FISCALES);
  if (impots.length === 0) return null;
  const total = lignes.find((l) => l.ligne_id === LIGNE_FISCALES);
  return {
    dateFinMois: impots[0].date_fin_mois,
    annee: impots[0].annee,
    totalFiscales: total?.montant_cumul ?? null,
    impots: impots.map((l) => ({
      ligne: l.ligne,
      ligneId: l.ligne_id,
      montantCumul: l.montant_cumul,
      montantCumulN1: l.montant_cumul_n1,
    })),
  };
}
