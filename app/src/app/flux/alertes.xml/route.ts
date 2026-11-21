/**
 * GET /flux/alertes.xml : flux Atom des alertes de /alertes, généré au build.
 * Les mêmes alertes que la page, pas une de plus : types retirés exclus par
 * la requête, comptes de campagne absents (agrégats sans nom sur
 * /financement), agrégats HATVP non nominatifs. Titre de l'alerte, lien de la
 * donnée officielle et lien vers la page qui donne la règle. Identifiant
 * d'entrée = id de l'alerte. Règles : lib/flux.ts.
 *
 * Base absente au build : erreur franche, comme les routes JSON.
 */
import { FLUX, entreesAlertes } from "@/lib/flux";
import { SOURCES_ALERTES, getAlertesToutes } from "@/lib/queries/alertes";
import { getMetaSourcesParIds } from "@/lib/queries/donnees";
import { erreurBaseAbsente, reponseFlux } from "@/lib/reponses-export";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-static";

export function GET() {
  const alertes = getAlertesToutes();
  const sources = getMetaSourcesParIds([...SOURCES_ALERTES]);
  if (alertes === null || sources === null) throw erreurBaseAbsente();
  const datesSources = Object.fromEntries(sources.map((s) => [s.source_id, s.date_donnees]));
  return reponseFlux(
    FLUX[2],
    entreesAlertes(alertes, datesSources, `${SITE_URL}${FLUX[2].page}`),
    sources,
  );
}
