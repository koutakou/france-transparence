/**
 * Référencement : URL canonique et données structurées schema.org (JSON-LD).
 *
 * Deux besoins distincts, réunis ici pour n'avoir qu'un seul endroit où
 * l'identité du site est décrite :
 *
 * 1. CANONIQUE ET `og:url` — chaque page passe par `metadonneesPage()`, qui
 *    pose les deux À PARTIR DU MÊME CHEMIN : ils sont résolus par le même
 *    résolveur de Next, ils ne peuvent donc pas diverger.
 *    Next résout un chemin relatif contre `metadataBase` (posé dans le
 *    layout racine à partir de SITE_URL) EN Y JOIGNANT son pathname :
 *    « /donnees/ » devient donc `<origine>/donnees/` quand le site est à la
 *    racine d'un domaine, et `<origine>/<basePath>/donnees/` sous un
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
import type { Metadata } from "next";
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
/* Métadonnées d'une page (canonique + Open Graph)                     */
/* ------------------------------------------------------------------ */

/**
 * Visuel de partage, commun à tout le site.
 *
 * URL ABSOLUE en dur : avec `metadataBase`, un chemin « /og.png » perdrait le
 * sous-chemin d'un déploiement sous basePath (SITE_URL le contient déjà).
 *
 * EXPORTÉ parce que la carte X du layout racine doit porter la MÊME image ET
 * le MÊME texte alternatif : X ne retombe pas systématiquement sur
 * `og:image:alt`, il faut lui poser `twitter:image:alt`. Recopier l'URL et
 * l'alternative textuelle dans le layout, c'était garantir qu'un jour l'une
 * des deux décrirait une autre image que celle réellement partagée.
 */
export const IMAGE_PARTAGE = {
  url: `${SITE_URL}/og.png`,
  width: 1200,
  height: 630,
  alt: "France Transparence — données publiques officielles",
};

/**
 * Les seuls `og:type` que le site sait décrire honnêtement : des pages, et
 * des fiches de personnes. Volontairement fermé — ajouter « article » ou
 * « video » exigerait les propriétés obligatoires qui vont avec, qu'aucune
 * page ne possède aujourd'hui.
 */
export type TypeOpenGraph = "website" | "profile";

/**
 * Bloc `openGraph` COMPLET d'une page — à n'appeler que d'ici et du layout.
 *
 * POURQUOI il recopie tout (type, siteName, locale, image) au lieu de ne
 * poser que `url` : Next NE FUSIONNE PAS `openGraph` champ à champ entre le
 * layout racine et la page. Sa boucle de fusion traite la clé EN BLOC —
 * `newResolvedMetadata.openGraph = resolveOpenGraph(metadata.openGraph, …)`
 * (next/dist/lib/metadata/resolve-metadata.js) : dès qu'une page déclare
 * `openGraph`, l'objet du layout est REMPLACÉ, pas complété. Une page qui ne
 * déclarerait que `{ url }` perdrait d'un coup og:type, og:site_name,
 * og:locale et og:image — la carte de partage se réduirait à un lien nu, et
 * la régression serait invisible en relecture de source.
 *
 * `title` et `description` restent au contraire volontairement ABSENTS :
 * quand ils manquent, Next les recopie du titre et de la description RÉSOLUS
 * de la page (`inheritFromMetadata`), gabarit « %s — France Transparence »
 * compris. Les poser ici les figerait sur la valeur du site entier — c'est
 * exactement le piège déjà évité dans le layout racine.
 *
 * `chemin` (facultatif) reçoit le MÊME chemin relatif que la canonique :
 * Next le résout avec le même résolveur, la même `metadataBase` et le même
 * `trailingSlash` — og:url et la canonique ne peuvent donc pas diverger.
 * Omis (layout racine, page 404), aucun `og:url` n'est émis : une page
 * d'erreur servie sous n'importe quelle adresse n'a pas d'URL canonique à
 * revendiquer, et en annoncer une serait un mensonge.
 *
 * `type` reste « website » par défaut — c'est ce qu'est chaque tableau de
 * bord du site. Une fiche d'élu, elle, décrit UNE PERSONNE : `og:type` y vaut
 * « profile », comme le JSON-LD de la même page le dit déjà (`ProfilePage` +
 * `Person`). Les deux descriptions de la page doivent raconter la même chose.
 *
 * `profil` n'est lu que pour « profile », et seuls les champs RÉELLEMENT
 * disponibles séparément en base (`elus.prenom`, `elus.nom`) sont émis :
 * `profile:first_name` et `profile:last_name` ne sont JAMAIS reconstitués en
 * découpant un nom complet, faute de règle sûre (particules, prénoms
 * composés, noms d'usage) — une civilité fausse sur une personne réelle est
 * un dommage, pas une imprécision.
 */
