/**
 * Formats français partagés (nombres, montants, pourcentages, dates).
 * Règles : docs/DATAVIZ.md §4 « Formats de nombres (français) » —
 * espace fine insécable (U+202F) pour les milliers et devant les unités,
 * virgule décimale, compaction intelligente `4,2 M€` / `1,3 Md€`
 * (jamais `4.2M`), `%` précédé d'une espace fine insécable.
 *
 * Module PUR : aucun accès base/réseau — importable côté serveur et client.
 */

/** Espace fine insécable — séparateur de milliers et d'unité. */
export const ESPACE_FINE = "\u202F";

/** Normalise les espaces produits par Intl (U+0020 / U+00A0) en U+202F. */
function normaliseEspaces(s: string): string {
  return s.replace(/[\u0020\u00A0]/g, ESPACE_FINE);
}

function nf(decimalesMax: number, decimalesMin = 0, signe = false): Intl.NumberFormat {
  return new Intl.NumberFormat("fr-FR", {
    maximumFractionDigits: decimalesMax,
    minimumFractionDigits: decimalesMin,
    signDisplay: signe ? "always" : "auto",
  });
}

/** `1284` → `1 284` (espace fine insécable, virgule décimale). */
export function formatNombre(v: number, decimales = 0): string {
  if (!Number.isFinite(v)) return "—";
  return normaliseEspaces(nf(decimales).format(v));
}

export type CompactionEuros = "auto" | "aucune" | "k" | "M" | "Md";

/**
 * Montant en euros, compaction intelligente :
 * `845` → `845 €` ; `12 480` → `12 480 €` ; `4 235 000` → `4,2 M€` ;
 * `1 300 000 000` → `1,3 Md€`. `compaction` force une unité si besoin
 * (utile pour homogénéiser une rangée de KPI).
 */
export function formatEuros(v: number, compaction: CompactionEuros = "auto"): string {
  if (!Number.isFinite(v)) return "—";
  const abs = Math.abs(v);
  let unite = "€";
  let u = v;
  const cible =
    compaction === "auto"
      ? abs >= 1e9
        ? "Md"
        : abs >= 1e6
          ? "M"
          : "aucune"
      : compaction;
  if (cible === "Md") {
    u = v / 1e9;
    unite = "Md€";
  } else if (cible === "M") {
    u = v / 1e6;
    unite = "M€";
  } else if (cible === "k") {
    u = v / 1e3;
    unite = "k€";
  }
  const decimales = unite === "€" ? 0 : Math.abs(u) >= 100 ? 0 : 1;
  return normaliseEspaces(nf(decimales).format(u)) + ESPACE_FINE + unite;
}

/**
 * Pourcentage : `12,4` → `12,4 %`. `signe: true` force `+`/`-`
 * (obligatoire pour un delta — DATAVIZ §3.5 : flèche + signe toujours).
 */
export function formatPct(v: number, decimales = 1, signe = false): string {
  if (!Number.isFinite(v)) return "—";
  return normaliseEspaces(nf(decimales, 0, signe).format(v)) + ESPACE_FINE + "%";
}

/** Date ISO → `JJ/MM/AAAA` (convention d'affichage fraîcheur, ARCHITECTURE §5). */
export function formatDateFr(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Europe/Paris",
  }).format(d);
}
