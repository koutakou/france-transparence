/**
 * GET /api/budget-mensuel.json — export statique généré au build :
 * situations mensuelles budgétaires de l'État (source S13, DGFiP), SÉRIE
 * COMPLÈTE 2013 → dernier mois publié (26 lignes par mois, montants en
 * euros : montant_cumul = cumul depuis le 1er janvier, montant_mois = flux
 * du mois seul). Le filtrage par année ou ligne se fait chez le
 * réutilisateur — plus de paramètres d'URL.
 *
 * Base absente au build → erreur franche : on ne publie JAMAIS un snapshot
 * vide (la CI ne déploie pas, le site de la veille reste servi tel quel).
 */
import { NextResponse } from "next/server";
import {
  getBudgetDernierMois,
  getBudgetMensuelComplet,
  getMetaSourcesParIds,
} from "@/lib/queries/donnees";

export const dynamic = "force-static";

export async function GET() {
  const lignes = getBudgetMensuelComplet();
  if (lignes === null) {
    throw new Error(
      "Base absente au build — lancer make ingest (ou poser FRANCE_DB_PATH) avant next build.",
    );
  }
  const s13 = (getMetaSourcesParIds(["S13"]) ?? [])[0];
  return NextResponse.json({
    meta: {
      description:
        "Situations mensuelles budgétaires de l'État (26 lignes par grands titres), série complète 2013 → dernier mois publié. Montants en euros : montant_cumul = cumul depuis le 1er janvier, montant_mois = flux mensuel, colonnes _n1 = même période N−1. Mois infra-annuels provisoires ; pas de détail mission/programme dans cette source ; pas de temps réel (~5-7 semaines de décalage). Snapshot statique régénéré à chaque build.",
      dernier_mois_publie: getBudgetDernierMois(),
      total: lignes.length,
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
  });
}
