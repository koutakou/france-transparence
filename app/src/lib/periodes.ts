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

/** `2026-10-14` → `2026-T4` ; `null` si la date est illisible. */
export function trimestreDe(dateIso: string): string | null {
  const m = /^(\d{4})-(\d{2})/.exec(dateIso.trim());
  if (!m) return null;
  const mois = Number(m[2]);
  if (mois < 1 || mois > 12) return null;
  return `${m[1]}-T${Math.ceil(mois / 3)}`;
}

/**
 * Le trimestre `trimestre` (`AAAA-Tn`) contient-il la date de donnée ? Seul
 * ce cas autorise à le dire « en cours » : si la donnée date du 01/10, le
 * dernier trimestre listé (T3) est clos.
 */
export function estTrimestreDeLaDonnee(trimestre: string | undefined, dateDonnees: string): boolean {
  return trimestre !== undefined && trimestre === trimestreDe(dateDonnees);
}

/** Dernier jour (minuit UTC) du mois `AAAA-MM` ; `null` si illisible. */
function finDeMois(mois: string): number | null {
  const m = /^(\d{4})-(\d{2})$/.exec(mois.trim());
  if (!m) return null;
  return Date.UTC(Number(m[1]), Number(m[2]), 0);
}

/**
 * Mois civils CLOS à la date de donnée : un mois dont le dernier jour est
 * postérieur à `dateDonnees` n'a pas fini d'exister, il ne se compare à
 * aucun autre. Les mois illisibles sont écartés, pas devinés.
 */
export function moisClos<T extends { mois: string }>(serie: T[], dateDonnees: string): T[] {
  const donnee = jourUTC(dateDonnees);
  if (donnee === null) return [];
  return serie.filter((m) => {
    const fin = finDeMois(m.mois);
    return fin !== null && fin <= donnee;
  });
}

/**
 * Premier mois `AAAA-MM` encore incomplet au sens d'un délai de publication :
 * un marché notifié le dernier jour de ce mois, ou plus tard, avait eu moins
 * de `delaiJours` jours pour être publié à la date de donnée. Avec le 9ᵉ
 * décile du délai observé, ce sont les mois dont plus d'un marché sur dix
 * peut encore manquer. `null` si une entrée est illisible.
 */
export function premierMoisIncomplet(dateDonnees: string, delaiJours: number): string | null {
  const donnee = jourUTC(dateDonnees);
  if (donnee === null || !Number.isFinite(delaiJours) || delaiJours < 0) return null;
  // Mois de la date `donnee − delai + 1 jour` : sa fin est à moins de
  // `delai` jours de la donnée, celle du mois précédent à `delai` ou plus.
  const limite = new Date(donnee - Math.round(delaiJours) * JOUR_MS + JOUR_MS);
  return limite.toISOString().slice(0, 7);
}

/**
 * Prédicat SQL d'une fenêtre de `jours` jours civils ARRÊTÉE à `@fin`, la
 * date des données de la source (`meta_sources.date_donnees`) : ]fin − jours ;
 * fin]. Jamais `date('now', …)` : évaluée au build, cette fenêtre-là
 * couvrait les 30 jours précédant la construction, se lisait « 30 derniers
 * jours » trois jours plus tard sur un site figé, et finissait sur des jours
 * vides quand la source avait du retard. Ancrée sur la donnée, elle dit la
 * même chose à toute date de lecture — à condition d'écrire `@fin` à côté.
 * `colonne` est un nom de colonne écrit dans le code, jamais une saisie.
 */
export function fenetreArreteeSql(colonne: string, jours: number): string {
  return `${colonne} > date(@fin, '-${Math.trunc(jours)} days') AND ${colonne} <= @fin`;
}
