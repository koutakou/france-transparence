/**
 * Référencement : URL canonique et données structurées schema.org (JSON-LD).
 *
 * Deux besoins distincts, réunis ici pour n'avoir qu'un seul endroit où
 * l'identité du site est décrite :
 *
 * 1. CANONIQUE — chaque page déclare `alternates.canonical` dans son objet
 *    `metadata`. Next résout un chemin relatif contre `metadataBase`
 *    (posé dans le layout racine à partir de SITE_URL) EN Y JOIGNANT son
 *    pathname : « /donnees/ » devient donc `<origine>/donnees/` quand le site
 *    est à la racine d'un domaine, et `<origine>/<basePath>/donnees/` sous un
 *    basePath — aucune URL n'est à recopier ici.
 *    Les chemins portent TOUJOURS le slash final (`trailingSlash: true` —
 *    le site sert des `index.html`), sinon la canonique désignerait une URL
 *    qui redirige, ce qui affaiblit le signal.
 *
 * 2. JSON-LD — schema.org n'est pas résolu par Next : les URL y sont
 *    ABSOLUES, construites sur SITE_URL (qui inclut déjà le basePath).
 *
 * Principe de sobriété : on ne balise QUE ce qui est réellement affiché sur
 * la page et réellement exploité par un consommateur (Google Dataset Search
 * pour les exports, désambiguïsation d'entité pour les élus). Aucun balisage
 * décoratif, aucune donnée qui ne figure pas déjà à l'écran.
 */
import { SITE_URL } from "@/lib/site";

/** Nom public du site (identique au `og:site_name` du layout). */
export const NOM_SITE = "France Transparence";

/**
 * Description du SITE (et non de la page d'accueil) : c'est l'objet décrit
 * par le nœud `WebSite`. Volontairement distincte de la `description` de la
 * page d'accueil, qui décrit un tableau de bord, pas le projet.
 */
const DESCRIPTION_SITE =
  "Dépenses de l'État, marchés publics, élus, lobbying, financement de la vie politique : données publiques officielles, fraîcheur mesurée et affichée, sources et limites documentées.";

/** Licence des agrégats publiés par le site (cf. pied de page et /donnees). */
export const URL_LICENCE = "https://www.etalab.gouv.fr/licence-ouverte-open-licence/";

/** Identifiant du nœud « projet » (éditeur/producteur), référencé partout. */
export const ID_PROJET = `${SITE_URL}/#projet`;
/** Identifiant du nœud « site web ». */
export const ID_SITE = `${SITE_URL}/#site`;

/** URL absolue d'une page du site — `chemin` commence par « / ». */
export function urlAbsolue(chemin: string): string {
  return `${SITE_URL}${chemin}`;
}

/* ------------------------------------------------------------------ */
/* Outillage                                                           */
/* ------------------------------------------------------------------ */

export type NoeudJsonLd = Record<string, unknown>;

/**
 * Retire récursivement les clés `undefined` / `null` et les tableaux vides :
 * un balisage ne doit jamais annoncer une propriété qu'il ne renseigne pas
 * (le validateur schema.org signale les valeurs nulles, et un consommateur
 * ne doit pas croire la donnée absente « connue et vide »).
 */
export function compacte<T>(valeur: T): T {
  if (Array.isArray(valeur)) {
    return valeur
      .filter((v) => v !== undefined && v !== null)
      .map((v) => compacte(v)) as unknown as T;
  }
  if (valeur && typeof valeur === "object") {
    const sortie: Record<string, unknown> = {};
    for (const [cle, v] of Object.entries(valeur as Record<string, unknown>)) {
      if (v === undefined || v === null) continue;
      if (Array.isArray(v) && v.length === 0) continue;
      if (typeof v === "string" && v.trim() === "") continue;
      sortie[cle] = compacte(v);
    }
    return sortie as unknown as T;
  }
  return valeur;
}

/** Enveloppe `@graph` avec le contexte schema.org. */
export function graphe(noeuds: NoeudJsonLd[]): NoeudJsonLd {
  return compacte({ "@context": "https://schema.org", "@graph": noeuds });
}

/* ------------------------------------------------------------------ */
/* Identité du site (accueil)                                          */
/* ------------------------------------------------------------------ */

