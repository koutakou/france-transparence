/**
 * Requêtes de la page /alertes et de l'API /api/alertes — table `alertes`
 * (1 590 lignes au 19/08/2026), calculée à l'ingestion par les pipelines
 * intégrité (A1_*), lobbying (lobbying_*) et financement (financement_*).
 *
 * Rappels docs/NOTES-FRONT.md § Alertes :
 * - TOUJOURS afficher règle + base légale (dépliable AlertItem) ;
 * - gravités en base : haute / moyenne / info ;
 * - les retards HATVP « présumés » sont des agrégats NON nominatifs — les
 *   lignes de la base portent déjà leurs réserves, on les affiche telles
 *   quelles, on ne nominalise jamais.
 *
 * Toutes les requêtes renvoient `null` si la base n'existe pas encore
 * (getDb() null → la page affiche un état honnête « lancer make ingest »).
 */
import { getDb } from "@/lib/db";

/** Gravités réellement présentes en base (du plus grave au moins grave). */
export const GRAVITES_ALERTE = ["haute", "moyenne", "info"] as const;
export type GraviteAlerte = (typeof GRAVITES_ALERTE)[number];

export function estGraviteAlerte(v: string): v is GraviteAlerte {
  return (GRAVITES_ALERTE as readonly string[]).includes(v);
}

/** Une ligne de la table `alertes` (schéma docs/SCHEMA-DB.md). */
export type Alerte = {
  id: string;
  type: string;
  gravite: string;
  titre: string;
  detail: string | null;
  regle: string | null;
  base_legale: string | null;
  source_url: string | null;
  date_calcul: string;
};

/** Pagination de la liste (consigne : 50 alertes par page). */
export const ALERTES_PAR_PAGE = 50;

export type AlertesStats = {
  total: number;
  parGravite: { gravite: string; nb: number }[];
  /** Date de calcul la plus récente (les alertes sont calculées à l'ingestion). */
  derniereDateCalcul: string | null;
};

/** KPI d'en-tête : total, répartition par gravité, dernière date de calcul. */
export function getAlertesStats(): AlertesStats | null {
  const db = getDb();
  if (!db) return null;
  const parGravite = db
    .prepare(
      `SELECT gravite, COUNT(*) AS nb FROM alertes
       GROUP BY gravite
       ORDER BY CASE gravite WHEN 'haute' THEN 0 WHEN 'moyenne' THEN 1 ELSE 2 END`,
    )
    .all() as { gravite: string; nb: number }[];
  const total = parGravite.reduce((s, g) => s + g.nb, 0);
  const derniere = db
    .prepare("SELECT MAX(date_calcul) AS d FROM alertes")
    .get() as { d: string | null };
  return { total, parGravite, derniereDateCalcul: derniere.d };
}

export type TypeAlerte = { type: string; nb: number };

/** Types d'alerte présents en base avec leur volume (pour la rangée de filtres). */
export function getAlertesTypes(): TypeAlerte[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare("SELECT type, COUNT(*) AS nb FROM alertes GROUP BY type ORDER BY nb DESC")
    .all() as TypeAlerte[];
}

export type DomaineAlerte = { domaine: string; nb: number };

/**
 * Répartition par domaine — le préfixe du type porte le domaine
 * (docs/NOTES-FRONT.md : types préfixés `A1_*`, `lobbying_*`, `financement_*`).
 * `\_` échappé : `_` est un joker LIKE.
 */
export function getAlertesDomaines(): DomaineAlerte[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT CASE
         WHEN type LIKE 'A1\\_%' ESCAPE '\\' THEN 'Intégrité des élus (HATVP)'
         WHEN type LIKE 'lobbying\\_%' ESCAPE '\\' THEN 'Lobbying'
         WHEN type LIKE 'financement\\_%' ESCAPE '\\' THEN 'Financement politique'
         ELSE 'Autre'
       END AS domaine, COUNT(*) AS nb
       FROM alertes GROUP BY domaine ORDER BY nb DESC`,
    )
    .all() as DomaineAlerte[];
}

/**
 * Dump complet des alertes (export statique /api/alertes.json) — même tri
 * stable que la liste paginée : gravité (haute → info), date de calcul
 * décroissante, id.
 */
export function getAlertesToutes(): Alerte[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT id, type, gravite, titre, detail, regle, base_legale, source_url, date_calcul
       FROM alertes
       ORDER BY CASE gravite WHEN 'haute' THEN 0 WHEN 'moyenne' THEN 1 ELSE 2 END,
                date_calcul DESC, id`,
    )
    .all() as Alerte[];
}

