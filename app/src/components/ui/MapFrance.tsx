"use client";

import { useState, type PointerEvent } from "react";
import { formatNombre } from "@/lib/format";
import {
  projectionFrance,
  type CarteFrancePrecalculee,
  type TraceDepartement,
} from "@/components/ui/projection-france";
import { TooltipGraphique } from "./TooltipGraphique";

/**
 * Carte de France des départements — SVG responsive.
 *
 * Les CONTOURS ne sont plus projetés ici : ils arrivent déjà tracés, dans le
 * repère du viewBox, par le fragment /data/carte-departements.json calculé
 * au build (voir components/ui/projection-france.ts). Ce composant n'a donc
 * plus qu'à peindre — la choroplèthe, la légende et les tooltips.
 *
 * Projection : conique conforme France métropolitaine (paramètres
 * Lambert-93 : parallèles 44°/49°, méridien 3°E, latitude 46,5°N), calée
 * sur le viewBox par `fitExtent` — aucune constante d'échelle magique. Son
 * échelle et sa translation voyagent dans le fragment : elles ne servent
 * plus qu'à placer les points « villes lumineuses », dont les coordonnées
 * (lon, lat) viennent, elles, des données de la page.
 *
 * OUTRE-MER : hors du rendu — le fragment ne contient que la métropole et la
 * Corse (96 départements). Si des DOM (971…976) y figuraient, le `fitExtent`
 * écraserait la métropole pour cadrer l'Atlantique/l'océan Indien : les
 * features dont le code commence par « 97 » sont donc écartées du cadrage ET
 * du rendu, à la fabrication du fragment. Les rendre visibles demanderait des encarts
 * dédiés.
 *
 * Choroplèthe (DATAVIZ §8) : rampe séquentielle ORDINALE, 5 classes max
 * (`--seq-3` → `--seq-7`), seuils par quantiles, légende d'échelle
 * obligatoire (rendue sous la carte) ; département sans valeur :
 * `--map-manquant` (#0d1930, hors rampe) + mention « donnée manquante »
 * dans le tooltip et la légende. Contours 1px `--map-contour`.
 *
 * Points « villes lumineuses » (§8) : l'AIRE encode le poids
 * (r = 3 + 11 × √(poids/max), donc 3 → 14px), couleur `--viz-serie-1`
 * (pas 4+ de la rampe : jamais de petite marque sous `--seq-4`), halo
 * radial de la même teinte 0,35 → 0 sur 2,5 × r, sans animation
 * (`prefers-reduced-motion` respecté d'office), cible de survol ≥ 24px,
 * tooltip natif nom + poids.
 *
 * Tooltips : HTML (DATAVIZ §5), pas le `<title>` SVG. Un seul arrêt
 * clavier sur la figure. La vue tableau jumelle (§9) reste à la page.
 *
 * @example
 * <MapFrance carte={carte}
 *   valeurs={{ "75": 1284, "13": 890, "69": 745 }}
 *   formatValeur={(v) => formatNombre(v)}
 *   legendeTitre="Marchés notifiés (30 j)"
 *   points={[{ lat: 48.8566, lon: 2.3522, label: "Paris", poids: 1284 }]} />
 */
export interface PointCarte {
  lat: number;
  lon: number;
  label: string;
  poids: number;
}

export interface MapFranceProps {
  /** Fond de carte précalculé (fragment /data/carte-departements.json). */
  carte: CarteFrancePrecalculee;
  /** Valeurs par code département → choroplèthe (absent = carte neutre). */
  valeurs?: Record<string, number>;
  /** Points optionnels (villes lumineuses). */
  points?: PointCarte[];
  /** Format des valeurs (légende + tooltips) — défaut nombre fr. */
  formatValeur?: (v: number) => string;
  /** Titre court de la légende (ex. « Marchés notifiés (30 j) »). */
  legendeTitre?: string;
  ariaLabel?: string;
  className?: string;
}

/** Rampe ordinale validée : pas 3 → 7 (DATAVIZ §3.2), 5 classes max. */
const RAMPE = ["var(--seq-3)", "var(--seq-4)", "var(--seq-5)", "var(--seq-6)", "var(--seq-7)"];