/**
 * Identité du site : `WebSite` + `Project`.
 *
 * `Project` (sous-classe de `Organization` chez schema.org) et NON
 * `Organization` : le site est édité à titre non professionnel par un
 * particulier (mentions légales, art. 1-1 II LCEN) — annoncer une
 * organisation serait faux. `Project` reste accepté partout où une
 * `Organization` est attendue (`creator`, `publisher`).
 *
 * PAS de `SearchAction` : la recherche du site est 100 % côté navigateur sur
 * un index statique, aucune URL de la forme `?q=` n'existe. Déclarer une
 * `SearchAction` dont la cible ne répond pas est une erreur classique — et
 * ici ce serait un mensonge vérifiable.
 */
export function jsonLdIdentiteSite(): NoeudJsonLd {
  return graphe([
    {
      "@type": "WebSite",
      "@id": ID_SITE,
      url: urlAbsolue("/"),
      name: NOM_SITE,
      description: DESCRIPTION_SITE,
      inLanguage: "fr-FR",
      isAccessibleForFree: true,
      license: URL_LICENCE,
      creator: { "@id": ID_PROJET },
      publisher: { "@id": ID_PROJET },
    },
    {
      "@type": "Project",
      "@id": ID_PROJET,
      name: NOM_SITE,
      url: urlAbsolue("/"),
      description:
        "Projet citoyen indépendant de mise en données de l'argent public et de la vie politique françaises, à partir des seules sources publiques officielles.",
      logo: urlAbsolue("/og.png"),
      sameAs: ["https://github.com/koutakou/france-transparence"],
    },
  ]);
}

/* ------------------------------------------------------------------ */
/* Fil d'Ariane                                                        */
/* ------------------------------------------------------------------ */

/**
 * `BreadcrumbList` — le dernier élément est la page courante et n'a
 * volontairement PAS d'`item` (recommandation Google : la position courante
 * ne se lie pas à elle-même).
 */
export function filAriane(
  etapes: { nom: string; chemin?: string }[],
): NoeudJsonLd {
  return {
    "@type": "BreadcrumbList",
    itemListElement: etapes.map((e, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: e.nom,
      item: e.chemin ? urlAbsolue(e.chemin) : undefined,
    })),
  };
}

/* ------------------------------------------------------------------ */
/* Jeux de données (/donnees)                                          */
/* ------------------------------------------------------------------ */

export type DescriptionDataset = {
  /** Fragment d'identifiant, ex. « api-elus ». */
  cle: string;
  nom: string;
  description: string;
  /** Chemin du fichier téléchargeable, ex. « /api/elus.json ». */
  chemin: string;
  /** Date réelle de dernière mise à jour (ISO) — jamais la date du build. */
  dateModified?: string | null;
  /** Couverture temporelle ISO 8601 (« 2013-01/2026-05 »), si connue. */
  temporalCoverage?: string | null;
  motsCles: string[];
};

/**
 * `DataCatalog` + un `Dataset` par export JSON — le balisage réellement
 * exploité par Google Dataset Search (journalistes de données, chercheurs),
 * qui exige `name` et `description` et valorise `creator`, `license`,
 * `distribution`, `temporalCoverage` et `dateModified`.
 *
 * `dateModified` est la date d'ingestion RÉELLE des sources qui composent
 * l'export (MAX sur `meta_sources`), pas la date du build : un build sans
 * ingestion ne doit pas faire croire à une donnée fraîche.
 */
