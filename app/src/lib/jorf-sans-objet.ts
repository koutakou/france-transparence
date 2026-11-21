/**
 * Ministère « sans objet » d'un texte du JO : module PUR, sans import, testé
 * par tests/jorf-sans-objet.test.mjs.
 *
 * Seuls une loi, une ordonnance et une décision du Conseil constitutionnel
 * n'ont pas de ministère par nature : on y affiche « s.o. ». Un décret, un
 * arrêté ou tout autre texte sans ministère en base est un vrai manque
 * (« n.d. »). Codes de nature DILA relevés en base le 21/11/2026 : LOI,
 * DECISION, DECRET, ARRETE, AVIS, ORDONNANCE, etc. Une décision n'est du
 * Conseil constitutionnel que si son titre porte un numéro de rôle du
 * Conseil (« Décision n° 2026-1225 QPC du 16 octobre 2026 »), les autres
 * décisions publiées viennent d'autorités ou d'administrations.
 */

const NATURES_SANS_MINISTERE = new Set(["LOI", "LOI_ORGANIQUE", "LOI_CONSTIT"]);

/** Numéro de rôle du Conseil constitutionnel : année, numéro(s), série. */
const DECISION_CONSEIL_CONSTITUTIONNEL =
  /^Décision n° \d{4}-\d+(?:\/\d+)* (?:DC|QPC|L|LP|LOM|FNR|AN|SEN|PDR|ELEC|REF|ORGA|RIP|AR16|D|I)\b/u;

export function ministereSansObjet(nature: string | null, titre: string | null): boolean {
  if (!nature) return false;
  if (NATURES_SANS_MINISTERE.has(nature)) return true;
  return nature === "DECISION" && DECISION_CONSEIL_CONSTITUTIONNEL.test(titre ?? "");
}
