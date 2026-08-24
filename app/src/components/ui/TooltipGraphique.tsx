import type { CSSProperties } from "react";

/**
 * Tooltip HTML des graphiques (DATAVIZ §5) — pas le `<title>` SVG natif.
 *
 * Chrome : fond `--surface-raised`, bordure `--border-raised`, rayon 8px,
 * ombre `0 8px 24px rgba(0,0,0,0.45)`, padding 8px 10px.
 * Ligne : clé = trait 12×2px de la couleur de série, **valeur d'abord**
 * (semibold `--ink-primary`), nom ensuite (`--ink-secondary`).
 *
 * Les noms passent en enfants JSX (`textContent`) — jamais `innerHTML`.
 * Visible/caché : le parent commande via `className` / `:has()` / état.
 * Aucune animation (respect `prefers-reduced-motion` par absence).
 */
export interface LigneTooltip {
  valeur: string;
  nom: string;
  couleur?: string;
}

/**
 * Règles CSS : le survol d'une colonne SVG `.col[data-i]` montre le
 * `.ft-tip[data-i]` HTML frère (pas le `<title>` natif). Un seul
 * `:focus-visible` sur le conteneur montre le point `data-dernier` —
 * jamais un tab stop par marque (refus G2 / G8).
 */
export function cssSurvolColonnes(conteneur: string, colonne: string, n: number): string {
  const hover = Array.from(
    { length: n },
    (_, i) =>
      `${conteneur}:has(.${colonne}[data-i="${i}"]:hover) .ft-tip[data-i="${i}"]{opacity:1;visibility:visible}`,
  );
  const focus = `${conteneur}:focus-visible:not(:has(.${colonne}:hover)) .ft-tip[data-dernier="1"]{opacity:1;visibility:visible}`;
  return `${conteneur} .ft-tip{opacity:0;visibility:hidden}${hover.join("")}${focus}`;
}

export interface TooltipGraphiqueProps {
  lignes: LigneTooltip[];
  /** Libellé X (mois, département…) — secondaire, au-dessus des lignes. */
  titre?: string;
  className?: string;
  style?: CSSProperties;
  /** Index de colonne/segment, lu par les règles `:has()` du parent. */
  "data-i"?: number;
  /** Tooltip montré au focus du graphe (un seul arrêt clavier). */
  "data-dernier"?: boolean;
}

const CHROME: CSSProperties = {
  background: "var(--surface-raised)",
  border: "1px solid var(--border-raised)",
  borderRadius: 8,
  boxShadow: "0 8px 24px rgba(0,0,0,0.45)",
  padding: "8px 10px",
};

export function TooltipGraphique({
  lignes,
  titre,
  className,
  style,
  "data-i": dataI,
  "data-dernier": dataDernier,
}: TooltipGraphiqueProps) {
  if (lignes.length === 0) return null;
  return (
    <div
      aria-hidden="true"
      data-i={dataI}
      data-dernier={dataDernier ? "1" : undefined}
      className={`ft-tip pointer-events-none absolute z-20 max-w-[16rem] ${className ?? ""}`}
      style={{ ...CHROME, ...style }}
    >
      {titre ? <p className="mb-1 text-[11px] leading-tight text-ink-muted">{titre}</p> : null}
      <ul className="flex flex-col gap-0.5">
        {lignes.map((l) => (
          <li key={l.nom} className="flex items-baseline gap-2 text-[12px] leading-tight">
            {l.couleur ? (
              <span
                aria-hidden="true"
                className="inline-block shrink-0 self-center rounded-full"
                style={{ width: 12, height: 2, background: l.couleur }}
              />
            ) : null}
            <span className="font-semibold text-ink">{l.valeur}</span>
            <span className="text-ink-secondary">{l.nom}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
