import { getDeputes } from "@/lib/queries/elus";

/**
 * Fragment statique : les 577 députés (mêmes colonnes que le tableau de
 * /elus). La page n'embarque que le premier écran ; ce fichier est chargé
 * au premier geste (filtre, « tout afficher ») et filtré côté client.
 * Généré au build, reconstruit chaque jour avec le site.
 */
export const dynamic = "force-static";

export async function GET() {
  return Response.json(getDeputes() ?? null);
}
