/**
 * GET /api/elus.json — export statique généré au build : le répertoire des
 * élus COMPLET (RNE × open data AN × open data Sénat), en champs publics
 * COMPACTS : identité, identifiants publics (uid AN, matricule Sénat), lien
 * HATVP et types de mandat. Les clés vides sont omises (documenté dans meta).
 *
 * Pourquoi compact : le dump intégral (mandats détaillés + profession) pèse
 * ~14 Mo — intenable en fichier statique quotidien. Le détail des mandats
 * reste visible sur les fiches élus et dans le RNE amont. La recherche
 * (ex-« ?q= ») se fait chez le réutilisateur.
 *
 * Base absente au build → erreur franche : on ne publie JAMAIS un snapshot
 * vide (la CI ne déploie pas, le site de la veille reste servi tel quel).
 */
import { NextResponse } from "next/server";
import { getElusExport, getMetaSourcesParIds, TYPES_MANDAT } from "@/lib/queries/donnees";

export const dynamic = "force-static";

/** Sources amont de la table elus (pipelines parlement + intégrité). */
const SOURCES_ELUS = ["S17", "S5-AMO10", "S6-ODSEN", "S14"];

export async function GET() {
  const elus = getElusExport();
  if (elus === null) {
    throw new Error(
      "Base absente au build — lancer make ingest (ou poser FRANCE_DB_PATH) avant next build.",
    );
  }
  const sources = getMetaSourcesParIds(SOURCES_ELUS) ?? [];
  return NextResponse.json({
    meta: {
      description:
        "Répertoire complet des élus (champs publics compacts, tous issus de l'open data) : identité, identifiants AN/Sénat, lien HATVP, types de mandat. Clés absentes = non renseigné. Le détail des mandats (communes, dates…) reste sur les fiches élus et dans le RNE amont ; conseillers municipaux non nominatifs (agrégats départementaux seulement). Snapshot statique régénéré à chaque build.",
      total: elus.length,
      types_mandats_possibles: TYPES_MANDAT,
      licence_agregats: "Licence Ouverte 2.0 (agrégats France Transparence)",
      sources: sources.map((s) => ({
        source_id: s.source_id,
        nom: s.nom,
        url: s.url,
        licence: s.licence,
        date_donnees: s.date_donnees,
      })),
    },
    donnees: elus,
  });
}
