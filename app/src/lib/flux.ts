/**
 * Contenu des quatre flux Atom (/flux/jo.xml, dossiers.xml, alertes.xml,
 * sources.xml) : des lignes de la base vers des entrées. Module pur (les
 * imports sont des types), testé par tests/flux-atom.test.mjs.
 *
 * Règles communes :
 * - une entrée = un titre et un lien officiels, plus pour les alertes le lien
 *   vers la page qui donne la règle. Aucun commentaire ajouté ;
 * - un flux ne montre jamais plus que la page qui lui correspond : les
 *   alertes sont prises dans celles de /alertes (types retirés exclus par la
 *   requête, comptes de campagne absents), les dossiers dans la navette de
 *   /documents/dossiers ;
 * - la date d'une entrée est celle du fait ou de la donnée, et ne change pas
 *   d'une ingestion à l'autre. Jamais la date des données d'une source pour
 *   dater un fait, jamais l'instant d'un calcul : une entrée sans date stable
 *   est absente du flux. `updated` du flux est la plus récente de ses
 *   entrées, jamais l'heure du build ;
 * - identifiants d'entrée : URI `tag:` (RFC 4151) sur une autorité et une
 *   date FIXES, suivies de l'identifiant officiel (NOR, numéro de dossier, id
 *   d'alerte, code source et date). Ils ne dépendent ni de l'adresse de
 *   déploiement ni du jour du build : un lecteur ne voit jamais deux fois la
 *   même entrée.
 */
import type { Alerte } from "@/lib/queries/alertes";
import type { DoleNavetteLigne } from "@/lib/queries/dole";
import type { MetaSource } from "@/lib/db";

/** Les flux publiés : chemin, titre (balise `<title>` et lien du layout) et page du site. */
export const FLUX = [
  {
    chemin: "/flux/jo.xml",
    titre: "France Transparence : Journal officiel, derniers numéros",
    page: "/documents/",
    description: "Les textes des trois derniers numéros du Journal officiel, avec leur lien Légifrance.",
  },
  {
    chemin: "/flux/dossiers.xml",
    titre: "France Transparence : dossiers législatifs en navette",
    page: "/documents/dossiers/",
    description: "Les dossiers législatifs de la législature en cours les plus récemment mis à jour, avec leur lien vie-publique.fr.",
  },
  {
    chemin: "/flux/alertes.xml",
    titre: "France Transparence : alertes sur les comptes des partis",
    page: "/alertes/",
    description:
      "Seulement les alertes de la page Alertes qui ont une date du fait fixe : la dépendance d'un parti à l'aide publique, datée de la clôture de l'exercice des comptes (31 décembre). Les alertes HATVP, lobbying et documentaires n'y sont pas, faute d'une date du fait qui ne change pas à chaque fichier publié. Chaque entrée renvoie à la donnée officielle et à la page de la règle.",
  },
  {
    chemin: "/flux/sources.xml",
    titre: "France Transparence : mises à jour des sources",
    page: "/donnees/",
    description: "Une entrée chaque fois qu'une source reçoit des données plus récentes, avec le lien de la source amont.",
  },
] as const;

export type DefinitionFlux = (typeof FLUX)[number];

/** Nombre de numéros du JO repris dans le flux (les plus récents). */
export const NB_JO_FLUX = 3;

/** Dossiers de la navette repris dans le flux (les plus récemment mis à jour). */
export const NB_DOSSIERS_FLUX = 100;

export type TexteJoFlux = {
  texte_id: string;
  nor: string | null;
  date_publi: string;
  titre: string;
  lien_legifrance: string;
};

/**
 * Identifiant d'un texte du JO : son NOR, suivi de l'identifiant Légifrance
 * (un rectificatif peut reprendre le NOR du texte qu'il corrige). Sans NOR,
 * l'identifiant Légifrance seul.
 */
export function idTexteJo(t: Pick<TexteJoFlux, "texte_id" | "nor">): string {
  const nor = t.nor?.trim();
  return idTag("jo", nor ? `${nor}/${t.texte_id}` : t.texte_id);
}

export function entreesJo(textes: TexteJoFlux[]): EntreeAtom[] {
  const entrees: EntreeAtom[] = [];
  for (const t of textes) {
    const maj = dateAtom(t.date_publi);
    if (!maj) continue;
    entrees.push({ id: idTexteJo(t), titre: t.titre, lien: t.lien_legifrance, maj });
  }
  return entrees;
}

/** Ligne de la navette, avec la date de création du dossier lue pour le flux. */
export type DossierFlux = DoleNavetteLigne & { date_creation: string | null };