export type TypeAlerteExport = {
  type: string;
  nb: number;
  /** Règle de calcul — une seule valeur distincte par type (vérifié en base). */
  regle: string | null;
  base_legale: string | null;
};

export type AlertesExport = {
  types: TypeAlerteExport[];
  alertes: Alerte[];
};

/**
 * Export complet pour le fragment statique /data/alertes.json : toutes les
 * alertes dans l'ORDRE de la liste (gravité, date décroissante, id — le même
 * tri que `getAlertesPage`), plus la table des types avec règle/base légale
 * (une seule valeur distincte par type en base — dédupliquée au transport).
 */
export function getAlertesExport(): AlertesExport | null {
  const db = getDb();
  if (!db) return null;
  const types = db
    .prepare(
      `SELECT type, COUNT(*) AS nb, MAX(regle) AS regle, MAX(base_legale) AS base_legale
       FROM alertes GROUP BY type ORDER BY nb DESC`,
    )
    .all() as TypeAlerteExport[];
  const alertes = db
    .prepare(
      `SELECT id, type, gravite, titre, detail, regle, base_legale, source_url, date_calcul
       FROM alertes
       ORDER BY CASE gravite WHEN 'haute' THEN 0 WHEN 'moyenne' THEN 1 ELSE 2 END,
                date_calcul DESC, id`,
    )
    .all() as Alerte[];
  return { types, alertes };
}

export type FiltresAlertes = {
  /** Type exact (`lobbying_defaut_declaration`…) — undefined = tous. */
  type?: string;
  /** Gravité exacte — undefined = toutes. */
  gravite?: GraviteAlerte;
  /** Page 1-indexée. */
  page?: number;
  /** Taille de page (défaut ALERTES_PAR_PAGE, plafond 500 pour l'API). */
  limite?: number;
};

export type PageAlertes = {
  alertes: Alerte[];
  /** Total APRÈS filtres (pour « Page x sur y — n alertes »). */
  total: number;
  page: number;
  pages: number;
};

/**
 * Liste paginée, filtrable par type et gravité. Tri stable : gravité
 * (haute → info), puis date de calcul décroissante, puis id (pagination
 * déterministe). SQL paramétré uniquement.
 */
export function getAlertesPage(filtres: FiltresAlertes = {}): PageAlertes | null {
  const db = getDb();
  if (!db) return null;
  const limite = Math.min(Math.max(filtres.limite ?? ALERTES_PAR_PAGE, 1), 500);
  const conditions: string[] = [];
  const params: (string | number)[] = [];
  if (filtres.type) {
    conditions.push("type = ?");
    params.push(filtres.type);
  }
  if (filtres.gravite) {
    conditions.push("gravite = ?");
    params.push(filtres.gravite);
  }
  const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";
  const { total } = db
    .prepare(`SELECT COUNT(*) AS total FROM alertes ${where}`)
    .get(...params) as { total: number };
  const pages = Math.max(Math.ceil(total / limite), 1);
  const page = Math.min(Math.max(filtres.page ?? 1, 1), pages);
  const alertes = db
    .prepare(
      `SELECT id, type, gravite, titre, detail, regle, base_legale, source_url, date_calcul
       FROM alertes ${where}
       ORDER BY CASE gravite WHEN 'haute' THEN 0 WHEN 'moyenne' THEN 1 ELSE 2 END,
                date_calcul DESC, id
       LIMIT ? OFFSET ?`,
    )
    .all(...params, limite, (page - 1) * limite) as Alerte[];
  return { alertes, total, page, pages };
}
