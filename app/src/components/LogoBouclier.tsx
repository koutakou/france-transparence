import { useId } from "react";

/**
 * Logo bouclier tricolore — chrome de marque du header.
 * Utilise les jetons `--tricolore-*` (globals.css) : des couleurs de
 * CHROME, jamais réutilisées comme couleurs de données (DATAVIZ §3).
 * Décoratif (aria-hidden) : le nom du site est porté par le titre adjacent.
 *
 * L'id du clipPath est unique (useId) : un second bouclier (RSS, autre
 * chrome) ne doit pas réutiliser `ft-bouclier`. Les deux-points que useId
 * insère (`:R1:`) cassent `url(#…)` SVG, d'où le sanitize.
 */
export function LogoBouclier({ taille = 28 }: { taille?: number }) {
  const uid = useId().replace(/:/g, "");
  const clipId = `ft-bouclier-${uid}`;
  return (
    <svg
      width={taille}
      height={(taille * 28) / 24}
      viewBox="0 0 24 28"
      aria-hidden="true"
      className="shrink-0"
    >
      <defs>
        <clipPath id={clipId}>
          <path d="M12 1.5 L21.5 5 V13 C21.5 19.6 17.6 24.6 12 26.6 C6.4 24.6 2.5 19.6 2.5 13 V5 Z" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${clipId})`}>
        <rect x="2" y="0" width="6.7" height="28" style={{ fill: "var(--tricolore-bleu)" }} />
        <rect x="8.7" y="0" width="6.6" height="28" style={{ fill: "var(--tricolore-blanc)" }} />
        <rect x="15.3" y="0" width="6.7" height="28" style={{ fill: "var(--tricolore-rouge)" }} />
      </g>
      <path
        d="M12 1.5 L21.5 5 V13 C21.5 19.6 17.6 24.6 12 26.6 C6.4 24.6 2.5 19.6 2.5 13 V5 Z"
        fill="none"
        stroke="var(--border-raised)"
        strokeWidth="1"
      />
    </svg>
  );
}
