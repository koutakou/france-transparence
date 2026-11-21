/**
 * Ligne de compte de la liste des alertes. La liste montre aussi les
 * synthèses (TYPES_SYNTHESES), qui récapitulent des alertes déjà comptées :
 * elles sont nommées à part, pour que la liste ne dise jamais un autre
 * nombre d'alertes que la tuile « Alertes au total ». Module pur : le
 * format des nombres est passé par l'appelant (`formatNombre`).
 */
export function libelleCompteAlertes(
  lignes: number,
  syntheses: number,
  page: number,
  pages: number,
  formatNombre: (n: number) => string = String,
): string {
  if (lignes === 0) return "Aucune alerte ne correspond à ces filtres.";
  const nbSyntheses = Math.min(Math.max(syntheses, 0), lignes);
  const nbAlertes = lignes - nbSyntheses;
  const parties: string[] = [];
  if (nbAlertes > 0) {
    parties.push(`${formatNombre(nbAlertes)} alerte${nbAlertes > 1 ? "s" : ""}`);
  }
  if (nbSyntheses > 0) {
    parties.push(
      `${formatNombre(nbSyntheses)} synthèse${nbSyntheses > 1 ? "s" : ""}`,
    );
  }
  return `${parties.join(" et ")}, page ${formatNombre(page)} sur ${formatNombre(pages)}`;
}
