"use client";

import { useEffect, useState } from "react";
import { DataTable, type Colonne } from "@/components/ui/DataTable";
import { LineChart } from "@/components/ui/LineChart";
import { formatEuros, formatNombre } from "@/lib/format";
import { urlSite } from "@/lib/basePath";
import { majParamsUrl } from "@/lib/urlEtat";
import { useUrlInitiale } from "@/lib/useUrlInitiale";
import type {
  MedianeStrateAnnuelle,
  SerieCommune,
  SeriesCommunes as SeriesCommunesData,
} from "@/lib/queries/collectivites";

/**
 * Grandes communes — sélection d'une commune CÔTÉ CLIENT, sur le modèle de
 * SeriesCollectivites (régions/départements) : le tableau des 200 communes
 * est rendu dans le HTML statique ; au premier clic, le fragment
 * /data/collectivites/series-communes.json (séries 2018-2025 + médianes de
 * strate, pré-générées) est chargé une fois, puis tout est instantané.
 * L'URL `?commune=<code INSEE>` est restaurée au montage.
 *
 * Cadre éditorial (non négociable) : fonctionnement et investissement
 * SÉPARÉS, en €/habitant, comparés UNIQUEMENT à la médiane de la strate
 * démographique de la commune — aucun classement, aucune note, aucun
 * adjectif de jugement. Un exercice absent de la source s'affiche « donnée
 * non disponible », jamais 0.
 */

/** Libellés des strates démographiques OFGL (population au 01/01/2025). */
const STRATES: Record<string, string> = {
  "0": "moins de 100 habitants",
  "1": "100 à 199 habitants",
  "2": "200 à 499 habitants",
  "3": "500 à 1 999 habitants",
  "4": "2 000 à 3 499 habitants",
  "5": "3 500 à 4 999 habitants",
  "6": "5 000 à 9 999 habitants",
  "7": "10 000 à 19 999 habitants",
  "8": "20 000 à 49 999 habitants",
  "9": "50 000 à 99 999 habitants",
  "10": "100 000 habitants ou plus",
};

export type LigneGrandeCommune = {
  code: string;
  nom: string;
  departement: string;
  population: number | null;
  fonctionnement_meur: number | null;
  fonct_euros_par_hab: number | null;
  investissement_meur: number | null;
  inv_euros_par_hab: number | null;
};

export interface SeriesCommunesProps {
  lignes: LigneGrandeCommune[];
  /** max-height CSS du tableau une fois tout affiché. */
  hauteurMax?: string;
}

let seriesPromesse: Promise<SeriesCommunesData | null> | null = null;

function chargerSeries(): Promise<SeriesCommunesData | null> {
  seriesPromesse ??= fetch(urlSite("/data/collectivites/series-communes.json"))
    .then((rep) => (rep.ok ? (rep.json() as Promise<SeriesCommunesData | null>) : null))
    .catch(() => null);
  return seriesPromesse;
}

/** Un graphique commune vs médiane de strate (fonctionnement OU investissement). */
function GraphiqueCompare({
  titre,
  labels,
  commune,
  mediane,
  libelleStrate,
}: {
  titre: string;
  labels: string[];
  commune: (number | null)[];
  mediane: (number | null)[];
  libelleStrate: string | null;
}) {
  return (
    <div>
      <h4 className="mb-1 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
        {titre}
      </h4>
      <LineChart
        labels={labels}
        series={[
          { nom: "Commune", valeurs: commune },
          {
            nom: libelleStrate
              ? `Médiane des communes de ${libelleStrate}`
              : "Médiane de la strate",
            valeurs: mediane,
            couleur: "var(--viz-autre)",
          },
        ]}
        hauteur={220}
        formatValeur={(v) => formatEuros(v)}
        ariaLabel={`${titre} : commune comparée à la médiane de sa strate démographique, par exercice`}
      />
    </div>
  );
}