export function openGraphPage(
  chemin?: string,
  type: TypeOpenGraph = "website",
  profil?: { prenom?: string | null; nom?: string | null },
): NonNullable<Metadata["openGraph"]> {
  const commun = {
    siteName: NOM_SITE,
    locale: "fr_FR",
    images: [IMAGE_PARTAGE],
    url: chemin,
  };
  if (type === "profile") {
    return {
      ...commun,
      type: "profile",
      ...(profil?.prenom ? { firstName: profil.prenom } : {}),
      ...(profil?.nom ? { lastName: profil.nom } : {}),
    };
  }
  return { ...commun, type: "website" };
}

/**
 * Métadonnées complètes d'une page indexable : titre, description, canonique
 * et Open Graph d'un seul tenant.
 *
 * Un seul point d'entrée pour que `alternates.canonical` et `openGraph.url`
 * soient CONSTRUITS DU MÊME `chemin` : les tenir à jour séparément dans
 * quatorze fichiers, c'est garantir qu'un jour l'un des deux désignera une
 * autre page que l'autre.
 *
 * `titre` et `description` sont optionnels, et leurs clés ne sont POSÉES QUE
 * si la valeur est fournie — jamais avec `undefined`. La fusion de Next itère
 * `for (const key in metadata)` : une clé PRÉSENTE mais `undefined` est
 * traitée quand même, et son cas efface la valeur héritée
 * (`resolveTitle(undefined)` rend `{ absolute: "" }`, `metadata[key] ?? null`
 * annule la description). Une page qui laisserait passer `titre: undefined`
 * perdrait donc le titre par défaut du layout — ce qui est exactement le
 * besoin de l'accueil (titre par défaut) et des chemins dégradés de
 * `generateMetadata` (fiche d'élu introuvable : pas de description à
 * annoncer, on garde celle du site).
 */
export function metadonneesPage(page: {
  /** Chemin du site, slash final compris (« /donnees/ », « / »). */
  chemin: string;
  /** Titre de la page, sans le suffixe du gabarit ; omis = titre par défaut. */
  titre?: string;
  /** Description propre à la page ; omise = description par défaut du site. */
  description?: string;
}): Metadata {
  return {
    ...(page.titre !== undefined && { title: page.titre }),
    ...(page.description !== undefined && { description: page.description }),
    alternates: { canonical: page.chemin },
    openGraph: openGraphPage(page.chemin),
  };
}

/**
 * Métadonnées d'une fiche de PERSONNE — `metadonneesPage()` au mot près,
 * `og:type=profile` en plus.
 *
 * POURQUOI une fabrique séparée plutôt qu'un paramètre de plus sur
 * `metadonneesPage()` : `prenom` et `nom` n'ont de sens que pour une
 * personne, et treize pages sur quatorze n'en décrivent aucune. Le bloc
 * `openGraph` est reconstruit À PARTIR DU MÊME `page.chemin` que la
 * canonique posée par `metadonneesPage()` : la garantie « canonique ==
 * og:url » tient donc ici exactement comme ailleurs, elle ne dépend pas de
 * l'ordre des clés.
 */
export function metadonneesFicheProfil(page: {
  /** Chemin de la fiche, slash final compris. */
  chemin: string;
  titre?: string;
  description?: string;
  /** Prénom TEL QU'EN BASE (`elus.prenom`) — jamais découpé d'un nom complet. */
  prenom?: string | null;
  /** Nom TEL QU'EN BASE (`elus.nom`). */
  nom?: string | null;
}): Metadata {
  return {
    ...metadonneesPage(page),
    openGraph: openGraphPage(page.chemin, "profile", {
      prenom: page.prenom,
      nom: page.nom,
    }),
  };
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
