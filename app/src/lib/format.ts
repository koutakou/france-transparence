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

/**
 * Le signe se décide sur la valeur ARRONDIE : `-0,04` à une décimale
 * s'écrit « 0 », jamais « -0 » ni « +0 » (un zéro n'a pas de sens).
 * `exceptZero` (signe forcé) et `negative` (signe des seuls négatifs)
 * appliquent cette règle d'eux-mêmes.
 */
function nf(decimalesMax: number, decimalesMin = 0, signe = false): Intl.NumberFormat {
  return new Intl.NumberFormat("fr-FR", {
    maximumFractionDigits: decimalesMax,
    minimumFractionDigits: decimalesMin,
    signDisplay: signe ? "exceptZero" : "negative",
  });
}

/** Valeur telle qu'elle s'affichera à `decimales` décimales. */
function arrondi(v: number, decimales: number): number {
  return Number(v.toFixed(decimales));
}

/** Vrai si `v` s'écrit « 0 » à `decimales` décimales (delta nul affiché). */
export function estNulAffiche(v: number, decimales: number): boolean {
  return !Number.isFinite(v) || arrondi(v, decimales) === 0;
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
  const ECHELLES = [
    { cible: "aucune", diviseur: 1, unite: "€" },
    { cible: "k", diviseur: 1e3, unite: "k€" },
    { cible: "M", diviseur: 1e6, unite: "M€" },
    { cible: "Md", diviseur: 1e9, unite: "Md€" },
  ] as const;
  const decimalesDe = (unite: string, u: number) =>
    unite === "€" ? 0 : Math.abs(u) >= 100 ? 0 : 1;
  let echelle = ECHELLES.find((e) => e.cible === compaction) ?? ECHELLES[0];
  if (compaction === "auto") {
    const abs = Math.abs(v);
    echelle = abs >= 1e9 ? ECHELLES[3] : abs >= 1e6 ? ECHELLES[2] : ECHELLES[0];
    // L'unité se choisit sur la valeur ARRONDIE : 999 950 000 s'écrit
    // « 1 Md€ », pas « 1 000 M€ » ; 999 999,6 s'écrit « 1 M€ ».
    const plafond = echelle.cible === "aucune" ? 1e6 : 1e3;
    const u = v / echelle.diviseur;
    if (echelle.cible !== "Md" && Math.abs(arrondi(u, decimalesDe(echelle.unite, u))) >= plafond) {
      echelle = echelle.cible === "aucune" ? ECHELLES[2] : ECHELLES[3];
    }
  }
  const u = v / echelle.diviseur;
  return (
    normaliseEspaces(nf(decimalesDe(echelle.unite, u)).format(u)) + ESPACE_FINE + echelle.unite
  );
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
