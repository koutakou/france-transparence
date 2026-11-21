/**
 * GET /api/marches-agregats-mois.provenance.txt : provenance de /api/marches-agregats-mois.csv (sources
 * amont, licence, date des données, URL, colonnes, format), générée au build
 * depuis meta_sources. Base absente au build : erreur franche.
 */
import { CSV_MARCHES_MOIS } from "@/lib/exports-csv";
import { reponseProvenance } from "@/lib/reponses-export";

export const dynamic = "force-static";

export function GET() {
  return reponseProvenance(CSV_MARCHES_MOIS);
}
