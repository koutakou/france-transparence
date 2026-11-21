// Règle : un texte publié ne contient ni tiret cadratin, ni tiret
// demi-cadratin, ni point-virgule, ni « … », sauf dans une valeur reprise
// telle quelle d'une colonne de COLONNES_SOURCES. Raison : le site promet de
// reproduire les sources officielles mot pour mot, il ne corrige donc pas leur
// ponctuation, mais tout texte que nous écrivons reste soumis à la règle.
//
// Typographie des textes publiés (décision du propriétaire du 21/11/2026).
// Les guillemets français restent.
//
// Ce module lit l'export statique construit (app/out) : texte et valeurs
// d'attributs des pages HTML, XML et SVG (sans <script> ni <style>, sauf le
// JSON-LD, qui est publié), chaînes des fichiers JSON, fichiers texte. Il est
// joué par scripts/poids-pages.mjs, donc par l'étape « Budget de poids des
// pages » de la CI, juste après le build. Le test des sources
// (tests/typographie.test.mjs) garde en plus les chaînes du code, dès npm test.
//
// Un signe dont le voisinage se retrouve tel quel dans une valeur d'une de ces
// colonnes est compté à part (« repris des sources ») et ne fait pas échouer
// le contrôle. La liste n'a pas d'échéance : elle change avec le schéma.
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

/**
 * Colonnes dont la valeur est reprise telle quelle d'une source officielle
 * (registre de transparence de l'UE, répertoire et déclarations HATVP, JO,
 * dossiers législatifs, scrutins, marchés publics, budget de l'État, Sirene,
 * CNCCFP, CADA, ADLC). Les textes écrits par nos pipelines (meta_sources,
 * alertes, notes, sources de calcul, libellés calculés comme les fourchettes
 * ou les étiquettes de millésime) n'y sont pas et restent bloquants. Chaque
 * entrée doit exister dans docs/SCHEMA-DB.md (tests/typographie.test.mjs).
 */
export const COLONNES_SOURCES = [
  // Marchés publics : DECP consolidées, BOAMP, programmations d'achats.
  "decp_marches.objet",
  "decp_marches.acheteur_nom",
  "decp_marches.titulaire_nom",
  "decp_marches.titulaires_json",
  "decp_derniers_marches.objet",
  "decp_derniers_marches.acheteur_nom",
  "decp_derniers_marches.titulaire_nom",
  "decp_derniers_marches.titulaires_json",
  "decp_top_acheteurs.nom",
  "decp_top_titulaires.nom",
  "ao_en_cours.objet",
  "ao_en_cours.acheteur",
  "annonces_recentes.objet",
  "annonces_recentes.acheteur",
  "annonces_recentes.titulaires",
  "marches_a_venir.intitule",
  "marches_a_venir.description",
  // Journal officiel et dossiers législatifs (DILA), scrutins des assemblées.
  "jorf_textes.titre",
  "jorf_textes.ministere",
  "dole_dossiers.titre",
  "dole_dossiers.derniere_etape",
  "scrutins.titre",
  "scrutins_senat.titre",
  // Répertoire des représentants d'intérêts et déclarations (HATVP).
  "lobby_entites.denomination",
  "lobby_entites.nom_usage",
  "lobby_agg_top_entites.denomination",
  "lobby_activites.objet",
  "lobby_activites.actions",
  "lobby_activites.decisions",
  "hatvp_decl_interets.organe_libelle",
  "hatvp_decl_lignes.libelle",
  "hatvp_decl_lignes.description",
  "hatvp_decl_lignes.commentaire",
  // Registre de transparence de l'UE : noms et adresses déclarés.
  "ue_registre_organisations.nom",
  "ue_registre_organisations.nom_latin",
  "ue_registre_organisations.acronyme",
  "ue_registre_organisations.siege_ville",
  "ue_registre_organisations.siege_code_postal",
  // Budget de l'État : PLF, budget vert, jaune des associations.
  "budget_vert.action",
  "budget_vert.libelle",
  "budget_destination_2025.libelle_mission",
  "budget_destination_2025.libelle_programme",
  "budget_destination_2025.libelle_action",
  "budget_destination_2025.libelle_sous_action",
  "recettes_plf_etat_a.libelle",
  "subventions_associations.denomination",
  "subventions_associations.objet",
  "subventions_associations.convention",
  // Noms d'organisations des référentiels et des décisions publiées.
  "sirene_unites_legales.denomination",
  "cada_administrations.libelle",
  "adlc_decisions.sous_titre",
  "adlc_lignes.denomination",
  "partis.nom",
  "partis_comptes.nom_declare",
];

