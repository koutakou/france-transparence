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
