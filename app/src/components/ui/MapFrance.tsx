import { geoConicConformal, geoPath } from "d3-geo";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import { formatNombre } from "@/lib/format";

/**
 * Carte de France des départements — SVG responsive, d3-geo uniquement.
 *
 * Projection : conique conforme France métropolitaine (paramètres
 * Lambert-93 : parallèles 44°/49°, méridien 3°E, latitude 46,5°N), calée
 * sur le viewBox par `fitExtent` — aucune constante d'échelle magique.
 *
 * OUTRE-MER : ignoré en v1 — ce composant suppose un GeoJSON
 * métropole + Corse (96 départements). Si des DOM (971…976) étaient
 * présents dans le fichier, le `fitExtent` écraserait la métropole pour
 * cadrer l'Atlantique/l'océan Indien : les features dont le code commence
 * par « 97 » sont donc écartées du cadrage ET du rendu. Une v2 leur devra
 * des encarts dédiés.
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
 * Tooltips : `<title>` SVG (natif, sans JS). La vue tableau jumelle (§9)
 * reste à la charge de la page.
 *
 * @example
 * <MapFrance geojson={departements}
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
  /** FeatureCollection des départements ; `properties.code` (« 01 »…« 2B », « 75 »), `properties.nom` optionnel. */
  geojson: FeatureCollection<Geometry, { code?: string; nom?: string } & Record<string, unknown>>;
  /** Valeurs par code département → choroplèthe (absent = carte neutre). */
  valeurs?: Record<string, number>;
  /** Points optionnels (villes lumineuses). */
  points?: PointCarte[];
  /** Format des valeurs (légende + tooltips) — défaut nombre fr. */
  formatValeur?: (v: number) => string;
  /** Titre court de la légende (ex. « Marchés notifiés (30 j) »). */
  legendeTitre?: string;
  largeur?: number;
  hauteur?: number;
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
  geojson,
  valeurs,
  points,
  formatValeur = (v) => formatNombre(v),
  legendeTitre,
  largeur = 520,
  hauteur = 500,
  ariaLabel = "Carte de France par département",
  className,
}: MapFranceProps) {
  // v1 : métropole + Corse seulement (voir note outre-mer en tête de fichier)
  const metropole: FeatureCollection<Geometry, MapFranceProps["geojson"]["features"][number]["properties"]> = {
    type: "FeatureCollection",
    features: geojson.features.filter((f) => !(f.properties?.code ?? "").startsWith("97")),
  };
  if (metropole.features.length === 0) return null;

  const pad = 8;
  const projection = geoConicConformal()
    .parallels([44, 49])
    .rotate([-3, 0])
    .center([0, 46.5])
    .fitExtent(
      [
        [pad, pad],
        [largeur - pad, hauteur - pad],
      ],
      metropole,
    );
  const trace = geoPath(projection);

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
    ? metropole.features.some((f) => {
        const code = f.properties?.code;
        return !code || !Number.isFinite(valeurs?.[code]);
      })
    : false;

  // Points : aire ∝ poids (r = 3 → 14px)
  const poidsMax = points && points.length > 0 ? Math.max(...points.map((p) => p.poids), 0) || 1 : 1;
  const rayon = (poids: number) => 3 + 11 * Math.sqrt(Math.max(poids, 0) / poidsMax);

  const remplissage = (f: Feature<Geometry, MapFranceProps["geojson"]["features"][number]["properties"]>) => {
    if (!choroplethe) return "var(--surface-raised)"; // carte neutre (pas d'encodage)
    const code = f.properties?.code;
    const v = code ? valeurs?.[code] : undefined;
    if (v === undefined || !Number.isFinite(v)) return "var(--map-manquant)";
    return pasRampe[classeDe(v)];
  };

  return (
    <figure className={className}>
      <svg
        viewBox={`0 0 ${largeur} ${hauteur}`}
        style={{ width: "100%", height: "auto" }}
        role="img"
        aria-label={ariaLabel}
      >
        <style>{`.ft-map-dep:hover { filter: brightness(1.18); } .ft-map-pt:hover circle { filter: brightness(1.18); }`}</style>
        <defs>
          {/* halo « lumineux » : même teinte que le point, 0,35 → 0 (§8) */}
          <radialGradient id="ft-map-halo">
            <stop offset="0%" style={{ stopColor: "var(--viz-serie-1)", stopOpacity: 0.35 }} />
            <stop offset="100%" style={{ stopColor: "var(--viz-serie-1)", stopOpacity: 0 }} />
          </radialGradient>
        </defs>
        {/* départements */}
        {metropole.features.map((f, i) => {
          const d = trace(f);
          if (!d) return null;
          const code = f.properties?.code ?? "";
          const nom = f.properties?.nom ?? code;
          const v = code ? valeurs?.[code] : undefined;
          const releve =
            choroplethe && (v === undefined || !Number.isFinite(v))
              ? "donnée manquante"
              : v !== undefined && Number.isFinite(v)
                ? formatValeur(v)
                : null;
          return (
            <path
              key={code || i}
              className="ft-map-dep"
              d={d}
              fill={remplissage(f)}
              stroke="var(--map-contour)"
              strokeWidth={1}
              vectorEffect="non-scaling-stroke"
            >
              <title>{releve ? `${nom} (${code}) : ${releve}` : `${nom}${code ? ` (${code})` : ""}`}</title>
            </path>
          );
        })}
        {/* villes lumineuses */}
        {points?.map((p, i) => {
          const projete = projection([p.lon, p.lat]);
          if (!projete) return null;
          const [x, y] = projete;
          const r = rayon(p.poids);
          return (
            <g key={`${p.label}-${i}`} className="ft-map-pt">
              <title>{`${p.label} : ${formatValeur(p.poids)}`}</title>
              <circle cx={x} cy={y} r={r * 2.5} fill="url(#ft-map-halo)" />
              <circle cx={x} cy={y} r={r} fill="var(--viz-serie-1)" />
              {/* cible de survol ≥ 24px (§5/§8) */}
              <circle cx={x} cy={y} r={Math.max(12, r)} fill="transparent" />
            </g>
          );
        })}
      </svg>
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
                    title={`${formatValeur(bornes[i])} – ${formatValeur(bornes[i + 1])}`}
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