/** Un signe banni, n'importe où dans la chaîne. */
export const SIGNES_BANNIS = /[—–;…]/u;
const SIGNES_GLOBAL = /[—–;…]/gu;

const NOMS = { "—": "tiret cadratin", "–": "tiret demi-cadratin", ";": "point-virgule", "…": "points de suspension" };

/** Noms des signes bannis présents dans `texte`. */
export function signesPresents(texte) {
  return [...new Set([...texte].filter((c) => NOMS[c]).map((c) => NOMS[c]))];
}

const ENTITES = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ", mdash: "—", ndash: "–", hellip: "…" };

/** Décode les entités HTML usuelles et numériques. */
export function decoderEntites(s) {
  return s.replace(/&(#x[0-9a-f]+|#[0-9]+|[a-z]+);/gi, (m, e) => {
    if (e[0] === "#") {
      const n = e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
      return Number.isFinite(n) && n <= 0x10ffff ? String.fromCodePoint(n) : m;
    }
    return ENTITES[e.toLowerCase()] ?? m;
  });
}

const echapper = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** Attributs de géométrie ou de style : pas du texte. */
const ATTRIBUTS_NON_TEXTE = new Set(["style", "d", "points", "transform", "viewbox", "class", "href", "src", "srcset"]);

/**
 * Texte lisible d'un document balisé (HTML, XML, SVG) : nœuds de texte et
 * valeurs d'attributs, entités décodées. Le contenu de <script> et <style>
 * et les commentaires ne comptent pas, sauf le JSON-LD (publié tel quel
 * pour les moteurs), dont les chaînes sont rendues. Rend une liste de chaînes.
 */
export function textesDuBalisage(doc) {
  const textes = [];
  for (const m of doc.matchAll(/<script\b[^>]*type\s*=\s*["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script\s*>/gi)) {
    try {
      textesDuJson(JSON.parse(m[1]), textes);
    } catch {
      textes.push(m[1]);
    }
  }
  const sansCode = doc
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, (_, c) => echapper(c))
    // Un commentaire sépare deux nœuds de texte (React les borne par <!-- -->).
    .replace(/<!--[\s\S]*?-->/g, "<!>")
    .replace(/<script\b[^>]*>[\s\S]*?<\/script\s*>/gi, "<!>")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style\s*>/gi, "<!>")
    // <code> cite un format ou une valeur technique (le séparateur « ; » des CSV).
    .replace(/<code\b[^>]*>[\s\S]*?<\/code\s*>/gi, "<!>");
  const balise = /<[^>]*>/g;
  let dernier = 0;
  let m;
  while ((m = balise.exec(sansCode))) {
    const avant = sansCode.slice(dernier, m.index);
    if (avant.trim()) textes.push(decoderEntites(avant));
    dernier = m.index + m[0].length;
    const tag = m[0];
    // Une balise <meta http-equiv> porte une directive technique (CSP), pas du texte.
    if (/^<[a-z]/i.test(tag) && !/^<meta\b[^>]*\shttp-equiv\s*=/i.test(tag)) {
      for (const a of tag.matchAll(/\s([^\s=/>]+)\s*=\s*("([^"]*)"|'([^']*)')/g)) {
        const nom = a[1].toLowerCase();
        if (ATTRIBUTS_NON_TEXTE.has(nom) || nom.startsWith("data-")) continue;
        const valeur = decoderEntites(a[3] ?? a[4] ?? "");
        if (valeur.trim()) textes.push(valeur);
      }
    }
  }
  const fin = sansCode.slice(dernier);
  if (fin.trim()) textes.push(decoderEntites(fin));
  return textes;
}

