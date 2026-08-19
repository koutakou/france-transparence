import { getAoParFamille } from "@/lib/queries/marches";

/**
 * Fragment statique : appels d'offres BOAMP en cours, pré-agrégés PAR
 * FAMILLE (clé `""` = toutes) — total, part sans montant publié, 20
 * échéances les plus proches. Le filtre par famille de /marches pioche
 * dans ce fichier côté client. Instantané re-filtré (annulations,
 * échéances passées) à chaque construction quotidienne du site.
 */
export const dynamic = "force-static";

export async function GET() {
  return Response.json(getAoParFamille() ?? null);
}
