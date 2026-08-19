import fs from "node:fs";
import { GEOJSON_DEPARTEMENTS_PATH } from "@/lib/queries/collectivites";

/**
 * Fond de carte des départements (GeoJSON, référentiel S27) servi en
 * fragment statique : les cartes sont dessinées CÔTÉ CLIENT (d3-geo) pour
 * ne plus embarquer ~700 Ko de tracés SVG dans le HTML de /marches et
 * /collectivites. Fichier généré au build (`dynamic = "force-static"`),
 * identique à `data/geo/departements.geojson`.
 *
 * `null` si le référentiel n'est pas encore ingéré — le composant carte
 * affiche alors le même message honnête qu'avant (tableaux complets).
 */
export const dynamic = "force-static";

export async function GET() {
  if (!fs.existsSync(GEOJSON_DEPARTEMENTS_PATH)) {
    return Response.json(null);
  }
  const brut = fs.readFileSync(GEOJSON_DEPARTEMENTS_PATH, "utf-8");
  return new Response(brut, {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}
