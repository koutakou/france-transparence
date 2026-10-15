/**
 * Périodes relatives à une date de donnée ou au moment de construction —
 * fonctions PURES, sans import : une phrase publique qui situe un chiffre
 * dans le temps (« J-1 », « trimestre en cours », « mois incomplets ») se
 * DÉRIVE de ces fonctions, jamais d'un libellé écrit en dur qui cesse d'être
 * vrai le jour où la donnée a du retard. Testées par `npm test`
 * (`app/tests/periodes.test.mjs`).
 */

const JOUR_MS = 86_400_000;

/** `AAAA-MM-JJ` du jour civil à Paris (en-CA écrit ce format). */
const FORMAT_JOUR_PARIS = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Europe/Paris",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/** Jour civil, heure de Paris, de l'instant `d` (`AAAA-MM-JJ`). */
export function jourParis(d: Date): string {
  return FORMAT_JOUR_PARIS.format(d);
}

/** Minuit UTC du jour `AAAA-MM-JJ` (préfixe d'un ISO) ; `null` si illisible. */
function jourUTC(iso: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso.trim());
  if (!m) return null;
  const t = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return Number.isNaN(t) ? null : t;
}

/**
 * La donnée est-elle datée de la VEILLE (heure de Paris) de `maintenant` ?
 * C'est la seule condition sous laquelle la mention « J-1 » est vraie : une
 * donnée en retard de plusieurs jours, ou datée du jour même, ne la porte pas.
 */
export function estVeille(dateDonnees: string, maintenant: Date): boolean {
  const donnee = jourUTC(dateDonnees);
  const aujourdhui = jourUTC(jourParis(maintenant));
  return donnee !== null && aujourdhui !== null && aujourdhui - donnee === JOUR_MS;
}
