/**
 * GET /flux/alertes.xml : flux Atom des alertes de /alertes, généré au
 * build. Chaque entrée est datée d'une date qui ne change pas d'une
 * ingestion à l'autre (dateAlerte, lib/flux.ts) : la clôture de l'exercice
 * pour la dépendance d'un parti à l'aide publique (source S25), le jour de
 * la première détection de l'alerte pour les autres (HATVP S14, lobbying
 * S4, partis privés d'aide S25). Jamais plus que la page : types retirés
 * exclus par la requête. Titre de l'alerte, lien de la donnée officielle et
 * lien vers la page qui donne la règle. Identifiant d'entrée = id de
 * l'alerte.
 *
 * Base absente au build : erreur franche, comme les routes JSON.
 */
import { FLUX, entreesAlertes } from "@/lib/flux";
import { getAlertesToutes } from "@/lib/queries/alertes";
import { getMetaSourcesParIds } from "@/lib/queries/donnees";
import { getDatesDetectionAlertes } from "@/lib/queries/flux";
import { erreurBaseAbsente, reponseFlux } from "@/lib/reponses-export";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-static";

/** Sources des alertes reprises dans le flux (licences, date du flux vide). */
const SOURCES_FLUX_ALERTES = ["S14", "S4", "S25"];

export function GET() {
  const alertes = getAlertesToutes();
  const detections = getDatesDetectionAlertes();
  const sources = getMetaSourcesParIds(SOURCES_FLUX_ALERTES);
  if (alertes === null || detections === null || sources === null) throw erreurBaseAbsente();
  const avecDetection = alertes.map((a) => ({ ...a, date_detection: detections.get(a.id) ?? null }));
  return reponseFlux(FLUX[2], entreesAlertes(avecDetection, `${SITE_URL}${FLUX[2].page}`), sources);
}
