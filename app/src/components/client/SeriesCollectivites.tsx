"use client";

import { useEffect, useState } from "react";
import { DataTable, type Colonne } from "@/components/ui/DataTable";
import { LineChart } from "@/components/ui/LineChart";
import { PuceOfficielle } from "@/components/ui/LienOfficiel";
import { VueTableau } from "@/components/ui/VueTableau";
import { formatEuros, formatNombre } from "@/lib/format";
import { urlAnnuaireEntreprise } from "@/lib/urlOfficielle";
import { urlSite } from "@/lib/basePath";
import { majParamsUrl } from "@/lib/urlEtat";
import { useUrlInitiale } from "@/lib/useUrlInitiale";
import type { SerieAnnuelle, ToutesSeries } from "@/lib/queries/collectivites";

/**
 * Régions / conseils départementaux — sélection d'une collectivité CÔTÉ
 * CLIENT (site statique : plus de `?region=…` interprété par le serveur).
 *
 * Le tableau (17 régions ou 97 conseils départementaux) est rendu dans le
 * HTML statique ; au premier clic sur une collectivité, le fragment
 * /data/collectivites/series.json (toutes les séries pluriannuelles,
 * pré-générées) est chargé une fois, puis la série s'affiche instantanément.
 * Les URL historiques `?region=…` / `?dep=…` sont restaurées au montage.
 *
 * La série (fonctionnement, investissement, épargne brute — slots 1-3
 * stables) suit DATAVIZ §3.5 : l'épargne brute peut être négative, affichée
 * signée, sans couleur de jugement.
 */

export type LigneCollectivite = {
  code: string;
  nom: string;
  siren?: string | null;
  est_ctu?: number;
  population: number | null;
  fonctionnement_meur: number | null;
  investissement_meur: number | null;
  epargne_meur: number | null;
  total_euros_par_hab: number | null;
};

export interface SeriesCollectivitesProps {
  niveau: "regions" | "departements";
  lignes: LigneCollectivite[];
  /** max-height CSS du tableau (les 97 conseils départementaux défilent). */
  hauteurMax?: string;
}

const CONFIG = {
  regions: {
    enteteNom: "Région",
    param: "region",
    retour: "← Toutes les régions",
  },
  departements: {
    enteteNom: "Collectivité",
    param: "dep",
    retour: "← Tous les départements",
  },
} as const;

let seriesPromesse: Promise<ToutesSeries | null> | null = null;

function chargerSeries(): Promise<ToutesSeries | null> {
  seriesPromesse ??= fetch(urlSite("/data/collectivites/series.json"))
    .then((rep) => (rep.ok ? (rep.json() as Promise<ToutesSeries | null>) : null))
    .catch(() => null);
  return seriesPromesse;
}

/** Série pluriannuelle d'une collectivité sélectionnée (graphique + tableau). */
function BlocSerie({
  titre,
  retourLabel,
  serie,
  surRetour,
}: {
  titre: string;
  retourLabel: string;
  serie: SerieAnnuelle[];
  surRetour: () => void;
}) {
  const labels = serie.map((s) => String(s.exercice));
  const epargneNegative = serie.some((s) => s.epargne_brute !== null && s.epargne_brute < 0);
  const lignes = serie.map((s) => ({
    exercice: String(s.exercice),
    fonctionnement_meur: s.fonctionnement === null ? null : s.fonctionnement / 1e6,
    investissement_meur: s.investissement === null ? null : s.investissement / 1e6,
    epargne_meur: s.epargne_brute === null ? null : s.epargne_brute / 1e6,
  }));
  return (
    <div className="mb-5 border-b border-card-border pb-5">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
          {titre}
          {serie.length > 0 ? ` — série ${labels[0]}-${labels[labels.length - 1]}` : ""}
        </h3>
        <button
          type="button"
          onClick={surRetour}
          className="text-xs text-ink-muted underline decoration-dotted underline-offset-2 transition-colors hover:text-ink-secondary"
        >
          {retourLabel}
        </button>
      </div>
      {serie.length === 0 ? (
        <p className="text-sm text-ink-muted">
          Aucune série pluriannuelle en base pour cette collectivité.
        </p>
      ) : (
        <>
          <LineChart
            labels={labels}
            series={[
              { nom: "Fonctionnement", valeurs: serie.map((s) => s.fonctionnement) },
              { nom: "Investissement", valeurs: serie.map((s) => s.investissement) },
              { nom: "Épargne brute", valeurs: serie.map((s) => s.epargne_brute) },
            ]}
            formatValeur={(v) => formatEuros(v)}
            ariaLabel={`${titre} : fonctionnement, investissement et épargne brute par exercice`}
          />
          {epargneNegative && (
            <p className="mt-1 text-[11px] text-ink-muted">
              Épargne brute négative sur certains exercices : donnée réelle, affichée signée.
            </p>
          )}
          <VueTableau>
            <DataTable
              colonnes={[
                { cle: "exercice", entete: "Exercice" },
                { cle: "fonctionnement_meur", entete: "Fonctionnement (M€)", type: "montant", decimales: 1 },
                { cle: "investissement_meur", entete: "Investissement (M€)", type: "montant", decimales: 1 },
                { cle: "epargne_meur", entete: "Épargne brute (M€)", type: "montant", decimales: 1 },
              ]}
              lignes={lignes}
              cleLigne={(l) => l.exercice}
            />
          </VueTableau>
        </>
      )}
    </div>
  );
}

