/**
 * Requêtes des comptes des APU INSEE (source S50, Insee Résultats
 * 8988845, tableaux 3.201–3.203 / 3.205 / 3.212 et 3.216).
 *
 * ────────────────────────────────────────────────────────────────────────
 * CLOISONNEMENT
 * ────────────────────────────────────────────────────────────────────────
 * Ce n'est PAS la source S13 (situations mensuelles DGFiP, budget de
 * l'État, cumul depuis le 1er janvier). Le secteur ESA S13 =
 * administrations publiques (État + Odac + APUL + ASSO).
 * Ce n'est PAS S44 (TE/TR Eurostat gov_10a_main, S13 seul).
 * Ce n'est PAS S42 (B9 Maastricht — non ingéré ici).
 * Ce n'est PAS S49 (CFAP / COFOG).
 * `source_id` = S50, jamais `'S13'`, `'S44'`, `'S42'` ni `'S49'`.
 *
 * Unité native : milliard d'euros (MdEUR) et, pour le PO, % du PIB
 * (PC_PIB). Jamais × 1000, jamais ÷ 1e9. On n'additionne pas les
 * sous-secteurs au total S13 (consolidations distinctes). On ne
 * ventile pas S44. S1311 n'est pas « la dette de l'État ». S1314
 * n'est pas « la Sécu ». Le PO n'est pas taxag.
 *
 * Convention « base absente » : `null` tant que la table n'est pas ingérée.
 */
import { getDb, type MetaSource } from "@/lib/db";

export type LigneCompteApu = {
  secteur: string;
  libelle: string;
  annee: number;
  depensesMd: number;
  recettesMd: number;
};

export type LignePo = {
  secteur: string;
  libelle: string;
  annee: number;
  valeurMd: number;
  pcPib: number | null;
};

export type ComptesApuInsee = {
  meta: MetaSource;
  annee: number;
  anneePrecedente: number | null;
  /** S1311, pour la tuile — pas un second total S13/S44. */
  centrale: LigneCompteApu;
  precedentCentrale: LigneCompteApu | null;
  deltaCentralePct: number | null;
  /** S1311, S1313, S1314 — ordre du producteur, non additifs, sans S13 ni S13111. */
  sousSecteursDepenses: LigneCompteApu[];
};

export type PrelevementsObligatoires = {
  meta: MetaSource;
  annee: number;
  total: LignePo;
  precedent: LignePo | null;
  deltaPct: number | null;
  /** S1311, S1313, S1314, S212 — ordre du producteur. */
  sousSecteurs: LignePo[];
};

const LIBELLES: Record<string, string> = {
  S13: "Administrations publiques (S13)",
  S1311: "Administration publique centrale (S1311)",
  S13111: "État (S13111)",
  S13112: "Organismes divers d'administration centrale (S13112)",
  S1313: "Administrations publiques locales (S1313)",
  S1314: "Administrations de sécurité sociale (S1314)",
  S212: "Institutions de l'Union européenne (S212)",
  S13_S212: "APU et institutions de l'UE (S13 et S212)",
};

const ORDRE_SOUS_DEP = ["S1311", "S1313", "S1314"] as const;
const ORDRE_PO = ["S1311", "S1313", "S1314", "S212"] as const;

/**
 * Périmètre obligatoire de la tuile S1311 (DATAVIZ §6).
 * L'année vient de la ligne, jamais d'une constante.
 */
export function perimetreCentrale(annee: number): string {
  return (
    `année ${annee} · comptes nationaux INSEE · S1311 (État + ODAC) · ` +
    `présentation dépenses et recettes · pas le budget général · ` +
    `pas la dette de l'État · pas un sous-total de S44`
  );
}

/**
 * Périmètre obligatoire de la tuile PO (DATAVIZ §6).
 * Le % du PIB vient de la ligne, jamais d'une constante.
 */
export function perimetrePo(dernier: LignePo): string {
  const pc =
    dernier.pcPib === null
      ? null
      : dernier.pcPib.toLocaleString("fr-FR", {
          minimumFractionDigits: 1,
          maximumFractionDigits: 1,
        });
  const parts = [
    `année ${dernier.annee}`,
    "comptes nationaux INSEE",
    "S13 et S212",
    "Md€",
  ];
  if (pc !== null) parts.push(`${pc} % du PIB`);
  parts.push("pas taxag");
  parts.push("pas TR Eurostat");
  parts.push("pas l'IR de caisse S13");
  return parts.join(" · ");
}

function tablePresente(): boolean {
  const db = getDb();
  if (!db) return false;
  const ligne = db
    .prepare(
      "SELECT count(*) AS n FROM sqlite_master WHERE type = 'table' AND name = 'comptes_apu_insee'",
    )
    .get() as { n: number };
  return ligne.n > 0;
}

function metaS50(): MetaSource | null {
  const db = getDb();
  if (!db || !tablePresente()) return null;
  const meta = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S50'")
    .get() as MetaSource | undefined;
  return meta ?? null;
}

function anneeMax(poste: string, unite: string): number | null {
  const db = getDb();
  if (!db) return null;
  const row = db
    .prepare(
      `SELECT max(annee) AS a FROM comptes_apu_insee
       WHERE poste = ? AND unite = ?`,
    )
    .get(poste, unite) as { a: number | null };
  return row.a ?? null;
}

