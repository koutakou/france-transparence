import { getReserveAoAccueil } from "@/lib/queries/accueil";

/**
 * Fragment statique : réserve d'appels d'offres « proches de la clôture » de
 * l'accueil — toutes les échéances des RESERVE_HEURES qui suivent la
 * construction, puis quelques-unes de plus (lib/echeances.ts). L'accueil
 * n'en rend que 4 dans son HTML ; dès que l'une est passée à l'heure du
 * visiteur, il charge ce fichier et y prend les premières encore ouvertes.
 * Base absente → `null`, comme ao.json.
 */
export const dynamic = "force-static";

export async function GET() {
  return Response.json(getReserveAoAccueil());
}