/**
 * Date d'un dossier : sa dernière mise à jour, sinon sa création. Jamais la
 * date des données de la source, qui change à chaque édition : un dossier
 * sans aucune de ces deux dates est écarté du flux.
 */
export function entreesDossiers(navette: DossierFlux[]): EntreeAtom[] {
  const entrees: EntreeAtom[] = [];
  for (const d of navette) {
    if (entrees.length >= NB_DOSSIERS_FLUX) break;
    const maj = dateAtom(d.date_modif) ?? dateAtom(d.date_creation);
    if (!maj) continue;
    entrees.push({ id: idTag("dossier", d.dossier_id), titre: d.titre, lien: d.lien_legifrance, maj });
  }
  return entrees;
}

/**
 * Types d'alerte publiés dans le flux, chacun avec la date de son fait, qui
 * ne change pas d'une ingestion à l'autre. Les autres types n'y sont pas :
 * - A1 (HATVP) : leur `date_fait` est la date du fichier liste.csv lu, qui
 *   change à chaque fichier publié ;
 * - lobbying (S4) : le pipeline n'écrit aucune date du fait ;
 * - partis privés d'aide (S25) : mention documentaire sur un avis publié en
 *   PDF, pas un fait daté.
 * Une dépendance à l'aide publique porte sur les comptes d'un exercice
 * (identifiant `FIN-PARTI-DEP-<exercice>-<parti>`, écrit par
 * pipelines/ingest_financement.py) : elle est datée de la clôture de cet
 * exercice, le 31 décembre. Un nouvel exercice donne un nouvel identifiant,
 * donc une nouvelle entrée.
 */
const DATE_FAIT_STABLE: Record<string, (a: Pick<Alerte, "id">) => string | null> = {
  financement_parti_dependance_aide: (a) => {
    const m = a.id.match(/^FIN-PARTI-DEP-(\d{4})-/);
    return m ? `${m[1]}-12-31` : null;
  },
};

export const TYPES_ALERTES_FLUX = Object.keys(DATE_FAIT_STABLE);

/**
 * Date d'une alerte dans le flux : la date stable de son fait, `null` si son
 * type n'en a pas (l'alerte est alors absente du flux). Jamais la date des
 * données d'une source ni l'instant du calcul, qui feraient remonter
 * l'entrée dans les lecteurs à chaque ingestion.
 */
export function dateAlerte(a: Pick<Alerte, "id" | "type">): string | null {
  const dater = DATE_FAIT_STABLE[a.type];
  return dater ? dateAtom(dater(a)) : null;
}

export function entreesAlertes(alertes: Alerte[], pageAlertes: string): EntreeAtom[] {
  const entrees: EntreeAtom[] = [];
  for (const a of alertes) {
    const maj = dateAlerte(a);
    if (!maj) continue;
    entrees.push({
      id: idTag("alerte", a.id),
      titre: a.titre,
      lien: a.source_url || pageAlertes,
      // Sans URL source, le lien principal est déjà la page de la règle.
      ...(a.source_url ? { lienRelie: pageAlertes } : {}),
      maj,
    });
  }
  return entrees;
}

/**
 * Une entrée par source et par date des données : quand une source reçoit
 * une édition plus récente, une nouvelle entrée apparaît. Une date publiée
 * au mois ou à l'année est datée du premier jour de la période. Une date
 * illisible fait échouer le build : aucune source n'est sautée en silence.
 */
export function entreesSources(
  sources: Pick<MetaSource, "source_id" | "nom" | "url" | "date_donnees">[],
  pageDonnees: string,
): EntreeAtom[] {
  const entrees: EntreeAtom[] = [];
  for (const s of sources) {
    const maj = dateAtom(debutPeriode(s.date_donnees));
    if (!maj) {
      // Jamais une source sautée sans le dire : le build échoue.
      throw new Error(
        `Flux sources : date des données illisible pour ${s.source_id} (« ${s.date_donnees} »), attendu AAAA, AAAA-MM ou AAAA-MM-JJ.`,
      );
    }
    entrees.push({
      id: idTag("source", `${s.source_id}/${s.date_donnees}`),
      titre: `${s.nom} : données du ${s.date_donnees}`,
      lien: s.url,
      lienRelie: pageDonnees,
      maj,
    });
  }
  return entrees.sort((a, b) => Date.parse(b.maj) - Date.parse(a.maj) || a.id.localeCompare(b.id));
}

/* ------------------------------------------------------------------ */
/* Écriture Atom (RFC 4287)                                             */
/* ------------------------------------------------------------------ */

