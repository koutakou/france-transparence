/**
 * Requêtes des agrégats ESA des APU (source S44, Eurostat gov_10a_main,
 * na_item ∈ {TE, TR}), servis en blocs cloisonnés sur /depenses (TE) et
 * /recettes (TR).
 *
 * ────────────────────────────────────────────────────────────────────────
 * CLOISONNEMENT
 * ────────────────────────────────────────────────────────────────────────
 * Ce n'est PAS la source S13 (situations mensuelles DGFiP, budget de
 * l'État, cumul depuis le 1er janvier). Le secteur ESA S13 =
 * administrations publiques (État + Odac + APUL + ASSO).
 * Ce n'est PAS S41 (encours, stock, na_item=GD) ni S42 (déficit
 * Maastricht, na_item=B9). `source_id` = S44, jamais `'S13'`, `'S41'`
 * ni `'S42'`. TE et TR ne sont PAS des indicateurs de Maastricht
 * (Maastricht = GD et B9 seulement).
 *
 * TE = Total des dépenses des administrations publiques (libellé
 * Eurostat FR). TR = Total des recettes des administrations publiques.
 * Ce sont des flux d'année civile, pas un cumul YTD, pas un stock.
 * Unité native MIO_EUR ; Md€ = MIO_EUR ÷ 1000 à la lecture — jamais
 * ÷ 1e9. PC_GDP est le % du PIB, lu à part. On ne recalcule pas
 * B9 = TR − TE (S42 reste le déficit officiel) et on n'additionne
 * pas à S13.
 *
 * Convention « base absente » : `null` tant que la table n'est pas ingérée.
 */
import { getDb, type MetaSource } from "@/lib/db";

export type NaItemAgregatApu = "TE" | "TR";

export type ObservationAgregatApu = {
  annee: number;
  valeur_mio_eur: number;
  valeur_pc_gdp: number;
  statut: string | null;
};

export type AgregatApu = {
  meta: MetaSource;
  naItem: NaItemAgregatApu;
  dernier: ObservationAgregatApu;
  precedent: ObservationAgregatApu | null;
  /** Md€ = MIO_EUR / 1000. */
  montantMd: number;
  /** Variation N/N−1 en %, `null` s'il n'y a pas d'année précédente. */
  deltaPct: number | null;
  serie: ObservationAgregatApu[];
};

/**
 * Périmètre obligatoire de la tuile (DATAVIZ §6) : année, ESA S13,
 * flux annuel (TE|TR), Md€, % du PIB comme fait, drapeau provisoire.
 * L'année et le % viennent de la ligne, jamais d'une constante.
 */
export function perimetreAgregat(
  dernier: ObservationAgregatApu,
  naItem: NaItemAgregatApu,
): string {
  const pc = dernier.valeur_pc_gdp.toLocaleString("fr-FR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  const parts = [
    `année ${dernier.annee}`,
    "ESA S13 = administrations publiques",
    `flux annuel (${naItem})`,
    "Md€",
    `${pc} % du PIB`,
  ];
  if (dernier.statut === "p") parts.push("provisoire (p)");
  return parts.join(" · ");
}

function tablePresente(): boolean {
  const db = getDb();
  if (!db) return false;
  const ligne = db
    .prepare(
      "SELECT count(*) AS n FROM sqlite_master WHERE type = 'table' AND name = 'agregats_apu_esa'",
    )
    .get() as { n: number };
  return ligne.n > 0;
}

/**
 * Dernière année observée + année précédente + série (pour le tableau),
 * pour un `na_item` TE ou TR.
 * `null` si la base n'existe pas ou si S44 n'est pas ingérée.
 */
export function getAgregatApu(naItem: NaItemAgregatApu): AgregatApu | null {
  const db = getDb();
  if (!db || !tablePresente()) return null;

  const meta = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S44'")
    .get() as MetaSource | undefined;
  if (!meta) return null;

  const serie = db
    .prepare(
      `SELECT annee, valeur_mio_eur, valeur_pc_gdp, statut
       FROM agregats_apu_esa
       WHERE na_item = ?
       ORDER BY annee ASC`,
    )
    .all(naItem) as ObservationAgregatApu[];
  if (serie.length === 0) return null;

  const dernier = serie[serie.length - 1];
  const precedent = serie.length >= 2 ? serie[serie.length - 2] : null;
  const montantMd = dernier.valeur_mio_eur / 1000;
  let deltaPct: number | null = null;
  if (precedent && precedent.valeur_mio_eur !== 0) {
    deltaPct =
      ((dernier.valeur_mio_eur - precedent.valeur_mio_eur) /
        Math.abs(precedent.valeur_mio_eur)) *
      100;
  }

  return {
    meta,
    naItem,
    dernier,
    precedent,
    montantMd,
    deltaPct,
    serie,
  };
}
