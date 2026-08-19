/**
 * Identité publique du site — l'unique endroit où l'URL de production est
 * écrite. GitHub Pages « project page » : le site vit sous le sous-chemin
 * /france-transparence (basePath Next), l'URL canonique l'inclut donc.
 *
 * SANS slash final : les consommateurs concatènent `${SITE_URL}/chemin/`.
 */
export const SITE_URL = "https://koutakou.github.io/france-transparence";

/** Dépôt public — code source du site et canal de contact (issues). */
export const REPO_URL = "https://github.com/koutakou/france-transparence";

/** Canal de contact public : les issues GitHub du dépôt. */
export const CONTACT_ISSUES_URL = `${REPO_URL}/issues`;
