"use client";

import { useEffect, useState } from "react";
import { DataTable, type Colonne } from "@/components/ui/DataTable";
import { LienOfficiel } from "@/components/ui/LienOfficiel";
import { Money } from "@/components/ui/Money";
import { formatNombre, formatPct } from "@/lib/format";
import { urlSite } from "@/lib/basePath";
import { majParamsUrl } from "@/lib/urlEtat";
import { useUrlInitiale } from "@/lib/useUrlInitiale";
import type { AoEnCours, AoParFamille, FamilleAO, VueAoFamille } from "@/lib/queries/marches";

/**
 * Appels d'offres BOAMP — filtre par famille CÔTÉ CLIENT (site statique).
 *
 * La vue « Toutes » est rendue dans le HTML statique ; au premier clic sur
 * une famille, le fragment /data/marches/ao.json (toutes les familles
 * pré-agrégées à la construction du site) est chargé une fois, puis le
 * filtre est instantané. Les URL historiques `?famille=…` sont restaurées
 * au montage et réécrites à chaque sélection.
 */

export interface AppelsOffresProps {
  familles: FamilleAO[];
  /** Vue « toutes familles », rendue dans le HTML statique. */
  vueToutes: VueAoFamille;
  /** Total d'AO en cours (pilule « Toutes »). */
  aoEnCours: number;
}

/** Tronque proprement un libellé long (le `title` porte le texte complet). */
function tronque(s: string | null, max: number): string {
  if (!s || s.trim() === "") return "—";
  return s.length > max ? `${s.slice(0, max - 1).trimEnd()}…` : s;
}

/** ISO datetime UTC → `JJ/MM/AAAA HHhMM` en heure de Paris. */
function formatDateHeureParis(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const date = new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Europe/Paris",
  }).format(d);
  const heure = new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Paris",
  }).format(d);
  return `${date} ${heure.replace(":", "h")}`;
}

const COLONNES_AO: Colonne<AoEnCours>[] = [
  {
    cle: "objet",
    entete: "Objet",
    rendu: (a) => {
      const texte = <span title={a.objet ?? undefined}>{tronque(a.objet, 80)}</span>;
      return a.url_avis ? (
        <LienOfficiel href={a.url_avis} source="BOAMP">
          {texte}
        </LienOfficiel>
      ) : (
        texte
      );
    },
  },
  {
    cle: "acheteur",
    entete: "Acheteur",
    rendu: (a) => <span title={a.acheteur ?? undefined}>{tronque(a.acheteur, 44)}</span>,
  },
  {
    cle: "montant_estime",
    entete: "Montant estimé",
    type: "montant",
    rendu: (a) =>
      a.montant_estime === null ? (
        <span className="text-ink-muted">non publié</span>
      ) : (
        <span className="inline-flex items-baseline gap-1.5">
          <Money valeur={a.montant_estime} />
          {a.montant_estime >= 1e9 && (
            <span
              className="text-[11px] text-ink-muted"
              title="Montant tel que publié dans l’annonce — non retraité."
            >
              tel que publié
            </span>
          )}
        </span>
      ),
  },
  {
    cle: "date_limite_reponse",
    entete: "Date limite (Paris)",
    largeur: "10rem",
    rendu: (a) => formatDateHeureParis(a.date_limite_reponse),
  },
];

let aoPromesse: Promise<AoParFamille | null> | null = null;

function chargerAo(): Promise<AoParFamille | null> {
  aoPromesse ??= fetch(urlSite("/data/marches/ao.json"))
    .then((rep) => (rep.ok ? (rep.json() as Promise<AoParFamille | null>) : null))
    .catch(() => null);
  return aoPromesse;
}

function stylePilule(actif: boolean): string {
  return `inline-flex items-center gap-1 rounded-full border px-2.5 py-1 transition-colors ${
    actif
      ? "border-raised-border bg-hover text-ink"
      : "border-card-border text-ink-secondary hover:bg-hover"
  }`;
}

