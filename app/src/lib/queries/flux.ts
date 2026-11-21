/**
 * Requêtes propres aux flux Atom (/flux/*.xml). Les autres flux réutilisent
 * les requêtes de leur page (alertes, dossiers, catalogue des sources), le
 * flux des dossiers y ajoute leur date de création.
 *
 * Toutes les requêtes renvoient `null` si la base n'existe pas encore.
 */
import { getDb } from "@/lib/db";
import type { TexteJoFlux } from "@/lib/flux";

/**
 * Date de création des dossiers législatifs (source S43), par numéro de
 * dossier : elle date l'entrée du flux quand le dossier n'a pas de date de
 * mise à jour. Les dossiers sans date de création n'y figurent pas.
 */
export function getDatesCreationDossiers(): Map<string, string> | null {
  const db = getDb();
  if (!db) return null;
  const lignes = db
    .prepare("SELECT dossier_id, date_creation FROM dole_dossiers WHERE date_creation IS NOT NULL")
    .all() as { dossier_id: string; date_creation: string }[];
  return new Map(lignes.map((l) => [l.dossier_id, l.date_creation]));
}

/**
 * Textes des `nbNumeros` derniers numéros du JO en base (source S3), dans
 * l'ordre du flux de /documents : JO le plus récent d'abord, puis ordre du
 * sommaire. Le NOR est lu pour l'identifiant d'entrée.
 */
export function getTextesJoFlux(nbNumeros: number): TexteJoFlux[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT texte_id, nor, date_publi, titre, lien_legifrance
       FROM jorf_textes
       WHERE date_publi IN (
         SELECT DISTINCT date_publi FROM jorf_textes ORDER BY date_publi DESC LIMIT ?
       )
       ORDER BY date_publi DESC, num_sequence ASC`,
    )
    .all(nbNumeros) as TexteJoFlux[];
}
