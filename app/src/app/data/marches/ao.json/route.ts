import { getAoParFamille } from "@/lib/queries/marches";

/**
 * Fragment statique : appels d'offres BOAMP en cours, pré-agrégés PAR
 * FAMILLE (clé `""` = toutes) — total, part sans montant publié, et la
 * réserve d'échéances (RESERVE_HEURES depuis la construction, puis quelques-
 * unes au-delà, lib/echeances.ts). Le filtre par famille de /marches
 * pioche dans ce fichier côté client. Instantané re-filtré (annulations,
 * échéances passées) à chaque construction quotidienne du site ; le
 * navigateur retire en plus les échéances passées à son heure.
 */
export const dynamic = "force-static";

export async function GET() {
  return Response.json(getAoParFamille() ?? null);
}
