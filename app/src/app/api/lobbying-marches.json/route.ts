/**
 * GET /api/lobbying-marches.json — export statique généré au build :
 * le croisement entre le répertoire HATVP des représentants d'intérêts
 * (source S4) et les marchés publics des DECP consolidées (source S1),
 * joints sur le SIREN (exact, sans rapprochement de noms).
 *
 * Pourquoi un export : la page /lobbying n'affiche qu'un extrait du
 * classement (20 lignes) ; le fichier publie les 566 représentants
 * d'intérêts titulaires avec leurs deux périmètres, pour que le calcul
 * puisse être refait ailleurs. Méthode, exclusions et limites :
 * docs/CROISEMENT-LOBBYING-MARCHES.md.
 *
 * Mentions obligatoires reprises dans meta — la méthode ne se lit pas dans
 * les chiffres : accords-cadres comptés à part (montant = maximum, pas une
 * dépense), montants écrêtés à 100 M€/marché puis ventilés entre
 * co-titulaires, drapeau « suspect » = borne basse non auditée, crédit de
 * la consolidation decp-processing, et le rappel qu'aucune des entités
 * listées n'est en tort du seul fait d'y figurer.
 *
 * Base absente au build → erreur franche : on ne publie JAMAIS un snapshot
 * vide (la CI ne déploie pas, le site de la veille reste servi tel quel).
 */
import { NextResponse } from "next/server";
import { getCroisementLobbyingMarches } from "@/lib/queries/croisement-lobbying-marches";

export const dynamic = "force-static";

export async function GET() {
  const croisement = getCroisementLobbyingMarches();
  if (croisement === null) {
    throw new Error(
      "Base absente au build — lancer make ingest (ou poser FRANCE_DB_PATH) avant next build.",
    );
  }
  const { metaS1, metaS4, couverture, agregats, ensemble, titulaires } = croisement;

  return NextResponse.json({
    meta: {
      description:
        "Croisement du répertoire HATVP des représentants d'intérêts et des marchés publics (DECP consolidées), joints sur le SIREN. Périmètre de référence : marchés HORS accords-cadres (le montant notifié d'un accord-cadre est un maximum contractuel, pas une dépense ; les accords-cadres sont fournis à part). Fenêtre : les 24 derniers mois, chaque marché compté à la date de sa notification INITIALE (un avenant ne le redate pas) ; montants et titulaires pris sur sa version courante. Montants = montant retenu écrêté à 100 M€ par marché, puis réparti à parts égales entre co-titulaires (la source ne les ventile pas) ; marchés sans montant renseigné comptés mais exclus des sommes ; le sous-total « hors montants suspects » est une BORNE BASSE, le drapeau n'ayant pas été audité marché par marché. Snapshot statique régénéré à chaque build.",
      avertissement:
        "Être inscrit au répertoire des représentants d'intérêts et être titulaire d'un marché public sont deux situations parfaitement légales qui se cumulent couramment : aucune entité de ce fichier n'est en tort du seul fait d'y figurer. Le champ defaut_declaration reprend tel quel le constat officiel de la HATVP (entité n'ayant pas communiqué tout ou partie des informations exigibles pour au moins un exercice) — il ne qualifie que la déclaration de représentation d'intérêts, jamais le marché.",
      methode:
        "docs/CROISEMENT-LOBBYING-MARCHES.md — jointure lobby_entites.identifiant_national (type_identifiant = 'SIREN') = 9 premiers caractères du SIRET de CHAQUE titulaire du marché (titulaires_json, co-titulaires compris).",
      credit:
        "Consolidation communautaire decp-processing (Colin Maudry) — à créditer en cas de réutilisation.",
      sources: [metaS1, metaS4].map((m) => ({
        source_id: m.source_id,
        nom: m.nom,
        url: m.url,
        licence: m.licence,
        date_donnees: m.date_donnees,
        date_ingestion: m.date_ingestion,
        notes: m.notes,
      })),
      licence_agregats: "Licence Ouverte 2.0 (agrégats France Transparence)",
    },
    couverture,
    agregats,
    ensemble_decp: ensemble,
    titulaires,
  });
}
