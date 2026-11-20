/**
 * Ce que la loi dit de la déclaration de patrimoine, selon le mandat de la
 * fiche. Le sous-titre de la carte « Déclarations HATVP » disait à tous
 * « il se consulte en préfecture », alors que cette consultation (art.
 * LO 135-2 du code électoral) ne vaut que pour les parlementaires : la
 * déclaration de patrimoine d'un président de conseil régional ou
 * départemental n'est pas rendue publique du tout (loi n° 2013-907 du
 * 11 octobre 2013, art. 11 et 12 : seule sa déclaration d'intérêts l'est).
 * La phrase était donc fausse sur toutes les fiches d'exécutif local.
 */
export function mentionPatrimoine(parlementaire: boolean): string {
  return parlementaire
    ? "Le contenu des déclarations de patrimoine n’est pas affiché : celle d’un parlementaire n’est consultable qu’en préfecture, par les électeurs du département, et sa divulgation est interdite (art. LO 135-2 du code électoral)."
    : "Le contenu des déclarations de patrimoine n’est pas affiché : pour un président de conseil régional ou départemental, la loi ne rend pas publique la déclaration de patrimoine, seule la déclaration d’intérêts l’est (loi n° 2013-907 du 11 octobre 2013, art. 11 et 12).";
}
