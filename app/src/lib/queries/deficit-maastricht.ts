/**
 * Requêtes du déficit public des APU au sens de Maastricht (source S42,
 * Eurostat gov_10dd_edpt1, na_item=B9), servi en bloc cloisonné sur /depenses.
 *
 * ────────────────────────────────────────────────────────────────────────
 * CLOISONNEMENT
 * ────────────────────────────────────────────────────────────────────────
 * Ce n'est PAS la source S13 (situations mensuelles DGFiP, solde du budget
 * de l'État). Le secteur ESA S13 = administrations publiques.
 * Ce n'est PAS S41 (encours, stock, na_item=GD, trimestriel).
 * `source_id` = S42, jamais `'S13'` ni `'S41'`.
 *
 * B9 est signé : négatif = besoin de financement (déficit), positif =
 * capacité (excédent). Unité native MIO_EUR ; Md€ = MIO_EUR ÷ 1000 à la
 * lecture — jamais ÷ 1e9. PC_GDP est le % du PIB, jamais comparé à 3 %.
 *
 * Convention « base absente » : `null` tant que la table n'est pas ingérée.
 */
import { getDb, type MetaSource } from "@/lib/db";

export type ObservationDeficitMaastricht = {
  annee: number;
  valeur_mio_eur: number;
  valeur_pc_gdp: number;
  statut: string | null;
};

export type DeficitMaastricht = {
  meta: MetaSource;
  dernier: ObservationDeficitMaastricht;
  precedent: ObservationDeficitMaastricht | null;
  /** Md€ = MIO_EUR / 1000, signé (négatif = déficit). */
  b9Md: number;
  /** |B9| en Md€ quand B9 < 0, sinon 0 — pour l'affichage « déficit ». */
  deficitMd: number;
  estDeficit: boolean;
  /** Variation N/N−1 en %, `null` s'il n'y a pas d'année précédente. */
  deltaPct: number | null;
  serie: ObservationDeficitMaastricht[];
};

/**
 * Périmètre obligatoire de la tuile (DATAVIZ §6) : année, ESA S13,
 * flux annuel B9, Md€, % du PIB comme fait, drapeau provisoire.
 * Aucune comparaison au seuil de 3 %.
 */
export function perimetreDeficit(dernier: ObservationDeficitMaastricht): string {
  const signe = dernier.valeur_pc_gdp < 0 ? "−" : dernier.valeur_pc_gdp > 0 ? "+" : "";
  const pc = Math.abs(dernier.valeur_pc_gdp).toLocaleString("fr-FR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  const parts = [
    `année ${dernier.annee}`,
    "ESA S13 = administrations publiques",
    "flux annuel (B9)",
    "Md€",
    `${signe}${pc} % du PIB`,
  ];
  if (dernier.statut === "p") parts.push("provisoire (p)");
  return parts.join(" · ");
}

function tablePresente(): boolean {
  const db = getDb();
  if (!db) return false;
  const ligne = db
    .prepare(
      "SELECT count(*) AS n FROM sqlite_master WHERE type = 'table' AND name = 'deficit_apu_maastricht'",
    )
    .get() as { n: number };
  return ligne.n > 0;
}

/**
 * Dernière année observée + année précédente + série (pour le tableau).
 * `null` si la base n'existe pas ou si S42 n'est pas ingérée.
 */
export function getDeficitMaastricht(): DeficitMaastricht | null {
  const db = getDb();
  if (!db || !tablePresente()) return null;

  const meta = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S42'")
    .get() as MetaSource | undefined;
  if (!meta) return null;

  const serie = db
    .prepare(
      `SELECT annee, valeur_mio_eur, valeur_pc_gdp, statut
       FROM deficit_apu_maastricht
       ORDER BY annee ASC`,
    )
    .all() as ObservationDeficitMaastricht[];
  if (serie.length === 0) return null;

  const dernier = serie[serie.length - 1];
  const precedent = serie.length >= 2 ? serie[serie.length - 2] : null;
  const b9Md = dernier.valeur_mio_eur / 1000;
  const estDeficit = dernier.valeur_mio_eur < 0;
  const deficitMd = estDeficit ? -b9Md : 0;
  // Delta sur la grandeur affichée (le déficit = −B9), pas sur B9 signé :
  // un B9 qui remonte de −169 à −152 Md€ réduit le déficit, delta négatif.
  let deltaPct: number | null = null;
  if (
    precedent &&
    dernier.valeur_mio_eur < 0 &&
    precedent.valeur_mio_eur < 0
  ) {
    const defN = -dernier.valeur_mio_eur;
    const defN1 = -precedent.valeur_mio_eur;
    deltaPct = ((defN - defN1) / defN1) * 100;
  }

  return {
    meta,
    dernier,
    precedent,
    b9Md,
    deficitMd,
    estDeficit,
    deltaPct,
    serie,
  };
}
