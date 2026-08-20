/**
 * GET /api/marches-agregats.json — export statique généré au build :
 * agrégats de marchés publics pré-calculés à l'ingestion (source S1, DECP
 * consolidées) :
 * - departements : decp_agg_departement (12 mois glissants, montants écrêtés
 *   à 100 M€/marché, montant_total NULL = aucun montant connu) ;
 * - mois : decp_agg_mois (36 mois glissants).
 *
 * Mentions obligatoires reprises dans meta (montants d'accords-cadres =
 * maximums, latence légale ≤ 2 mois, crédit decp-processing).
 *
 * Base absente au build → erreur franche : on ne publie JAMAIS un snapshot
 * vide (la CI ne déploie pas, le site de la veille reste servi tel quel).
 */
import { NextResponse } from "next/server";
import { getMarchesAgregats, getMetaSourcesParIds } from "@/lib/queries/donnees";

export const dynamic = "force-static";

export async function GET() {
  const agregats = getMarchesAgregats();
  if (agregats === null) {
    throw new Error(
      "Base absente au build — lancer make ingest (ou poser FRANCE_DB_PATH) avant next build.",
    );
  }
  const s1 = (getMetaSourcesParIds(["S1"]) ?? [])[0];
  return NextResponse.json({
    meta: {
      description:
        "Agrégats DECP par département (12 mois, montants écrêtés à 100 M€/marché ; NULL = aucun montant connu) et par mois (36 mois). Marchés notifiés = engagements contractuels, pas des paiements ; montants d'accords-cadres = maximums ; latence légale de publication jusqu'à 2 mois (données en cours de consolidation). Snapshot statique régénéré à chaque build.",
      credit:
        "Consolidation communautaire decp-processing (Colin Maudry) — à créditer en cas de réutilisation.",
      source: s1
        ? {
            source_id: s1.source_id,
            nom: s1.nom,
            url: s1.url,
            licence: s1.licence,
            date_donnees: s1.date_donnees,
            date_ingestion: s1.date_ingestion,
            notes: s1.notes,
          }
        : null,
      licence_agregats: "Licence Ouverte 2.0 (agrégats France Transparence)",
    },
    donnees: agregats,
  });
}
