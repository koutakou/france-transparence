import { formatNombre } from "@/lib/format";
import { ecarteEtiquettes, indicesEtiquettesX, ticksRonds } from "./echelle";
import { cssSurvolColonnes, TooltipGraphique } from "./TooltipGraphique";

/**
 * Courbes (tendance dans le temps) — SVG maison, 1 à 3 séries MAX.
 *
 * Specs DATAVIZ :
 * - lignes 2px, jointures/bouts arrondis (§4) ;
 * - grille horizontale 1px `--viz-grid` (3–6 lignes, jamais pointillée),
 *   PAS de grille verticale ; ligne de base `--viz-axis` 1px ; ticks Y en
 *   nombres ronds, `--ink-muted` 11px (§4) ;
 * - couleurs : slots catégoriels dans l'ordre (`--viz-serie-1..3`), la
 *   couleur suit l'entité (§3.1) ; pour l'emphase, passer le contexte en
 *   `couleur: "var(--viz-autre)"` ;
 * - légende dès 2 séries (trait 16×2px), AUCUNE boîte de légende pour une
 *   série unique — le titre de la carte la nomme (§4) ;
 * - étiquetage sélectif : valeur en FIN de ligne (§4) ;
 * - survol §5 : le réticule trouve le X (filet 1px `--viz-crosshair` aimanté
 *   par colonne), marqueurs ≥ 8px à anneau 2px `--surface-card`, et UN
 *   tooltip HTML (pas le `<title>` SVG) listant TOUTES les séries à ce X,
 *   valeur d'abord. Un seul arrêt clavier sur le graphe (`tabIndex={0}`),
 *   pas un par point. Vue tableau jumelle à fournir par la page (§9).
 *
 * `valeurs[i] === null` = trou de donnée (la ligne s'interrompt — jamais de
 * donnée fabriquée). Vue tableau jumelle à fournir par la page (§9).
 *
 * @example
 * <LineChart
 *   labels={["jan", "fév", "mar", "avr"]}
 *   series={[
 *     { nom: "2026", valeurs: [410, 425, null, 431] },
 *     { nom: "2025", valeurs: [402, 411, 407, 415], couleur: "var(--viz-autre)" },
 *   ]}
 *   formatValeur={(v) => `${formatNombre(v, 0)} M€`}
 * />
 */
export interface LineChartSerie {
  nom: string;
  /** Alignées sur `labels` ; `null` = donnée manquante (trou). */
  valeurs: (number | null)[];
  /** Override (emphase/dé-emphase) — défaut : slot catégoriel suivant. */
  couleur?: string;
}

export interface LineChartProps {
  /** Catégories X (dates, mois…), partagées par toutes les séries. */
  labels: string[];
  /** 1 à 3 séries — au-delà, seules les 3 premières sont tracées (§ contrat). */
  series: LineChartSerie[];
  formatValeur?: (v: number) => string;
  largeur?: number;
  hauteur?: number;
  /** Ancre la base à 0 quand tout est ≥ 0 (défaut true). */
  depuisZero?: boolean;
  ariaLabel?: string;
  className?: string;
}

const SLOTS = ["var(--viz-serie-1)", "var(--viz-serie-2)", "var(--viz-serie-3)"];

