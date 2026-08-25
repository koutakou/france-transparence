/**
 * Requêtes des sanctions financières de l'Autorité de la concurrence
 * (source S52, CSV 2009+ joint aux métadonnées).
 *
 * ────────────────────────────────────────────────────────────────────────
 * CLOISONNEMENT
 * ────────────────────────────────────────────────────────────────────────
 * Ce n'est PAS un marché public (S1 / S2 / S9). Ce n'est PAS une recette
 * du budget général (S13 / S46). Ce n'est PAS un recouvrement. Ce n'est
 * PAS S39 (jaune opérateurs, 0 €). `source_id` = S52.
 *
 * Grain du héros = SUM(montant_total) sur `adlc_decisions` (une ligne
 * par id_decision). On ne somme JAMAIS montant_individuel, on ne somme
 * JAMAIS un total répété sur les lignes d'entreprise.
 *
 * Md€ = euros ÷ 1e9.
 *
 * Convention « base absente » : `null` tant que la table n'est pas ingérée.
 */
import { getDb, type MetaSource } from "@/lib/db";

export type DecisionAdlc = {
  id_decision: string;
  date_decision: string;
  montant_total: number;
  sous_titre: string | null;
  url_site: string | null;
};

export type SanctionsAdlc = {
  meta: MetaSource;
  /** Somme des Montant total, une fois par décision. */
  totalEuros: number;
  nbDecisions: number;
  anneeMin: number;
  anneeMax: number;
  /** Décisions de l'année civile max, par date — pas un palmarès. */
  decisionsAnnee: DecisionAdlc[];
};

/**
 * Périmètre obligatoire de la tuile héros (DATAVIZ §6) : dans la tuile,
 * pas plus bas sur la page.
 */
export function perimetreAdlc(nb: number, anneeMin: number, anneeMax: number): string {
  return (
    `${nb} décisions ${anneeMin}–${anneeMax}, une ligne par décision ` +
    `(montant total ADLC) — avant appels et recours ; ce n'est pas un ` +
    `marché public, pas une recette du budget général, pas un recouvrement`
  );
}

function tablePresente(): boolean {
  const db = getDb();
  if (!db) return false;
  const ligne = db
    .prepare(
      "SELECT count(*) AS n FROM sqlite_master WHERE type = 'table' AND name = 'adlc_decisions'",
    )
    .get() as { n: number };
  return ligne.n > 0;
}

function metaS52(): MetaSource | null {
  const db = getDb();
  if (!db || !tablePresente()) return null;
  const meta = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S52'")
    .get() as MetaSource | undefined;
  return meta ?? null;
}

/**
 * Héros S52 + décisions de l'année civile la plus récente.
 * `null` si la base n'existe pas ou si S52 n'est pas ingérée.
 */
export function getSanctionsAdlc(): SanctionsAdlc | null {
  const meta = metaS52();
  const db = getDb();
  if (!meta || !db) return null;

  const totaux = db
    .prepare(
      `SELECT
         count(*) AS n,
         coalesce(sum(montant_total), 0) AS total,
         min(annee) AS annee_min,
         max(annee) AS annee_max
       FROM adlc_decisions`,
    )
    .get() as {
    n: number;
    total: number;
    annee_min: number | null;
    annee_max: number | null;
  };
  if (!totaux.n || totaux.annee_max === null || totaux.annee_min === null) {
    return null;
  }

  const decisionsAnnee = db
    .prepare(
      `SELECT id_decision, date_decision, montant_total, sous_titre, url_site
       FROM adlc_decisions
       WHERE annee = ?
       ORDER BY date_decision ASC, id_decision ASC`,
    )
    .all(totaux.annee_max) as DecisionAdlc[];

  return {
    meta,
    totalEuros: totaux.total,
    nbDecisions: totaux.n,
    anneeMin: totaux.annee_min,
    anneeMax: totaux.annee_max,
    decisionsAnnee,
  };
}
