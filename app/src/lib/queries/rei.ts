/**
 * Requêtes REI (source S48, DGFiP / DESF).
 *
 * ────────────────────────────────────────────────────────────────────────
 * CLOISONNEMENT
 * ────────────────────────────────────────────────────────────────────────
 * Ce n'est PAS la source S16 (comptes OFGL, agrégat comptable
 * « Impôts locaux » du budget principal des communes). Ce n'est PAS
 * S13 (caisse du budget général) ni S47 (IR net sur rôle, année des
 * revenus). Les montants S48 sont les impositions primitives du rôle
 * général, année d'IMPOSITION, par taxe et par collectivité
 * bénéficiaire. `source_id` = S48, jamais `'S16'` ni `'S13'` ni
 * `'S47'`. On n'additionne pas.
 *
 * Unité native REI : euros. Md€ = euros / 1e9 à la lecture, jamais
 * ÷ 1000. Cellule vide = secret statistique, pas un zéro.
 *
 * Convention « base absente » : `null` tant que la table n'est pas
 * ingérée.
 */
import { getDb, type MetaSource } from "@/lib/db";

export const ETIQUETTE_REI =
  "impositions primitives du rôle général, année d'imposition — pas les comptes OFGL, pas l'IRCOM, pas la caisse de l'État";

export type LigneReiDep = {
  dep: string;
  nom: string;
  nCommunes: number;
  nTfpbNc: number;
  tfpb: number;
};

export type ReiTaxe = { id: string; libelle: string; euros: number };

export type ReiNational = {
  meta: MetaSource;
  annee: number;
  etiquette: string;
  nCommunes: number;
  nTfpbNc: number;
  tfpb: number;
  tfpbMd: number;
  teom: number;
  cfe: number;
  ths: number;
  thlv: number;
  tfpnb: number;
  tascom: number;
  ifer: number;
  additionnelles: number;
  totalFdl: number;
  taxes: ReiTaxe[];
  departements: LigneReiDep[];
};

export function perimetreTfpb(annee: number): string {
  return (
    `imposition ${annee} · REI · TFPB · rôle général · ` +
    `somme des communes publiées, hors occultées · ` +
    `hors taxes annexes et hors frais d'État · pas les comptes OFGL`
  );
}

export function perimetreFdl(annee: number): string {
  return (
    `imposition ${annee} · REI · rôle général, impositions primitives · ` +
    `TFPB + TFPNB + THS + THLV + CFE + TEOM (F13, dont part incitative) + TASCOM + IFER + ` +
    `TSE + GEMAPI + TASA + TAFNB + TSC · hors compensations TVA · ` +
    `hors chambres · pas S16`
  );
}

function tablePresente(): boolean {
  const db = getDb();
  if (!db) return false;
  const ligne = db
    .prepare(
      "SELECT count(*) AS n FROM sqlite_master WHERE type = 'table' AND name = 'rei_national'",
    )
    .get() as { n: number } | undefined;
  return (ligne?.n ?? 0) > 0;
}

export function getSourceRei(): MetaSource | null {
  const db = getDb();
  if (!db) return null;
  return (
    (db
      .prepare("SELECT * FROM meta_sources WHERE source_id = 'S48'")
      .get() as MetaSource | undefined) ?? null
  );
}

export function getRei(): ReiNational | null {
  const db = getDb();
  if (!db || !tablePresente()) return null;
  const meta = getSourceRei();
  if (!meta) return null;
  const nat = db
    .prepare(
      `SELECT annee, n_communes, n_tfpb_nc, tfpb, tfpnb, ths, thlv,
              cfe, teom, teomi, tascom, ifer_local, ifer_reg,
              tse, gemapi, tasa, tafnb, tsc
       FROM rei_national
       ORDER BY annee DESC
       LIMIT 1`,
    )
    .get() as
    | {
        annee: number;
        n_communes: number;
        n_tfpb_nc: number;
        tfpb: number;
        tfpnb: number;
        ths: number;
        thlv: number;
        cfe: number;
        teom: number;
        teomi: number;
        tascom: number;
        ifer_local: number;
        ifer_reg: number;
        tse: number;
        gemapi: number;
        tasa: number;
        tafnb: number;
        tsc: number;
      }
    | undefined;
  if (!nat) return null;
  const ifer = nat.ifer_local + nat.ifer_reg;
  // TEOMI (TIEOM*) est une PART de F13 (CGI 1522 bis), pas une taxe
  // en plus — ne pas l'ajouter ici (même piège que F23).
  const additionnelles =
    nat.tse + nat.gemapi + nat.tasa + nat.tafnb + nat.tsc;
  const totalFdl =
    nat.tfpb +
    nat.tfpnb +
    nat.ths +
    nat.thlv +
    nat.cfe +
    nat.teom +
    nat.tascom +
    ifer +
    additionnelles;
  const taxes: ReiTaxe[] = [
    { id: "tfpb", libelle: "Taxe foncière bâtie", euros: nat.tfpb },
    { id: "teom", libelle: "TEOM", euros: nat.teom },
    { id: "cfe", libelle: "CFE", euros: nat.cfe },
    { id: "ths", libelle: "TH résidences secondaires", euros: nat.ths },
    { id: "tfpnb", libelle: "Taxe foncière non bâtie", euros: nat.tfpnb },
    { id: "ifer", libelle: "IFER", euros: ifer },
    { id: "tascom", libelle: "TASCOM", euros: nat.tascom },
    { id: "thlv", libelle: "TH logements vacants", euros: nat.thlv },
    { id: "add", libelle: "Taxes additionnelles", euros: additionnelles },
  ].sort((a, b) => b.euros - a.euros);
  const deps = db
    .prepare(
      `SELECT d.dep_carte AS dep,
              COALESCE(r.nom, d.dep_carte) AS nom,
              d.n_communes AS nCommunes,
              d.n_tfpb_nc AS nTfpbNc,
              d.tfpb AS tfpb
       FROM rei_departements d
       LEFT JOIN ref_departements r ON r.code = d.dep_carte
       WHERE d.annee = ?
       ORDER BY d.tfpb DESC`,
    )
    .all(nat.annee) as LigneReiDep[];
  return {
    meta,
    annee: nat.annee,
    etiquette: ETIQUETTE_REI,
    nCommunes: nat.n_communes,
    nTfpbNc: nat.n_tfpb_nc,
    tfpb: nat.tfpb,
    tfpbMd: nat.tfpb / 1e9,
    teom: nat.teom,
    cfe: nat.cfe,
    ths: nat.ths,
    thlv: nat.thlv,
    tfpnb: nat.tfpnb,
    tascom: nat.tascom,
    ifer,
    additionnelles,
    totalFdl,
    taxes,
    departements: deps,
  };
}
