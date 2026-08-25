/**
 * Requêtes des dépenses des APU par fonction (source S49, Eurostat
 * gov_10a_exp, CFAP / COFOG-99, na_item=TE), servies en bloc cloisonné
 * sur /depenses.
 *
 * ────────────────────────────────────────────────────────────────────────
 * CLOISONNEMENT
 * ────────────────────────────────────────────────────────────────────────
 * Ce n'est PAS la source S13 (situations mensuelles DGFiP, budget de
 * l'État, cumul depuis le 1er janvier). Le secteur ESA S13 =
 * administrations publiques (État + Odac + APUL + ASSO).
 * Ce n'est PAS S44 (totaux TE/TR de gov_10a_main, table distincte) :
 * on ne ventile pas le chiffre S44 et on n'additionne pas les deux.
 * Ce n'est PAS S45 (prestations DREES, tous régimes). `source_id` =
 * S49, jamais `'S13'`, `'S44'` ni `'S45'`. Ce n'est PAS un agrégat
 * Maastricht (Maastricht = GD et B9 seulement).
 *
 * TOTAL + dix divisions GF01–GF10, ordre du producteur — pas un
 * classement par montant. Unité native MIO_EUR ; Md€ = MIO_EUR ÷ 1000
 * à la lecture — jamais ÷ 1e9. PC_GDP est le % du PIB, lu à part, non
 * additif. Pas de groupes GF0101…, pas de par habitant, pas de
 * sous-secteur S.1311.
 *
 * Convention « base absente » : `null` tant que la table n'est pas ingérée.
 */
import { getDb, type MetaSource } from "@/lib/db";

const DIVISIONS = [
  "GF01",
  "GF02",
  "GF03",
  "GF04",
  "GF05",
  "GF06",
  "GF07",
  "GF08",
  "GF09",
  "GF10",
] as const;

export type ObservationCofogApu = {
  annee: number;
  valeur_mio_eur: number;
  valeur_pc_gdp: number;
  statut: string | null;
};

export type DivisionCofogApu = {
  cofog99: string;
  libelle: string;
  valeur_mio_eur: number;
  valeur_pc_gdp: number;
};

export type CofogApu = {
  meta: MetaSource;
  dernier: ObservationCofogApu;
  precedent: ObservationCofogApu | null;
  /** Md€ = MIO_EUR / 1000. */
  montantMd: number;
  /** Variation N/N−1 en %, `null` s'il n'y a pas d'année précédente. */
  deltaPct: number | null;
  serie: ObservationCofogApu[];
  /** TIME max, ordre GF01…GF10 — pas un classement par montant. */
  divisions: DivisionCofogApu[];
};

/**
 * Périmètre obligatoire de la tuile (DATAVIZ §6) : année, ESA S13,
 * flux annuel TE CFAP, Md€, % du PIB, drapeau provisoire.
 */
export function perimetreCofog(dernier: ObservationCofogApu): string {
  const pc = dernier.valeur_pc_gdp.toLocaleString("fr-FR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  const parts = [
    `année ${dernier.annee}`,
    "ESA S13 = administrations publiques",
    "flux annuel (TE, CFAP)",
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
      "SELECT count(*) AS n FROM sqlite_master WHERE type = 'table' AND name = 'cofog_apu_esa'",
    )
    .get() as { n: number };
  return ligne.n > 0;
}

/**
 * TOTAL de la dernière année + année précédente + série + dix divisions
 * du TIME max, dans l'ordre du producteur.
 * `null` si la base n'existe pas ou si S49 n'est pas ingérée.
 */
export function getCofogApu(): CofogApu | null {
  const db = getDb();
  if (!db || !tablePresente()) return null;

  const meta = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S49'")
    .get() as MetaSource | undefined;
  if (!meta) return null;

  const serie = db
    .prepare(
      `SELECT annee, valeur_mio_eur, valeur_pc_gdp, statut
       FROM cofog_apu_esa
       WHERE cofog99 = 'TOTAL'
       ORDER BY annee ASC`,
    )
    .all() as ObservationCofogApu[];
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

  const divisionsBrutes = db
    .prepare(
      `SELECT cofog99, libelle, valeur_mio_eur, valeur_pc_gdp
       FROM cofog_apu_esa
       WHERE annee = ? AND cofog99 != 'TOTAL'`,
    )
    .all(dernier.annee) as DivisionCofogApu[];
  const parCode = new Map(divisionsBrutes.map((d) => [d.cofog99, d]));
  const divisions = DIVISIONS.map((code) => parCode.get(code)).filter(
    (d): d is DivisionCofogApu => d !== undefined,
  );
  if (divisions.length !== 10) return null;

  return {
    meta,
    dernier,
    precedent,
    montantMd,
    deltaPct,
    serie,
    divisions,
  };
}
