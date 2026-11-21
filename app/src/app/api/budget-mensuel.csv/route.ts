/**
 * GET /api/budget-mensuel.csv : version tableur de /api/budget-mensuel.json,
 * générée au build, ruptures de périmètre comprises (colonnes
 * rupture_perimetre_*). Colonnes, sources et format : lib/exports-csv.ts et
 * lib/csv.ts. Provenance publiée à côté (/api/budget-mensuel.provenance.txt).
 *
 * Base absente au build : erreur franche, comme les routes JSON.
 */
import { CSV_BUDGET_MENSUEL } from "@/lib/exports-csv";
import { annoterRuptures, getRupturesBudget } from "@/lib/queries/budget-ruptures";
import { getBudgetMensuelComplet } from "@/lib/queries/donnees";
import { reponseCsv } from "@/lib/reponses-export";

export const dynamic = "force-static";

export function GET() {
  const lignes = getBudgetMensuelComplet();
  return reponseCsv(
    CSV_BUDGET_MENSUEL,
    lignes === null ? null : annoterRuptures(lignes, getRupturesBudget()),
  );
}
