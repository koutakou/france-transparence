import { getEntitesEnDefaut, type EntiteEnDefaut } from "@/lib/queries/lobbying";

/**
 * Fragment statique : liste COMPLÈTE des entités inscrites sur la liste
 * officielle HATVP des représentants d'intérêts en défaut de déclaration
 * (316 au 19/08/2026), tri alphabétique — même requête et même tri que la
 * page /lobbying, qui n'embarque que les 50 premières lignes dans son HTML
 * et charge ce fragment au clic « Tout afficher ».
 *
 * `null` si la base n'est pas encore construite — le composant client
 * affiche alors un message honnête (les 50 premières restent lisibles).
 */
export const dynamic = "force-static";

export type DefautsFragment = {
  entites: EntiteEnDefaut[];
};

export async function GET() {
  const entites = getEntitesEnDefaut();
  if (!entites) return Response.json(null);
  const fragment: DefautsFragment = { entites };
  return Response.json(fragment);
}
