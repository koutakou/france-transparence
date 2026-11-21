/**
 * GET /api/lobbying-marches.csv : version tableur de la partie « titulaires » de /api/lobbying-marches.json,
 * générée au build. Colonnes, sources et format : lib/exports-csv.ts et
 * lib/csv.ts. Provenance publiée à côté (/api/lobbying-marches.provenance.txt).
 *
 * Base absente au build : erreur franche, comme les routes JSON.
 */
import { CSV_LOBBYING_MARCHES } from "@/lib/exports-csv";
import { getCroisementLobbyingMarches } from "@/lib/queries/croisement-lobbying-marches";
import { reponseCsv } from "@/lib/reponses-export";

export const dynamic = "force-static";

export function GET() {
  return reponseCsv(CSV_LOBBYING_MARCHES, getCroisementLobbyingMarches()?.titulaires ?? null);
}
