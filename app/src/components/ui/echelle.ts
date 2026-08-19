/**
 * Échelles d'axes — helpers purs partagés par BarChart/LineChart.
 * DATAVIZ §4 : ticks Y en nombres RONDS (0, 1 000, 2 000…), 3 à 6 lignes
 * de grille horizontales.
 */

/** Arrondit un pas brut au « joli » pas 1/2/5 × 10^k le plus proche. */
function pasJoli(brut: number): number {
  const exp = Math.floor(Math.log10(brut));
  const base = 10 ** exp;
  const f = brut / base;
  if (f <= 1) return base;
  if (f <= 2) return 2 * base;
  if (f <= 5) return 5 * base;
  return 10 * base;
}

/**
 * Ticks ronds couvrant [min, max] (3 à 6 valeurs, bornes incluses).
 * `depuisZero` (défaut) ancre la base à 0 quand toutes les valeurs sont ≥ 0
 * — la ligne de base honnête d'une magnitude.
 */
export function ticksRonds(min: number, max: number, depuisZero = true): number[] {
  let lo = depuisZero && min >= 0 ? 0 : min;
  let hi = max;
  if (lo === hi) {
    // série constante : ouvrir une plage lisible autour de la valeur
    hi = lo === 0 ? 1 : lo + Math.abs(lo) * 0.25;
    if (lo > 0 && depuisZero) lo = 0;
    else if (lo === hi) lo = hi - 1;
  }
  const pas = pasJoli((hi - lo) / 4);
  const debut = Math.floor(lo / pas) * pas;
  const fin = Math.ceil(hi / pas) * pas;
  const ticks: number[] = [];
  // garde-fou flottants : nombre d'itérations borné
  const n = Math.round((fin - debut) / pas);
  for (let i = 0; i <= n && i <= 12; i++) ticks.push(debut + i * pas);
  // resserrer si plus de 6 lignes (garder 1 tick sur 2)
  return ticks.length > 6 ? ticks.filter((_, i) => i % 2 === 0 || i === ticks.length - 1) : ticks;
}

/** Réduit une liste d'étiquettes X à ~`maxVisibles` (1re et dernière gardées). */
export function indicesEtiquettesX(total: number, maxVisibles = 7): Set<number> {
  if (total <= maxVisibles) return new Set(Array.from({ length: total }, (_, i) => i));
  const pas = Math.ceil(total / maxVisibles);
  const indices = new Set<number>();
  for (let i = 0; i < total; i += pas) indices.add(i);
  indices.add(total - 1);
  return indices;
}

/** Écarte verticalement des étiquettes de fin de ligne trop proches (≥ `ecartMin` px). */
export function ecarteEtiquettes(ys: number[], ecartMin = 14): number[] {
  const ordre = ys.map((y, i) => ({ y, i })).sort((a, b) => a.y - b.y);
  for (let k = 1; k < ordre.length; k++) {
    if (ordre[k].y - ordre[k - 1].y < ecartMin) ordre[k].y = ordre[k - 1].y + ecartMin;
  }
  const resultat = ys.slice();
  for (const { y, i } of ordre) resultat[i] = y;
  return resultat;
}