/** Chaînes (valeurs) d'une valeur JSON. */
export function textesDuJson(valeur, out = []) {
  if (typeof valeur === "string") out.push(valeur);
  else if (Array.isArray(valeur)) for (const v of valeur) textesDuJson(v, out);
  else if (valeur && typeof valeur === "object") for (const v of Object.values(valeur)) textesDuJson(v, out);
  return out;
}

/** Voisinage gardé de part et d'autre d'un signe pour le rattacher à une source. */
const VOISINAGE = 10;
/**
 * Contexte (caractères autour du signe) en dessous duquel une clé est une
 * valeur courte prise entière : elle ne compte que si, dans le texte publié,
 * elle n'est pas collée à une lettre ou à un chiffre.
 */
const CONTEXTE_MINIMAL = 8;
const ALPHANUM = /[\p{L}\p{N}]/u;

/**
 * Clés de voisinage d'une valeur de source : une par signe, bornée à la
 * valeur. Une valeur plus courte que la fenêtre sert de clé entière. Une clé
 * sans lettre ni chiffre (le signe seul) n'est pas gardée.
 */
export function clesDeValeur(valeur, cles = new Set()) {
  for (const m of valeur.matchAll(SIGNES_GLOBAL)) {
    const i = m.index;
    const g = Math.min(VOISINAGE, i);
    const d = Math.min(VOISINAGE, valeur.length - 1 - i);
    const cle = valeur.slice(i - g, i + d + 1);
    if (ALPHANUM.test(cle)) cles.add(cle);
  }
  return cles;
}

/**
 * Voisinages des signes bannis présents dans les colonnes `colonnes`
 * (COLONNES_SOURCES par défaut). Rend { cles, absentes } : `cles` est un Set,
 * vide si la base est absente, `absentes` les colonnes introuvables en base.
 */
export function voisinagesSources(cheminBase, colonnes = COLONNES_SOURCES) {
  const cles = new Set();
  const absentes = [];
  if (!cheminBase || !fs.existsSync(cheminBase)) return { cles, absentes };
  const require = createRequire(import.meta.url);
  const Database = require("better-sqlite3");
  const db = new Database(cheminBase, { readonly: true, fileMustExist: true });
  try {
    const q = (n) => `"${n.replace(/"/g, '""')}"`;
    for (const tc of colonnes) {
      const [table, col] = tc.split(".");
      if (!db.prepare(`PRAGMA table_info(${q(table)})`).all().some((c) => c.name === col)) {
        absentes.push(tc);
        continue;
      }
      const c = q(col);
      const sql = `SELECT ${c} AS v FROM ${q(table)} WHERE typeof(${c}) = 'text' AND (instr(${c}, char(8212)) OR instr(${c}, char(8211)) OR instr(${c}, ';') OR instr(${c}, char(8230)))`;
      for (const { v } of db.prepare(sql).iterate()) clesDeValeur(v, cles);
    }
  } finally {
    db.close();
  }
  return { cles, absentes };
}

/** Vrai si le signe en position `i` de `texte` a un voisinage pris dans une source. */
function venuDUneSource(texte, i, cles) {
  if (cles.size === 0) return false;
  for (let g = Math.min(VOISINAGE, i); g >= 0; g--) {
    for (let d = Math.min(VOISINAGE, texte.length - 1 - i); d >= 0; d--) {
      if (!cles.has(texte.slice(i - g, i + d + 1))) continue;
      if (g + d >= CONTEXTE_MINIMAL) return true;
      // Valeur courte : entière dans le texte, pas un morceau d'un mot plus long.
      const avant = texte[i - g - 1];
      const apres = texte[i + d + 1];
      if (!(avant && ALPHANUM.test(avant)) && !(apres && ALPHANUM.test(apres))) return true;
    }
  }
  return false;
}

/** Fichiers de l'export à lire, chemins relatifs. `_next/` (code) est exclu. */
function* fichiersPublies(racine, dossier = racine) {
  for (const e of fs.readdirSync(dossier, { withFileTypes: true })) {
    const chemin = path.join(dossier, e.name);
    if (e.isDirectory()) {
      if (e.name === "_next") continue;
      yield* fichiersPublies(racine, chemin);
    } else if (/\.(html|xml|svg|json|txt|webmanifest)$/i.test(e.name)) {
      yield path.relative(racine, chemin).split(path.sep).join("/");
    }
  }
}

