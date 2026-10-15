/**
 * Pourquoi une commune suivie par le site manque aux résultats d'un scrutin.
 * Module PUR (testé par `npm test`, tests/absences-electorales.test.mjs).
 *
 * Une raison n'est écrite que si elle est STRUCTURELLE et vraie pour la
 * famille et le tour affichés (docs/ELECTIONS.md, piège 3). Sinon la commune
 * est nommée absente, sans raison inventée.
 */

/** Saint-Barthélemy et Saint-Martin : absentes des seules municipales. */
const CONSEIL_TERRITORIAL: Record<string, string> = {
  "97701": "Saint-Barthélemy",
  "97801": "Saint-Martin",
};

/** Uvea : absente de tous les scrutins (Wallis-et-Futuna publié en bloc). */
const UVEA = "98613";

export interface ScrutinAbsences {
  /** Libellé de famille (« Municipales », « Législatives »…). */
  famille: string;
  tour: number;
}

/** Codes suivis absents du scrutin, dans l'ordre de `suivis`. */
export function codesAbsents(suivis: string[], presents: Iterable<string>): string[] {
  const ici = new Set(presents);
  return suivis.filter((c) => !ici.has(c));
}

/**
 * Phrases d'explication, dans l'ordre : absences structurelles, puis le
 * reste. `nom(code)` rend le libellé connu d'une commune, ou son code.
 */
export function expliquerAbsences(
  scrutin: ScrutinAbsences,
  absents: string[],
  nom: (code: string) => string,
): string[] {
  const municipales = scrutin.famille === "Municipales";
  const phrases: string[] = [];
  const restants: string[] = [];
  const territoriales: string[] = [];
  let uvea = false;
  for (const code of absents) {
    if (code === UVEA) uvea = true;
    else if (municipales && code in CONSEIL_TERRITORIAL) territoriales.push(code);
    else restants.push(code);
  }

  if (territoriales.length > 0) {
    const liste = territoriales.map((c) => `${CONSEIL_TERRITORIAL[c]} (${c})`).join(" et ");
    phrases.push(
      `${liste} ${territoriales.length > 1 ? "élisent" : "élit"} un conseil territorial, pas un conseil municipal (collectivités de l’article 74 de la Constitution).`,
    );
  }
  if (uvea) {
    phrases.push(
      "Uvea (98613) relève de Wallis-et-Futuna, territoire sans communes, dont le ministère publie les résultats sous une entité unique.",
    );
  }
  if (restants.length === 0) return phrases;

  // Les absences structurelles ont déjà leur phrase : le reste est
  // introduit comme tel, pour ne pas lui attribuer leur raison.
  const n = restants.length;
  const pour = phrases.length > 0 ? `Pour ${n > 1 ? `les ${n} autres` : "l’autre"} : ` : "";
  const majuscule = (t: string) => (pour ? t : t.charAt(0).toUpperCase() + t.slice(1));
  if (municipales && scrutin.tour >= 2) {
    phrases.push(
      pour +
        majuscule(
          "à un second tour de municipales ne votent que les communes dont le conseil n’a pas été élu dès le premier.",
        ),
    );
  } else if (scrutin.famille === "Législatives" && scrutin.tour >= 2) {
    phrases.push(
      pour +
        majuscule(
          "à un second tour de législatives ne votent que les circonscriptions sans député élu au premier ; une commune manque quand aucune des siennes n’a eu de second tour.",
        ),
    );
  } else {
    phrases.push(
      `${n > 1 ? "Absentes" : "Absente"} des résultats publiés par le ministère pour ce scrutin : ${restants.map((c) => nom(c)).join(", ")}.`,
    );
  }
  return phrases;
}
