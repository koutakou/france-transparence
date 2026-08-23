/**
 * Requêtes des prestations de protection sociale (source S45, DREES,
 * comptes de la protection sociale), servies en bloc cloisonné sur
 * /depenses.
 *
 * ────────────────────────────────────────────────────────────────────────
 * CLOISONNEMENT
 * ────────────────────────────────────────────────────────────────────────
 * Ce n'est PAS la source S13 (situations mensuelles DGFiP, budget de
 * l'État, cumul depuis le 1er janvier). Ce n'est PAS S41 (encours,
 * stock, na_item=GD), ni S42 (déficit Maastricht, na_item=B9), ni
 * S44 (TE/TR ESA), ni S22 (CGE, stock patrimonial de l'État).
 * `source_id` = S45, jamais `'S13'`, `'S41'`, `'S42'`, `'S44'` ni
 * `'S22'`. Ce n'est PAS la LFSS.
 *
 * Flux annuel des PRESTATIONS (E11), tous régimes (si_code S1), pas
 * les recettes, pas les frais de gestion. Le régime général (S13141)
 * est un régime parmi d'autres : S13142 existe à côté — on n'invente
 * pas une « sécurité sociale » = S13141+S13142.
 *
 * Unité native : million d'euros (`val_mio_eur`). Md€ = million ÷ 1000
 * à la lecture — jamais ÷ 1e9. Pas de % du PIB (absent de ce jeu),
 * pas de par habitant.
 *
 * Convention « base absente » : `null` tant que la table n'est pas ingérée.
 */
import { getDb, type MetaSource } from "@/lib/db";

const CODES_RISQUE = ["E11-1", "E11-2", "E11-3", "E11-4", "E11-5", "E11-6"] as const;
const CODE_REGIME_GENERAL = "S13141";

export type ObservationProtectionSociale = {
  annee: number;
  val_mio_eur: number;
};

export type LigneProtectionSociale = {
  code: string;
  libelle: string;
  val_mio_eur: number;
};

export type RegimeGeneral = {
  code: string;
  libelle: string;
  /** Md€ = val_mio_eur / 1000. */
  montantMd: number;
};

export type ProtectionSociale = {
  meta: MetaSource;
  dernier: ObservationProtectionSociale;
  precedent: ObservationProtectionSociale | null;
  /** Md€ = million d'euros / 1000. */
  montantMd: number;
  /** Variation N/N−1 en %, `null` s'il n'y a pas d'année précédente. */
  deltaPct: number | null;
  serie: ObservationProtectionSociale[];
  /** TIME max, ordre officiel E11-1 … E11-6 — pas un classement par montant. */
  risques: LigneProtectionSociale[];
  regimeGeneral: RegimeGeneral;
  /** TIME max, ordre des codes producteur — pas un classement par montant. */
  regimes: LigneProtectionSociale[];
};

/**
 * Périmètre obligatoire de la tuile (DATAVIZ §6) : année, tous régimes,
 * flux annuel des prestations, Md€. Pas de % du PIB.
 */
export function perimetreTotal(dernier: ObservationProtectionSociale): string {
  return [
    `année ${dernier.annee}`,
    "tous régimes",
    "flux annuel des prestations",
    "Md€",
  ].join(" · ");
}

/**
 * Périmètre du régime général : un régime parmi d'autres, pas
 * l'ensemble de la protection sociale.
 */
export function perimetreRegimeGeneral(annee: number): string {
  return [
    `année ${annee}`,
    "S13141",
    "régime général",
    "pas l'ensemble de la protection sociale",
    "Md€",
  ].join(" · ");
}

function tablePresente(): boolean {
  const db = getDb();
  if (!db) return false;
  const ligne = db
    .prepare(
      "SELECT count(*) AS n FROM sqlite_master WHERE type = 'table' AND name = 'protection_sociale_prestations'",
    )
    .get() as { n: number };
  return ligne.n > 0;
}

/**
 * Dernière année observée + année précédente + série des totaux,
 * risques et régimes du TIME max.
 * `null` si la base n'existe pas ou si S45 n'est pas ingérée.
 */
export function getProtectionSociale(): ProtectionSociale | null {
  const db = getDb();
  if (!db || !tablePresente()) return null;

  const meta = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S45'")
    .get() as MetaSource | undefined;
  if (!meta) return null;

  const serie = db
    .prepare(
      `SELECT annee, val_mio_eur
       FROM protection_sociale_prestations
       WHERE grain = 'total' AND code = 'S1'
       ORDER BY annee ASC`,
    )
    .all() as ObservationProtectionSociale[];
  if (serie.length === 0) return null;

  const dernier = serie[serie.length - 1];
  const precedent = serie.length >= 2 ? serie[serie.length - 2] : null;
  const montantMd = dernier.val_mio_eur / 1000;
  let deltaPct: number | null = null;
  if (precedent && precedent.val_mio_eur !== 0) {
    deltaPct =
      ((dernier.val_mio_eur - precedent.val_mio_eur) /
        Math.abs(precedent.val_mio_eur)) *
      100;
  }

  const risquesBruts = db
    .prepare(
      `SELECT code, libelle, val_mio_eur
       FROM protection_sociale_prestations
       WHERE annee = ? AND grain = 'risque'`,
    )
    .all(dernier.annee) as LigneProtectionSociale[];
  const parCode = new Map(risquesBruts.map((r) => [r.code, r]));
  const risques = CODES_RISQUE.flatMap((code) => {
    const ligne = parCode.get(code);
    return ligne ? [ligne] : [];
  });

  const regimes = db
    .prepare(
      `SELECT code, libelle, val_mio_eur
       FROM protection_sociale_prestations
       WHERE annee = ? AND grain = 'regime'
       ORDER BY code`,
    )
    .all(dernier.annee) as LigneProtectionSociale[];

  const rg = regimes.find((r) => r.code === CODE_REGIME_GENERAL);
  if (!rg) return null;

  return {
    meta,
    dernier,
    precedent,
    montantMd,
    deltaPct,
    serie,
    risques,
    regimeGeneral: {
      code: rg.code,
      libelle: rg.libelle,
      montantMd: rg.val_mio_eur / 1000,
    },
    regimes,
  };
}