/** Série d'une commune sélectionnée : 2 graphiques + tableau + réserves. */
function BlocSerieCommune({
  titre,
  commune,
  medianes,
  exercices,
  surRetour,
}: {
  titre: string;
  commune: SerieCommune;
  medianes: MedianeStrateAnnuelle[];
  exercices: number[];
  surRetour: () => void;
}) {
  const labels = exercices.map((e) => String(e));
  const parExercice = new Map(commune.serie.map((s) => [s.exercice, s]));
  const medianeParExercice = new Map(medianes.map((m) => [m.exercice, m]));
  const fonct = exercices.map((e) => parExercice.get(e)?.fonct_hab ?? null);
  const inv = exercices.map((e) => parExercice.get(e)?.inv_hab ?? null);
  const fonctMediane = exercices.map((e) => medianeParExercice.get(e)?.fonct_hab ?? null);
  const invMediane = exercices.map((e) => medianeParExercice.get(e)?.inv_hab ?? null);
  const manquants = exercices.filter(
    (e) => parExercice.get(e)?.fonct_hab == null && parExercice.get(e)?.inv_hab == null,
  );
  const libelleStrate = commune.strate !== null ? (STRATES[commune.strate] ?? null) : null;
  const lignesTableau = exercices.map((e) => ({
    exercice: String(e),
    fonct_hab: parExercice.get(e)?.fonct_hab ?? null,
    fonct_mediane: medianeParExercice.get(e)?.fonct_hab ?? null,
    inv_hab: parExercice.get(e)?.inv_hab ?? null,
    inv_mediane: medianeParExercice.get(e)?.inv_hab ?? null,
  }));
  return (
    <div className="mb-5 border-b border-card-border pb-5">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
          {titre}
          {labels.length > 0 ? ` — série ${labels[0]}-${labels[labels.length - 1]}` : ""}
        </h3>
        <button
          type="button"
          onClick={surRetour}
          className="text-xs text-ink-muted underline decoration-dotted underline-offset-2 transition-colors hover:text-ink-secondary"
        >
          ← Toutes les communes
        </button>
      </div>
      {commune.epci !== null && commune.epci !== "" && (
        <p className="mb-2 text-xs text-ink-secondary">
          Intercommunalité : {commune.epci}. Seul le budget principal de la commune est
          tracé ici — les compétences transférées à l&apos;intercommunalité n&apos;y
          figurent pas.
        </p>
      )}
      <div className="grid gap-6 lg:grid-cols-2">
        <GraphiqueCompare
          titre="Fonctionnement (€/habitant)"
          labels={labels}
          commune={fonct}
          mediane={fonctMediane}
          libelleStrate={libelleStrate}
        />
        <GraphiqueCompare
          titre="Investissement (€/habitant)"
          labels={labels}
          commune={inv}
          mediane={invMediane}
          libelleStrate={libelleStrate}
        />
      </div>
      {manquants.length > 0 && (
        <p className="mt-2 text-xs text-ink-secondary">
          {manquants.length === 1
            ? `Exercice ${manquants[0]} : donnée non disponible`
            : `Exercices ${manquants.join(", ")} : donnée non disponible`}{" "}
          — la commune est absente de la source pour{" "}
          {manquants.length === 1 ? "cet exercice" : "ces exercices"} ; la courbe
          s&apos;interrompt, rien n&apos;est compté à 0.
        </p>
      )}
      <details className="mt-2">
        <summary className="cursor-pointer text-xs text-ink-muted transition-colors hover:text-ink-secondary">
          Vue tableau (« — » = donnée non disponible)
        </summary>
        <div className="mt-2">
          <DataTable
            colonnes={[
              { cle: "exercice", entete: "Exercice" },
              { cle: "fonct_hab", entete: "Fonct. (€/hab)", type: "montant" },
              { cle: "fonct_mediane", entete: "Médiane strate (€/hab)", type: "montant" },
              { cle: "inv_hab", entete: "Inv. (€/hab)", type: "montant" },
              { cle: "inv_mediane", entete: "Médiane strate (€/hab)", type: "montant" },
            ]}
            lignes={lignesTableau}
            cleLigne={(l) => l.exercice}
          />
        </div>
      </details>
    </div>
  );
}

/** Lignes rendues avant « Tout afficher » (le reste voyage déjà en props). */
const PREMIER_ECRAN = 20;

export function SeriesCommunes({ lignes, hauteurMax }: SeriesCommunesProps) {
  // Sélection : état initial restauré d'une URL partagée `?commune=…`
  // (validée), surchargé par tout clic (y compris le retour).
  const urlInitiale = new URLSearchParams(useUrlInitiale());
  const [surcharge, setSurcharge] = useState<{ code: string | null } | null>(null);
  const [tout, setTout] = useState(false);
  const [series, setSeries] = useState<SeriesCommunesData | null>(null);
  const [indisponible, setIndisponible] = useState(false);

  const codeUrl = urlInitiale.get("commune");
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
    majParamsUrl({ commune: nouveau });
  };

  const selection = code !== null ? (lignes.find((l) => l.code === code) ?? null) : null;
  const serie = selection && series ? (series.communes[selection.code] ?? null) : null;
  const medianes =
    serie && serie.strate !== null ? (series?.strates[serie.strate] ?? []) : [];
  const tronque = !tout && lignes.length > PREMIER_ECRAN;
  const affichees = lignes.slice(0, PREMIER_ECRAN);

  const colonnes: Colonne<LigneGrandeCommune>[] = [
    {
      cle: "nom",
      entete: "Commune",
      rendu: (l) => (
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
      ),
    },
    { cle: "departement", entete: "Dép." },
    { cle: "population", entete: "Population", type: "nombre" },
    { cle: "fonctionnement_meur", entete: "Fonctionnement (M€)", type: "montant", decimales: 1 },
    { cle: "fonct_euros_par_hab", entete: "Fonct. (€/hab)", type: "montant" },
    { cle: "investissement_meur", entete: "Investissement (M€)", type: "montant", decimales: 1 },
    { cle: "inv_euros_par_hab", entete: "Inv. (€/hab)", type: "montant" },
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
          Séries pluriannuelles indisponibles (fragment
          /data/collectivites/series-communes.json non chargé) — le tableau ci-dessous
          reste complet.
        </p>
      )}
      {selection && series !== null && serie === null && (
        <p className="mb-3 text-xs text-ink-muted">
          Aucune série pluriannuelle en base pour {selection.nom}.
        </p>
      )}
      {selection && serie !== null && (
        <BlocSerieCommune
          titre={`${selection.nom} (${selection.departement})`}
          commune={serie}
          medianes={medianes}
          exercices={series?.exercices ?? []}
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
            Affichage des {formatNombre(PREMIER_ECRAN)} premières communes sur{" "}
            {formatNombre(lignes.length)} (même tri que le tableau complet).
          </span>
          <button
            type="button"
            onClick={() => setTout(true)}
            className="rounded-lg border border-card-border bg-raised px-2.5 py-1 text-ink transition-colors hover:bg-hover"
          >
            Tout afficher ({formatNombre(lignes.length)})
          </button>
        </p>
      )}
      <p className="mt-2 text-[11px] text-ink-muted">
        Sélectionner une commune pour afficher son évolution 2018-2025 (fonctionnement et
        investissement séparés, en €/habitant), comparée uniquement à la médiane de sa
        strate démographique.
      </p>
    </div>
  );
}
