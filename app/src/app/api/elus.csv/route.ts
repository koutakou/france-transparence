/**
 * GET /api/elus.csv : version tableur de /api/elus.json,
 * générée au build. Colonnes, sources et format : lib/exports-csv.ts et
 * lib/csv.ts. Provenance publiée à côté (/api/elus.provenance.txt).
 *
 * Base absente au build : erreur franche, comme les routes JSON.
 */
import { CSV_ELUS } from "@/lib/exports-csv";
import { getElusExport } from "@/lib/queries/donnees";
import { reponseCsv } from "@/lib/reponses-export";

export const dynamic = "force-static";

export function GET() {
  return reponseCsv(CSV_ELUS, getElusExport());
}
