/**
 * GET /api/marches-top-titulaires.csv : version tableur de le tableau « Top titulaires » de /marches,
 * générée au build. Colonnes, sources et format : lib/exports-csv.ts et
 * lib/csv.ts. Provenance publiée à côté (/api/marches-top-titulaires.provenance.txt).
 *
 * Base absente au build : erreur franche, comme les routes JSON.
 */
import { CSV_TOP_TITULAIRES } from "@/lib/exports-csv";
import { getTopsMarches } from "@/lib/queries/marches";
import { reponseCsv } from "@/lib/reponses-export";

export const dynamic = "force-static";

export function GET() {
  return reponseCsv(CSV_TOP_TITULAIRES, getTopsMarches()?.titulaires ?? null);
}
