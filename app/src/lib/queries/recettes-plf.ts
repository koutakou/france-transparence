/**
 * Requêtes des recettes du budget général au PLF (source S46, État A).
 *
 * ────────────────────────────────────────────────────────────────────────
 * CLOISONNEMENT
 * ────────────────────────────────────────────────────────────────────────
 * Ce n'est PAS la source S13 (situations mensuelles DGFiP, recettes
 * NETTES, cumul depuis le 1er janvier, exécution). Les montants S46
 * sont ceux du Projet de loi de finances, recettes BRUTES de l'État A,
 * année civile du PLF. `source_id` = S46, jamais `'S13'`. On n'additionne
 * pas, on ne calcule pas de nettes, on ne présente pas un total fiscal
 * de 500 Md€ comme les 380 Md€ nettes de S13.
 *
 * Ce que la page affiche : le détail des recettes **non fiscales**
 * (56 lignes au 24/08/2026) — c'est le trou que S13 laisse en un seul
 * total — et, parmi elles, les trois lignes de participations /
 * dividendes (codes 2110, 2116, 2199). Le reste du jeu (fiscales
 * brutes, PSR) est ingéré et catalogue, pas additionné à S13.
 *
 * Unité native : euros. Md€ = euros ÷ 1e9 à la lecture, jamais ÷ 1000.
 *
 * Convention « base absente » : `null` tant que la table n'est pas ingérée.
 */
import { getDb, type MetaSource } from "@/lib/db";

const CODES_PARTICIPATIONS = [2110, 2116, 2199] as const;

export const ETIQUETTE_PLF = (
  "PLF 2025 déposé en octobre 2024 — projet, pas la LFI 2025 votée, pas l'exécution (S13)"
);

export type LigneRecettePlf = {
  code: number;
  libelle: string;
  montantEuros: number;
};

export type RecettesPlfNonFiscales = {
  meta: MetaSource;
  annee: number;
  etiquette: string;
  totalEuros: number;
  /** Md€ = euros / 1e9. */
  totalMd: number;
  lignes: LigneRecettePlf[];
  participations: {
    totalEuros: number;
    totalMd: number;
    lignes: LigneRecettePlf[];
  };
};

export function perimetreNonFiscales(annee: number): string {
  return (
    `PLF ${annee} · projet · budget général · État A · recettes brutes · ` +
    `pas l'exécution S13 · pas la LFI votée`
  );
}

export function perimetreParticipations(annee: number): string {
  return (
    `lignes 2110, 2116 et 2199 du PLF ${annee} · projet · ` +
    `pas le rapport de l'Agence des participations de l'État`
  );
}

function tablePresente(): boolean {
  const db = getDb();
  if (!db) return false;
  const ligne = db
    .prepare(
      "SELECT count(*) AS n FROM sqlite_master WHERE type = 'table' AND name = 'recettes_plf_etat_a'",
    )
    .get() as { n: number } | undefined;
  return (ligne?.n ?? 0) > 0;
}

export function getSourceRecettesPlf(): MetaSource | null {
  const db = getDb();
  if (!db) return null;
  const ligne = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S46'")
    .get() as MetaSource | undefined;
  return ligne ?? null;
}

export function getRecettesPlfNonFiscales(): RecettesPlfNonFiscales | null {
  const db = getDb();
  if (!db || !tablePresente()) return null;
  const meta = getSourceRecettesPlf();
  if (!meta) return null;
  const anneeRow = db
    .prepare("SELECT MAX(annee) AS annee FROM recettes_plf_etat_a")
    .get() as { annee: number | null } | undefined;
  const annee = anneeRow?.annee;
  if (annee == null) return null;
  const lignes = db
    .prepare(
      `SELECT code, libelle, montant_euros AS montantEuros
         FROM recettes_plf_etat_a
        WHERE annee = ? AND type_recette = 'non_fiscales'
        ORDER BY montant_euros DESC, code ASC`,
    )
    .all(annee) as LigneRecettePlf[];
  if (lignes.length === 0) return null;
  const totalEuros = lignes.reduce((s, l) => s + l.montantEuros, 0);
  const participationsLignes = CODES_PARTICIPATIONS.map((code) =>
    lignes.find((l) => l.code === code),
  ).filter((l): l is LigneRecettePlf => l != null);
  if (participationsLignes.length !== CODES_PARTICIPATIONS.length) return null;
  const participationsTotal = participationsLignes.reduce(
    (s, l) => s + l.montantEuros,
    0,
  );
  return {
    meta,
    annee,
    etiquette: ETIQUETTE_PLF,
    totalEuros,
    totalMd: totalEuros / 1e9,
    lignes,
    participations: {
      totalEuros: participationsTotal,
      totalMd: participationsTotal / 1e9,
      lignes: participationsLignes,
    },
  };
}
