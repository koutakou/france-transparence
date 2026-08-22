/**
 * Requêtes des dossiers législatifs DILA (source S43, fonds DOLE), servis
 * en bloc cloisonné sur /documents et en page dédiée /documents/dossiers.
 *
 * ────────────────────────────────────────────────────────────────────────
 * CLOISONNEMENT
 * ────────────────────────────────────────────────────────────────────────
 * Ce n'est PAS la source S3 (JORFSIMPLE, fenêtre des 30 derniers JO).
 * Ce n'est PAS S35 (autres fonds DILA non ingérés).
 * `source_id` = S43, jamais `'S3'` ni `'S35'`.
 *
 * TYPE n'est PAS « en navette aujourd'hui ». Un PROJET_LOI d'une
 * législature close reste typé projet dans le fichier. La navette
 * affichée est : type ∈ {PROJET_LOI, PROPOSITION_LOI, PROJET_ORDONNANCE}
 * ET legislature_num = max(CAST(legislature_num AS INT)) parmi les
 * numéros entièrement numériques. Ne pas coder le numéro 17 en dur.
 *
 * Les volumes (stock, navette, ventilations) dérivent à chaque ingestion ;
 * ne pas les figer dans un commentaire comme un invariant.
 *
 * Convention « base / table absente » : `null` tant que `dole_dossiers`
 * n'est pas ingérée — la section n'est pas rendue, jamais un zéro inventé.
 */
import { getDb, type MetaSource } from "@/lib/db";

const TYPES_NAVETTE = ["PROJET_LOI", "PROPOSITION_LOI", "PROJET_ORDONNANCE"] as const;
const SQL_IN_NAVETTE = TYPES_NAVETTE.map((t) => `'${t}'`).join(", ");

/** Aperçu sur /documents ; le tableau complet est sur /documents/dossiers/. */
export const NAVETTE_APERCU = 20;

export type DoleLegislature = {
  num: string;
  libelle: string;
};

export type DoleParType = {
  type: string;
  nb: number;
};

export type DoleNavetteLigne = {
  dossier_id: string;
  titre: string;
  type: string;
  date_modif: string | null;
  derniere_etape: string;
  lien_legifrance: string;
};

export type DoleVue = {
  meta: MetaSource;
  legislatureCourante: DoleLegislature;
  /** Plus ancienne législature numérotée du fichier (le producteur annonce la XIIe). */
  legislatureMin: DoleLegislature;
  nbDossiers: number;
  /** Navette de la législature courante seulement. */
  nbNavette: number;
  nbLoisPubliees: number;
  nbOrdonnancesPubliees: number;
  parType: DoleParType[];
  navette: DoleNavetteLigne[];
};

function tablePresente(): boolean {
  const db = getDb();
  if (!db) return false;
  const ligne = db
    .prepare(
      "SELECT count(*) AS n FROM sqlite_master WHERE type = 'table' AND name = 'dole_dossiers'",
    )
    .get() as { n: number };
  return ligne.n > 0;
}

/** Numéro entièrement numérique (équivalent Python `str.isdigit()`). */
const SQL_NUMERO_NUMERIQUE =
  "length(legislature_num) > 0 AND legislature_num NOT GLOB '*[^0-9]*'";

function lireLegislature(ordre: "ASC" | "DESC"): DoleLegislature | null {
  const db = getDb();
  if (!db) return null;
  const ligne = db
    .prepare(
      `SELECT legislature_num AS num,
              MAX(legislature_libelle) AS libelle
       FROM dole_dossiers
       WHERE ${SQL_NUMERO_NUMERIQUE}
       GROUP BY legislature_num
       ORDER BY CAST(legislature_num AS INTEGER) ${ordre}
       LIMIT 1`,
    )
    .get() as { num: string; libelle: string | null } | undefined;
  if (!ligne) return null;
  return { num: ligne.num, libelle: ligne.libelle ?? "" };
}

export function libelleLegislatureDole(leg: DoleLegislature): string {
  const lib = leg.libelle.trim();
  return lib || `législature n° ${leg.num}`;
}

