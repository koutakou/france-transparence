/**
 * Requêtes des comptes des ODAC INSEE (source S51, Insee Résultats
 * 8988845, tableau 3.204, secteur S13112).
 *
 * ────────────────────────────────────────────────────────────────────────
 * CLOISONNEMENT
 * ────────────────────────────────────────────────────────────────────────
 * Ce n'est PAS la source S13 (situations mensuelles DGFiP, budget de
 * l'État). Ce n'est PAS S50 (comptes des APU : S1311 contient déjà
 * S13112). Ce n'est PAS l'État (S13111). Ce n'est PAS S39 (jaune
 * opérateurs du PLF, liste sans €). Ce n'est PAS S44, S42 ni S49.
 * `source_id` = S51, jamais `'S13'`, `'S50'`, `'S39'` ni `'S44'`.
 *
 * Unité native : milliard d'euros (MdEUR). Jamais × 1000, jamais ÷ 1e9.
 * On n'additionne pas S13112 à S13111 ni à S1311 (déjà dans S1311).
 * On n'affiche pas REC_TOTAL : REC − DEP serait un solde (B9).
 *
 * Convention « base absente » : `null` tant que la table n'est pas ingérée.
 */
import { getDb, type MetaSource } from "@/lib/db";

const LIBELLE_ODAC = "Organismes divers d'administration centrale (S13112)";

export type LigneOdac = {
  secteur: string;
  libelle: string;
  annee: number;
  depensesMd: number;
};

export type OdacInsee = {
  meta: MetaSource;
  annee: number;
  anneePrecedente: number | null;
  odac: LigneOdac;
  precedent: LigneOdac | null;
  deltaPct: number | null;
};

/**
 * Périmètre obligatoire de la tuile S13112 (DATAVIZ §6).
 * L'année vient de la ligne, jamais d'une constante.
 */
export function perimetreOdac(annee: number): string {
  return (
    `année ${annee} · comptes nationaux INSEE · S13112 (ODAC) · ` +
    `déjà dans S1311 · ne s'additionne pas à l'État (S13111) · ` +
    `pas les opérateurs du jaune PLF · pas le budget général`
  );
}

function tablePresente(): boolean {
  const db = getDb();
  if (!db) return false;
  const ligne = db
    .prepare(
      "SELECT count(*) AS n FROM sqlite_master WHERE type = 'table' AND name = 'comptes_odac_insee'",
    )
    .get() as { n: number };
  return ligne.n > 0;
}

function metaS51(): MetaSource | null {
  const db = getDb();
  if (!db || !tablePresente()) return null;
  const meta = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S51'")
    .get() as MetaSource | undefined;
  return meta ?? null;
}

function ligneDep(annee: number): LigneOdac | null {
  const db = getDb();
  if (!db) return null;
  const dep = db
    .prepare(
      `SELECT valeur_md, libelle FROM comptes_odac_insee
       WHERE secteur = 'S13112' AND poste = 'DEP_TOTAL' AND unite = 'MdEUR' AND annee = ?`,
    )
    .get(annee) as { valeur_md: number; libelle: string } | undefined;
  if (!dep) return null;
  return {
    secteur: "S13112",
    libelle: LIBELLE_ODAC,
    annee,
    depensesMd: dep.valeur_md,
  };
}

/**
 * Dépenses S13112 au millésime max.
 * `null` si la base n'existe pas ou si S51 n'est pas ingérée.
 */
export function getOdacInsee(): OdacInsee | null {
  const meta = metaS51();
  const db = getDb();
  if (!meta || !db) return null;

  const row = db
    .prepare(
      `SELECT max(annee) AS a FROM comptes_odac_insee
       WHERE secteur = 'S13112' AND poste = 'DEP_TOTAL' AND unite = 'MdEUR'`,
    )
    .get() as { a: number | null };
  const annee = row.a ?? null;
  if (annee === null) return null;

  const odac = ligneDep(annee);
  if (!odac) return null;

  const annees = db
    .prepare(
      `SELECT DISTINCT annee FROM comptes_odac_insee
       WHERE secteur = 'S13112' AND poste = 'DEP_TOTAL' AND unite = 'MdEUR'
       ORDER BY annee ASC`,
    )
    .all() as { annee: number }[];
  const anneePrecedente =
    annees.length >= 2 ? annees[annees.length - 2].annee : null;
  const precedent =
    anneePrecedente === null ? null : ligneDep(anneePrecedente);

  let deltaPct: number | null = null;
  if (precedent && precedent.depensesMd !== 0) {
    deltaPct =
      ((odac.depensesMd - precedent.depensesMd) /
        Math.abs(precedent.depensesMd)) *
      100;
  }

  return {
    meta,
    annee,
    anneePrecedente,
    odac,
    precedent,
    deltaPct,
  };
}
