/**
 * Requêtes propres aux flux Atom (/flux/*.xml). Les autres flux réutilisent
 * les requêtes de leur page (alertes, dossiers, catalogue des sources).
 *
 * Toutes les requêtes renvoient `null` si la base n'existe pas encore.
 */
import { getDb } from "@/lib/db";
import type { TexteJoFlux } from "@/lib/flux";

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
