/**
 * GET /api/meta.csv : version tableur de /api/meta.json (sans la fraîcheur calculée, qui dépend du jour de lecture),
 * générée au build. Colonnes, sources et format : lib/exports-csv.ts et
 * lib/csv.ts. Provenance publiée à côté (/api/meta.provenance.txt).
 *
 * Base absente au build : erreur franche, comme les routes JSON.
 */
import { CSV_META } from "@/lib/exports-csv";
import { getCatalogueSources } from "@/lib/queries/donnees";
import { reponseCsv } from "@/lib/reponses-export";

export const dynamic = "force-static";

export function GET() {
  return reponseCsv(CSV_META, getCatalogueSources(new Date()));
}
