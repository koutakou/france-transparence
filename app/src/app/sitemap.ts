import type { MetadataRoute } from "next";
import { getDb } from "@/lib/db";
import { SITE_URL } from "@/lib/site";

/**
 * Sitemap statique, généré au build (convention Next `app/sitemap.ts`) :
 * - les pages du site + les deux pages légales ;
 * - les fiches élus réellement pré-rendues — mandats nationaux et exécutifs
 *   uniquement (docs/deploiement/DECISION.md : députés, sénateurs,
 *   présidents de conseil départemental et régional, ≈ 1 053 fiches).
 *
 * URLs absolues en dur sur SITE_URL (GitHub Pages, basePath inclus) et
 * TRAILING SLASH systématique (le site statique sert des index.html).
 */

/** Pages statiques du site ("" = accueil). */
const PAGES_STATIQUES = [
  "",
  "depenses",
  "marches",
  "elus",
  "collectivites",
  "lobbying",
  "financement",
  "frais",
  "alertes",
  "documents",
  "donnees",
  "mentions-legales",
  "donnees-personnelles",
];

/** Types de mandat dont la fiche élu est pré-rendue (DECISION.md §R2). */
const TYPES_MANDAT_FICHE = [
  "depute",
  "senateur",
  "president_conseil_departemental",
  "president_conseil_regional",
];

export default function sitemap(): MetadataRoute.Sitemap {
  const urls: MetadataRoute.Sitemap = PAGES_STATIQUES.map((p) => ({
    url: p === "" ? `${SITE_URL}/` : `${SITE_URL}/${p}/`,
  }));

  // Fiches élus : ids distincts porteurs d'au moins un mandat pré-rendu.
  // Garde « base absente » héritée de getDb() : sans base (dev sans
  // ingestion), le sitemap reste valide avec les seules pages statiques.
  const db = getDb();
  if (db) {
    const jetons = TYPES_MANDAT_FICHE.map(() => "?").join(", ");
    const lignes = db
      .prepare(
        `SELECT DISTINCT e.id
           FROM elus e, json_each(e.mandats) je
          WHERE json_extract(je.value, '$.type') IN (${jetons})
          ORDER BY e.id`,
      )
      .all(...TYPES_MANDAT_FICHE) as { id: string }[];
    for (const { id } of lignes) {
      urls.push({ url: `${SITE_URL}/elus/${encodeURIComponent(id)}/` });
    }
  }

  return urls;
}
