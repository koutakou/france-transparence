/**
 * Onglet courant de la navigation principale. Module PUR, testé par
 * `npm test` (tests/navigation.test.mjs).
 *
 * Un onglet est courant sur sa page et ses sous-pages, comparées SEGMENT
 * par segment : « /donnees-personnelles » commence par les caractères
 * « /donnees » sans être une sous-page de /donnees.
 */
export function estActif(href: string, pathname: string): boolean {
  if (href === "/") return pathname === "/";
  const base = href.endsWith("/") ? href.slice(0, -1) : href;
  return pathname === base || pathname.startsWith(`${base}/`);
}
