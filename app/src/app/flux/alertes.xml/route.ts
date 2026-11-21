/**
 * GET /flux/alertes.xml : flux Atom d'une partie des alertes de /alertes,
 * généré au build. Seuls les types dont le fait a une date qui ne change pas
 * d'une ingestion à l'autre y entrent (TYPES_ALERTES_FLUX, lib/flux.ts) :
 * aujourd'hui la dépendance d'un parti à l'aide publique (source S25),
 * datée de la clôture de l'exercice. Jamais plus que la page : types retirés
 * exclus par la requête. Titre de l'alerte, lien de la donnée officielle et
 * lien vers la page qui donne la règle. Identifiant d'entrée = id de
 * l'alerte.
 *
 * Base absente au build : erreur franche, comme les routes JSON.
 */
import { FLUX, entreesAlertes } from "@/lib/flux";
import { getAlertesToutes } from "@/lib/queries/alertes";
import { getMetaSourcesParIds } from "@/lib/queries/donnees";
import { erreurBaseAbsente, reponseFlux } from "@/lib/reponses-export";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-static";

/** Source des types d'alerte repris dans le flux (licence, date du flux vide). */
const SOURCES_FLUX_ALERTES = ["S25"];

export function GET() {
  const alertes = getAlertesToutes();
  const sources = getMetaSourcesParIds(SOURCES_FLUX_ALERTES);
  if (alertes === null || sources === null) throw erreurBaseAbsente();
  return reponseFlux(FLUX[2], entreesAlertes(alertes, `${SITE_URL}${FLUX[2].page}`), sources);
}
