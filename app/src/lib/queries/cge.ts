/**
 * Requêtes du bilan patrimonial de l'État (source S22, CGE DGFiP),
 * servi en bloc cloisonné sur /depenses.
 *
 * ────────────────────────────────────────────────────────────────────────
 * CLOISONNEMENT
 * ────────────────────────────────────────────────────────────────────────
 * Ce n'est PAS la source S13 (situations mensuelles DGFiP, caisse, flux
 * YTD du budget de l'État). C'est la comptabilité générale : droits
 * constatés, stock au 31 décembre, personne morale État.
 * Ce n'est PAS S41 (encours Maastricht APU, GD), ni S42 (B9), ni S44
 * (TE/TR ESA). `source_id` = S22, jamais `'S13'`, `'S41'`, `'S42'`
 * ni `'S44'`.
 *
 * Totaux lus dans la pièce de synthèse officielle (xlsx), jamais
 * sommés depuis les balances compte × programme. Situation nette =
 * TOTAL ACTIF (I) − TOTAL PASSIF hors SN (II). Ce n'est pas « la
 * dette de l'État ». Unité native : euro ; Md€ = euros ÷ 1e9 à la
 * lecture — jamais ÷ 1000 (convention Eurostat MIO_EUR).
 *
 * Convention « base absente » : `null` tant que la table n'est pas ingérée.
 */
import { getDb, type MetaSource } from "@/lib/db";

export type PosteCge =
  | "actif"
  | "passif_hors_sn"
  | "situation_nette"
  | "dettes_financieres"
  | "solde_exercice";

export type LigneCge = {
  annee: number;
  poste: PosteCge;
  valeur_euros: number;
};

export type AnneeCge = {
  annee: number;
  actif: number;
  passifHorsSn: number;
  situationNette: number;
  dettesFinancieres: number;
  soldeExercice: number | null;
};

export type BilanCge = {
  meta: MetaSource;
  dernier: AnneeCge;
  precedent: AnneeCge | null;
  /** Md€ = euros / 1e9, signé. */
  situationNetteMd: number;
  actifMd: number;
  passifHorsSnMd: number;
  /** Variation N/N−1 de la situation nette, relative à |N−1|. */
  deltaPct: number | null;
  serie: AnneeCge[];
};

/**
 * Périmètre obligatoire de la tuile (DATAVIZ §6) : date, CGE, État
 * (pas APU), stock I−II, Md€. Aucun « dette de l'État ».
 */
export function perimetreCge(dernier: AnneeCge): string {
  return [
    `31/12/${dernier.annee}`,
    "comptabilité générale de l'État",
    "stock (I − II)",
    "Md€",
    "publié net",
  ].join(" · ");
}

function tablePresente(): boolean {
  const db = getDb();
  if (!db) return false;
  const ligne = db
    .prepare(
      "SELECT count(*) AS n FROM sqlite_master WHERE type = 'table' AND name = 'cge_bilan_etat'",
    )
    .get() as { n: number };
  return ligne.n > 0;
}

function pivoter(lignes: LigneCge[]): AnneeCge[] {
  const par = new Map<number, Partial<AnneeCge> & { annee: number }>();
  for (const l of lignes) {
    const row = par.get(l.annee) ?? { annee: l.annee };
    if (l.poste === "actif") row.actif = l.valeur_euros;
    else if (l.poste === "passif_hors_sn") row.passifHorsSn = l.valeur_euros;
    else if (l.poste === "situation_nette") row.situationNette = l.valeur_euros;
    else if (l.poste === "dettes_financieres") row.dettesFinancieres = l.valeur_euros;
    else if (l.poste === "solde_exercice") row.soldeExercice = l.valeur_euros;
    par.set(l.annee, row);
  }
  const out: AnneeCge[] = [];
  for (const row of [...par.values()].sort((a, b) => a.annee - b.annee)) {
    if (
      row.actif === undefined ||
      row.passifHorsSn === undefined ||
      row.situationNette === undefined ||
      row.dettesFinancieres === undefined
    ) {
      continue;
    }
    out.push({
      annee: row.annee,
      actif: row.actif,
      passifHorsSn: row.passifHorsSn,
      situationNette: row.situationNette,
      dettesFinancieres: row.dettesFinancieres,
      soldeExercice: row.soldeExercice ?? null,
    });
  }
  return out;
}

/**
 * Dernière année de la pièce de synthèse + précédente + série.
 * `null` si la base n'existe pas ou si S22 n'est pas ingérée.
 */
export function getBilanCge(): BilanCge | null {
  const db = getDb();
  if (!db || !tablePresente()) return null;

  const meta = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S22'")
    .get() as MetaSource | undefined;
  if (!meta) return null;

  const lignes = db
    .prepare(
      `SELECT annee, poste, valeur_euros
       FROM cge_bilan_etat
       ORDER BY annee, poste`,
    )
    .all() as LigneCge[];
  const serie = pivoter(lignes);
  if (serie.length === 0) return null;

  const dernier = serie[serie.length - 1];
  const precedent = serie.length >= 2 ? serie[serie.length - 2] : null;
  let deltaPct: number | null = null;
  if (precedent && precedent.situationNette !== 0) {
    deltaPct =
      ((dernier.situationNette - precedent.situationNette) /
        Math.abs(precedent.situationNette)) *
      100;
  }

  return {
    meta,
    dernier,
    precedent,
    situationNetteMd: dernier.situationNette / 1e9,
    actifMd: dernier.actif / 1e9,
    passifHorsSnMd: dernier.passifHorsSn / 1e9,
    deltaPct,
    serie,
  };
}
