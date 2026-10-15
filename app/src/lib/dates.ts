/**
 * Arithmétique de dates civiles (ISO AAAA-MM-JJ). Module PUR, testé par
 * `npm test` (tests/dates.test.mjs).
 */

/**
 * Dernier jour du même mois, un an plus tôt : la date de comparaison
 * « N−1 » d'une situation arrêtée en fin de mois. Recopier le jour ne marche
 * pas après un 29 février (« 2027-02-29 » n'existe pas, `Date` le lit
 * 01/03/2027).
 */
export function finDeMoisAnneePrecedente(iso: string): string {
  const annee = Number(iso.slice(0, 4));
  const mois = Number(iso.slice(5, 7));
  // Jour 0 du mois suivant = dernier jour du mois voulu.
  return new Date(Date.UTC(annee - 1, mois, 0)).toISOString().slice(0, 10);
}
