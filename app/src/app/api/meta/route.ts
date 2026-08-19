/**
 * GET /api/meta — le catalogue meta_sources complet (25 sources tracées) :
 * nom, URL amont, licence, fréquence, date des données, date d'ingestion,
 * volumétrie, notes, plus la fraîcheur relative calculée (règle documentée
 * sur /donnees et dans lib/queries/donnees.ts).
 *
 * Lecture seule, aucun paramètre. 503 si la base n'est pas construite.
 */
import { NextResponse } from "next/server";
import { getCatalogueSources, getDerniereIngestion } from "@/lib/queries/donnees";

export const dynamic = "force-dynamic";

const CACHE_OK = "public, max-age=300, stale-while-revalidate=3600";

export async function GET() {
  const sources = getCatalogueSources();
  if (sources === null) {
    return NextResponse.json(
      { erreur: "Base de données absente — lancer make ingest pour construire data/france.db." },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
  return NextResponse.json(
    {
      meta: {
        description:
          "Catalogue des sources ingérées par France Transparence (table meta_sources) — la licence et la date des données de chaque source figurent dans sa ligne.",
        total_sources: sources.length,
        derniere_ingestion: getDerniereIngestion(),
        licence_agregats: "Licence Ouverte 2.0 (agrégats France Transparence)",
        regle_fraicheur:
          "âge = aujourd'hui − date_donnees, comparé à la période P de la fréquence promise (quotidienne 1 j, hebdomadaire 7 j, mensuelle 30 j, trimestrielle 91 j) : verte si âge ≤ 2×P+2 j, orange si ≤ 4×P+7 j, rouge au-delà ; « millesime » pour les fréquences sans âge attendu pertinent (décalage structurel documenté).",
        genere_le: new Date().toISOString(),
      },
      donnees: sources,
    },
    { headers: { "Cache-Control": CACHE_OK } },
  );
}
