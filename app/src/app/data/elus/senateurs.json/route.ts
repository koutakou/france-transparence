import { getSenateurs } from "@/lib/queries/elus";

/**
 * Fragment statique : les sénateurs en exercice (mêmes colonnes que le
 * tableau de /elus, y compris le taux calculé ici). Chargé au premier
 * geste (filtre, « tout afficher ») et filtré côté client. Généré au
 * build, reconstruit chaque jour avec le site.
 */
export const dynamic = "force-static";

export async function GET() {
  return Response.json(getSenateurs() ?? null);
}
