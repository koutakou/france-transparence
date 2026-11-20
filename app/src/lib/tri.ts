/**
 * Ordre alphabétique français des listes de personnes. Module PUR, testé
 * par `npm test` (tests/tri.test.mjs).
 *
 * SQLite trie en BINAIRE : les minuscules après les majuscules, les lettres
 * accentuées après « z ». « de Courson » se rangeait après « Youssouffa »,
 * « Éblé » en dernier. La collation française ignore casse et accents ; le
 * nom affiché est trié tel qu'il s'écrit (« de Courson » à la lettre D).
 */
const COLLATION = new Intl.Collator("fr", { sensitivity: "base" });

export function comparerNomPrenom(
  a: { nom: string; prenom: string | null },
  b: { nom: string; prenom: string | null },
): number {
  return COLLATION.compare(a.nom, b.nom) || COLLATION.compare(a.prenom ?? "", b.prenom ?? "");
}

/**
 * Tris proposés sur les tableaux de parlementaires : nom ou groupe, rien
 * d’autre. Décision du 20/11/2026 : un tri par taux de participation ferait
 * de la colonne un classement, ce que ce taux ne permet pas (voir
 * lib/participation.ts).
 */
export const TRIS_PARLEMENTAIRES = [
  { valeur: "nom", libelle: "Nom" },
  { valeur: "groupe", libelle: "Groupe" },
] as const;

export type TriParlementaires = (typeof TRIS_PARLEMENTAIRES)[number]["valeur"];

/** Valeur d’URL ou de formulaire → tri connu, sinon le tri par nom. */
export function lireTriParlementaires(valeur: string | null | undefined): TriParlementaires {
  return TRIS_PARLEMENTAIRES.some((t) => t.valeur === valeur)
    ? (valeur as TriParlementaires)
    : "nom";
}

/**
 * Copie triée. Par groupe : groupe dans l’ordre alphabétique français, sans
 * groupe en dernier, puis nom et prénom.
 */
export function trierParlementaires<T extends { nom: string; prenom: string | null }>(
  lignes: readonly T[],
  tri: TriParlementaires,
  groupeDe: (l: T) => string | null,
): T[] {
  const copie = [...lignes];
  if (tri === "nom") return copie.sort(comparerNomPrenom);
  return copie.sort((a, b) => {
    const ga = groupeDe(a);
    const gb = groupeDe(b);
    if (ga === null || gb === null) {
      if (ga !== gb) return ga === null ? 1 : -1;
    } else {
      const c = COLLATION.compare(ga, gb);
      if (c) return c;
    }
    return comparerNomPrenom(a, b);
  });
}