/** Lignes rendues avant « Tout afficher » (le reste voyage déjà en props). */
const PREMIER_ECRAN = 20;

export function SeriesCollectivites({ niveau, lignes, hauteurMax }: SeriesCollectivitesProps) {
  const cfg = CONFIG[niveau];
  // Sélection : état initial restauré d'une URL partagée `?region=…` /
  // `?dep=…` (validée), surchargé par tout clic (y compris le retour).
  const urlInitiale = new URLSearchParams(useUrlInitiale());
  const [surcharge, setSurcharge] = useState<{ code: string | null } | null>(null);
  const [tout, setTout] = useState(false);
  const [series, setSeries] = useState<ToutesSeries | null>(null);
  const [indisponible, setIndisponible] = useState(false);

  const codeUrl = urlInitiale.get(cfg.param);
  const code =
    surcharge !== null
      ? surcharge.code
      : codeUrl !== null && lignes.some((l) => l.code === codeUrl)
        ? codeUrl
        : null;
  const chargement = code !== null && series === null && !indisponible;

  useEffect(() => {
    if (code === null || series !== null) return;
    let monte = true;
    chargerSeries().then((s) => {
      if (!monte) return;
      if (s === null) setIndisponible(true);
      else setSeries(s);
    });
    return () => {
      monte = false;
    };
  }, [code, series]);

  const choisir = (nouveau: string | null) => {
    setSurcharge({ code: nouveau });
    majParamsUrl({ [cfg.param]: nouveau });
  };

  const selection = code !== null ? (lignes.find((l) => l.code === code) ?? null) : null;
  const serie = selection && series ? (series[niveau][selection.code] ?? []) : null;
  const tronque = !tout && lignes.length > PREMIER_ECRAN;
  const affichees = lignes.slice(0, PREMIER_ECRAN);

  const colonnes: Colonne<LigneCollectivite>[] = [
    {
      cle: "nom",
      entete: cfg.enteteNom,
      rendu: (l) => {
        const url = urlAnnuaireEntreprise(l.siren);
        return (
          <>
            <button
              type="button"
              onClick={() => choisir(l.code)}
              aria-current={code === l.code ? "true" : undefined}
              className={`text-left underline decoration-dotted underline-offset-2 transition-colors hover:text-accent ${
                code === l.code ? "font-medium text-accent" : ""
              }`}
            >
              {l.nom}
            </button>
            {url ? <PuceOfficielle href={url} libelle="Sirene" nom={l.nom} /> : null}
            {l.est_ctu === 1 && <span className="text-ink-muted"> · CTU</span>}
          </>
        );
      },
    },
    { cle: "population", entete: "Population", type: "nombre" },
    { cle: "fonctionnement_meur", entete: "Fonctionnement (M€)", type: "montant", decimales: 1 },
    { cle: "investissement_meur", entete: "Investissement (M€)", type: "montant", decimales: 1 },
    { cle: "epargne_meur", entete: "Épargne brute (M€)", type: "montant", decimales: 1 },
    { cle: "total_euros_par_hab", entete: "Total (€/hab)", type: "montant" },
  ];

  return (
    <div>
      {selection && chargement && (
        <p className="mb-3 text-xs text-ink-muted" aria-live="polite">
          Chargement de la série pluriannuelle de {selection.nom}…
        </p>
      )}
      {selection && indisponible && (
        <p className="mb-3 text-xs text-ink-muted">
          Séries pluriannuelles indisponibles (fragment /data/collectivites/series.json non
          chargé) — le tableau ci-dessous reste complet.
        </p>
      )}
      {selection && serie !== null && (
        <BlocSerie
          titre={
            niveau === "regions" ? `${selection.nom} (${selection.code})` : selection.nom
          }
          retourLabel={cfg.retour}
          serie={serie}
          surRetour={() => choisir(null)}
        />
      )}
      <DataTable
        colonnes={colonnes}
        lignes={tronque ? affichees : lignes}
        cleLigne={(l) => l.code}
        hauteurMax={tronque ? undefined : hauteurMax}
      />
      {tronque && (
        <p className="mt-2 flex flex-wrap items-center gap-3 text-xs text-ink-muted" aria-live="polite">
          <span>
            Affichage des {formatNombre(PREMIER_ECRAN)} premières collectivités sur{" "}
            {formatNombre(lignes.length)} (même tri que le tableau complet).
          </span>
          <button
            type="button"
            onClick={() => setTout(true)}
            className="inline-flex min-h-11 items-center rounded-lg border border-card-border bg-raised px-3 text-ink transition-colors hover:bg-hover"
          >
            Tout afficher ({formatNombre(lignes.length)})
          </button>
        </p>
      )}
      <p className="mt-2 text-[11px] text-ink-muted">
        Sélectionner une {niveau === "regions" ? "région" : "collectivité"} pour afficher sa série
        pluriannuelle (fonctionnement, investissement, épargne brute). Total (€/hab) =
        (fonctionnement + investissement) / population.
      </p>
    </div>
  );
}
