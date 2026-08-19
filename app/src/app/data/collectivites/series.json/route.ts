import { getToutesSeries } from "@/lib/queries/collectivites";

/**
 * Fragment statique : séries pluriannuelles (fonctionnement,
 * investissement, épargne brute) des 17 régions et 97 conseils
 * départementaux, indexées par code. Chargé au premier clic sur une
 * collectivité dans /collectivites, puis servi depuis la mémoire.
 */
export const dynamic = "force-static";

export async function GET() {
  return Response.json(getToutesSeries() ?? null);
}
