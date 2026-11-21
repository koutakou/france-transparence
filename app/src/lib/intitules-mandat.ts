/**
 * Intitulés de mandat d'une fiche d'élu, accordés au sexe publié par la
 * source. Module PUR, testé par `npm test` (`tests/intitules-mandat.test.mjs`).
 *
 * Le même intitulé sert à l'affichage et au balisage schema.org
 * (`roleName`) : une fiche ne doit pas lire « Née le … » puis « Président du
 * conseil régional » à l'écran quand son balisage, lui, est accordé.
 */

/** Libellés d'interface, épicènes (point médian) quand le sexe manque. */
export const TYPES_MANDAT: Record<string, string> = {
  depute: "Député·e",
  senateur: "Sénateur·rice",
  maire: "Maire",
  president_epci: "Président·e d’intercommunalité (EPCI)",
  president_conseil_departemental: "Président·e de conseil départemental",
  president_conseil_regional: "Président·e de conseil régional",
};

const ACCORDS: Record<string, [feminin: string, masculin: string]> = {
  depute: ["Députée", "Député"],
  senateur: ["Sénatrice", "Sénateur"],
  maire: ["Maire", "Maire"],
  president_epci: [
    "Présidente d’intercommunalité (EPCI)",
    "Président d’intercommunalité (EPCI)",
  ],
  president_conseil_departemental: [
    "Présidente de conseil départemental",
    "Président de conseil départemental",
  ],
  president_conseil_regional: ["Présidente de conseil régional", "Président de conseil régional"],
};

/**
 * Intitulé d'un type de mandat, accordé quand le sexe est publié par la
 * source. Sans sexe connu, le libellé épicène d'interface.
 */
export function titreMandat(type: string, sexe: string | null): string {
  const accord = ACCORDS[type];
  if (!accord) return TYPES_MANDAT[type] ?? type;
  if (sexe === "F") return accord[0];
  if (sexe === "M") return accord[1];
  return TYPES_MANDAT[type] ?? accord[1];
}

/**
 * Intitulé d'un mandat du RNE. La fonction publiée par le RNE est plus
 * précise que le type (« Président du conseil communautaire ») mais
 * toujours au masculin, quel que soit l'élu : seul son premier mot est
 * accordé, le reste est repris tel quel. Sans fonction, l'intitulé du type.
 */
export function intituleMandat(
  type: string | null | undefined,
  fonction: string | null | undefined,
  sexe: string | null,
): string | null {
  if (fonction) {
    if (sexe === "F") return fonction.replace(/^Président(?=\s|$)/, "Présidente");
    return fonction;
  }
  return type ? titreMandat(type, sexe) : null;
}

/**
 * Codes de mandat de la liste des déclarations HATVP (`type_mandat`), tels
 * que la HATVP les publie, et leur libellé lisible. Un code inconnu reste
 * affiché tel quel plutôt que deviné.
 */
const MANDATS_HATVP: Record<string, string> = {
  depute: "Député ou députée",
  senateur: "Sénateur ou sénatrice",
  europe: "Parlement européen",
  gouvernement: "Membre du Gouvernement",
  region: "Mandat régional",
  departement: "Mandat départemental",
  commune: "Mandat communal",
  epci: "Intercommunalité (EPCI)",
  ctsp: "Collectivité à statut particulier",
  autre: "Autre",
};

export function libelleMandatHatvp(code: string | null | undefined): string {
  if (!code) return "—";
  return MANDATS_HATVP[code] ?? code;
}
