// Typographie des textes publiés (décision du propriétaire du 21/11/2026) :
// aucun tiret cadratin, tiret demi-cadratin, point-virgule ni points de
// suspension typographiques dans ce que le site publie. Les guillemets
// français restent.
//
// Ce module lit l'export statique construit (app/out) : texte et valeurs
// d'attributs des pages HTML, XML et SVG (sans <script> ni <style>, sauf le
// JSON-LD, qui est publié), chaînes des fichiers JSON, fichiers texte. Il est
// joué par scripts/poids-pages.mjs, donc par l'étape « Budget de poids des
// pages » de la CI, juste après le build. Le test des sources
// (tests/typographie.test.mjs) garde en plus les chaînes du code, dès npm test.
//
// TOLÉRANCE PROVISOIRE (21/11/2026) : les textes écrits en base par les
// pipelines sont nettoyés par un autre lot. D'ici là, un signe dont le
// voisinage se retrouve tel quel dans une valeur de la base est compté à
// part (« venu de la base ») et ne fait pas échouer le contrôle. Retirer
// TOLERANCE_TEXTES_BASE (mettre `null`) une fois ce lot fusionné.
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

export const TOLERANCE_TEXTES_BASE = {
  depuis: "2026-11-21",
  aRetirerLe: "2026-12-05",
  motif: "textes écrits en base par les pipelines, nettoyés par le lot « Style des textes publiés, pipelines »",
};

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

/** Voisinage gardé de part et d'autre d'un signe pour le rattacher à la base. */
const VOISINAGE = 10;
/** Contexte minimal (caractères autour du signe) pour qu'un rattachement compte. */
const CONTEXTE_MINIMAL = 8;

/** Clés de voisinage d'une valeur de la base : une par signe, bornée à la valeur. */
function clesDeValeur(valeur, cles) {
  for (const m of valeur.matchAll(SIGNES_GLOBAL)) {
    const i = m.index;
    const g = Math.min(VOISINAGE, i);
    const d = Math.min(VOISINAGE, valeur.length - 1 - i);
    if (g + d >= CONTEXTE_MINIMAL) cles.add(valeur.slice(i - g, i + d + 1));
  }
}

/**
 * Voisinages de tous les signes bannis présents dans les colonnes texte de la
 * base. Rend un Set, vide si la base est absente ou illisible.
 */
export function voisinagesBase(cheminBase) {
  const cles = new Set();
  if (!cheminBase || !fs.existsSync(cheminBase)) return cles;
  const require = createRequire(import.meta.url);
  const Database = require("better-sqlite3");
  const db = new Database(cheminBase, { readonly: true, fileMustExist: true });
  try {
    const tables = db
      .prepare("SELECT name, sql FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
      .all()
      .filter((t) => !/^\s*CREATE\s+VIRTUAL/i.test(t.sql ?? ""));
    const q = (n) => `"${n.replace(/"/g, '""')}"`;
    for (const { name } of tables) {
      const colonnes = db
        .prepare(`PRAGMA table_info(${q(name)})`)
        .all()
        .filter((c) => c.type === "" || /CHAR|CLOB|TEXT/i.test(c.type));
      for (const { name: col } of colonnes) {
        const c = q(col);
        const sql = `SELECT ${c} AS v FROM ${q(name)} WHERE typeof(${c}) = 'text' AND (instr(${c}, char(8212)) OR instr(${c}, char(8211)) OR instr(${c}, ';') OR instr(${c}, char(8230)))`;
        for (const { v } of db.prepare(sql).iterate()) clesDeValeur(v, cles);
      }
    }
  } finally {
    db.close();
  }
  return cles;
}

/** Vrai si le signe en position `i` de `texte` a un voisinage pris dans la base. */
function venuDeLaBase(texte, i, cles) {
  if (cles.size === 0) return false;
  for (let g = Math.min(VOISINAGE, i); g >= 0; g--) {
    for (let d = Math.min(VOISINAGE, texte.length - 1 - i); d >= 0; d--) {
      if (g + d < CONTEXTE_MINIMAL) break;
      if (cles.has(texte.slice(i - g, i + d + 1))) return true;
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
 * Contrôle `racine` (l'export). `cles` : voisinages de la base tolérés (Set,
 * vide pour ne rien tolérer). Rend { fichiers, app, base }, où `app` et `base`
 * listent { fichier, signe, extrait }.
 */
export function controlerTypographie(racine, cles = new Set()) {
  const app = [];
  const base = [];
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
        (venuDeLaBase(texte, i, cles) ? base : app).push(occ);
      }
    }
  }
  return { fichiers, app, base };
}

/** Journal et code de sortie (0 ou 1) du contrôle, pour poids-pages.mjs. */
export function rapporterTypographie(racine, cheminBase) {
  const cles = TOLERANCE_TEXTES_BASE ? voisinagesBase(cheminBase) : new Set();
  const { fichiers, app, base } = controlerTypographie(racine, cles);
  console.log(
    `Typographie des textes publiés (${fichiers} fichiers lus) : ${app.length} signe(s) banni(s) hors base, ${base.length} venu(s) de la base`,
  );
  if (TOLERANCE_TEXTES_BASE) {
    const echue = new Date().toISOString().slice(0, 10) > TOLERANCE_TEXTES_BASE.aRetirerLe;
    console.log(
      `  ${echue ? "TOLÉRANCE PROVISOIRE ÉCHUE, à retirer" : "Tolérance provisoire"} depuis le ${TOLERANCE_TEXTES_BASE.depuis} (retrait prévu le ${TOLERANCE_TEXTES_BASE.aRetirerLe}) : ${TOLERANCE_TEXTES_BASE.motif}`,
    );
    const parFichier = new Map();
    for (const o of base) parFichier.set(o.fichier, (parFichier.get(o.fichier) ?? 0) + 1);
    const tri = [...parFichier].sort((a, b) => b[1] - a[1]);
    for (const [f, n] of tri.slice(0, 15)) console.log(`  base : ${String(n).padStart(6)}  ${f}`);
    if (tri.length > 15) console.log(`  base : ${tri.length - 15} autre(s) fichier(s)`);
    for (const o of base.slice(0, 10)) console.log(`  base, exemple (${o.signe}) : ${o.fichier} : « ${o.extrait} »`);
  }
  for (const o of app.slice(0, 50)) console.error(`ÉCHEC : ${o.signe} dans ${o.fichier} : « ${o.extrait} »`);
  if (app.length > 50) console.error(`ÉCHEC : ${app.length - 50} autre(s) occurrence(s)`);
  return app.length > 0 ? 1 : 0;
}
