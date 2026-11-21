/**
 * GET /flux/dossiers.xml : flux Atom des dossiers législatifs en navette de
 * la législature en cours (source S43), les plus récemment mis à jour, comme
 * sur /documents/dossiers. Titre et lien officiel de chaque dossier,
 * identifiant d'entrée = numéro du dossier, date = dernière mise à jour du
 * dossier, sinon sa création (jamais la date des données de la source).
 * Règles : lib/flux.ts.
 *
 * Base absente au build : erreur franche, comme les routes JSON.
 */
import { FLUX, entreesDossiers } from "@/lib/flux";
import { getDole } from "@/lib/queries/dole";
import { getDatesCreationDossiers } from "@/lib/queries/flux";
import { erreurBaseAbsente, reponseFlux } from "@/lib/reponses-export";

export const dynamic = "force-static";

export function GET() {
  const dole = getDole();
  const creations = getDatesCreationDossiers();
  if (dole === null || creations === null) throw erreurBaseAbsente();
  const navette = dole.navette.map((d) => ({ ...d, date_creation: creations.get(d.dossier_id) ?? null }));
  return reponseFlux(FLUX[1], entreesDossiers(navette), [dole.meta]);
}
