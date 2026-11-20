/**
 * Réserves du taux de participation aux scrutins publics, affichées au
 * contact du chiffre (fiches élus, tableau de /elus). Module PUR, sans
 * import, testé par `npm test` (tests/participation.test.mjs).
 *
 * Décision du 20/11/2026 : le taux reste publié, avec sa réserve visible à
 * côté de lui, et ne sert jamais de classement (aucun tri par ce taux).
 */

/** Ce que le taux d’un député ne mesure pas. */
export const RESERVE_PARTICIPATION_AN =
  "Ce taux compte les votes exprimés aux scrutins publics en séance, rien d’autre. Il ne mesure ni le travail en commission, ni les questions au gouvernement, ni les rapports. Une absence justifiée (mission, maladie, congé) y compte comme une absence, et un vote émis par délégation y compte comme un vote. Ce n’est pas un jugement sur l’activité d’un élu.";

/** Pourquoi les motions de censure sont écartées du calcul. */
export const METHODE_CENSURE =
  "Les motions de censure sont écartées du calcul : seuls les votes pour y sont recueillis, un député qui ne la vote pas ne peut donc pas y prendre part.";

/** Le vote de groupe au Sénat, et ce qu’il implique pour le taux. */
export const RESERVE_PARTICIPATION_SENAT =
  "Au scrutin public ordinaire du Sénat, un sénateur peut voter pour l’ensemble de son groupe. Les membres du groupe sont alors comptés comme votants sans avoir voté eux-mêmes, et les taux sont proches de 100 % par construction. Ce taux ne mesure donc pas la présence en séance, ne se compare pas à celui d’un député et n’est pas un jugement sur l’activité d’un élu.";
