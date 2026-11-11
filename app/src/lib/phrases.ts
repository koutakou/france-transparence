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

/**
 * Liste d'échéances épuisée chez le visiteur (accueil, /marches). La page ne
 * reçoit que la réserve arrêtée à sa construction (lib/echeances.ts) : quand
 * celle-ci est passée, d'autres appels d'offres de l'instantané peuvent être
 * encore ouverts. La phrase dit donc ce que la page a reçu, jamais
 * qu'aucun appel d'offres n'est ouvert. `construction` est déjà formatée.
 */
export function phraseEcheancesEpuisees(construction: string, heures: number): string {
  return `Les échéances livrées avec cette page, arrêtées à sa construction (${construction}) pour les ${heures} heures suivantes, sont toutes passées à cette heure ; les appels d’offres qui clôturent plus tard n’y figurent pas. La liste est reconstruite à chaque publication du site.`;
}

/**
 * Début du compteur de /marches : « 20 échéances encore ouvertes, les plus
 * proches, affichées sur », accordé, et sans « 0 échéances » quand la liste
 * livrée est épuisée. `nombre` est le compte déjà formaté.
 */
export function debutCompteEcheances(n: number, nombre: string): string {
  if (n === 0) return "Aucune échéance encore ouverte dans la liste livrée avec la page, sur";
  if (n === 1) return `${nombre} échéance encore ouverte, la plus proche, affichée sur`;
  return `${nombre} échéances encore ouvertes, les plus proches, affichées sur`;
}
