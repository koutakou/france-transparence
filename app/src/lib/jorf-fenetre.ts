/**
 * Ce que la fenêtre du Journal officiel contient VRAIMENT, dit là où un
 * chiffre est lu (tuiles, flux, badge, accueil). Module PUR, testé par
 * `npm test` (tests/jorf-fenetre.test.mjs).
 *
 * La fenêtre visée est « les derniers JO parus ». Deux cas la démentent :
 * - elle est plus courte que visé (base neuve devant un dépôt DILA
 *   renouvelé, qui ne propose plus les éditions antérieures) : le compte de
 *   JO, lu en base, le dit déjà ;
 * - elle a un TROU (ingestion arrêtée plusieurs jours pendant que le dépôt
 *   se vidait) : « N derniers JO parus » serait alors faux, des JO parus
 *   dans l'intervalle manquent. Le libellé nomme l'intervalle.
 */

/**
 * Écart normal, en jours civils, entre deux JO consécutifs : 2 autour d'un
 * lundi, 3 autour d'un pont. Même valeur que `ECART_NORMAL_ENTRE_JO` de
 * `pipelines/ingest_jorf.py`, qui la mesure : ne pas changer l'une sans
 * l'autre.
 */
export const ECART_NORMAL_ENTRE_JO = 3;

/**
 * Débuts de la note S3 de `meta_sources` quand le pipeline signale la
 * fenêtre (MARQUE_FENETRE_REDUITE, MARQUE_FENETRE_DISCONTINUE de
 * `pipelines/ingest_jorf.py`) : ne pas les reformuler d'un seul côté.
 */
export const MARQUES_FENETRE_SIGNALEE = ["Fenêtre réduite", "Fenêtre discontinue"];

const LIBELLE_JORF = "JORF Lois et décrets";

/** Intervalle sans JO entre deux JO consécutifs de la fenêtre. */
export type TrouJo = { avant: string; apres: string; jours: number };

const jour = (iso: string) => Date.parse(`${iso}T00:00:00Z`) / 86_400_000;

/** `2026-11-08` → `08/11/2026`, sans fuseau. */
const fr = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;

/**
 * Intervalles de plus de ECART_NORMAL_ENTRE_JO jours entre deux JO
 * consécutifs. `dates` : dates ISO des JO de la fenêtre, croissantes.
 */
export function trousEntreJo(dates: readonly string[]): TrouJo[] {
  const trous: TrouJo[] = [];
  for (let i = 1; i < dates.length; i++) {
    const jours = jour(dates[i]) - jour(dates[i - 1]);
    if (jours > ECART_NORMAL_ENTRE_JO) {
      trous.push({ avant: dates[i - 1], apres: dates[i], jours });
    }
  }
  return trous;
}

const ditTrous = (trous: readonly TrouJo[]) =>
  trous.map((t) => `entre le ${fr(t.avant)} et le ${fr(t.apres)}`).join(", ni ");

/**
 * Périmètre au contact d'un chiffre de la fenêtre : « 30 derniers JO
 * parus », ou « 22 JO, aucun entre le 04/10/2026 et le 10/11/2026 ».
 */
export function mentionFenetreJo(dates: readonly string[]): string {
  const trous = trousEntreJo(dates);
  if (trous.length === 0) return `${dates.length} derniers JO parus`;
  return `${dates.length} JO, aucun ${ditTrous(trous)}`;
}

/** Forme courte pour un libellé de tuile : « 30 derniers JO ». */
export function libelleFenetreJo(dates: readonly string[]): string {
  return trousEntreJo(dates).length === 0
    ? `${dates.length} derniers JO`
    : `${dates.length} JO, série interrompue`;
}

/**
 * Phrase d'en-tête, bornes comprises : « les 30 derniers JO parus, du … au
 * … » ou « 22 JO parus entre le … et le …, aucun entre le … et le … ».
 */
export function phraseFenetreJo(dates: readonly string[]): string {
  if (dates.length === 0) return "aucun JO";
  const debut = fr(dates[0]);
  const fin = fr(dates[dates.length - 1]);
  const trous = trousEntreJo(dates);
  if (trous.length === 0) {
    return `les ${dates.length} derniers JO parus, du ${debut} au ${fin}`;
  }
  return `${dates.length} JO parus entre le ${debut} et le ${fin}, aucun ${ditTrous(trous)}`;
}

/**
 * Périmètre de la tuile d'accueil « Textes au JO (30 j) », qui compte les
 * textes parus depuis `seuil` (ISO, aujourd'hui − 30 jours).
 * - un intervalle sans JO déborde sur ces 30 jours : il est nommé ;
 * - le premier JO repris est postérieur au seuil : la tuile ne couvre pas
 *   30 jours, elle dit depuis quand ;
 * - sinon : « 30 derniers jours ».
 */
export function perimetreJo30j(dates: readonly string[], seuil: string): string {
  const trous = trousEntreJo(dates).filter((t) => t.apres > seuil);
  if (trous.length > 0) {
    return `${LIBELLE_JORF}, 30 derniers jours — aucun JO repris ici ${ditTrous(trous)}`;
  }
  if (dates.length > 0 && dates[0] > seuil) {
    return `${LIBELLE_JORF} — seulement les JO parus depuis le ${fr(dates[0])} : moins de 30 jours repris ici`;
  }
  return `${LIBELLE_JORF}, 30 derniers jours`;
}

/**
 * Note datée du pipeline, à afficher TELLE QUELLE sous le compte de JO, ou
 * `null` quand elle ne signale rien.
 */
export function noteFenetreSignalee(notes: string | null | undefined): string | null {
  const note = notes?.trim();
  if (!note) return null;
  return MARQUES_FENETRE_SIGNALEE.some((m) => note.startsWith(m)) ? note : null;
}
