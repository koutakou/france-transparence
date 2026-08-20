import { getDonneesElections } from "@/lib/queries/elections";

/**
 * Fragment statique : le bloc participation électorale COMPLET (7 scrutins,
 * effectifs bruts par département et par commune, libellés, fraîcheur S26).
 * Le HTML de /collectivites n'embarque que le scrutin initial et les résumés
 * des boutons (`getDonneesElectionsInline`) ; ce fragment est chargé au
 * premier changement de scrutin, puis servi depuis la mémoire (promesse
 * mémoïsée dans `ParticipationElectorale`).
 */
export const dynamic = "force-static";

export async function GET() {
  return Response.json(getDonneesElections() ?? null);
}
