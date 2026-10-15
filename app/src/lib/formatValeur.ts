import { ESPACE_FINE, formatEuros, formatNombre, formatPct } from "@/lib/format";

/**
 * Format de valeur SÉRIALISABLE : une fonction ne traverse pas la frontière
 * serveur → client, un objet si. Les îles client (components/client/
 * Graphiques.tsx) le traduisent en fonction avec `formateur`. Module neutre
 * (ni serveur ni client) : la page l'importe pour construire ses specs.
 */
export type FormatValeur =
  /** `formatNombre(v / diviseur, decimales)` suivi de `suffixe` (« Md€ »…). */
  | { type: "nombre"; decimales?: number; diviseur?: number; suffixe?: string }
  /** `formatPct(v, decimales)`. */
  | { type: "pct"; decimales?: number }
  /** `formatEuros(v)` (compaction automatique). */
  | { type: "euros" };

/**
 * Milliards d'euros, suffixe insécable : `formatMd(2)` → « 12,34 Md€ » pour une
 * valeur déjà en Md€, `formatMd(2, 1e9)` pour une valeur en euros.
 */
export function formatMd(decimales: number, diviseur = 1): FormatValeur {
  return { type: "nombre", decimales, diviseur, suffixe: `${ESPACE_FINE}Md€` };
}

export function formateur(format: FormatValeur | undefined): (v: number) => string {
  if (!format) return (v) => formatNombre(v);
  switch (format.type) {
    case "pct":
      return (v) => formatPct(v, format.decimales);
    case "euros":
      return (v) => formatEuros(v);
    default: {
      const { decimales = 0, diviseur = 1, suffixe = "" } = format;
      return (v) => `${formatNombre(v / diviseur, decimales)}${suffixe}`;
    }
  }
}
