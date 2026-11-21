/**
 * Listes paginées ou repliées côté client : sans JavaScript, seules les
 * premières entrées du HTML statique s'affichent. La page ne le signale
 * (`<noscript>` qui renvoie à l'export complet) que s'il existe une suite
 * au-delà de ces entrées. Module pur, utilisable au rendu serveur comme
 * dans un composant client.
 */
export function suiteMasqueeSansScript(affichees: number, total: number): boolean {
  return total > affichees;
}
