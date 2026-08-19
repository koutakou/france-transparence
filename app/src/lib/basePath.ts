/**
 * Préfixe de base du site (GitHub Pages sert sous /france-transparence).
 *
 * `NEXT_PUBLIC_BASE_PATH` est inliné AU BUILD par Next : côté client, la
 * valeur est figée dans le bundle. Tout `fetch()` client vers une ressource
 * du site (fragments /data/*.json) DOIT passer par ce préfixe — jamais de
 * `fetch("/data/…")` nu, qui casserait sous un basePath non vide.
 */
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

/** URL absolue-site d'une ressource statique (`cheminSite` commence par `/`). */
export function urlSite(cheminSite: string): string {
  return `${BASE_PATH}${cheminSite}`;
}
