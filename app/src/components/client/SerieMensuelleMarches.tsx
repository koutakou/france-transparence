"use client";

import { BarChart } from "@/components/ui/BarChart";
import { DataTable } from "@/components/ui/DataTable";
import { LineChart } from "@/components/ui/LineChart";
import { Money } from "@/components/ui/Money";
import { formatNombre } from "@/lib/format";
import type { MoisAgg } from "@/lib/queries/marches";

/**
 * Série mensuelle DECP (36 mois) — deux graphiques + vue tableau jumelle,
 * rendus CÔTÉ CLIENT à partir des 36 points bruts (≈ 2 Ko de props).
 *
 * Pourquoi client : rendus serveur, ces deux SVG (36 barres + 36 points,
 * cibles de survol comprises) pesaient ~35 Ko de HTML et ~150 Ko d'arbre
 * d'éléments dupliqué dans le payload RSC — le tracé est recalculé dans le
 * navigateur, à données et rendu identiques.
 */

const MOIS_COURTS = [
  "janv.", "févr.", "mars", "avr.", "mai", "juin",
  "juil.", "août", "sept.", "oct.", "nov.", "déc.",
];

/** `'2023-09'` → `sept. 23` (étiquette d'axe compacte). */
function moisCourt(mois: string): string {
  const [annee, mm] = mois.split("-");
  const i = Number(mm) - 1;
  return MOIS_COURTS[i] ? `${MOIS_COURTS[i]} ${annee.slice(2)}` : mois;
}

/** `'2023-09'` → `sept. 2023` (vue tableau). */
function moisLong(mois: string): string {
  const [annee, mm] = mois.split("-");
  const i = Number(mm) - 1;
  return MOIS_COURTS[i] ? `${MOIS_COURTS[i]} ${annee}` : mois;
}

/** Md€ pour axes/tooltips (1 décimale, 0 exact nu). */
function formatMd(v: number): string {
  return v === 0 ? "0 Md€" : `${formatNombre(v / 1e9, 1)} Md€`;
}

export function SerieMensuelleMarches({ serie }: { serie: MoisAgg[] }) {
  return (
    <>
      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          <p className="mb-2 text-xs text-ink-secondary">Marchés notifiés par mois</p>
          <LineChart
            labels={serie.map((m) => moisCourt(m.mois))}
            series={[
              {
                nom: "Marchés notifiés",
                valeurs: serie.map((m) => m.nb_marches),
              },
            ]}
            formatValeur={(v) => formatNombre(v)}
            ariaLabel="Nombre de marchés notifiés par mois sur 36 mois"
          />
        </div>
        <div>
          <p className="mb-2 text-xs text-ink-secondary">
            Montant notifié par mois (écrêté)
          </p>
          <BarChart
            items={serie.map((m) => ({
              libelle: moisCourt(m.mois),
              valeur: m.montant_total ?? 0,
            }))}
            formatValeur={formatMd}
            ariaLabel="Montant notifié par mois sur 36 mois, en milliards d’euros écrêtés"
          />
        </div>
      </div>
      <details className="group mt-3">
        <summary className="cursor-pointer list-none text-xs text-ink-muted transition-colors hover:text-ink-secondary">
          <span aria-hidden="true" className="mr-1 inline-block transition-transform group-open:rotate-90">
            ›
          </span>
          Vue tableau — 36 mois
        </summary>
        <div className="mt-2">
          <DataTable
            hauteurMax="320px"
            colonnes={[
              { cle: "mois", entete: "Mois", rendu: (m) => moisLong(m.mois) },
              { cle: "nb_marches", entete: "Marchés", type: "nombre" },
              {
                cle: "montant_total",
                entete: "Montant",
                type: "montant",
                rendu: (m) =>
                  m.montant_total === null ? "—" : <Money valeur={m.montant_total} />,
              },
            ]}
            lignes={serie}
            cleLigne={(m) => m.mois}
          />
        </div>
      </details>
    </>
  );
}
