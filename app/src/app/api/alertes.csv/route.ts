/**
 * GET /api/alertes.csv : version tableur de /api/alertes.json,
 * générée au build. Colonnes, sources et format : lib/exports-csv.ts et
 * lib/csv.ts. Provenance publiée à côté (/api/alertes.provenance.txt).
 *
 * Base absente au build : erreur franche, comme les routes JSON.
 */
import { CSV_ALERTES } from "@/lib/exports-csv";
import { getAlertesToutes } from "@/lib/queries/alertes";
import { reponseCsv } from "@/lib/reponses-export";

export const dynamic = "force-static";

export function GET() {
  return reponseCsv(CSV_ALERTES, getAlertesToutes());
}