function ligneDepRec(secteur: string, annee: number): LigneCompteApu | null {
  const db = getDb();
  if (!db) return null;
  const dep = db
    .prepare(
      `SELECT valeur_md FROM comptes_apu_insee
       WHERE secteur = ? AND poste = 'DEP_TOTAL' AND unite = 'MdEUR' AND annee = ?`,
    )
    .get(secteur, annee) as { valeur_md: number } | undefined;
  const rec = db
    .prepare(
      `SELECT valeur_md FROM comptes_apu_insee
       WHERE secteur = ? AND poste = 'REC_TOTAL' AND unite = 'MdEUR' AND annee = ?`,
    )
    .get(secteur, annee) as { valeur_md: number } | undefined;
  if (!dep || !rec) return null;
  return {
    secteur,
    libelle: LIBELLES[secteur] ?? secteur,
    annee,
    depensesMd: dep.valeur_md,
    recettesMd: rec.valeur_md,
  };
}

/**
 * Dépenses / recettes par sous-secteur, millésime max.
 * `null` si la base n'existe pas ou si S50 n'est pas ingérée.
 */
export function getComptesApuInsee(): ComptesApuInsee | null {
  const meta = metaS50();
  const db = getDb();
  if (!meta || !db) return null;
  const annee = anneeMax("DEP_TOTAL", "MdEUR");
  if (annee === null) return null;

  const sousSecteursDepenses: LigneCompteApu[] = [];
  for (const secteur of ORDRE_SOUS_DEP) {
    const l = ligneDepRec(secteur, annee);
    if (!l) return null;
    sousSecteursDepenses.push(l);
  }
  const centrale = sousSecteursDepenses[0];
  if (!centrale || centrale.secteur !== "S1311") return null;

  const annees = db
    .prepare(
      `SELECT DISTINCT annee FROM comptes_apu_insee
       WHERE poste = 'DEP_TOTAL' AND unite = 'MdEUR' AND secteur = 'S1311'
       ORDER BY annee ASC`,
    )
    .all() as { annee: number }[];
  const anneePrecedente =
    annees.length >= 2 ? annees[annees.length - 2].annee : null;
  const precedentCentrale =
    anneePrecedente === null ? null : ligneDepRec("S1311", anneePrecedente);

  let deltaCentralePct: number | null = null;
  if (precedentCentrale && precedentCentrale.depensesMd !== 0) {
    deltaCentralePct =
      ((centrale.depensesMd - precedentCentrale.depensesMd) /
        Math.abs(precedentCentrale.depensesMd)) *
      100;
  }

  return {
    meta,
    annee,
    anneePrecedente,
    centrale,
    precedentCentrale,
    deltaCentralePct,
    sousSecteursDepenses,
  };
}

function lignePo(secteur: string, annee: number): LignePo | null {
  const db = getDb();
  if (!db) return null;
  const md = db
    .prepare(
      `SELECT valeur_md, libelle FROM comptes_apu_insee
       WHERE secteur = ? AND poste = 'PO' AND unite = 'MdEUR' AND annee = ?`,
    )
    .get(secteur, annee) as { valeur_md: number; libelle: string } | undefined;
  if (!md) return null;
  const pc = db
    .prepare(
      `SELECT valeur_md FROM comptes_apu_insee
       WHERE secteur = ? AND poste = 'PO' AND unite = 'PC_PIB' AND annee = ?`,
    )
    .get(secteur, annee) as { valeur_md: number } | undefined;
  return {
    secteur,
    libelle: LIBELLES[secteur] ?? md.libelle,
    annee,
    valeurMd: md.valeur_md,
    pcPib: pc ? pc.valeur_md : null,
  };
}

/**
 * Prélèvements obligatoires (tableau 3.216), millésime max.
 * `null` si S50 n'est pas ingérée.
 */
export function getPrelevementsObligatoires(): PrelevementsObligatoires | null {
  const meta = metaS50();
  const db = getDb();
  if (!meta || !db) return null;
  const annee = anneeMax("PO", "MdEUR");
  if (annee === null) return null;
  const total = lignePo("S13_S212", annee);
  if (!total) return null;

  const annees = db
    .prepare(
      `SELECT DISTINCT annee FROM comptes_apu_insee
       WHERE poste = 'PO' AND unite = 'MdEUR' AND secteur = 'S13_S212'
       ORDER BY annee ASC`,
    )
    .all() as { annee: number }[];
  const anneePrecedente =
    annees.length >= 2 ? annees[annees.length - 2].annee : null;
  const precedent =
    anneePrecedente === null ? null : lignePo("S13_S212", anneePrecedente);

  let deltaPct: number | null = null;
  if (precedent && precedent.valeurMd !== 0) {
    deltaPct =
      ((total.valeurMd - precedent.valeurMd) / Math.abs(precedent.valeurMd)) *
      100;
  }

  const sousSecteurs = ORDRE_PO.map((s) => lignePo(s, annee)).filter(
    (l): l is LignePo => l !== null,
  );
  if (sousSecteurs.length !== 4) return null;

  return { meta, annee, total, precedent, deltaPct, sousSecteurs };
}
