/**
 * GET /api/alertes.json — export statique généré au build : TOUTES les
 * alertes calculées à l'ingestion (table `alertes`, dump complet), chacune
 * avec sa règle de calcul, sa base légale et son URL source. Le filtrage
 * (type, gravité) se fait chez le réutilisateur — plus de paramètres d'URL.
 *
 * Base absente au build → erreur franche : on ne publie JAMAIS un snapshot
 * vide (la CI ne déploie pas, le site de la veille reste servi tel quel).
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
      "Base absente au build — lancer make ingest (ou poser FRANCE_DB_PATH) avant next build.",
    );
  }
  const sources = getMetaSourcesParIds(SOURCES_ALERTES) ?? [];
  return NextResponse.json({
    meta: {
      description:
        "Alertes calculées à l'ingestion des données publiques — chaque alerte cite sa règle et sa base légale ; les retards HATVP « présumés » sont des agrégats non nominatifs. Snapshot statique complet régénéré à chaque build.",
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