/** Autorité et date fixes des identifiants `tag:` (ne jamais les changer). */
export const AUTORITE_TAG = "francetransparence.fr,2026";

export function idTag(espace: string, identifiant: string): string {
  // Caractères admis dans la partie spécifique d'un tag (RFC 4151) : on
  // encode le reste pour garder un IRI valide.
  return `tag:${AUTORITE_TAG}:${espace}/${encodeURIComponent(identifiant).replace(/%2F/gi, "/")}`;
}

/** Caractères interdits en XML 1.0 (contrôles hors tabulation et sauts de ligne). */
const INTERDITS_XML = /[\u0000-\u0008\u000B\u000C\u000E-\u001F￾￿]/g;

export function echapperXml(s: string): string {
  return s
    .replace(INTERDITS_XML, "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/**
 * Date des données publiée à la granularité d'une période : `AAAA-MM`
 * devient le premier jour du mois, `AAAA` le 1er janvier. Les autres
 * valeurs sont rendues telles quelles.
 */
export function debutPeriode(valeur: string): string {
  const v = valeur.trim();
  if (/^\d{4}-\d{2}$/.test(v)) return `${v}-01`;
  if (/^\d{4}$/.test(v)) return `${v}-01-01`;
  return v;
}

/**
 * Date de la base vers une date RFC 3339 : `AAAA-MM-JJ` devient minuit UTC
 * du jour, un instant sans fuseau est lu en UTC, un instant avec fuseau est
 * gardé. `null` si la valeur n'est pas une date lisible.
 */
export function dateAtom(valeur: string | null | undefined): string | null {
  if (!valeur) return null;
  const v = valeur.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return `${v}T00:00:00Z`;
  const m = v.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)(Z|[+-]\d{2}:\d{2})?$/);
  if (!m) return null;
  const heure = m[2].length === 5 ? `${m[2]}:00` : m[2];
  return `${m[1]}T${heure}${m[3] ?? "Z"}`;
}

export type EntreeAtom = {
  id: string;
  titre: string;
  /** Lien officiel de la donnée (rel="alternate"). */
  lien: string;
  /** Lien vers la page du site qui l'explique (rel="related"), facultatif. */
  lienRelie?: string;
  /** Date RFC 3339 (voir `dateAtom`). */
  maj: string;
};

export type FluxAtom = {
  id: string;
  titre: string;
  sousTitre: string;
  /** Adresse absolue du flux (rel="self"). */
  lienSelf: string;
  /** Adresse absolue de la page du site (rel="alternate"). */
  lienPage: string;
  auteur: string;
  droits: string;
  entrees: EntreeAtom[];
  /** Date du flux quand il n'a aucune entrée (date des données de sa source). */
  majSansEntree: string;
};

/** Plus récente des dates RFC 3339 (comparaison en instant, pas en texte). */
export function plusRecente(dates: string[]): string | null {
  let meilleure: string | null = null;
  let t = -Infinity;
  for (const d of dates) {
    const v = Date.parse(d);
    if (Number.isFinite(v) && v > t) {
      t = v;
      meilleure = d;
    }
  }
  return meilleure;
}

export function documentAtom(f: FluxAtom): string {
  const maj = plusRecente(f.entrees.map((e) => e.maj)) ?? f.majSansEntree;
  const x = echapperXml;
  const lignes: string[] = [
    '<?xml version="1.0" encoding="utf-8"?>',
    '<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="fr">',
    `  <id>${x(f.id)}</id>`,
    `  <title>${x(f.titre)}</title>`,
    `  <subtitle>${x(f.sousTitre)}</subtitle>`,
    `  <link rel="self" type="application/atom+xml" href="${x(f.lienSelf)}"/>`,
    `  <link rel="alternate" type="text/html" href="${x(f.lienPage)}"/>`,
    `  <updated>${x(maj)}</updated>`,
    `  <author><name>${x(f.auteur)}</name></author>`,
    `  <rights>${x(f.droits)}</rights>`,
  ];
  for (const e of f.entrees) {
    lignes.push("  <entry>");
    lignes.push(`    <id>${x(e.id)}</id>`);
    lignes.push(`    <title>${x(e.titre)}</title>`);
    lignes.push(`    <link rel="alternate" href="${x(e.lien)}"/>`);
    if (e.lienRelie) lignes.push(`    <link rel="related" type="text/html" href="${x(e.lienRelie)}"/>`);
    lignes.push(`    <updated>${x(e.maj)}</updated>`);
    lignes.push("  </entry>");
  }
  lignes.push("</feed>");
  return lignes.join("\n") + "\n";
}
