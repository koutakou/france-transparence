/**
 * GET /api/budget-mensuel.provenance.txt : provenance de /api/budget-mensuel.csv (sources
 * amont, licence, date des données, URL, colonnes, format), générée au build
 * depuis meta_sources. Base absente au build : erreur franche.
 */
import { CSV_BUDGET_MENSUEL } from "@/lib/exports-csv";
import { reponseProvenance } from "@/lib/reponses-export";

export const dynamic = "force-static";

export function GET() {
  return reponseProvenance(CSV_BUDGET_MENSUEL);
}
