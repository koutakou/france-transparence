/**
 * GET /api/budget-mensuel.json — export statique généré au build :
 * situations mensuelles budgétaires de l'État (source S13, DGFiP), SÉRIE
 * COMPLÈTE 2013 → dernier mois publié (26 lignes par mois, montants en
 * euros : montant_cumul = cumul depuis le 1er janvier, montant_mois = flux
 * du mois seul). Le filtrage par année ou ligne se fait chez le
 * réutilisateur — plus de paramètres d'URL.
 *
 * Ruptures de périmètre (table `budget_mensuel_ruptures`, contrôle de P1) :
 * chaque ligne porte `rupture_perimetre`, null ou l'objet qui dit pourquoi
 * `montant_cumul` ne se compare pas à `montant_cumul_n1` ; la liste est
 * aussi dans `meta.ruptures_perimetre` et nommée dans `meta.description`.
 * Aucune valeur publiée n'est retirée ni corrigée.
 *
 * Base absente au build → erreur franche : on ne publie JAMAIS un snapshot
 * vide (le build échoue, `ft-deploy` ne bascule pas : la release précédente
 * reste servie telle quelle).
 */
import { NextResponse } from "next/server";
import {
  getBudgetDernierMois,
  getBudgetMensuelComplet,
  getMetaSourcesParIds,
} from "@/lib/queries/donnees";
import { annoterRuptures, getRupturesBudget } from "@/lib/queries/budget-ruptures";
import { formatDateFr } from "@/lib/format";

export const dynamic = "force-static";

export async function GET() {
  const lignes = getBudgetMensuelComplet();
  if (lignes === null) {
    throw new Error(
      "Base absente au build — lancer make ingest (ou poser FRANCE_DB_PATH) avant next build.",
    );
  }
  const s13 = (getMetaSourcesParIds(["S13"]) ?? [])[0];
  const ruptures = getRupturesBudget();
  const listeRuptures = [...ruptures.values()].sort((a, b) =>
    a.dateFinMois === b.dateFinMois
      ? a.ligneId.localeCompare(b.ligneId)
      : a.dateFinMois.localeCompare(b.dateFinMois),
  );
  // Nommées dans la description elle-même : c'est le champ qu'un
  // réutilisateur lit d'abord, et une variation à travers ces cellules
  // comparerait deux définitions différentes.
  const phraseRuptures =
    listeRuptures.length === 0
      ? " Aucune rupture de périmètre constatée par le contrôle des totaux (rupture_perimetre = null sur toutes les lignes)."
      : ` Rupture de périmètre amont : ${listeRuptures
          .map(
            (r) =>
              `${r.ligneId} au ${formatDateFr(r.dateFinMois)} (${
                r.definitionConstatee
                  ? `vaut ${r.definitionConstatee}, les autres mois ${r.identite}`
                  : `ne vaut pas ${r.identite}, contrairement aux autres mois`
              })`,
          )
          .join(" ; ")}. Valeur publiée telle quelle ; ne pas la comparer à montant_cumul_n1 ni à la même date N+1 : voir rupture_perimetre sur chaque ligne, et montant_mois NULL à travers la cellule.`;
  return NextResponse.json({
    meta: {
      description:
        "Situations mensuelles budgétaires de l'État (26 lignes par grands titres), série complète 2013 → dernier mois publié. Montants en euros : montant_cumul = cumul depuis le 1er janvier, montant_mois = flux mensuel, colonnes _n1 = même période N−1. Mois infra-annuels provisoires ; pas de détail mission/programme dans cette source ; pas de temps réel (~5-7 semaines de décalage). Snapshot statique régénéré à chaque build." +
        phraseRuptures,
      ruptures_perimetre: listeRuptures.map((r) => ({
        ligne_id: r.ligneId,
        date_fin_mois: r.dateFinMois,
        montant_publie: r.montantPublie,
        identite: r.identite,
        definition_constatee: r.definitionConstatee,
      })),
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
    donnees: annoterRuptures(lignes, ruptures),
  });
}
