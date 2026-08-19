/**
 * GET /api/elus?q=&mandat=&limit= — recherche dans le répertoire des élus
 * (36 018 lignes, RNE × open data AN × open data Sénat). Champs PUBLICS
 * uniquement : identité, profession, identifiants publics (uid AN,
 * matricule Sénat), lien HATVP, mandats (JSON).
 *
 * Paramètres (tous optionnels) :
 * - q      : sous-chaîne du nom ou du prénom, 2 à 80 caractères
 * - mandat : maire | president_epci | depute | senateur |
 *            president_conseil_departemental | president_conseil_regional
 * - limit  : 1 à 500 (défaut 50)
 * Erreurs : 400 paramètre invalide, 503 base non construite.
 */
import { NextResponse } from "next/server";
import {
  estTypeMandat,
  getMetaSourcesParIds,
  rechercheElus,
  TYPES_MANDAT,
  type TypeMandat,
} from "@/lib/queries/donnees";

export const dynamic = "force-dynamic";

const CACHE_OK = "public, max-age=300, stale-while-revalidate=3600";
/** Sources amont de la table elus (pipelines parlement + intégrité). */
const SOURCES_ELUS = ["S17", "S5-AMO10", "S6-ODSEN", "S14"];

function erreur(status: number, message: string) {
  return NextResponse.json(
    { erreur: message },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;

  const qBrut = params.get("q");
  let q: string | undefined;
  if (qBrut !== null) {
    q = qBrut.trim();
    if (q.length < 2 || q.length > 80) {
      return erreur(400, "Paramètre q invalide : 2 à 80 caractères.");
    }
  }

  const mandatBrut = params.get("mandat");
  let mandat: TypeMandat | undefined;
  if (mandatBrut !== null) {
    if (!estTypeMandat(mandatBrut)) {
      return erreur(400, `Paramètre mandat invalide : ${TYPES_MANDAT.join(", ")}.`);
    }
    mandat = mandatBrut;
  }

  const limitBrut = params.get("limit");
  let limite = 50;
  if (limitBrut !== null) {
    limite = Number.parseInt(limitBrut, 10);
    if (!Number.isFinite(limite) || String(limite) !== limitBrut || limite < 1 || limite > 500) {
      return erreur(400, "Paramètre limit invalide : entier entre 1 et 500.");
    }
  }

  const elus = rechercheElus({ q, mandat, limite });
  if (elus === null) {
    return erreur(503, "Base de données absente — lancer make ingest pour construire data/france.db.");
  }
  const sources = getMetaSourcesParIds(SOURCES_ELUS) ?? [];

  return NextResponse.json(
    {
      meta: {
        description:
          "Répertoire des élus (champs publics uniquement, tous issus de l'open data). Conseillers municipaux non nominatifs (agrégats départementaux seulement).",
        filtres: { q: q ?? null, mandat: mandat ?? null, limit: limite },
        nb_resultats: elus.length,
        licence_agregats: "Licence Ouverte 2.0 (agrégats France Transparence)",
        sources: sources.map((s) => ({
          source_id: s.source_id,
          nom: s.nom,
          url: s.url,
          licence: s.licence,
          date_donnees: s.date_donnees,
        })),
      },
      donnees: elus.map((e) => {
        let mandats: unknown = null;
        if (e.mandats) {
          try {
            mandats = JSON.parse(e.mandats);
          } catch {
            mandats = null;
          }
        }
        return { ...e, mandats };
      }),
    },
    { headers: { "Cache-Control": CACHE_OK } },
  );
}
