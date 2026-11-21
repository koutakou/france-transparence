/**
 * GET /api/alertes.json — export statique généré au build : TOUTES les
 * alertes calculées à l'ingestion (table `alertes`, dump complet), chacune
 * avec sa règle de calcul, sa base légale et son URL source. Le filtrage
 * (type, gravité) se fait chez le réutilisateur — plus de paramètres d'URL.
 *
 * Base absente au build → erreur franche : on ne publie JAMAIS un snapshot
 * vide (le build échoue, `ft-deploy` ne bascule pas : la release précédente
 * reste servie telle quelle).
 */
import { NextResponse } from "next/server";
import { getAlertesStats, getAlertesToutes } from "@/lib/queries/alertes";
import { getMetaSourcesParIds } from "@/lib/queries/donnees";

export const dynamic = "force-static";

/** Sources amont des trois domaines d'alertes (A1_*, lobbying_*, financement_*). */
const SOURCES_ALERTES = ["S14", "S17", "S4", "S25", "S29"];

export async function GET() {
  const alertes = getAlertesToutes();
  const stats = getAlertesStats();
  if (alertes === null || stats === null) {
    throw new Error(
      "Base absente au build : lancer make ingest (ou poser FRANCE_DB_PATH) avant next build.",
    );
  }
  const sources = getMetaSourcesParIds(SOURCES_ALERTES) ?? [];
  return NextResponse.json({
    meta: {
      description:
        "Alertes calculées à l'ingestion des données publiques. Chaque alerte cite sa règle et sa base légale. date_calcul est l'instant du calcul, date_fait la date du fait selon la source (null quand la source ne la donne pas). Les comptes de campagne rejetés ou approuvés après réformation ne sont pas dans cet export : ils sont comptés sans nom sur /financement, qui renvoie aux décisions du Conseil constitutionnel sur conseil-constitutionnel.fr. Les déclarations HATVP au statut « En cours » plus de 2 mois après l'entrée en fonction sont des agrégats non nominatifs, jamais sous 3 personnes. Snapshot statique complet régénéré à chaque build.",
      dernier_calcul: stats.derniereDateCalcul,
      total: alertes.length,
      licence_agregats: "Licence Ouverte 2.0 (agrégats France Transparence)",
      sources: sources.map((s) => ({
        source_id: s.source_id,
        nom: s.nom,
        url: s.url,
        licence: s.licence,
        date_donnees: s.date_donnees,
      })),
    },
    donnees: alertes,
  });
}
