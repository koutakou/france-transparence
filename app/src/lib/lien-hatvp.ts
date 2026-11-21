/**
 * Liens HATVP de fiche nominative : ce qui est AFFICHÉ ou EXPORTÉ comme lien,
 * distinct de ce qui sert de clé en base.
 *
 * La HATVP publie parfois dans `url_dossier` de liste.csv un chemin que son
 * site ne sert pas (« capitanio-olivier[ », « martin-(gironde)-alexandra-26044 »,
 * « echaniz-iñaki-24343 », relevés le 21/11/2026 : 404 ou retour à l'accueil).
 * Le pipeline garde l'URL brute dans `elus.hatvp_url` et
 * `hatvp_declarations.url_fiche`, car elle rattache à une fiche les
 * déclarations de cette personne et d'elle seule. Le lien publié, lui, passe
 * par `lienHatvpAffichable` : un chemin mal formé renvoie à la liste.
 *
 * Pur : importable depuis un composant client (pas de sqlite).
 */

/** Liste officielle des déclarations publiées, commune à toutes les personnes. */
export const URL_HATVP_LISTE = "https://www.hatvp.fr/livraison/opendata/liste.csv";

/** Même motif que `MOTIF_URL_DOSSIER` de pipelines/ingest_integrite.py. */
const MOTIF_FICHE_HATVP = /^https:\/\/www\.hatvp\.fr\/pages_nominatives\/[a-z0-9-]+$/;

/** L'URL est-elle une fiche nominative HATVP bien formée ? */
export function estFicheHatvpBienFormee(url: string | null | undefined): boolean {
  return !!url && MOTIF_FICHE_HATVP.test(url);
}

/**
 * Lien HATVP publiable : l'URL telle quelle si c'est une fiche nominative bien
 * formée ou la liste, sinon la liste. `null` si aucune URL.
 */
export function lienHatvpAffichable(url: string | null | undefined): string | null {
  if (!url) return null;
  if (url === URL_HATVP_LISTE || estFicheHatvpBienFormee(url)) return url;
  return URL_HATVP_LISTE;
}

/**
 * Lien HATVP d'une fiche d'élu parmi plusieurs URL candidates, dans l'ordre
 * de préférence : la première fiche nominative bien formée, sinon le lien
 * affichable de la première URL renseignée (la liste quand elle est mal
 * formée). `null` si aucune.
 */
export function choisirLienHatvp(...candidates: (string | null | undefined)[]): string | null {
  const bienFormee = candidates.find((u) => estFicheHatvpBienFormee(u));
  if (bienFormee) return bienFormee;
  return lienHatvpAffichable(candidates.find((u) => !!u));
}

/**
 * Clés de rattachement des déclarations à une fiche d'élu
 * (`hatvp_declarations.url_fiche IN (...)`) : les URL brutes, dédoublonnées,
 * sans vide et JAMAIS l'URL de la liste. Commune à tous, elle rattacherait à
 * un élu les déclarations d'autres personnes.
 */
export function clesRattachementHatvp(...urls: (string | null | undefined)[]): string[] {
  return [...new Set(urls.filter((u): u is string => !!u && u !== URL_HATVP_LISTE))];
}
