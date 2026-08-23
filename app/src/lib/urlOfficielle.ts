/**
 * URLs de fiches officielles dérivées d'un identifiant DÉJÀ en base.
 *
 * Contrat G7 : on ne fabrique une URL que si l'identifiant la détermine
 * sans ambiguïté. Un SIREN de 9 chiffres déjà retenu (S18 = cités, unités
 * non diffusibles écartées) pointe vers l'annuaire des entreprises
 * (data.gouv / INSEE). On ne complète pas un SIRET, on ne « répare » pas
 * 13 chiffres, on n'invente pas de fiche Datan ni CNCCFP.
 *
 * Pur : importable depuis un composant client (pas de sqlite).
 */

const SIREN_9 = /^[0-9]{9}$/;

/**
 * Fiche Sirene d'une unité légale. `null` si ce n'est pas un SIREN de 9
 * chiffres (espaces, SIRET, 13 chiffres, NULL).
 */
export function urlAnnuaireEntreprise(siren: string | null | undefined): string | null {
  if (!siren || !SIREN_9.test(siren)) return null;
  return `https://annuaire-entreprises.data.gouv.fr/entreprise/${siren}`;
}

/**
 * L'URL déjà stockée est-elle une fiche d'entité (personne, organisation,
 * texte), pas un jeu de données ni un export ?
 *
 * Sert aux alertes : `source_url` pointe parfois vers liste.csv / un
 * dataset data.gouv — ce n'est pas une fiche, on ne pose pas le nom dessus.
 */
export function estFicheOfficielleEntite(url: string | null | undefined): boolean {
  if (!url) return false;
  let u: URL;
  try {
    u = new URL(url);
  } catch {
    return false;
  }
  const hote = u.hostname.replace(/^www\./, "");
  const chemin = u.pathname;
  if (hote === "hatvp.fr") {
    return (
      chemin.startsWith("/pages_nominatives/") || chemin.startsWith("/fiche-organisation/")
    );
  }
  if (hote === "assemblee-nationale.fr" || hote.endsWith(".assemblee-nationale.fr")) {
    return chemin.includes("/deputes/");
  }
  if (hote === "senat.fr") {
    return chemin.includes("/senateur/");
  }
  if (hote === "boamp.fr") {
    return chemin.includes("/avis");
  }
  if (hote === "annuaire-entreprises.data.gouv.fr") {
    return chemin.startsWith("/entreprise/");
  }
  if (hote === "legifrance.gouv.fr") {
    return chemin.length > 1;
  }
  if (hote === "transparency-register.europa.eu") {
    return chemin.includes("organisation-detail");
  }
  return false;
}
