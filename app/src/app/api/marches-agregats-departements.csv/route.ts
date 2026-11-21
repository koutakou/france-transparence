/**
 * GET /api/marches-agregats-departements.csv : version tableur de la partie « departements » de /api/marches-agregats.json,
 * générée au build. Colonnes, sources et format : lib/exports-csv.ts et
 * lib/csv.ts. Provenance publiée à côté (/api/marches-agregats-departements.provenance.txt).
 *
 * Base absente au build : erreur franche, comme les routes JSON.
 */
import { CSV_MARCHES_DEPARTEMENTS } from "@/lib/exports-csv";
import { getMarchesAgregats } from "@/lib/queries/donnees";
import { reponseCsv } from "@/lib/reponses-export";

export const dynamic = "force-static";

export function GET() {
  return reponseCsv(CSV_MARCHES_DEPARTEMENTS, getMarchesAgregats()?.departements ?? null);
}
