/**
 * Règles de texte de /frais, sans base ni JSX (testées par
 * tests/frais-textes.test.mjs).
 */

/**
 * Producteurs officiels admis comme source d'un fait de /frais : loi,
 * décret, rapport de la Cour des comptes ou d'une assemblée, décision de
 * justice. La page citait un média d'opinion, un site de presse et un
 * cabinet d'avocats comme sources de faits. Décision du propriétaire du
 * 20/11/2026 : faute de source officielle, l'affirmation est retirée. Le
 * pipeline (ingest_trainvie.py) ne cite plus que ces domaines, et l'écran
 * écarte ce qui y échapperait encore (base servie avant la réingestion).
 */
const DOMAINES_OFFICIELS = [
  "assemblee-nationale.fr",
  "senat.fr",
  "ccomptes.fr",
  "conseil-etat.fr",
  "conseil-constitutionnel.fr",
  "elysee.fr",
  "gouv.fr",
] as const;

export function sourceOfficielle(url: string): boolean {
  let u: URL;
  try {
    u = new URL(url);
  } catch {
    return false;
  }
  if (u.protocol !== "https:") return false;
  const hote = u.hostname;
  return DOMAINES_OFFICIELS.some((d) => hote === d || hote.endsWith(`.${d}`));
}

/**
 * Libellé de la ligne qui explique pourquoi une donnée n'est pas publiée.
 * « Base du refus » s'affichait sur chaque cas, y compris quand personne n'a
 * rien refusé (calendrier de la Cour des comptes, choix de publication du
 * Sénat, absence d'obligation légale). « Refus » n'est employé que si le
 * texte cite un refus daté.
 */
export function libelleCadre(texte: string): string {
  return /refus[^.]{0,120}\d{2}\/\d{2}\/\d{4}/i.test(texte) ? "Base du refus" : "Cadre";
}
