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

/**
 * Adresse de contact du site — canal PRIVÉ, et seul canal convenable pour une
 * demande qui porte sur une personne : obliger quelqu'un à publier sa demande
 * de rectification dans une issue indexée est contraire à l'esprit de
 * l'article 12 du RGPD. Les issues restent le canal public des signalements
 * d'erreur qui ne concernent personne en particulier.
 *
 * Boîte hébergée chez Proton (Suisse) : voir la page /donnees-personnelles,
 * qui mentionne ce transit dans son bloc « Destinataires ».
 */
export const CONTACT_EMAIL = "mickael.faust.pro@proton.me";
