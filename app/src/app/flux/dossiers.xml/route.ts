/**
 * GET /flux/dossiers.xml : flux Atom des dossiers législatifs en navette de
 * la législature en cours (source S43), les plus récemment mis à jour, comme
 * sur /documents/dossiers. Titre et lien officiel de chaque dossier,
 * identifiant d'entrée = numéro du dossier. Règles : lib/flux.ts.
 *
 * Base absente au build : erreur franche, comme les routes JSON.
 */
import { FLUX, entreesDossiers } from "@/lib/flux";
import { getDole } from "@/lib/queries/dole";
import { erreurBaseAbsente, reponseFlux } from "@/lib/reponses-export";

export const dynamic = "force-static";

export function GET() {
  const dole = getDole();
  if (dole === null) throw erreurBaseAbsente();
  return reponseFlux(FLUX[1], entreesDossiers(dole.navette, dole.meta.date_donnees), [dole.meta]);
}
