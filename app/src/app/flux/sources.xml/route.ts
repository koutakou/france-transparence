/**
 * GET /flux/sources.xml : flux Atom des mises à jour des sources, généré au
 * build depuis meta_sources. Une entrée par source et par date des données
 * (identifiant = code source et date) : une édition plus récente ajoute une
 * entrée. Lien de la source amont. Règles : lib/flux.ts.
 *
 * Base absente au build : erreur franche, comme les routes JSON.
 */
import { FLUX, entreesSources } from "@/lib/flux";
import { getCatalogueSources } from "@/lib/queries/donnees";
import { erreurBaseAbsente, reponseFlux } from "@/lib/reponses-export";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-static";

export function GET() {
  const sources = getCatalogueSources(new Date());
  if (sources === null) throw erreurBaseAbsente();
  return reponseFlux(
    FLUX[3],
    entreesSources(sources, `${SITE_URL}${FLUX[3].page}`),
    sources,
    "Catalogue des sources de France Transparence, Licence Ouverte 2.0. Chaque entrée renvoie à sa source amont, sous sa propre licence.",
  );
}
