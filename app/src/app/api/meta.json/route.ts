/**
 * GET /api/meta.json — export statique généré au build : le catalogue
 * meta_sources complet (28 sources tracées) avec nom, URL amont, licence,
 * fréquence, date des données, date d'ingestion, volumétrie, notes et
 * fraîcheur relative calculée : niveau, âge, unité de comptage et les deux
 * seuils calibrés pour la source (règle et seuils détaillés sur /donnees).
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
        "âge = aujourd'hui − date_donnees, comparé à DEUX seuils calibrés source par source (et non à une période déduite de la fréquence promise) : « a_jour » sous le seuil de retard, « a_surveiller » entre les deux seuils, « en_retard » au-delà du seuil d'alerte, « attente_edition » quand le dépassement excède à son tour la largeur de la bande de surveillance, « non_calibre » si la source n'a pas de ligne au référentiel. Chaque ligne porte ses propres seuils (seuilRetardJours, seuilAlerteJours) et l'unité dans laquelle l'âge est compté (unite : « jc » jours calendaires, « jo » jours ouvrés — jours fériés français exclus, comme le moniteur du serveur). « attente_edition » décrit la SOURCE et non le site : à la date de génération, aucune édition plus récente n'a été publiée en amont.",
      genere_le: new Date().toISOString(),
    },
    donnees: sources,
  });
}
