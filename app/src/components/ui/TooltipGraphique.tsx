import type { CSSProperties } from "react";

/**
 * Tooltip HTML des graphiques (DATAVIZ §5) — pas le `<title>` SVG natif.
 *
 * Chrome : fond `--surface-raised`, bordure `--border-raised`, rayon 8px,
 * ombre `0 8px 24px rgba(0,0,0,0.45)`, padding 8px 10px — classes `.ft-tip*`
 * de globals.css, posées une fois pour toute la page (le style en ligne ne
 * porte que la position et la couleur de série).
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
      className={`ft-tip ${className ?? ""}`}
      style={style}
    >
      {titre ? <p className="ft-tip-titre">{titre}</p> : null}
      <ul className="ft-tip-lignes">
        {lignes.map((l) => (
          <li key={l.nom} className="ft-tip-ligne">
            {l.couleur ? (
              <span aria-hidden="true" className="ft-tip-cle" style={{ background: l.couleur }} />
            ) : null}
            <span className="ft-tip-valeur">{l.valeur}</span>
            <span className="ft-tip-nom">{l.nom}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