/**
 * Périmètre de la tuile « Dossiers au fichier » : stock DILA, de la plus
 * ancienne législature numérotée du fichier à la courante. Le producteur
 * annonce la XIIe (juin 2002) ; le fichier porte aussi la XIe.
 */
export function perimetreDoleStock(vue: Pick<DoleVue, "legislatureMin" | "legislatureCourante">): string {
  const min = libelleLegislatureDole(vue.legislatureMin);
  const courante = libelleLegislatureDole(vue.legislatureCourante);
  if (vue.legislatureMin.num === vue.legislatureCourante.num) {
    return `stock DILA, ${courante} — le producteur annonce la XIIe`;
  }
  return `stock DILA, ${min} → ${courante} — le producteur annonce la XIIe`;
}

/**
 * Périmètre de la tuile « En navette » : législature courante nommée,
 * types ouverts seulement. Les PPL du fichier n'entrent qu'après adoption
 * par la 1re assemblée (réforme 2008).
 */
export function perimetreDoleNavette(leg: DoleLegislature): string {
  return (
    `${libelleLegislatureDole(leg)} · projets, propositions et projets d’ordonnance` +
    " · PPL après 1re assemblée (réforme 2008)"
  );
}

/**
 * Stock + navette de la législature courante.
 * `null` si la base n'existe pas, si S43 n'est pas ingérée, ou s'il n'y a
 * aucune législature numérotée.
 */
export function getDole(): DoleVue | null {
  const db = getDb();
  if (!db || !tablePresente()) return null;

  const meta = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S43'")
    .get() as MetaSource | undefined;
  if (!meta) return null;

  const legislatureCourante = lireLegislature("DESC");
  const legislatureMin = lireLegislature("ASC");
  if (!legislatureCourante || !legislatureMin) return null;

  const cadrage = db
    .prepare(
      `SELECT COUNT(*) AS nbDossiers,
              SUM(CASE WHEN type = 'LOI_PUBLIEE' THEN 1 ELSE 0 END) AS nbLoisPubliees,
              SUM(CASE WHEN type = 'ORDONNANCE_PUBLIEE' THEN 1 ELSE 0 END) AS nbOrdonnancesPubliees,
              SUM(CASE WHEN type IN (${SQL_IN_NAVETTE})
                        AND legislature_num = ?
                       THEN 1 ELSE 0 END) AS nbNavette
       FROM dole_dossiers`,
    )
    .get(legislatureCourante.num) as {
    nbDossiers: number;
    nbLoisPubliees: number | null;
    nbOrdonnancesPubliees: number | null;
    nbNavette: number | null;
  };
  if (cadrage.nbDossiers === 0) return null;

  const parType = db
    .prepare(
      `SELECT type, COUNT(*) AS nb
       FROM dole_dossiers
       GROUP BY type
       ORDER BY CASE type
         WHEN 'LOI_PUBLIEE' THEN 1
         WHEN 'ORDONNANCE_PUBLIEE' THEN 2
         WHEN 'PROJET_LOI' THEN 3
         WHEN 'PROPOSITION_LOI' THEN 4
         WHEN 'PROJET_ORDONNANCE' THEN 5
         ELSE 6
       END,
       type`,
    )
    .all() as DoleParType[];

  const navette = db
    .prepare(
      `SELECT dossier_id, titre, type, date_modif, derniere_etape, lien_legifrance
       FROM dole_dossiers
       WHERE type IN (${SQL_IN_NAVETTE})
         AND legislature_num = ?
       ORDER BY date_modif DESC, dossier_id`,
    )
    .all(legislatureCourante.num) as DoleNavetteLigne[];

  return {
    meta,
    legislatureCourante,
    legislatureMin,
    nbDossiers: cadrage.nbDossiers,
    nbNavette: cadrage.nbNavette ?? 0,
    nbLoisPubliees: cadrage.nbLoisPubliees ?? 0,
    nbOrdonnancesPubliees: cadrage.nbOrdonnancesPubliees ?? 0,
    parType,
    navette,
  };
}

export { TYPES_NAVETTE as TYPES_NAVETTE_DOLE };
