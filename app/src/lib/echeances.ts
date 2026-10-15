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

/* ------------------------------------------------------------------ */
/* Tranches horaires : le navigateur ne charge que l'heure qu'il vit   */
/* ------------------------------------------------------------------ */
//
// La réserve entière (RESERVE_HEURES de clôtures, ~1 000 lignes un jour
// ouvré) se chargeait D'ELLE-MÊME l'après-midi, dès qu'une échéance du HTML
// passait : un fragment de plusieurs centaines de Ko, sans aucun geste du
// visiteur, pour en afficher 20 (ou 4 sur l'accueil). La construction la
// découpe donc en TRANCHES d'une heure, alignées sur l'heure UTC (même
// découpage pour toutes les pages et tous les fragments d'une construction,
// quel que soit l'instant exact où chacun est rendu). La tranche d'une heure
// porte exactement les lignes qu'une visite pendant cette heure peut
// afficher — `lignesAffichables` —, ni plus ni moins.

/** Durée d'une tranche (ms). */
export const TRANCHE_MS = 3_600_000;

/** Numéro de la tranche qui contient `instant` (heures UTC depuis l'époque). */
export function trancheDe(instant: number): number {
  return Math.floor(instant / TRANCHE_MS);
}

/** Nom de fichier d'une tranche : son heure UTC, `2026-10-15T14`. */
export function nomTranche(tranche: number): string {
  return new Date(tranche * TRANCHE_MS).toISOString().slice(0, 13);
}

/** Inverse de `nomTranche` ; `null` pour un nom qui n'en est pas un. */
export function trancheDeNom(nom: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}$/.test(nom)) return null;
  const t = Date.parse(`${nom}:00:00Z`);
  return Number.isFinite(t) && nomTranche(trancheDe(t)) === nom ? trancheDe(t) : null;
}

/**
 * Tranches que la PAGE peut demander, d'après SON instant de construction :
 * de celle de la construction à celle qui contient la fin de la réserve.
 * Au-delà, le navigateur reste sur la dernière (qui porte, comme la réserve
 * d'avant, les échéances suivantes) : la liste s'épuise alors et le dit.
 */
export function tranchesDeLaPage(
  construitLe: number,
  heures: number = RESERVE_HEURES,
): { premiere: number; derniere: number } {
  return {
    premiere: trancheDe(construitLe),
    derniere: trancheDe(construitLe + heures * 3_600_000),
  };
}

/**
 * Tranches que la CONSTRUCTION écrit : celles de la page, plus une de chaque
 * côté. La page et le fragment évaluent chacun leur propre `Date.now()`,
 * à quelques secondes ou minutes d'écart : cette marge garantit que toute
 * tranche demandée par la page existe.
 */
export function tranchesAEcrire(
  construitLe: number,
  heures: number = RESERVE_HEURES,
): number[] {
  const { premiere, derniere } = tranchesDeLaPage(construitLe, heures);
  const tranches: number[] = [];
  for (let t = premiere - 1; t <= derniere + 1; t++) tranches.push(t);
  return tranches;
}

/** La tranche que la page demande à `maintenant` (bornée à sa plage). */
export function trancheAConsulter(maintenant: number, construitLe: number): number {
  const { premiere, derniere } = tranchesDeLaPage(construitLe);
  return Math.min(Math.max(trancheDe(maintenant), premiere), derniere);
}

/**
 * Les lignes que `echeancesOuvertes(lignesTriees, …, t, maxi)` peut rendre
 * pour un instant `t` QUELCONQUE de [debut, fin], et seulement elles, dans
 * l'ordre reçu. Les lignes doivent être triées par date limite croissante
 * (l'ordre du SQL, départage compris).
 *
 * La liste affichée ne change qu'au passage d'une échéance : il suffit de
 * l'évaluer à `debut` puis à chaque date limite de [debut, fin[. Une ligne
 * qui n'entre dans aucune de ces listes n'est jamais affichée pendant la
 * tranche — par exemple la 21e d'un lot de 133 clôtures à midi pile, que
 * les 20 premières du lot précèdent jusqu'à midi et qui est close ensuite.
 */
export function lignesAffichables<T>(
  lignesTriees: readonly T[],
  dateLimite: (l: T) => string,
  debut: number,
  fin: number,
  maxi: number,
): T[] {
  const lisibles: { l: T; t: number }[] = [];
  for (const l of lignesTriees) {
    const t = Date.parse(dateLimite(l));
    if (Number.isFinite(t)) lisibles.push({ l, t });
  }
  const retenues = new Set<number>();
  // Instants où la liste peut changer : debut, puis chaque date limite de
  // [debut, fin[. À chacun, la liste affichée est la fenêtre des `maxi`
  // lignes qui suivent la première date limite strictement postérieure.
  let i = 0;
  let instant = debut;
  while (i < lisibles.length && lisibles[i].t <= instant) i++;
  for (;;) {
    for (let j = i; j < Math.min(i + maxi, lisibles.length); j++) retenues.add(j);
    if (i >= lisibles.length) break;
    instant = lisibles[i].t;
    if (instant >= fin) break;
    while (i < lisibles.length && lisibles[i].t <= instant) i++;
  }
  return [...retenues].sort((a, b) => a - b).map((j) => lisibles[j].l);
}

/**
 * Contenu d'une tranche : les lignes affichables pendant l'heure `tranche`.
 * Pour toute visite à un instant de cette heure, `echeancesOuvertes` sur la
 * tranche rend EXACTEMENT ce qu'il rendrait sur la liste complète.
 */
export function contenuTranche<T>(
  lignesTriees: readonly T[],
  dateLimite: (l: T) => string,
  tranche: number,
  maxi: number,
): T[] {
  return lignesAffichables(
    lignesTriees,
    dateLimite,
    tranche * TRANCHE_MS,
    (tranche + 1) * TRANCHE_MS,
    maxi,
  );
}
