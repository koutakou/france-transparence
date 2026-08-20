/**
 * Identité de l'HÉBERGEUR — donnée de déploiement, pas constante de code.
 *
 * La LCEN (loi n° 2004-575 du 21 juin 2004, art. 1-1, III) impose de publier
 * « le nom, la dénomination ou la raison sociale ET l'adresse ET le numéro de
 * téléphone » de l'hébergeur. Les trois, pas deux : le téléphone est aussi
 * obligatoire que l'adresse, et un formulaire de support ne s'y substitue pas. Or cette identité ne dépend pas du code : elle
 * change le jour où le site change de machine, sans qu'une seule ligne de
 * source bouge. L'écrire en dur dans le JSX obligeait le serveur de
 * production à réécrire les sources à chaque build. Chaque champ est donc
 * lisible depuis une variable d'environnement `NEXT_PUBLIC_HEBERGEUR_*`, la
 * valeur par défaut étant celle du déploiement de référence.
 *
 * ATTENTION — une mention légale fausse est une infraction, et une mention
 * légale sans source vérifiable ne vaut rien. Toute modification de ces
 * valeurs (ici ou par variables d'environnement) doit être accompagnée d'une
 * vérification équivalente à celle ci-dessous.
 *
 * VALEURS PAR DÉFAUT VÉRIFIÉES le 19/08/2026 dans la base RIPE,
 * `whois 163.172.32.71` (plage 163.172.0.0/16 dont relève le serveur) :
 *   netname:  SCALEWAY-DEDIBOX
 *   descr:    Scaleway Dedibox - Paris, France
 *   org-name: Scaleway SAS  (ORG-TT1-RIPE)
 *   address:  8, rue de la Ville L'eveque / 75008 / Paris / FRANCE
 *   phone:    +33173502000        (objet ORG-TT1-RIPE lui-même)
 *   reg-nr:   433 115 904 R.C.S Paris
 * Service d'hébergement : Scaleway Dedibox (serveur dédié) —
 * https://www.scaleway.com/fr/dedibox/
 * Support : https://console.scaleway.com/support/ et
 * https://www.scaleway.com/fr/contact/
 *
 * NB : `process.env.NEXT_PUBLIC_*` est remplacé littéralement au build par
 * Next.js. Les accès doivent rester écrits en toutes lettres — pas d'accès
 * indexé ni de boucle sur les noms, qui ne seraient pas substitués.
 */

/** Description complète de l'hébergeur, telle que publiée par la LCEN. */
export type Hebergeur = {
  /** Raison sociale, publiée en tête du bloc « Hébergeur ». */
  raisonSociale: string;
  /** Adresse postale, ligne à ligne, hors pays. */
  adresse: string[];
  /** Pays, publié sur sa propre ligne. */
  pays: string;
  /**
   * Numéro de téléphone de l'hébergeur — EXIGÉ par l'art. 1-1, III de la LCEN
   * au même titre que la raison sociale et l'adresse. Format international,
   * espacé pour la lecture ; la version `tel:` est dérivée à l'affichage.
   */
  telephone: string;
  /** Forme juridique et immatriculation (phrase complète, ponctuée). */
  formeJuridique: string;
  /** Nom commercial du service d'hébergement effectivement utilisé. */
  serviceNom: string;
  /** Page publique de ce service. */
  serviceUrl: string;
  /** Support de l'hébergeur — canal principal. */
  supportUrl: string;
  /** Support de l'hébergeur — canal secondaire (formulaire de contact). */
  contactUrl: string;
};

export const HEBERGEUR: Hebergeur = {
  raisonSociale:
    process.env.NEXT_PUBLIC_HEBERGEUR_RAISON_SOCIALE || "Scaleway SAS",
  adresse: [
    process.env.NEXT_PUBLIC_HEBERGEUR_ADRESSE_1 ||
      "8 rue de la Ville l'Évêque",
    process.env.NEXT_PUBLIC_HEBERGEUR_ADRESSE_2 || "75008 Paris",
    process.env.NEXT_PUBLIC_HEBERGEUR_ADRESSE_3 || "",
    // Une ligne vide ne doit pas produire un <br /> orphelin dans la page.
  ].filter((ligne) => ligne.trim() !== ""),
  pays: process.env.NEXT_PUBLIC_HEBERGEUR_PAYS || "France",
  telephone:
    process.env.NEXT_PUBLIC_HEBERGEUR_TELEPHONE || "+33 1 73 50 20 00",
  formeJuridique:
    process.env.NEXT_PUBLIC_HEBERGEUR_FORME_JURIDIQUE ||
    "Société par actions simplifiée (anciennement Online SAS), immatriculée au registre du commerce et des sociétés de Paris sous le numéro 433 115 904.",
  serviceNom:
    process.env.NEXT_PUBLIC_HEBERGEUR_SERVICE_NOM || "Scaleway Dedibox",
  serviceUrl:
    process.env.NEXT_PUBLIC_HEBERGEUR_SERVICE_URL ||
    "https://www.scaleway.com/fr/dedibox/",
  supportUrl:
    process.env.NEXT_PUBLIC_HEBERGEUR_SUPPORT_URL ||
    "https://console.scaleway.com/support/",
  contactUrl:
    process.env.NEXT_PUBLIC_HEBERGEUR_CONTACT_URL ||
    "https://www.scaleway.com/fr/contact/",
};

/**
 * Nature du service, en une expression réutilisable en prose : « serveur
 * dédié », « hébergement mutualisé »… Sert dans la `description` des
 * métadonnées et dans le corps des mentions légales.
 */
export const HEBERGEUR_NATURE_SERVICE =
  process.env.NEXT_PUBLIC_HEBERGEUR_NATURE_SERVICE || "serveur dédié";

/**
 * Mention courte « X (Service, nature) », pour les métadonnées — évite de
 * réécrire l'hébergeur dans une `description` qui divergerait du bloc publié.
 */
export const HEBERGEUR_MENTION = `${HEBERGEUR.raisonSociale} (${HEBERGEUR.serviceNom}, ${HEBERGEUR_NATURE_SERVICE})`;

/** Domaine du support, affiché en clair comme libellé de lien. */
export const HEBERGEUR_SUPPORT_LIBELLE = HEBERGEUR.supportUrl
  .replace(/^https?:\/\//, "")
  .replace(/\/+$/, "");

/**
 * Le même numéro sous la forme attendue par un lien `tel:` — chiffres et `+`
 * uniquement. Dérivé plutôt que saisi deux fois : deux champs à tenir à jour
 * finiraient par diverger, et c'est une mention légale.
 */
export const HEBERGEUR_TELEPHONE_LIEN = `tel:${HEBERGEUR.telephone.replace(/[^+0-9]/g, "")}`;
