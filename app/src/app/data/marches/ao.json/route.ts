import { getAoParFamille } from "@/lib/queries/marches";

/**
 * Fragment statique chargé AU CLIC sur une famille de /marches : appels
 * d'offres BOAMP en cours pré-agrégés PAR FAMILLE — total, part sans montant
 * publié, et la réserve d'échéances (RESERVE_HEURES depuis la construction,
 * puis quelques-unes au-delà, lib/echeances.ts). La vue « Toutes » n'y est
 * pas : ses totaux sont dans le HTML, ses échéances dans les tranches
 * horaires /data/marches/ao-toutes/<heure>.json. Instantané re-filtré
 * (annulations, échéances passées) à chaque construction quotidienne du
 * site ; le navigateur retire en plus les échéances passées à son heure.
 */
export const dynamic = "force-static";

export async function GET() {
  return Response.json(getAoParFamille() ?? null);
}
