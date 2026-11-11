/**
 * Ce qui dépend du MOMENT DE LECTURE et non de la donnée : instant de
 * construction, âge révolu d'une personne, bandeau du site resté figé.
 * Module PUR, sans base ni réseau : importable au build comme dans le
 * navigateur, testé par `npm test` (`tests/fraicheur-lecture.test.mjs`).
 *
 * Le site est un export statique reconstruit chaque nuit, et « le site de la
 * veille reste servi avec sa vraie fraîcheur » quand un cycle échoue : tout
 * ce qui est relatif à « maintenant » doit donc soit être daté (vrai sans
 * JavaScript), soit être recalculé chez le lecteur à partir de ce que la page
 * contient déjà — jamais en appelant un serveur.
 */

/**
 * Instant de construction (ms) : un Server Component de l'export statique
 * n'est rendu qu'une fois, au build. Une fonction plutôt qu'un `Date.now()`
 * dans le composant : la règle de pureté de React le refuse au rendu, alors
 * qu'ici l'instant est précisément ce que l'on veut figer — et dire.
 */
export function instantDeConstruction(): number {
  return Date.now();
}

/** Instant (ms) → `JJ/MM/AAAA à HHhMM`, heure de Paris. */
export function formatInstantFr(ms: number): string {
  const d = new Date(ms);
  const date = new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Europe/Paris",
  }).format(d);
  const heure = new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Paris",
  }).format(d);
  return `${date} à ${heure.replace(":", "h")}`;
}

/** `AAAA-MM-JJ` du jour civil à Paris (en-CA écrit ce format). */
const FORMAT_JOUR_PARIS = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Europe/Paris",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/**
 * Âge révolu, au jour civil de Paris de `maintenant`, d'une personne née le
 * `naissance` (`AAAA-MM-JJ…`) ; `null` si la date est illisible ou future.
 * Calculé sur les composantes de la date, jamais par une division de durée
 * (un an n'a pas 365,25 jours le jour d'un anniversaire).
 */
export function ageRevolu(naissance: string | null, maintenant: Date): number | null {
  const n = /^(\d{4})-(\d{2})-(\d{2})/.exec(naissance?.trim() ?? "");
  if (!n) return null;
  const [an, mois, jour] = FORMAT_JOUR_PARIS.format(maintenant).split("-").map(Number);
  const [nAn, nMois, nJour] = [Number(n[1]), Number(n[2]), Number(n[3])];
  let age = an - nAn;
  if (mois < nMois || (mois === nMois && jour < nJour)) age -= 1;
  return age >= 0 ? age : null;
}

/* ------------------------------------------------------------------ */
/* Bandeau « site non reconstruit »                                    */
/* ------------------------------------------------------------------ */

/**
 * Au-delà de cet écart entre l'instant de construction de la page et
 * l'instant de lecture, le bandeau s'affiche. Le cycle serveur bascule vers
 * 05h30 (heure de Paris) : une page normale a entre 0 et ~24 h. 36 h laisse
 * une demi-journée à un cycle lent sans fausse alerte, et signale le premier
 * cycle manqué le jour même.
 */
export const SEUIL_SITE_FIGE_HEURES = 36;

/** Identifiant du bandeau dans le gabarit (layout). */
export const ID_BANDEAU_SITE_FIGE = "ft-site-fige";

/**
 * Le script EN LIGNE du bandeau, tel qu'il part dans chaque page.
 *
 * Il ne lit que ce que la page porte (l'instant de construction, attribut
 * `data-construit-le`) et l'horloge du navigateur : aucun appel réseau, aucun
 * stockage, aucun cookie. Compatible avec la CSP du site
 * (`script-src 'self' 'unsafe-inline'`). Sans JavaScript, le bandeau reste
 * masqué et la date de construction du pied de page reste vraie.
 *
 * Il ÉCRIT dans un nœud que React n'hydrate pas (`dangerouslySetInnerHTML`
 * du gabarit) : modifier un nœud hydraté avant l'hydratation provoquerait
 * un écart que React corrigerait en effaçant le bandeau.
 */
export const SCRIPT_BANDEAU_SITE_FIGE = `(function(){var b=document.getElementById("${ID_BANDEAU_SITE_FIGE}");if(!b)return;var c=Number(b.getAttribute("data-construit-le"));var h=(Date.now()-c)/36e5;if(!(h>=${SEUIL_SITE_FIGE_HEURES}))return;var j=Math.floor(h/24);var a=b.querySelector("[data-anciennete]");if(a)a.textContent=j+(j>1?" jours":" jour");b.hidden=false;})();`;

/**
 * Le HTML du bandeau (masqué) suivi de son script. La date de construction
 * est écrite au build ; le script ne fait que dire depuis combien de jours.
 */
export function htmlBandeauSiteFige(construitLe: number): string {
  return (
    `<p id="${ID_BANDEAU_SITE_FIGE}" hidden data-construit-le="${construitLe}" role="note" ` +
    `class="mt-4 rounded-lg border border-card-border bg-card px-4 py-3 text-[13px] leading-relaxed text-ink-secondary" ` +
    `style="border-left:3px solid var(--status-warning)">` +
    `<strong class="text-ink">Cette page a été construite le ${formatInstantFr(construitLe)}, ` +
    `il y a <span data-anciennete></span>.</strong> ` +
    `Le site est prévu pour être reconstruit chaque nuit : ses données s’arrêtent aux dates ` +
    `indiquées par leurs badges «&nbsp;Données au&nbsp;…&nbsp;», et ce qui a pu paraître depuis ` +
    `chez les sources n’y figure pas.` +
    `</p><script>${SCRIPT_BANDEAU_SITE_FIGE}</script>`
  );
}
