/**
 * GET /api/meta.json — export statique généré au build : le catalogue
 * meta_sources complet (25 sources tracées) avec nom, URL amont, licence,
 * fréquence, date des données, date d'ingestion, volumétrie, notes et
 * fraîcheur relative calculée (règle documentée sur /donnees).
 *
 * `meta.genere_le` (ISO, date du build) est le témoin de fraîcheur du
 * déploiement : le site est reconstruit après chaque ingestion quotidienne.
 *
 * Base absente au build → erreur franche : on ne publie JAMAIS un snapshot
 * vide (la CI ne déploie pas, le site de la veille reste servi tel quel).
 */
import { NextResponse } from "next/server";
import { getCatalogueSources, getDerniereIngestion } from "@/lib/queries/donnees";

export const dynamic = "force-static";

export async function GET() {
  const sources = getCatalogueSources();
  if (sources === null) {
    throw new Error(
      "Base absente au build — lancer make ingest (ou poser FRANCE_DB_PATH) avant next build.",
    );
  }
  return NextResponse.json({
    meta: {
      description:
        "Catalogue des sources ingérées par France Transparence (table meta_sources) — la licence et la date des données de chaque source figurent dans sa ligne. Snapshot statique régénéré à chaque build.",
      total_sources: sources.length,
      derniere_ingestion: getDerniereIngestion(),
      licence_agregats: "Licence Ouverte 2.0 (agrégats France Transparence)",
      regle_fraicheur:
        "âge = aujourd'hui − date_donnees, comparé à la période P de la fréquence promise (quotidienne 1 j, hebdomadaire 7 j, mensuelle 30 j, trimestrielle 91 j) : verte si âge ≤ 2×P+2 j, orange si ≤ 4×P+7 j, rouge au-delà ; « millesime » pour les fréquences sans âge attendu pertinent (décalage structurel documenté).",
      genere_le: new Date().toISOString(),
    },
    donnees: sources,
  });
}
