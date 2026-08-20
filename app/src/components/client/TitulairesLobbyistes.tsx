"use client";

import { useState } from "react";
import { DataTable } from "@/components/ui/DataTable";
import { formatNombre } from "@/lib/format";

/**
 * Table des représentants d'intérêts titulaires de marchés publics, avec
 * BASCULE entre deux périmètres — c'est tout l'objet du composant.
 *
 * Pourquoi une bascule et pas deux tableaux : le montant d'un accord-cadre
 * notifié est un MAXIMUM contractuel, pas une dépense. Les additionner au
 * reste gonfle le total de 48 Md€ sans qu'un euro soit forcément dépensé ;
 * les cacher priverait le lecteur d'un pan entier de la commande publique
 * (14 017 des 25 191 marchés du croisement). La bascule les traite donc
 * explicitement : périmètre de référence par défaut (hors accords-cadres),
 * périmètre complet à un clic, avec l'avertissement qui va avec.
 *
 * Rendu côté client uniquement pour l'état de la bascule : les DEUX
 * classements sont calculés au build et sérialisés dans la page — aucun
 * fetch, aucun recalcul, la table est lisible avant toute hydratation.
 *
 * AUCUN jugement n'est porté par ce tableau : être inscrit au répertoire des
 * représentants d'intérêts et être titulaire d'un marché public sont deux
 * situations légales qui se cumulent couramment. La seule étiquette posée
 * sur une ligne est le constat officiel « en défaut de déclaration » de la
 * HATVP, repris tel quel.
 */

/** Une ligne de classement, déjà mise en forme par la page (montant en M€). */
export type LigneTitulaireLobbyiste = {
  siren: string;
  denomination: string;
  categorie: string | null;
  url_fiche: string | null;
  /** Flag natif HATVP (0/1) — constat officiel, pas un calcul du site. */
  defaut_declaration: number;
  activites_12m: number;
  nb_marches: number;
  /** Montant écrêté puis ventilé entre co-titulaires, EN MILLIONS d'euros. */
  montant_meur: number | null;
};

export interface TitulairesLobbyistesProps {
  /** Classement du périmètre de référence (accords-cadres exclus). */
  horsAccordsCadres: LigneTitulaireLobbyiste[];
  /** Classement tous marchés confondus (accords-cadres compris). */
  tousMarches: LigneTitulaireLobbyiste[];
}

/** Étiquette du constat HATVP — icône + libellé, jamais la couleur seule. */
function EtiquetteDefaut() {
  return (
    <span
      className="ml-2 inline-flex items-center gap-1 whitespace-nowrap text-[11px] text-ink-muted"
      title="Constat officiel de la HATVP : entité inscrite sur la liste des représentants d'intérêts n'ayant pas communiqué tout ou partie des informations exigibles pour au moins un exercice."
    >
      <svg
        width="10"
        height="10"
        viewBox="0 0 14 14"
        aria-hidden="true"
        style={{ color: "var(--status-warning)" }}
      >
        <path d="M7 1.5L13 12H1z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M7 5.4v3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="7" cy="10.2" r="0.9" fill="currentColor" />
      </svg>
      en défaut de déclaration
    </span>
  );
}

/** Lien sortant vers la fiche du répertoire (jamais de fetch serveur). */
function LienFiche({ url }: { url: string | null }) {
  if (!url) return <>—</>;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
    >
      Fiche HATVP
    </a>
  );
}

export function TitulairesLobbyistes({
  horsAccordsCadres,
  tousMarches,
}: TitulairesLobbyistesProps) {
  const [avecAccordsCadres, setAvecAccordsCadres] = useState(false);
  const lignes = avecAccordsCadres ? tousMarches : horsAccordsCadres;

  return (
    <div>
      {/* Bascule de périmètre — deux boutons plutôt qu'un interrupteur :
          l'état courant se lit sans convention à deviner (aria-pressed). */}
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-ink-muted">Périmètre :</span>
        {[
          { actif: false, libelle: "Hors accords-cadres" },
          { actif: true, libelle: "Tous marchés" },
        ].map((o) => (
          <button
            key={o.libelle}
            type="button"
            aria-pressed={avecAccordsCadres === o.actif}
            onClick={() => setAvecAccordsCadres(o.actif)}
            className={`rounded-lg border px-2.5 py-1 transition-colors ${
              avecAccordsCadres === o.actif
                ? "border-raised-border bg-raised text-ink"
                : "border-card-border bg-card text-ink-muted hover:text-ink-secondary"
            }`}
          >
            {o.libelle}
          </button>
        ))}
      </div>

      <DataTable<LigneTitulaireLobbyiste>
        colonnes={[
          {
            cle: "denomination",
            entete: "Représentant d'intérêts titulaire",
            rendu: (l) => (
              <span>
                {l.denomination}
                {l.defaut_declaration === 1 && <EtiquetteDefaut />}
              </span>
            ),
          },
          { cle: "categorie", entete: "Catégorie (libellé natif HATVP)" },
          { cle: "nb_marches", entete: "Marchés", type: "nombre", largeur: "6rem" },
          {
            cle: "montant_meur",
            entete: "Montant (M€)",
            type: "montant",
            decimales: 1,
            largeur: "8rem",
          },
          {
            cle: "activites_12m",
            entete: "Activités déclarées (12 mois)",
            type: "nombre",
            largeur: "9rem",
          },
          {
            cle: "url_fiche",
            entete: "Registre",
            rendu: (l) => <LienFiche url={l.url_fiche} />,
            largeur: "7rem",
          },
        ]}
        lignes={lignes}
        cleLigne={(l) => l.siren}
        vide="Aucun titulaire inscrit au répertoire sur ce périmètre."
      />

      <p className="mt-2 text-xs leading-relaxed text-ink-muted" aria-live="polite">
        {avecAccordsCadres ? (
          <>
            Périmètre complet, accords-cadres compris :{" "}
            <strong className="font-medium text-ink">
              le montant d&apos;un accord-cadre est un maximum contractuel, pas
              une dépense
            </strong>{" "}
            — ce classement additionne donc des engagements plafonds et des
            montants notifiés fermes, et ne se compare pas au précédent.
          </>
        ) : (
          <>
            Périmètre de référence : accords-cadres exclus, leur montant notifié
            étant un maximum contractuel et non une dépense. Le classement porte
            sur {formatNombre(lignes.length)} entités —{" "}
            <strong className="font-medium text-ink">
              aucune n&apos;est en tort du seul fait d&apos;y figurer
            </strong>
            .
          </>
        )}{" "}
        Montants retenus écrêtés à 100&nbsp;M€ par marché, puis répartis à parts
        égales entre co-titulaires (la source ne les ventile pas) ; les marchés
        sans montant renseigné sont comptés mais exclus des sommes.
      </p>
    </div>
  );
}
