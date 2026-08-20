"use client";

import { useEffect, useRef, useState } from "react";
import { MapFrance, type PointCarte } from "@/components/ui/MapFrance";
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
 *
 * DÉCLENCHEMENT À L'APPROCHE DU VIEWPORT (IntersectionObserver, marge 600 px).
 *
 * Pourquoi : la séquence qui suit l'hydratation est chère et se fait sur le
 * thread principal — fetch de 692 Ko bruts (225 Ko compressés), `JSON.parse`
 * de ces 692 Ko, puis projection `geoConicConformal().fitExtent()` et
 * `geoPath()` sur 96 features multipolygones avant de rendre ~96 <path>.
 * C'est le delta de TBT de l'accueil (330 ms) face à une fiche d'élu (50 ms),
 * qui charge pourtant les MÊMES gros chunks JS — ce n'étaient donc pas eux.
 *
 * En mobile la mise en page passe en une colonne : la carte est très loin
 * sous la ligne de flottaison, et tout ce travail est aujourd'hui fait
 * pendant que le visiteur lit un contenu situé bien au-dessus. En desktop la
 * marge de 600 px fait qu'elle entre en observation immédiatement : le
 * comportement y est inchangé (et le TBT y était déjà de 20 ms).
 *
 * Le rendu n'est pas modifié, et le cadre de chargement — celui qui porte
 * l'`aspectRatio` garantissant un CLS à 0 — est exactement le même avant et
 * après. Si `IntersectionObserver` est absent, on retombe sur le chemin
 * historique : chargement immédiat au montage.
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
  /** Points « villes lumineuses » optionnels (données sérialisables). */
  points?: PointCarte[];
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
  points,
  largeur = 520,
  hauteur = 500,
  messageAbsent = "Fond de carte indisponible — les valeurs restent lisibles dans le tableau.",
  className,
}: CarteDepartementsProps) {
  // undefined = chargement en cours ; null = fond indisponible.
  const [geojson, setGeojson] = useState<GeojsonDepartements | null | undefined>(undefined);
  // false tant que la carte n'approche pas du viewport (aucun travail engagé).
  const [approche, setApproche] = useState(false);
  const cadre = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Pas d'IntersectionObserver (ou plus de cadre à observer) : chemin
    // historique, on charge tout de suite.
    if (typeof IntersectionObserver === "undefined" || cadre.current === null) {
      setApproche(true);
      return;
    }
    const observateur = new IntersectionObserver(
      (entrees) => {
        if (entrees.some((e) => e.isIntersecting)) {
          setApproche(true);
          observateur.disconnect();
        }
      },
      // 600 px d'avance : le fond est prêt avant que la carte soit lue.
      { rootMargin: "600px" },
    );
    observateur.observe(cadre.current);
    return () => observateur.disconnect();
  }, []);

  useEffect(() => {
    if (!approche) return;
    let monte = true;
    chargerGeo().then((geo) => {
      if (monte) setGeojson(geo);
    });
    return () => {
      monte = false;
    };
  }, [approche]);

  if (geojson === undefined) {
    return (
      <div
        ref={cadre}
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
      points={points}
      formatValeur={FORMATS[format]}
      legendeTitre={legendeTitre}
      largeur={largeur}
      hauteur={hauteur}
      ariaLabel={ariaLabel}
      className={className}
    />
  );
}
