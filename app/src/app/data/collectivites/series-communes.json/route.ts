import { getSeriesCommunes } from "@/lib/queries/collectivites";

/**
 * Fragment statique : séries pluriannuelles 2018-2025 des 200 communes les
 * plus peuplées (fonctionnement / investissement en €/habitant, budgets
 * principaux) + médianes d'€/habitant par strate démographique. Chargé au
 * premier clic sur une commune dans /collectivites, puis servi depuis la
 * mémoire — le HTML de la page n'embarque aucune série. Fragment séparé de
 * /data/collectivites/series.json : un clic sur une région ne paie pas les
 * communes, et réciproquement.
 */
export const dynamic = "force-static";

export async function GET() {
  return Response.json(getSeriesCommunes() ?? null);
}
