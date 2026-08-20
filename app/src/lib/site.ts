/**
 * Identité publique du site — l'unique endroit où l'URL de production est
 * écrite. Le site est servi à la RACINE d'un domaine propre
 * (https://francetransparence.fr) : export statique publié par nginx sur un
 * serveur dédié, sans basePath, l'URL canonique ne comporte donc aucun
 * sous-chemin. GitHub Pages ne reçoit plus qu'une page de redirection
 * (pages-redirection/), et non le site.
 *
 * L'URL est une donnée de DÉPLOIEMENT, pas une constante de code : elle se
 * règle par `NEXT_PUBLIC_SITE_URL` au build (un miroir, une préproduction ou
 * un fork changent d'adresse sans changer une ligne de source). La valeur par
 * défaut est celle du déploiement de référence.
 *
 * SANS slash final : les consommateurs concatènent `${SITE_URL}/chemin/`. La
 * normalisation ci-dessous retire un éventuel slash final de la variable
 * d'environnement, pour qu'une valeur mal terminée ne produise pas d'URL à
 * double slash.
 */
export const SITE_URL = (
  process.env.NEXT_PUBLIC_SITE_URL || "https://francetransparence.fr"
).replace(/\/+$/, "");

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