/** Charge utile React (RSC) d'une page : `index.txt` à lignes « 0:… ». */
const estChargeRsc = (contenu) => /^[0-9a-f]*:/.test(contenu);

/** Chaînes publiées d'un fichier de l'export, ou null s'il n'est pas du texte publié. */
export function textesDuFichier(rel, contenu) {
  if (/\.(html|xml|svg)$/i.test(rel)) return textesDuBalisage(contenu);
  if (/\.(json|webmanifest)$/i.test(rel)) {
    try {
      return textesDuJson(JSON.parse(contenu));
    } catch {
      return [contenu];
    }
  }
  if (estChargeRsc(contenu)) return null;
  return [contenu];
}

/**
 * Contrôle `racine` (l'export). `cles` : voisinages des colonnes sources
 * acceptés (Set, vide pour ne rien accepter). Rend { fichiers, app, sources },
 * où `app` (bloquant) et `sources` listent { fichier, signe, extrait }.
 */
export function controlerTypographie(racine, cles = new Set()) {
  const app = [];
  const sources = [];
  let fichiers = 0;
  for (const rel of fichiersPublies(racine)) {
    const contenu = fs.readFileSync(path.join(racine, rel), "utf8");
    if (!SIGNES_BANNIS.test(contenu) && !/&(mdash|ndash|hellip|#8211|#8212|#8230|#x201[34]|#x2026);/i.test(contenu)) {
      fichiers++;
      continue;
    }
    const textes = textesDuFichier(rel, contenu);
    if (textes === null) continue;
    fichiers++;
    for (const texte of textes) {
      for (const m of texte.matchAll(SIGNES_GLOBAL)) {
        const i = m.index;
        const extrait = texte.slice(Math.max(0, i - 40), i + 41).replace(/\s+/g, " ").trim();
        const occ = { fichier: rel, signe: NOMS[m[0]], extrait };
        (venuDUneSource(texte, i, cles) ? sources : app).push(occ);
      }
    }
  }
  return { fichiers, app, sources };
}

/** Journal et code de sortie (0 ou 1) du contrôle, pour poids-pages.mjs. */
export function rapporterTypographie(racine, cheminBase) {
  const { cles, absentes } = voisinagesSources(cheminBase);
  const { fichiers, app, sources } = controlerTypographie(racine, cles);
  console.log(
    `Typographie des textes publiés (${fichiers} fichiers lus) : ${app.length} signe(s) banni(s) hors sources, ${sources.length} repris tel(s) quel(s) de ${COLONNES_SOURCES.length} colonnes sources`,
  );
  if (absentes.length > 0) console.log(`  colonnes sources absentes de cette base : ${absentes.join(", ")}`);
  const parFichier = new Map();
  for (const o of sources) parFichier.set(o.fichier, (parFichier.get(o.fichier) ?? 0) + 1);
  const tri = [...parFichier].sort((a, b) => b[1] - a[1]);
  for (const [f, n] of tri.slice(0, 10)) console.log(`  sources : ${String(n).padStart(6)}  ${f}`);
  if (tri.length > 10) console.log(`  sources : ${tri.length - 10} autre(s) fichier(s)`);
  // Un même texte répété sur plusieurs pages n'est cité qu'une fois.
  const parExtrait = new Map();
  for (const o of app) {
    const cle = `${o.signe} « ${o.extrait} »`;
    const vu = parExtrait.get(cle);
    if (vu) vu.n++;
    else parExtrait.set(cle, { fichier: o.fichier, n: 1 });
  }
  const distincts = [...parExtrait];
  for (const [cle, { fichier, n }] of distincts.slice(0, 60)) {
    console.error(`ÉCHEC : ${cle} dans ${fichier}${n > 1 ? ` et ${n - 1} autre(s) endroit(s)` : ""}`);
  }
  if (distincts.length > 60) console.error(`ÉCHEC : ${distincts.length - 60} autre(s) texte(s) distinct(s)`);
  return app.length > 0 ? 1 : 0;
}
