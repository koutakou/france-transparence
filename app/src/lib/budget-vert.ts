/**
 * Périmètre du jeu « PLF 2026 : Budget vert » (S20, table `budget_vert`).
 *
 * La notice du jeu (data.economie.gouv.fr, lue le 21/11/2026) écrit que,
 * pour les crédits budgétaires et les taxes affectées plafonnées, « le champ
 * retenu est [...] celui du périmètre des dépenses de l'État (PDE) soit
 * 501 Md€ en 2026 ». En base, 479,5 Md€ de crédits budgétaires et 21,4 Md€
 * de taxes affectées plafonnées. Ce n'est pas l'ensemble des crédits du PLF :
 * la mission « Remboursements et dégrèvements » n'y figure pas, et la mission
 * « Engagements financiers de l'État » n'y compte que 1,1 Md€ (54,2 Md€ de
 * charge de la dette au PLF 2025 par destination). Les libellés servis ne
 * disent que ce que la notice dit : le nom du périmètre.
 */

/** Périmètre servi à côté de chaque chiffre tiré de `budget_vert`. */
export const PERIMETRE_BUDGET_VERT =
  "périmètre des dépenses de l’État (PDE) retenu par la notice du budget vert, pas l’ensemble des crédits du PLF";

/**
 * Libellés de `budget_vert.mission` qui ne sont pas des missions mais des
 * prélèvements sur recettes (base de production du 20/11/2026).
 */
export const PRELEVEMENTS_SUR_RECETTES = ["PSRCT", "PSRUE"] as const;
export type PrelevementSurRecettes = (typeof PRELEVEMENTS_SUR_RECETTES)[number];

/** Nom complet servi à la place du sigle de la source. */
export const NOMS_PRELEVEMENTS_SUR_RECETTES: Record<PrelevementSurRecettes, string> = {
  PSRCT: "Prélèvements sur recettes au profit des collectivités territoriales",
  PSRUE: "Prélèvements sur recettes au profit de l’Union européenne",
};

const LISTE_SQL = PRELEVEMENTS_SUR_RECETTES.map((m) => `'${m}'`).join(", ");

/** Condition SQL (littéraux constants) : missions seules. */
export const SQL_MISSIONS_SEULES = `mission NOT IN (${LISTE_SQL})`;

/** Condition SQL (littéraux constants) : prélèvements sur recettes seuls. */
export const SQL_PRELEVEMENTS_SEULS = `mission IN (${LISTE_SQL})`;

/** Nom complet d'une ligne de prélèvement (le sigle si inconnu). */
export function nomPrelevement(mission: string): string {
  return (NOMS_PRELEVEMENTS_SUR_RECETTES as Record<string, string>)[mission] ?? mission;
}