export function AppelsOffres({ familles, vueToutes, aoEnCours }: AppelsOffresProps) {
  // Filtre : état initial restauré d'une URL partagée `?famille=…`
  // (validée contre la liste réelle), surchargé par tout clic.
  const urlInitiale = new URLSearchParams(useUrlInitiale());
  const [surcharge, setSurcharge] = useState<string | null>(null);
  const [fragment, setFragment] = useState<AoParFamille | null>(null);
  const [indisponible, setIndisponible] = useState(false);

  const fUrl = urlInitiale.get("famille") ?? "";
  const famille =
    surcharge ?? (familles.some((f) => f.famille === fUrl) ? fUrl : "");
  const chargement = famille !== "" && fragment === null && !indisponible;

  useEffect(() => {
    if (famille === "" || fragment !== null) return;
    let monte = true;
    chargerAo().then((ao) => {
      if (!monte) return;
      if (ao === null) setIndisponible(true);
      else setFragment(ao);
    });
    return () => {
      monte = false;
    };
  }, [famille, fragment]);

  const choisir = (code: string) => {
    setSurcharge(code);
    majParamsUrl({ famille: code || null });
  };

  const vue: VueAoFamille =
    famille === "" ? vueToutes : (fragment?.vues[famille] ?? vueToutes);
  const familleAffichee = famille !== "" && fragment?.vues[famille] ? famille : "";
  const libelleFamille = familles.find((f) => f.famille === familleAffichee)?.famille_libelle;
  const pctSansMontant = vue.total > 0 ? (100 * vue.sansMontant) / vue.total : null;

  return (
    <div>
      <nav
        aria-label="Filtrer les appels d’offres par famille"
        className="mb-3 mt-4 flex flex-wrap items-center gap-1.5 text-xs"
      >
        <button type="button" onClick={() => choisir("")} className={stylePilule(famille === "")}>
          {famille === "" && (
            <span aria-hidden="true" className="font-bold">
              ✓
            </span>
          )}
          Toutes ({formatNombre(aoEnCours)})
        </button>
        {familles.map((f) => (
          <button
            key={f.famille}
            type="button"
            onClick={() => choisir(f.famille)}
            className={stylePilule(famille === f.famille)}
          >
            {famille === f.famille && (
              <span aria-hidden="true" className="font-bold">
                ✓
              </span>
            )}
            {f.famille_libelle ?? f.famille} ({formatNombre(f.nb)})
          </button>
        ))}
      </nav>

      {indisponible && famille !== "" && (
        <p className="mb-2 text-xs text-ink-muted">
          Détail par famille indisponible (fragment /data/marches/ao.json non chargé) — la vue
          « Toutes » reste affichée.
        </p>
      )}

      <div className={chargement ? "opacity-50 transition-opacity" : "transition-opacity"}>
        <DataTable
          colonnes={COLONNES_AO}
          lignes={vue.lignes}
          cleLigne={(a) => a.idweb}
          vide="Aucun appel d’offres en cours pour ce filtre"
        />
      </div>
      <p className="mt-3 text-xs leading-relaxed text-ink-muted" aria-live="polite">
        {formatNombre(vue.lignes.length)} échéances les plus proches affichées sur{" "}
        {formatNombre(vue.total)} appels d’offres en cours pour{" "}
        {familleAffichee === "" ? "toutes les familles" : `la famille ${libelleFamille ?? familleAffichee}`}
        {pctSansMontant !== null && (
          <>
            {" "}
            — {formatPct(pctSansMontant)} d’entre eux ne publient pas de montant dans l’annonce
            (« non publié »)
          </>
        )}
        . Les montants publiés sont repris tels quels, y compris les valeurs extrêmes réelles
        (étiquetées, jamais tronquées).
        {chargement ? " Chargement du détail par famille…" : ""}
      </p>
    </div>
  );
}
