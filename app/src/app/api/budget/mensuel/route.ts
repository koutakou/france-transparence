/**
 * GET /api/budget/mensuel?annee=&ligne= — situations mensuelles budgétaires
 * de l'État (source S13, DGFiP), 26 lignes par mois, montants en euros =
 * CUMULS depuis le 1er janvier (montant_mois = flux du mois seul).
 *
 * Paramètres (optionnels, combinables) :
 * - annee : année à quatre chiffres (série 2013 → courant)
 * - ligne : ligne_id exact (ex. depenses/budget-general/depenses-de-personnel)
 * Sans paramètre : photographie du dernier mois publié (26 lignes).
 * Erreurs : 400 paramètre invalide, 503 base non construite.
 */
import { NextResponse } from "next/server";
import {
  getBudgetDernierMois,
  getBudgetMensuel,
  getMetaSourcesParIds,
} from "@/lib/queries/donnees";

export const dynamic = "force-dynamic";

const CACHE_OK = "public, max-age=300, stale-while-revalidate=3600";

function erreur(status: number, message: string) {
  return NextResponse.json(
    { erreur: message },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;

  const anneeBrute = params.get("annee");
  let annee: number | undefined;
  if (anneeBrute !== null) {
    if (!/^\d{4}$/.test(anneeBrute)) {
      return erreur(400, "Paramètre annee invalide : quatre chiffres (ex. 2026).");
    }
    annee = Number.parseInt(anneeBrute, 10);
  }

  const ligneBrute = params.get("ligne");
  let ligne: string | undefined;
  if (ligneBrute !== null) {
    if (!/^[a-z0-9/-]{1,150}$/.test(ligneBrute)) {
      return erreur(
        400,
        "Paramètre ligne invalide : ligne_id en minuscules (lettres, chiffres, - et /), 150 caractères max.",
      );
    }
    ligne = ligneBrute;
  }

  const lignes = getBudgetMensuel({ annee, ligne });
  if (lignes === null) {
    return erreur(503, "Base de données absente — lancer make ingest pour construire data/france.db.");
  }
  const s13 = (getMetaSourcesParIds(["S13"]) ?? [])[0];

  return NextResponse.json(
    {
      meta: {
        description:
          "Situations mensuelles budgétaires de l'État (26 lignes par grands titres). Montants en euros : montant_cumul = cumul depuis le 1er janvier, montant_mois = flux mensuel, colonnes _n1 = même période N−1. Mois infra-annuels provisoires ; pas de détail mission/programme dans cette source ; pas de temps réel (~5-7 semaines de décalage).",
        dernier_mois_publie: getBudgetDernierMois(),
        filtres: { annee: annee ?? null, ligne: ligne ?? null },
        nb_resultats: lignes.length,
        source: s13
          ? {
              source_id: s13.source_id,
              nom: s13.nom,
              url: s13.url,
              licence: s13.licence,
              date_donnees: s13.date_donnees,
              date_ingestion: s13.date_ingestion,
            }
          : null,
        licence_agregats: "Licence Ouverte 2.0 (agrégats France Transparence)",
      },
      donnees: lignes,
    },
    { headers: { "Cache-Control": CACHE_OK } },
  );
}