/** Seuils par quantiles (k classes) sur les valeurs présentes. */
function seuilsQuantiles(valeurs: number[], k: number): number[] {
  const tri = [...valeurs].sort((a, b) => a - b);
  const seuils: number[] = [];
  for (let i = 1; i < k; i++) {
    seuils.push(tri[Math.min(tri.length - 1, Math.floor((i * tri.length) / k))]);
  }
  return [...new Set(seuils)]; // valeurs peu variées → moins de classes
}

export function MapFrance({
  carte,
  valeurs,
  points,
  formatValeur = (v) => formatNombre(v),
  legendeTitre,
  ariaLabel = "Carte de France par département",
  className,
}: MapFranceProps) {
  const [tip, setTip] = useState<{
    nom: string;
    valeur: string;
    x: number;
    y: number;
  } | null>(null);
  const departements = carte.departements;
  if (departements.length === 0) return null;
  const { largeur, hauteur } = carte;

  // Classes de la choroplèthe (quantiles, 5 max)
  const valeursPresentes = valeurs
    ? Object.values(valeurs).filter((v) => Number.isFinite(v))
    : [];
  const choroplethe = valeursPresentes.length > 0;
  const seuils = choroplethe ? seuilsQuantiles(valeursPresentes, 5) : [];
  const nbClasses = seuils.length + 1;
  // classes réparties sur la rampe (1 classe → pas central --seq-5)
  const pasRampe =
    nbClasses === 1
      ? [RAMPE[2]]
      : Array.from({ length: nbClasses }, (_, i) => RAMPE[Math.round((i * (RAMPE.length - 1)) / (nbClasses - 1))]);
  const classeDe = (v: number) => seuils.filter((s) => v > s).length;

  const min = choroplethe ? Math.min(...valeursPresentes) : 0;
  const max = choroplethe ? Math.max(...valeursPresentes) : 0;
  const bornes = [min, ...seuils, max];
  const manquants = choroplethe
    ? departements.some((d) => !Number.isFinite(valeurs?.[d.code]))
    : false;

  // Points : aire ∝ poids (r = 3 → 14px). La projection n'est reconstruite
  // que s'il y a des points à placer — les contours, eux, arrivent tracés.
  const projection =
    points && points.length > 0 ? projectionFrance(carte.echelle, carte.translation) : null;
  const poidsMax = points && points.length > 0 ? Math.max(...points.map((p) => p.poids), 0) || 1 : 1;
  const rayon = (poids: number) => 3 + 11 * Math.sqrt(Math.max(poids, 0) / poidsMax);

  const remplissage = (dep: TraceDepartement) => {
    if (!choroplethe) return "var(--surface-raised)"; // carte neutre (pas d'encodage)
    const v = valeurs?.[dep.code];
    if (v === undefined || !Number.isFinite(v)) return "var(--map-manquant)";
    return pasRampe[classeDe(v)];
  };

  const poserTip = (
    e: PointerEvent<SVGElement>,
    nom: string,
    valeur: string,
  ) => {
    const cadre = e.currentTarget.ownerSVGElement?.parentElement;
    if (!cadre) return;
    const box = cadre.getBoundingClientRect();
    const x = e.clientX - box.left;
    const y = e.clientY - box.top;
    setTip({ nom, valeur, x, y });
  };

  return (
    <figure
      className={`relative ${className ?? ""}`}
      tabIndex={0}
      aria-label={ariaLabel}
    >
      <svg
        viewBox={`0 0 ${largeur} ${hauteur}`}
        style={{ width: "100%", height: "auto" }}
        aria-hidden="true"
        onPointerLeave={() => setTip(null)}
      >
        <style>{`.ft-map-dep:hover { filter: brightness(1.18); } .ft-map-pt:hover circle { filter: brightness(1.18); }
          @media (prefers-reduced-motion: reduce) { .ft-map-dep:hover, .ft-map-pt:hover circle { filter: none; } }`}</style>
        <defs>
          {/* halo « lumineux » : même teinte que le point, 0,35 → 0 (§8) */}
          <radialGradient id="ft-map-halo">
            <stop offset="0%" style={{ stopColor: "var(--viz-serie-1)", stopOpacity: 0.35 }} />
            <stop offset="100%" style={{ stopColor: "var(--viz-serie-1)", stopOpacity: 0 }} />
          </radialGradient>
        </defs>
        {/* départements */}
        {departements.map((dep, i) => {
          const { code, nom, d } = dep;
          const v = valeurs?.[code];
          const releve =
            choroplethe && (v === undefined || !Number.isFinite(v))
              ? "donnée manquante"
              : v !== undefined && Number.isFinite(v)
                ? formatValeur(v)
                : null;
          const libelle = code ? `${nom} (${code})` : nom;
          return (
            <path
              key={code || i}
              className="ft-map-dep"
              d={d}
              fill={remplissage(dep)}
              stroke="var(--map-contour)"
              strokeWidth={1}
              vectorEffect="non-scaling-stroke"
              onPointerEnter={(e) => poserTip(e, libelle, releve ?? "—")}
              onPointerMove={(e) => poserTip(e, libelle, releve ?? "—")}
            />
          );
        })}
        {/* villes lumineuses */}
        {points?.map((p, i) => {
          const projete = projection?.([p.lon, p.lat]);
          if (!projete) return null;
          const [x, y] = projete;
          const r = rayon(p.poids);
          return (
            <g
              key={`${p.label}-${i}`}
              className="ft-map-pt"
              onPointerEnter={(e) => poserTip(e, p.label, formatValeur(p.poids))}
              onPointerMove={(e) => poserTip(e, p.label, formatValeur(p.poids))}
            >
              <circle cx={x} cy={y} r={r * 2.5} fill="url(#ft-map-halo)" />
              <circle cx={x} cy={y} r={r} fill="var(--viz-serie-1)" />
              {/* cible de survol ≥ 24px (§5/§8) */}
              <circle cx={x} cy={y} r={Math.max(12, r)} fill="transparent" />
            </g>
          );
        })}
      </svg>
      {tip && (
        <TooltipGraphique
          lignes={[{ nom: tip.nom, valeur: tip.valeur, couleur: "var(--viz-serie-1)" }]}
          style={{
            left: tip.x,
            top: tip.y,
            transform:
              tip.x < 80
                ? "translate(8px, calc(-100% - 8px))"
                : "translate(-50%, calc(-100% - 8px))",
          }}
        />
      )}
      {/* légende d'échelle obligatoire (§8) */}
      {(choroplethe || (points && points.length > 0)) && (
        <figcaption className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-ink-secondary">
          {legendeTitre && <span className="font-medium text-ink-secondary">{legendeTitre}</span>}
          {choroplethe && (
            <span className="inline-flex items-center gap-1.5">
              <span className="text-ink-muted">{formatValeur(bornes[0])}</span>
              <span className="inline-flex overflow-hidden rounded-[3px]">
                {pasRampe.map((c, i) => (
                  <span
                    key={i}
                    className="inline-block h-2.5 w-6"
                    style={{ background: c }}
                    aria-label={`${formatValeur(bornes[i])} – ${formatValeur(bornes[i + 1])}`}
                  />
                ))}
              </span>
              <span className="text-ink-muted">{formatValeur(bornes[bornes.length - 1])}</span>
            </span>
          )}
          {manquants && (
            <span className="inline-flex items-center gap-1.5 text-ink-muted">
              <span className="inline-block h-2.5 w-2.5 rounded-[3px]" style={{ background: "var(--map-manquant)" }} />
              donnée manquante
            </span>
          )}
          {points && points.length > 0 && (
            <span className="inline-flex items-center gap-1.5 text-ink-muted">
              <span
                className="inline-block size-2.5 rounded-full"
                style={{ background: "var(--viz-serie-1)" }}
              />
              aire du point ∝ valeur
            </span>
          )}
        </figcaption>
      )}
    </figure>
  );
}
