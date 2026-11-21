/**
 * GET /flux/jo.xml : flux Atom des textes des derniers numéros du Journal
 * officiel (source S3), généré au build. Titre et lien Légifrance de chaque
 * texte, identifiant d'entrée tiré du NOR. Règles : lib/flux.ts.
 *
 * Base absente au build : erreur franche, comme les routes JSON.
 */
import { FLUX, NB_JO_FLUX, entreesJo } from "@/lib/flux";
import { getMetaSourcesParIds } from "@/lib/queries/donnees";
import { getTextesJoFlux } from "@/lib/queries/flux";
import { erreurBaseAbsente, reponseFlux } from "@/lib/reponses-export";

export const dynamic = "force-static";

export function GET() {
  const textes = getTextesJoFlux(NB_JO_FLUX);
  if (textes === null) throw erreurBaseAbsente();
  return reponseFlux(FLUX[0], entreesJo(textes), getMetaSourcesParIds(["S3"]));
}
