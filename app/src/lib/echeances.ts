/**
 * Échéances d'appels d'offres — fonctions PURES, sans import.
 *
 * Le site est un export statique : `datetime('now')` est évalué UNE fois, à
 * la construction (tôt le matin, heure de Paris), et la page est ensuite servie
 * jusqu'à la publication suivante — plusieurs jours si une publication
 * échoue. Une liste « proches de la clôture » arrêtée à la construction
 * montre donc, l'après-midi, des appels d'offres déjà clos. Le navigateur
 * retire ceux dont la date limite est passée À SON HEURE ; pour qu'il lui en
 * reste à montrer, la construction livre une RÉSERVE définie par une DURÉE,
 * pas par un nombre de lignes : environ 480 appels d'offres ferment par jour
 * ouvré (481 le 16/10/2026 dans la base du 15/10, dont 133 à midi pile), un
 * nombre fixe de lignes est épuisé en quelques heures.
 */

/** Lignes affichées par la liste de /marches (et par famille). */
export const AO_AFFICHEES = 20;
/** Lignes affichées sur l'accueil. */
export const AO_ACCUEIL_AFFICHEES = 4;
/**
 * Durée couverte par la réserve, depuis la construction : jusqu'au lendemain
 * soir et au-delà de la publication suivante (une page construite à 07 h est
 * encore pleine à 23 h le lendemain, 40 h plus tard ; ce cas est testé).
 */
export const RESERVE_HEURES = 48;
/** Échéances livrées en plus, au-delà de la durée de réserve. */
export const RESERVE_AU_DELA = AO_AFFICHEES;

/**
 * Réserve livrée par la construction : toutes les lignes (déjà triées par
 * date limite croissante, déjà ouvertes à `construitLe`) dont la date limite
 * tombe dans les `heures` qui suivent la construction, puis les `auDela`
 * suivantes. Une date illisible n'entre pas dans la réserve.
 */
export function reserveEcheances<T>(
  lignesTriees: readonly T[],
  dateLimite: (l: T) => string,
  construitLe: number,
  heures: number = RESERVE_HEURES,
  auDela: number = RESERVE_AU_DELA,
): T[] {
  const borne = construitLe + heures * 3_600_000;
  const reserve: T[] = [];
  let ajoutees = 0;
  for (const l of lignesTriees) {
    const t = Date.parse(dateLimite(l));
    if (!Number.isFinite(t)) continue;
    if (t > borne) {
      if (ajoutees >= auDela) break;
      ajoutees += 1;
    }
    reserve.push(l);
  }
  return reserve;
}

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
