/**
 * GET /api/alertes?type=&gravite=&limit= — les alertes calculées à
 * l'ingestion (table `alertes`), chacune avec sa règle de calcul, sa base
 * légale et son URL source.
 *
 * Paramètres (tous optionnels) :
 * - type    : type exact (ex. lobbying_defaut_declaration) — [A-Za-z0-9_]
 * - gravite : haute | moyenne | info
 * - limit   : 1 à 500 (défaut 100)
 * Erreurs : 400 paramètre invalide, 503 base non construite.
 */
import { NextResponse } from "next/server";
import {
  estGraviteAlerte,
  getAlertesPage,
  getAlertesStats,
  type GraviteAlerte,
} from "@/lib/queries/alertes";
import { getMetaSourcesParIds } from "@/lib/queries/donnees";

export const dynamic = "force-dynamic";

const CACHE_OK = "public, max-age=300, stale-while-revalidate=3600";
/** Sources amont des trois domaines d'alertes (A1_*, lobbying_*, financement_*). */
const SOURCES_ALERTES = ["S14", "S17", "S4", "S25", "S29"];

function erreur(status: number, message: string) {
  return NextResponse.json(
    { erreur: message },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;

  const typeBrut = params.get("type");
  if (typeBrut !== null && !/^[A-Za-z0-9_]{1,64}$/.test(typeBrut)) {
    return erreur(400, "Paramètre type invalide : lettres, chiffres et _ uniquement (64 caractères max).");
  }
  const type = typeBrut ?? undefined;

  const graviteBrute = params.get("gravite");
  let gravite: GraviteAlerte | undefined;
  if (graviteBrute !== null) {
    if (!estGraviteAlerte(graviteBrute)) {
      return erreur(400, "Paramètre gravite invalide : haute, moyenne ou info.");
    }
    gravite = graviteBrute;
  }

  const limitBrut = params.get("limit");
  let limite = 100;
  if (limitBrut !== null) {
    limite = Number.parseInt(limitBrut, 10);
    if (!Number.isFinite(limite) || String(limite) !== limitBrut || limite < 1 || limite > 500) {
      return erreur(400, "Paramètre limit invalide : entier entre 1 et 500.");
    }
  }

  const stats = getAlertesStats();
  const page = getAlertesPage({ type, gravite, page: 1, limite });
  if (stats === null || page === null) {
    return erreur(503, "Base de données absente — lancer make ingest pour construire data/france.db.");
  }
  const sources = getMetaSourcesParIds(SOURCES_ALERTES) ?? [];

  return NextResponse.json(
    {
      meta: {
        description:
          "Alertes calculées à l'ingestion des données publiques — chaque alerte cite sa règle et sa base légale ; les retards HATVP « présumés » sont des agrégats non nominatifs.",
        dernier_calcul: stats.derniereDateCalcul,
        total_filtre: page.total,
        total_base: stats.total,
        filtres: { type: type ?? null, gravite: gravite ?? null, limit: limite },
        licence_agregats: "Licence Ouverte 2.0 (agrégats France Transparence)",
        sources: sources.map((s) => ({
          source_id: s.source_id,
          nom: s.nom,
          url: s.url,
          licence: s.licence,
          date_donnees: s.date_donnees,
        })),
      },
      donnees: page.alertes,
    },
    { headers: { "Cache-Control": CACHE_OK } },
  );
}
