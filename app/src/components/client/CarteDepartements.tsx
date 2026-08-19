"use client";

import { useEffect, useState } from "react";
import { MapFrance } from "@/components/ui/MapFrance";
import type { GeojsonDepartements } from "@/lib/queries/collectivites";
import { formatEuros, formatNombre } from "@/lib/format";
import { urlSite } from "@/lib/basePath";

/**
 * Carte de France dessinée CÔTÉ CLIENT — le fond GeoJSON (~700 Ko) est
 * chargé une seule fois depuis le fragment statique /data/geo-departements.json
 * (mémoïsé au niveau module : une seule requête pour toutes les cartes de
 * toutes les pages), puis rendu par le composant MapFrance existant.
 *
 * Pourquoi : rendue côté serveur, chaque carte embarquait ~700 Ko de tracés
 * SVG dans le HTML (dupliqués dans le payload RSC) — c'était la cause
 * principale du dépassement de budget de /marches et /collectivites.
 *
 * Honnêteté : pendant le chargement, un cadre neutre aux mêmes proportions
 * (aucun saut de layout) ; si le fond est indisponible, le même message
 * qu'avant — les valeurs restent lisibles dans les tableaux.
 */

/** Formats sérialisables (une fonction ne traverse pas la frontière RSC). */
export type FormatCarte = "euros" | "euros-par-hab" | "nombre";

const FORMATS: Record<FormatCarte, (v: number) => string> = {
  euros: (v) => formatEuros(v),
  "euros-par-hab": (v) => `${formatNombre(v)} €/hab`,
  nombre: (v) => formatNombre(v),
};

let geoPromesse: Promise<GeojsonDepartements | null> | null = null;

function chargerGeo(): Promise<GeojsonDepartements | null> {
  geoPromesse ??= fetch(urlSite("/data/geo-departements.json"))
    .then((rep) => (rep.ok ? (rep.json() as Promise<GeojsonDepartements | null>) : null))
    .catch(() => null);
  return geoPromesse;
}

export interface CarteDepartementsProps {
  valeurs: Record<string, number>;
  format: FormatCarte;
  legendeTitre: string;
  ariaLabel: string;
  largeur?: number;
  hauteur?: number;
  /** Message affiché si le fond de carte est indisponible. */
  messageAbsent?: string;
  className?: string;
}

export function CarteDepartements({
  valeurs,
  format,
  legendeTitre,
  ariaLabel,
  largeur = 520,
  hauteur = 500,
  messageAbsent = "Fond de carte indisponible — les valeurs restent lisibles dans le tableau.",
  className,
}: CarteDepartementsProps) {
  // undefined = chargement en cours ; null = fond indisponible.
  const [geojson, setGeojson] = useState<GeojsonDepartements | null | undefined>(undefined);

  useEffect(() => {
    let monte = true;
    chargerGeo().then((geo) => {
      if (monte) setGeojson(geo);
    });
    return () => {
      monte = false;
    };
  }, []);

  if (geojson === undefined) {
    return (
      <div
        className={`flex items-center justify-center rounded-lg border border-card-border bg-raised text-sm text-ink-muted ${className ?? ""}`}
        style={{ aspectRatio: `${largeur} / ${hauteur}` }}
        role="status"
      >
        Chargement du fond de carte…
      </div>
    );
  }

  if (geojson === null) {
    return (
      <p
        className={`rounded-lg border border-card-border bg-raised p-4 text-sm text-ink-muted ${className ?? ""}`}
      >
        {messageAbsent}
      </p>
    );
  }

  return (
    <MapFrance
      geojson={geojson}
      valeurs={valeurs}
      formatValeur={FORMATS[format]}
      legendeTitre={legendeTitre}
      largeur={largeur}
      hauteur={hauteur}
      ariaLabel={ariaLabel}
      className={className}
    />
  );
}
