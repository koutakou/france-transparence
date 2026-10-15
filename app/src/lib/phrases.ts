/**
 * Phrases publiques qui dépendent d'un compte (accord en nombre, cas zéro).
 * Module PUR, testé par `npm test` (tests/phrases.test.mjs).
 */

/**
 * Marchés notifiés sans montant : « Aucun marché… », « 1 marché est… »,
 * « 12 marchés sont… ». `nombre` est le compte déjà formaté.
 */
export function phraseMarchesSansMontant(n: number, nombre: string): string {
  if (n === 0) return "Aucun marché n’est notifié sans montant renseigné.";
  if (n === 1) {
    return `${nombre} marché est notifié sans montant renseigné : compté dans le nombre de marchés, exclu de toutes les sommes.`;
  }
  return `${nombre} marchés sont notifiés sans montant renseigné : comptés dans le nombre de marchés, exclus de toutes les sommes.`;
}
