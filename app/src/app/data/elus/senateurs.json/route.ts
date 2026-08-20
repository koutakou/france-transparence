import { getSenateurs } from "@/lib/queries/elus";

/**
 * Fragment statique : les 348 sénateurs (mêmes colonnes que le tableau de
 * /elus). Chargé au premier geste (filtre, « tout afficher ») et filtré
 * côté client. Généré au build, reconstruit chaque jour avec le site.
 */
export const dynamic = "force-static";

export async function GET() {
  return Response.json(getSenateurs() ?? null);
}