export function LineChart({
  labels,
  series,
  formatValeur = (v) => formatNombre(v),
  largeur = 640,
  hauteur = 260,
  depuisZero = true,
  ariaLabel,
  className,
}: LineChartProps) {
  if (labels.length === 0 || series.length === 0) return null;
  if (process.env.NODE_ENV !== "production" && series.length > 3) {
    console.warn(`LineChart : ${series.length} séries reçues — 3 max (DATAVIZ §2), les suivantes sont ignorées.`);
  }
  const tracees = series.slice(0, 3).map((s, i) => ({
    ...s,
    couleur: s.couleur ?? SLOTS[i],
  }));

  const plates = tracees.flatMap((s) => s.valeurs).filter((v): v is number => v !== null && Number.isFinite(v));
  if (plates.length === 0) return null;
  const ticks = ticksRonds(Math.min(...plates), Math.max(...plates), depuisZero);
  const yMin = ticks[0];
  const yMax = ticks[ticks.length - 1];

  const margeGauche = 8 + Math.max(...ticks.map((t) => formatValeur(t).length)) * 6.6;
  const margeDroite = 12 + Math.max(...tracees.map((s) => {
    const derniere = [...s.valeurs].reverse().find((v) => v !== null);
    return derniere === undefined || derniere === null ? 0 : formatValeur(derniere).length;
  })) * 6.6;
  const margeBas = 22; // bande d'axe X incluse dans la hauteur (§4)
  const margeHaut = 10;
  const traceL = largeur - margeGauche - margeDroite;
  const traceH = hauteur - margeHaut - margeBas;

  const x = (i: number) => (labels.length === 1 ? margeGauche + traceL / 2 : margeGauche + (i * traceL) / (labels.length - 1));
  const y = (v: number) => margeHaut + (1 - (v - yMin) / (yMax - yMin || 1)) * traceH;

  /** Chemin par série, interrompu sur les null. */
  const chemin = (valeurs: (number | null)[]): string => {
    let d = "";
    let enCours = false;
    valeurs.forEach((v, i) => {
      if (v === null || !Number.isFinite(v)) {
        enCours = false;
        return;
      }
      d += `${enCours ? "L" : "M"}${x(i).toFixed(2)},${y(v).toFixed(2)} `;
      enCours = true;
    });
    return d.trim();
  };

  // étiquettes de fin (valeur en fin de ligne), écartées d'au moins 14px
  const fins = tracees.map((s) => {
    for (let i = s.valeurs.length - 1; i >= 0; i--) {
      const v = s.valeurs[i];
      if (v !== null && Number.isFinite(v)) return { i, v };
    }
    return null;
  });
  const ysFins = ecarteEtiquettes(fins.map((f) => (f ? y(f.v) : -100)));

  const visiblesX = indicesEtiquettesX(labels.length, 7);
  const largeurColonne = labels.length === 1 ? traceL : traceL / (labels.length - 1);

  let iDernier = labels.length - 1;
  for (let i = labels.length - 1; i >= 0; i--) {
    if (tracees.some((s) => s.valeurs[i] !== null && Number.isFinite(s.valeurs[i] as number))) {
      iDernier = i;
      break;
    }
  }

  const lignesAu = (i: number) =>
    tracees.map((s) => {
      const v = s.valeurs[i];
      return {
        nom: s.nom,
        valeur: v === null || v === undefined || !Number.isFinite(v) ? "donnée manquante" : formatValeur(v),
        couleur: s.couleur,
      };
    });

  const posTip = (i: number) => {
    const pct = (x(i) / largeur) * 100;
    const ys = tracees
      .map((s) => s.valeurs[i])
      .filter((v): v is number => v !== null && Number.isFinite(v))
      .map((v) => y(v));
    const top = ys.length > 0 ? Math.min(...ys) : margeHaut;
    return {
      left: `${pct}%`,
      top: `${(top / hauteur) * 100}%`,
      transform: pct < 18 ? "translate(0, calc(-100% - 8px))" : pct > 82 ? "translate(-100%, calc(-100% - 8px))" : "translate(-50%, calc(-100% - 8px))",
    };
  };

  return (
    <figure className={className}>
      {tracees.length >= 2 && (
        <figcaption className="mb-2 flex flex-wrap gap-x-4 gap-y-1">
          {tracees.map((s) => (
            <span key={s.nom} className="inline-flex items-center gap-1.5 text-xs text-ink-secondary">
              <span aria-hidden="true" className="inline-block h-[2px] w-4 rounded-full" style={{ background: s.couleur }} />
              {s.nom}
            </span>
          ))}
        </figcaption>
      )}
      <div
        className="ft-lc relative"
        tabIndex={ariaLabel ? 0 : undefined}
        aria-label={ariaLabel}
      >
      <style>{cssSurvolColonnes(".ft-lc", "ft-lc-col", labels.length)}</style>
      <svg
        viewBox={`0 0 ${largeur} ${hauteur}`}
        style={{ width: "100%", height: "auto" }}
        aria-hidden={ariaLabel ? true : undefined}
      >
        <style>{`
          .ft-lc-col .ft-lc-hover { opacity: 0; }
          .ft-lc-col:hover .ft-lc-hover { opacity: 1; }
        `}</style>
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
            <text x={margeGauche - 6} y={y(t) + 3.5} textAnchor="end" fontSize={11} fill="var(--ink-muted)">
              {formatValeur(t)}
            </text>
          </g>
        ))}
        <line
          x1={margeGauche}
          x2={margeGauche + traceL}
          y1={y(Math.max(yMin, 0))}
          y2={y(Math.max(yMin, 0))}
          stroke="var(--viz-axis)"
          strokeWidth={1}
          vectorEffect="non-scaling-stroke"
        />
        {/* étiquettes X (réduites pour ne jamais se percuter) */}
        {labels.map((l, i) =>
          visiblesX.has(i) ? (
            <text key={i} x={x(i)} y={hauteur - 6} textAnchor="middle" fontSize={11} fill="var(--ink-muted)">
              {l}
            </text>
          ) : null,
        )}
        {/* lignes 2px arrondies */}
        {tracees.map((s) => (
          <path
            key={s.nom}
            d={chemin(s.valeurs)}
            fill="none"
            stroke={s.couleur}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />
        ))}
        {/* valeur en fin de ligne (étiquetage sélectif, §4) */}
        {fins.map((f, k) =>
          f ? (
            <text
              key={tracees[k].nom}
              x={x(f.i) + 8}
              y={ysFins[k] + 4}
              fontSize={12}
              fill="var(--ink-secondary)"
            >
              {formatValeur(f.v)}
            </text>
          ) : null,
        )}
        {/* couche de survol : une colonne par X — réticule + marqueurs + tooltip toutes-séries */}
        {labels.map((_, i) => {
          return (
            <g key={`col-${i}`} className="ft-lc-col" data-i={i}>
              <rect
                x={x(i) - largeurColonne / 2}
                y={margeHaut}
                width={largeurColonne}
                height={traceH}
                fill="transparent"
              />
              <g className="ft-lc-hover">
                <line
                  x1={x(i)}
                  x2={x(i)}
                  y1={margeHaut}
                  y2={margeHaut + traceH}
                  stroke="var(--viz-crosshair)"
                  strokeWidth={1}
                  vectorEffect="non-scaling-stroke"
                />
                {tracees.map((s) => {
                  const v = s.valeurs[i];
                  if (v === null || !Number.isFinite(v)) return null;
                  return (
                    <circle
                      key={s.nom}
                      cx={x(i)}
                      cy={y(v)}
                      r={4}
                      fill={s.couleur}
                      stroke="var(--surface-card)"
                      strokeWidth={2}
                    />
                  );
                })}
              </g>
            </g>
          );
        })}
      </svg>
        {labels.map((l, i) => (
          <TooltipGraphique
            key={`tip-${l}-${i}`}
            data-i={i}
            data-dernier={i === iDernier}
            titre={l}
            lignes={lignesAu(i)}
            style={posTip(i)}
          />
        ))}
      </div>
    </figure>
  );
}
