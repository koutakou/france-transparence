/**
 * Sparkline SVG — tendance nue, sans axes ni grille (DATAVIZ §6).
 * Trait 2px, jointures et bouts arrondis. En mode `emphaseFin` (contrat de
 * la stat tile) : ligne en `--viz-autre`, dernier segment + point terminal
 * en `--viz-serie-1`, le point portant un anneau 2px `--surface-card` pour
 * rester lisible en croisant la ligne (règle des deux séparateurs, §4).
 *
 * 12 points attendus pour une stat tile (§6) ; tout tableau non vide est
 * accepté. Composant pur : aucune donnée en dur.
 *
 * @example <Sparkline valeurs={[3,4,4,5,6,5,7,8,8,9,10,11]} emphaseFin />
 */
export interface SparklineProps {
  valeurs: number[];
  /** Couleur du trait — défaut `var(--viz-serie-1)`. */
  couleur?: string;
  /** Style stat tile : ligne `--viz-autre`, fin en `--viz-serie-1`. */
  emphaseFin?: boolean;
  largeur?: number;
  hauteur?: number;
  /** Description accessible (sinon l'élément est décoratif, aria-hidden). */
  ariaLabel?: string;
  className?: string;
}

export function Sparkline({
  valeurs,
  couleur = "var(--viz-serie-1)",
  emphaseFin = false,
  largeur = 120,
  hauteur = 32,
  ariaLabel,
  className,
}: SparklineProps) {
  const n = valeurs.length;
  if (n === 0) return null;

  const pad = 3; // marge pour le trait 2px et le point terminal
  const min = Math.min(...valeurs);
  const max = Math.max(...valeurs);
  const plage = max - min || 1; // série plate → ligne médiane
  const x = (i: number) => (n === 1 ? largeur / 2 : pad + (i * (largeur - 2 * pad)) / (n - 1));
  const y = (v: number) => pad + (1 - (v - min) / plage) * (hauteur - 2 * pad);
  const pts = valeurs.map((v, i) => [x(i), y(v)] as const);
  const chemin = (liste: readonly (readonly [number, number])[]) =>
    liste.map(([px, py], i) => `${i === 0 ? "M" : "L"}${px.toFixed(2)},${py.toFixed(2)}`).join(" ");

  const traitBase = emphaseFin ? "var(--viz-autre)" : couleur;
  const fin = pts[n - 1];

  return (
    <svg
      width={largeur}
      height={hauteur}
      viewBox={`0 0 ${largeur} ${hauteur}`}
      className={className}
      role={ariaLabel ? "img" : undefined}
      aria-label={ariaLabel}
      aria-hidden={ariaLabel ? undefined : true}
    >
      <path
        d={chemin(pts)}
        fill="none"
        stroke={traitBase}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {emphaseFin && n >= 2 && (
        <path
          d={chemin(pts.slice(n - 2))}
          fill="none"
          stroke="var(--viz-serie-1)"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}
      {emphaseFin && (
        <circle
          cx={fin[0]}
          cy={fin[1]}
          r={3}
          fill="var(--viz-serie-1)"
          stroke="var(--surface-card)"
          strokeWidth={2}
        />
      )}
    </svg>
  );
}