export function jsonLdCatalogueDonnees(
  datasets: DescriptionDataset[],
  dateCatalogue: string | null,
): NoeudJsonLd {
  const idCatalogue = `${urlAbsolue("/donnees/")}#catalogue`;
  return graphe([
    {
      "@type": "DataCatalog",
      "@id": idCatalogue,
      name: `Exports de données — ${NOM_SITE}`,
      description:
        "Instantanés JSON quotidiens des données publiques agrégées par France Transparence : budget de l'État, marchés publics, élus, alertes d'intégrité, catalogue des sources.",
      url: urlAbsolue("/donnees/"),
      inLanguage: "fr-FR",
      isAccessibleForFree: true,
      license: URL_LICENCE,
      creator: { "@id": ID_PROJET },
      publisher: { "@id": ID_PROJET },
      dateModified: dateCatalogue ?? undefined,
      dataset: datasets.map((d) => ({ "@id": `${urlAbsolue("/donnees/")}#${d.cle}` })),
    },
    ...datasets.map((d) => ({
      "@type": "Dataset",
      "@id": `${urlAbsolue("/donnees/")}#${d.cle}`,
      name: d.nom,
      description: d.description,
      url: urlAbsolue("/donnees/"),
      inLanguage: "fr-FR",
      isAccessibleForFree: true,
      license: URL_LICENCE,
      creator: { "@id": ID_PROJET },
      publisher: { "@id": ID_PROJET },
      includedInDataCatalog: { "@id": idCatalogue },
      keywords: d.motsCles,
      spatialCoverage: { "@type": "Place", name: "France" },
      temporalCoverage: d.temporalCoverage ?? undefined,
      dateModified: d.dateModified ?? undefined,
      distribution: [
        {
          "@type": "DataDownload",
          encodingFormat: "application/json",
          contentUrl: urlAbsolue(d.chemin),
        },
      ],
    })),
  ]);
}

/* ------------------------------------------------------------------ */
/* Fiche d'élu (/elus/[id])                                            */
/* ------------------------------------------------------------------ */

export type RoleElu = {
  /** Intitulé du mandat tel qu'affiché (« Députée », « Sénateur »…). */
  roleName: string;
  /** Institution ou collectivité d'exercice. */
  organisation: string;
  /** Début de mandat (ISO), si la source le publie. */
  debut?: string | null;
};

export type DescriptionPersonne = {
  chemin: string;
  nomComplet: string;
  prenom?: string | null;
  nom: string;
  /** Date de naissance publiée par la source officielle ET affichée. */
  naissance?: string | null;
  /** Intitulé principal (`jobTitle`), ex. « Députée ». */
  fonction?: string | null;
  /** Mandats en cours, tels que listés sur la fiche. */
  roles: RoleElu[];
  /** Groupe politique / rattachement, tel qu'affiché. */
  groupes: string[];
  /** Fiches officielles liées depuis la page (AN, Sénat, HATVP). */
  sameAs: string[];
  description: string;
};

/**
 * `Person` + `ProfilePage` + fil d'Ariane pour une fiche d'élu.
 *
 * Ce sont des PERSONNES RÉELLES : le balisage est strictement limité aux
 * données déjà publiées sur la page, elles-mêmes issues des open data
 * officiels (Assemblée nationale, Sénat, RNE, HATVP). Rien n'est déduit,
 * rien n'est enrichi, aucune donnée sensible (le sexe, la profession
 * déclarée et les votes restent hors balisage : sans usage aval légitime,
 * les baliser reviendrait à faciliter un profilage que la page n'organise
 * pas).
 */
export function jsonLdFicheElu(p: DescriptionPersonne): NoeudJsonLd {
  const url = urlAbsolue(p.chemin);
  const idPersonne = `${url}#personne`;
  return graphe([
    {
      "@type": "ProfilePage",
      "@id": `${url}#page`,
      url,
      name: p.nomComplet,
      inLanguage: "fr-FR",
      isPartOf: { "@id": ID_SITE },
      mainEntity: { "@id": idPersonne },
      breadcrumb: filAriane([
        { nom: "Accueil", chemin: "/" },
        { nom: "Élus & institutions", chemin: "/elus/" },
        { nom: p.nomComplet },
      ]),
    },
    {
      "@type": "Person",
      "@id": idPersonne,
      name: p.nomComplet,
      givenName: p.prenom ?? undefined,
      familyName: p.nom,
      birthDate: p.naissance ?? undefined,
      jobTitle: p.fonction ?? undefined,
      description: p.description,
      mainEntityOfPage: { "@id": `${url}#page` },
      url,
      memberOf: p.roles.map((r) => ({
        "@type": "OrganizationRole",
        roleName: r.roleName,
        startDate: r.debut ?? undefined,
        memberOf: { "@type": "Organization", name: r.organisation },
      })),
      affiliation: p.groupes.map((g) => ({ "@type": "Organization", name: g })),
      sameAs: p.sameAs,
    },
  ]);
}
