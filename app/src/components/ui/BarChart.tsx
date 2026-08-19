import { formatNombre } from "@/lib/format";
import { indicesEtiquettesX, ticksRonds } from "./echelle";

/**
 * Colonnes verticales SIMPLES (une série) — SVG maison.
 *
 * Specs DATAVIZ §4 :
 * - colonne ≤ 24px, bout de donnée arrondi 4px, CARRÉ à la ligne de base ;
 * - grille horizontale 1px `--viz-grid` (3–6 lignes, jamais pointillée),
 *   pas de grille verticale ; ligne de base `--viz-axis` 1px ;
 * - ticks Y nombres ronds 11px `--ink-muted` ;
 * - une série nominale = UNE couleur (`--viz-serie-1`) — jamais de rampe de
 *   valeur sur des catégories (§3.2) ;
 * - survol : la MARQUE est la cible (brightness 1.18 + tooltip natif
 *   `<title>`) ; valeur au sommet quand ≤ 8 colonnes (étiquetage sélectif).
 *
 * La hauteur du conteneur INCLUT la bande d'axe X (§4). Vue tableau
 * jumelle : à fournir par la page (toggle « Tableau », §7/§9).
 *
 * @example
 * <BarChart items={[{ libelle: "2022", valeur: 412 }, { libelle: "2023", valeur: 431 }]}
 *           formatValeur={(v) => `${formatNombre(v)} Md€`} />
 */
export interface BarChartItem {
  libelle: string;
  valeur: number;
  /** Dé-emphase ponctuelle uniquement (« Autre » → `var(--viz-autre)`). */
  couleur?: string;
}

export interface BarChartProps {
  items: BarChartItem[];
  /** Format des valeurs (ticks + étiquettes) — défaut nombre fr. */
  formatValeur?: (v: number) => string;
  largeur?: number;
  hauteur?: number;
  /** Ancre la base à 0 (défaut true — base honnête d'une magnitude). */
  depuisZero?: boolean;
  /** Description accessible du graphique. */
  ariaLabel?: string;
  className?: string;
}

export function BarChart({
  items,
  formatValeur = (v) => formatNombre(v),
  largeur = 560,
  hauteur = 240,
  depuisZero = true,
  ariaLabel,
  className,
}: BarChartProps) {
  if (items.length === 0) return null;

  const valeurs = items.map((i) => i.valeur).filter((v) => Number.isFinite(v));
  const ticks = ticksRonds(Math.min(...valeurs, 0), Math.max(...valeurs, 0), depuisZero);
  const yMin = ticks[0];
  const yMax = ticks[ticks.length - 1];

  const margeGauche = 8 + Math.max(...ticks.map((t) => formatValeur(t).length)) * 6.6;
  const margeBas = 22; // bande d'axe X incluse dans la hauteur (§4)
  const margeHaut = 14;
  const traceL = largeur - margeGauche - 8;
  const traceH = hauteur - margeHaut - margeBas;

  const y = (v: number) => margeHaut + (1 - (v - yMin) / (yMax - yMin || 1)) * traceH;
  const bande = traceL / items.length;
  const epaisseur = Math.min(24, Math.max(4, bande * 0.55));
  const yBase = y(Math.max(yMin, 0));
  const visiblesX = indicesEtiquettesX(items.length, 8);
  const etiquettesSommet = items.length <= 8;

  /** Colonne au bout arrondi 4px (haut), carrée à la base. */
  const cheminColonne = (x0: number, yHaut: number, yBas: number, l: number): string => {
    const r = Math.min(4, l / 2, Math.abs(yBas - yHaut));
    return [
      `M${x0.toFixed(2)},${yBas.toFixed(2)}`,
      `L${x0.toFixed(2)},${(yHaut + r).toFixed(2)}`,
      `Q${x0.toFixed(2)},${yHaut.toFixed(2)} ${(x0 + r).toFixed(2)},${yHaut.toFixed(2)}`,
      `L${(x0 + l - r).toFixed(2)},${yHaut.toFixed(2)}`,
      `Q${(x0 + l).toFixed(2)},${yHaut.toFixed(2)} ${(x0 + l).toFixed(2)},${(yHaut + r).toFixed(2)}`,
      `L${(x0 + l).toFixed(2)},${yBas.toFixed(2)}`,
      "Z",
    ].join(" ");
  };

  return (
    <svg
      viewBox={`0 0 ${largeur} ${hauteur}`}
      style={{ width: "100%", height: "auto" }}
      role={ariaLabel ? "img" : undefined}
      aria-label={ariaLabel}
      className={className}
    >
      <style>{`.ft-bc-col:hover path { filter: brightness(1.18); }`}</style>
      {/* grille horizontale 1px --viz-grid, ticks ronds --ink-muted */}
      {ticks.map((t) => (
        <g key={t}>
          <line
            x1={margeGauche}
            x2={margeGauche + traceL}
            y1={y(t)}
            y2={y(t)}
            stroke="var(--viz-grid)"
            strokeWidth={1}
            vectorEffect="non-scaling-stroke"
          />
          <text
            x={margeGauche - 6}
            y={y(t) + 3.5}
            textAnchor="end"
            fontSize={11}
            fill="var(--ink-muted)"
          >
            {formatValeur(t)}
          </text>
        </g>
      ))}
      {/* colonnes — cible de survol = la bande entière (≥ 24px, §5) */}
      {items.map((item, i) => {
        const x0 = margeGauche + i * bande + (bande - epaisseur) / 2;
        const yV = y(item.valeur);
        const haut = Math.min(yV, yBase);
        const bas = Math.max(yV, yBase);
        return (
          <g key={`${item.libelle}-${i}`} className="ft-bc-col">
            <title>{`${item.libelle} : ${formatValeur(item.valeur)}`}</title>
            <rect
              x={margeGauche + i * bande}
              y={margeHaut}
              width={bande}
              height={traceH}
              fill="transparent"
            />
            <path
              d={
                item.valeur >= 0
                  ? cheminColonne(x0, haut, bas, epaisseur)
                  : // valeur négative : bout arrondi vers le bas
                    cheminColonne(x0, haut, bas, epaisseur)
              }
              transform={
                item.valeur < 0
                  ? `rotate(180 ${(x0 + epaisseur / 2).toFixed(2)} ${((haut + bas) / 2).toFixed(2)})`
                  : undefined
              }
              fill={item.couleur ?? "var(--viz-serie-1)"}
            />
            {etiquettesSommet && item.valeur >= 0 && (
              <text
                x={x0 + epaisseur / 2}
                y={haut - 5}
                textAnchor="middle"
                fontSize={11}
                fill="var(--ink-secondary)"
              >
                {formatValeur(item.valeur)}
              </text>
            )}
            {visiblesX.has(i) && (
              <text
                x={margeGauche + i * bande + bande / 2}
                y={hauteur - 6}
                textAnchor="middle"
                fontSize={11}
                fill="var(--ink-muted)"
              >
                {item.libelle}
              </text>
            )}
          </g>
        );
      })}
      {/* ligne de base --viz-axis 1px */}
      <line
        x1={margeGauche}
        x2={margeGauche + traceL}
        y1={yBase}
        y2={yBase}
        stroke="var(--viz-axis)"
        strokeWidth={1}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
