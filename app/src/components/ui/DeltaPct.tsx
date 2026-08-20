import { formatPct } from "@/lib/format";

/**
 * Delta en pourcentage — flèche + signe + période nommée, JAMAIS la couleur
 * seule (DATAVIZ §3.5, règle absolue) :
 *
 * `couleur = signe × upIsGood`
 * - `upIsGood: null` (DÉFAUT — cas des montants de dépense) : delta NEUTRE,
 *   flèche + signe en `--ink-secondary`, ni vert ni rouge. Une hausse de
 *   dépense publique n'est pas « mauvaise », une baisse n'est pas « bonne ».
 * - `upIsGood: true` (taux de publication, délais tenus…) :
 *   hausse `--delta-bon`, baisse `--delta-mauvais`.
 * - `upIsGood: false` (retards, non-conformités, dépassements) : inversé.
 *
 * @example <DeltaPct valeur={4.2} vs="2024" />                    → ▲ +4,2 % vs 2024 (neutre)
 * @example <DeltaPct valeur={-2.1} vs="T1" upIsGood={true} />     → ▼ -2,1 % vs T1 (mauvais)
 * @example <DeltaPct valeur={12.5} vs="2025" upIsGood={false} />  → ▲ +12,5 % vs 2025 (mauvais)
 */
export interface DeltaPctProps {
  /** Variation en points de pourcentage (ex. 4.2 pour +4,2 %). */
  valeur: number;
  /** Période de comparaison NOMMÉE (« 2024 », « mois précédent »)… toujours la donner. */
  vs?: string;
  /** Jugement explicite — défaut `null` = neutre (cas des dépenses). */
  upIsGood?: boolean | null;
  /** Décimales (défaut 1). */
  decimales?: number;
  className?: string;
}

export function DeltaPct({
  valeur,
  vs,
  upIsGood = null,
  decimales = 1,
  className,
}: DeltaPctProps) {
  const nul = !Number.isFinite(valeur) || valeur === 0;
  const fleche = nul ? "" : valeur > 0 ? "▲" : "▼";
  let couleur = "var(--ink-secondary)";
  if (upIsGood !== null && !nul) {
    const bon = upIsGood ? valeur > 0 : valeur < 0;
    couleur = bon ? "var(--delta-bon)" : "var(--delta-mauvais)";
  }
  return (
    <span
      className={`inline-flex items-baseline gap-1 text-[13px] ${className ?? ""}`}
      style={{ color: couleur }}
    >
      {fleche && <span aria-hidden="true">{fleche}</span>}
      <span>
        {formatPct(valeur, decimales, true)}
        {vs ? ` vs ${vs}` : ""}
      </span>
    </span>
  );
}
