/**
 * Accès (lecture seule) à la base SQLite servie : data/france.db à la racine
 * du dépôt. L'app ne fait AUCUN fetch externe au runtime : elle ne lit que
 * cette base, produite par les pipelines Python (`make ingest`).
 *
 * Garde « base absente » : tant que `make ingest` n'a pas tourné, le fichier
 * n'existe pas — `getDb()` renvoie alors `null` et chaque page doit afficher
 * un état « données en cours d'ingestion » plutôt que planter.
 */
import fs from "node:fs";
import path from "node:path";
import Database from "better-sqlite3";

type Db = InstanceType<typeof Database>;

/** Chemin de la base : ../data/france.db relatif à app/ (cwd de next),
 *  surchargeable par FRANCE_DB_PATH (chemin absolu). */
export const DB_PATH = process.env.FRANCE_DB_PATH
  ? path.resolve(process.env.FRANCE_DB_PATH)
  : path.resolve(process.cwd(), "..", "data", "france.db");

const globalForDb = globalThis as unknown as { __franceDb?: Db };

/**
 * Connexion partagée, ouverte en LECTURE SEULE.
 * Renvoie `null` si la base n'existe pas encore (le null n'est pas mis en
 * cache : dès que l'ingestion crée le fichier, la connexion s'ouvre).
 */
export function getDb(): Db | null {
  if (globalForDb.__franceDb) return globalForDb.__franceDb;
  if (!fs.existsSync(DB_PATH)) return null;
  const db = new Database(DB_PATH, { readonly: true, fileMustExist: true });
  db.pragma("query_only = ON");
  globalForDb.__franceDb = db;
  return db;
}

/** Ligne de fraîcheur d'une source (table noyau meta_sources). */
export type MetaSource = {
  source_id: string;
  nom: string;
  url: string;
  licence: string;
  frequence: string;
  date_donnees: string; // ISO
  date_ingestion: string; // ISO
  lignes: number;
  notes: string | null;
};

/**
 * Fraîcheur de toutes les sources ingérées (pour le bandeau
 * « Données au JJ/MM/AAAA · source · fréquence » et la page /donnees).
 * `null` tant que la base n'existe pas.
 */
export function getMetaSources(): MetaSource[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare("SELECT * FROM meta_sources ORDER BY source_id")
    .all() as MetaSource[];
}

/** Formatte une date ISO en JJ/MM/AAAA (convention d'affichage fraîcheur). */
export function formatDateFr(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Europe/Paris",
  }).format(d);
}
