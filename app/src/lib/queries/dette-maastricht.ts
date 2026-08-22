/**
 * Requêtes de l'encours de dette des APU au sens de Maastricht (source S41,
 * Eurostat gov_10q_ggdebt), servi en bloc cloisonné sur /depenses.
 *
 * ────────────────────────────────────────────────────────────────────────
 * CLOISONNEMENT
 * ────────────────────────────────────────────────────────────────────────
 * Ce n'est PAS la source S13 (situations mensuelles DGFiP, flux de l'État).
 * Le secteur ESA S13 = administrations publiques (État, Odac, APUL, ASSO).
 * `source_id` = S41, jamais `'S13'`.
 *
 * Unité native : MIO_EUR (millions d'euros). Conversion Md€ = MIO_EUR ÷ 1000
 * à la lecture — jamais ÷ 1e9, qui est l'unité des flux S13 (euros).
 *
 * Convention « base absente » : `null` tant que la table n'est pas ingérée.
 */
import { getDb, type MetaSource } from "@/lib/db";

export type ObservationDetteMaastricht = {
  trimestre: string;
  valeur_mio_eur: number;
  statut: string | null;
};

export type DetteMaastricht = {
  meta: MetaSource;
  dernier: ObservationDetteMaastricht;
  precedent: ObservationDetteMaastricht | null;
  /** Md€ = MIO_EUR / 1000, à la lecture. */
  encoursMd: number;
  /** Variation T/T-1 en %, `null` s'il n'y a pas de trimestre précédent. */
  deltaPct: number | null;
};

/** `2026-Q1` → `2026-T1` (libellé français, le code source reste YYYY-Qn). */
export function libelleTrimestre(trimestre: string): string {
  return trimestre.replace("-Q", "-T");
}

/**
 * Périmètre obligatoire de la tuile (DATAVIZ §6) : trimestre, ESA S13,
 * stock consolidé brut, Md€, et le drapeau provisoire s'il est porté.
 */
export function perimetreDette(dernier: ObservationDetteMaastricht): string {
  const parts = [
    `trimestre ${libelleTrimestre(dernier.trimestre)}`,
    "ESA S13 = administrations publiques",
    "stock consolidé brut",
    "Md€",
  ];
  if (dernier.statut === "p") parts.push("provisoire (p)");
  return parts.join(" · ");
}

function tablePresente(): boolean {
  const db = getDb();
  if (!db) return false;
  const ligne = db
    .prepare(
      "SELECT count(*) AS n FROM sqlite_master WHERE type = 'table' AND name = 'dette_apu_maastricht'",
    )
    .get() as { n: number };
  return ligne.n > 0;
}

/**
 * Dernier trimestre observé + trimestre précédent.
 * `null` si la base n'existe pas ou si S41 n'est pas ingérée.
 */
export function getDetteMaastricht(): DetteMaastricht | null {
  const db = getDb();
  if (!db || !tablePresente()) return null;

  const meta = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S41'")
    .get() as MetaSource | undefined;
  if (!meta) return null;

  const lignes = db
    .prepare(
      `SELECT trimestre, valeur_mio_eur, statut
       FROM dette_apu_maastricht
       ORDER BY trimestre DESC
       LIMIT 2`,
    )
    .all() as ObservationDetteMaastricht[];
  if (lignes.length === 0) return null;

  const dernier = lignes[0];
  const precedent = lignes[1] ?? null;
  const encoursMd = dernier.valeur_mio_eur / 1000;
  let deltaPct: number | null = null;
  if (precedent && precedent.valeur_mio_eur !== 0) {
    deltaPct =
      ((dernier.valeur_mio_eur - precedent.valeur_mio_eur) /
        Math.abs(precedent.valeur_mio_eur)) *
      100;
  }

  return { meta, dernier, precedent, encoursMd, deltaPct };
}
