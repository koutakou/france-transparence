/**
 * Échéances d'appels d'offres — fonctions PURES, sans import.
 *
 * Le site est un export statique : `datetime('now')` est évalué UNE fois, à
 * la construction (vers 05 h 20, heure de Paris), et la page est ensuite
 * servie toute la journée — plusieurs jours si une publication échoue. Une
 * liste « proches de la clôture » arrêtée à la construction montre donc,
 * l'après-midi, des appels d'offres déjà clos. La construction en livre
 * davantage que ce qui s'affiche ; le navigateur retire ceux dont la date
 * limite est passée À SON HEURE, et n'en garde que le nombre voulu.
 */

/** Lignes affichées par la liste de /marches (et par famille). */
export const AO_AFFICHEES = 20;
/** Lignes livrées par la construction pour /marches : réserve de la journée. */
export const AO_LIVREES = 60;
/** Lignes affichées sur l'accueil. */
export const AO_ACCUEIL_AFFICHEES = 4;
/** Lignes livrées par la construction pour l'accueil. */
export const AO_ACCUEIL_LIVREES = 20;

/**
 * Les `maxi` premières lignes dont la date limite est STRICTEMENT postérieure
 * à `maintenant` (ms depuis l'époque), dans l'ordre reçu. Une date illisible
 * n'est pas une échéance ouverte : elle est écartée, comme le fait déjà
 * `datetime(...) > datetime('now')` côté SQL.
 */
export function echeancesOuvertes<T>(
  lignes: readonly T[],
  dateLimite: (l: T) => string,
  maintenant: number,
  maxi: number,
): T[] {
  const ouvertes: T[] = [];
  for (const l of lignes) {
    if (ouvertes.length >= maxi) break;
    const t = Date.parse(dateLimite(l));
    if (Number.isFinite(t) && t > maintenant) ouvertes.push(l);
  }
  return ouvertes;
}
