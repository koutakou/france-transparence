/**
 * GET /api/lobbying-marches.provenance.txt : provenance de /api/lobbying-marches.csv (sources
 * amont, licence, date des données, URL, colonnes, format), générée au build
 * depuis meta_sources. Base absente au build : erreur franche.
 */
import { CSV_LOBBYING_MARCHES } from "@/lib/exports-csv";
import { reponseProvenance } from "@/lib/reponses-export";

export const dynamic = "force-static";

export function GET() {
  return reponseProvenance(CSV_LOBBYING_MARCHES);
}
