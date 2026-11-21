/**
 * GET /api/marches-top-acheteurs.provenance.txt : provenance de /api/marches-top-acheteurs.csv (sources
 * amont, licence, date des données, URL, colonnes, format), générée au build
 * depuis meta_sources. Base absente au build : erreur franche.
 */
import { CSV_TOP_ACHETEURS } from "@/lib/exports-csv";
import { reponseProvenance } from "@/lib/reponses-export";

export const dynamic = "force-static";

export function GET() {
  return reponseProvenance(CSV_TOP_ACHETEURS);
}
