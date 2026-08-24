/**
 * Requêtes IRCOM (source S47, DGFiP / DESF).
 *
 * ────────────────────────────────────────────────────────────────────────
 * CLOISONNEMENT
 * ────────────────────────────────────────────────────────────────────────
 * Ce n'est PAS la source S13 (situations mensuelles DGFiP, Impôt sur le
 * revenu net de caisse du budget général, cumul depuis le 1er janvier).
 * Les montants S47 sont l'impôt net SUR RÔLE des foyers fiscaux, pour
 * l'année des REVENUS, par commune de résidence. `source_id` = S47,
 * jamais `'S13'`. On n'additionne pas. On ne rapproche pas les totaux.
 *
 * Unité native IRCOM : milliers d'euros. Stockage : euros (× 1000).
 * Md€ = euros / 1e9 à la lecture, jamais ÷ 1000.
 *
 * n.c. = secret statistique : le total national est la somme des
 * communes dont l'impôt net n'est pas n.c. — ce n'est pas un total
 * officiel France du fichier national.xls (OLE, non lu).
 *
 * Convention « base absente » : `null` tant que la table n'est pas ingérée.
 */
import { getDb, type MetaSource } from "@/lib/db";

export const ETIQUETTE_IRCOM =
  "impôt net sur rôle, année des revenus, par commune de résidence — pas l'IR de caisse S13, pas le PFU";

export type LigneIrcomDep = {
  dep: string;
  nom: string;
  nCommunes: number;
  nCommunesNc: number;
  nFoyers: number;
  impotEuros: number;
};

export type IrcomNational = {
  meta: MetaSource;
  annee: number;
  etiquette: string;
  nCommunes: number;
  nCommunesNc: number;
  nFoyers: number;
  impotEuros: number;
  impotMd: number;
  departements: LigneIrcomDep[];
};

export function perimetreIrcom(annee: number): string {
  return (
    `revenus ${annee} · IRCOM · impôt net sur rôle · ` +
    `somme des communes publiées, hors n.c. · pas l'exécution S13`
  );
}

export function perimetreFoyersIrcom(annee: number): string {
  return (
    `foyers fiscaux IRCOM, revenus ${annee} · une déclaration = un foyer · ` +
    `somme des communes publiées, hors n.c.`
  );
}

function tablePresente(): boolean {
  const db = getDb();
  if (!db) return false;
  const ligne = db
    .prepare(
      "SELECT count(*) AS n FROM sqlite_master WHERE type = 'table' AND name = 'ircom_national'",
    )
    .get() as { n: number } | undefined;
  return (ligne?.n ?? 0) > 0;
}

export function getSourceIrcom(): MetaSource | null {
  const db = getDb();
  if (!db) return null;
  return (
    (db
      .prepare("SELECT * FROM meta_sources WHERE source_id = 'S47'")
      .get() as MetaSource | undefined) ?? null
  );
}

export function getIrcom(): IrcomNational | null {
  const db = getDb();
  if (!db || !tablePresente()) return null;
  const meta = getSourceIrcom();
  if (!meta) return null;
  const nat = db
    .prepare(
      `SELECT annee, n_communes, n_communes_nc, n_foyers, impot_net_euros
       FROM ircom_national
       ORDER BY annee DESC
       LIMIT 1`,
    )
    .get() as
    | {
        annee: number;
        n_communes: number;
        n_communes_nc: number;
        n_foyers: number;
        impot_net_euros: number;
      }
    | undefined;
  if (!nat) return null;
  const deps = db
    .prepare(
      `SELECT d.dep_carte AS dep,
              COALESCE(r.nom, d.dep_carte) AS nom,
              d.n_communes AS nCommunes,
              d.n_communes_nc AS nCommunesNc,
              d.n_foyers AS nFoyers,
              d.impot_net_euros AS impotEuros
       FROM ircom_departements d
       LEFT JOIN ref_departements r ON r.code = d.dep_carte
       WHERE d.annee = ?
       ORDER BY d.impot_net_euros DESC`,
    )
    .all(nat.annee) as LigneIrcomDep[];
  return {
    meta,
    annee: nat.annee,
    etiquette: ETIQUETTE_IRCOM,
    nCommunes: nat.n_communes,
    nCommunesNc: nat.n_communes_nc,
    nFoyers: nat.n_foyers,
    impotEuros: nat.impot_net_euros,
    impotMd: nat.impot_net_euros / 1e9,
    departements: deps,
  };
}
