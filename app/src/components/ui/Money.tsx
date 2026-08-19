import { formatEuros, formatNombre, type CompactionEuros } from "@/lib/format";

/**
 * Montant en euros au format français (DATAVIZ §4) : espaces fines
 * insécables, virgule décimale, compaction intelligente `4,2 M€` / `1,3 Md€`.
 * Quand le montant est compacté, l'attribut `title` porte la valeur exacte.
 *
 * Couleur : `--ink-primary` par défaut. `vedette` peint `--montant`
 * (réservé aux montants VEDETTES : valeur de KPI, chiffre héros, total de
 * donut — jamais les colonnes denses d'un tableau, DATAVIZ §3.5).
 *
 * @example <Money valeur={4235000} />            → 4,2 M€
 * @example <Money valeur={12480} />              → 12 480 €
 * @example <Money valeur={1.3e9} vedette />      → 1,3 Md€ (en --montant)
 * @example <Money valeur={845} compaction="k" /> → 0,8 k€
 */
export interface MoneyProps {
  valeur: number;
  /** Unité forcée (`"aucune" | "k" | "M" | "Md"`) — défaut `"auto"`. */
  compaction?: CompactionEuros;
  /** Montant vedette : peint `--montant` (KPI, héros, total de donut). */
  vedette?: boolean;
  className?: string;
}

export function Money({ valeur, compaction = "auto", vedette = false, className }: MoneyProps) {
  const texte = formatEuros(valeur, compaction);
  const compacte = Number.isFinite(valeur) && /(k€|M€|Md€)$/.test(texte);
  return (
    <span
      className={className}
      style={vedette ? { color: "var(--montant)" } : undefined}
      title={compacte ? `${formatNombre(valeur)}\u202F€` : undefined}
    >
      {texte}
    </span>
  );
}
