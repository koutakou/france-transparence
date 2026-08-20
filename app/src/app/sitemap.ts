import type { MetadataRoute } from "next";
import { getDb } from "@/lib/db";
import { SITE_URL } from "@/lib/site";

// Exigé par `output: "export"` (route metadata générée au build).
export const dynamic = "force-static";

/**
 * Sitemap statique, généré au build (convention Next `app/sitemap.ts`) :
 * - les pages du site + les deux pages légales ;
 * - les fiches élus réellement pré-rendues — mandats nationaux et exécutifs
 *   uniquement (docs/deploiement/DECISION.md : députés, sénateurs,
 *   présidents de conseil départemental et régional, ≈ 1 053 fiches).
 *
 * URLs absolues en dur sur SITE_URL (GitHub Pages, basePath inclus) et
 * TRAILING SLASH systématique (le site statique sert des index.html).
 *
 * `lastmod` — c'est la date de la DERNIÈRE INGESTION (MAX
 * `meta_sources.date_ingestion`), pas celle du build : un rebuild sans
 * ingestion ne change rien au contenu, et annoncer une modification qui n'a
 * pas eu lieu apprend à un moteur à ignorer le champ. Toutes les pages de
 * données partagent la même valeur parce que c'est la vérité : le site
 * entier est régénéré à partir d'une seule ingestion nocturne. Les deux
 * pages légales, elles, ne dépendent d'aucune donnée : elles n'ont donc
 * PAS de `lastmod` plutôt qu'un `lastmod` faux.
 */

/** Pages statiques alimentées par la base ("" = accueil). */
const PAGES_DONNEES = [
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
];

/** Pages éditoriales, indépendantes de l'ingestion (aucun `lastmod`). */
const PAGES_LEGALES = ["mentions-legales", "donnees-personnelles"];

/** Types de mandat dont la fiche élu est pré-rendue (DECISION.md §R2). */
const TYPES_MANDAT_FICHE = [
  "depute",
  "senateur",
  "president_conseil_departemental",
  "president_conseil_regional",
];

export default function sitemap(): MetadataRoute.Sitemap {
  // Garde « base absente » héritée de getDb() : sans base (dev sans
  // ingestion), le sitemap reste valide — sans `lastmod` et sans fiches.
  const db = getDb();

  let lastModified: Date | undefined;
  if (db) {
    const r = db
      .prepare("SELECT MAX(date_ingestion) AS d FROM meta_sources")
      .get() as { d: string | null };
    const t = r.d ? new Date(r.d) : null;
    if (t && !Number.isNaN(t.getTime())) lastModified = t;
  }

  const urls: MetadataRoute.Sitemap = PAGES_DONNEES.map((p) => ({
    url: p === "" ? `${SITE_URL}/` : `${SITE_URL}/${p}/`,
    lastModified,
  }));
  for (const p of PAGES_LEGALES) urls.push({ url: `${SITE_URL}/${p}/` });

  // Fiches élus : ids distincts porteurs d'au moins un mandat pré-rendu.
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
      urls.push({ url: `${SITE_URL}/elus/${encodeURIComponent(id)}/`, lastModified });
    }
  }

  return urls;
}
