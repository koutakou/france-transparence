import { construireIndexRecherche } from "@/lib/recherche-index";

/**
 * Index de recherche pré-généré (élus + entités) — chargé par la SearchBox
 * à la première frappe, interrogé côté client. Format et contrat fiches :
 * voir `src/lib/recherche-index.ts`. Reconstruit chaque jour avec le site.
 */
export const dynamic = "force-static";

export async function GET() {
  return Response.json(construireIndexRecherche() ?? null);
}
