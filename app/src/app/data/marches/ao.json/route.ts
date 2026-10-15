import { getAoParFamille } from "@/lib/queries/marches";

/**
 * Fragment statique : appels d'offres BOAMP en cours, pré-agrégés PAR
 * FAMILLE (clé `""` = toutes) — total, part sans montant publié, et les
 * AO_LIVREES échéances les plus proches. Le filtre par famille de /marches
 * pioche dans ce fichier côté client. Instantané re-filtré (annulations,
 * échéances passées) à chaque construction quotidienne du site ; le
 * navigateur retire en plus les échéances passées à son heure.
 */
export const dynamic = "force-static";

export async function GET() {
  return Response.json(getAoParFamille() ?? null);
}
