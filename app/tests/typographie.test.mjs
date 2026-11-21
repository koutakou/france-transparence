// Typographie des textes publiés (décision du propriétaire du 21/11/2026) :
// aucun tiret cadratin, tiret demi-cadratin, point-virgule ni points de
// suspension typographiques dans ce que le site publie.
//
// Deux gardes :
// - ici, dès npm test : les chaînes et textes JSX du code (commentaires non
//   lus), les fichiers publics, et le contrôle de l'export lui-même ;
// - après le build, scripts/poids-pages.mjs joue scripts/typographie.mjs sur
//   l'export construit (texte, attributs, JSON-LD, JSON, XML, fichiers texte).
// Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Database from "better-sqlite3";
import { SIGNES_BANNIS, signesPresents, textesDuBalisage, textesDuSource } from "./outils/typographie.mjs";
import { COLONNES_SOURCES, clesDeValeur, controlerTypographie, voisinagesSources } from "../scripts/typographie.mjs";

const APP = fileURLToPath(new URL("../", import.meta.url));

function fichiers(dossier, motif) {
  const out = [];
  for (const e of fs.readdirSync(dossier, { withFileTypes: true })) {
    const p = path.join(dossier, e.name);
    if (e.isDirectory()) out.push(...fichiers(p, motif));
    else if (motif.test(e.name)) out.push(p);
  }
  return out;
}

/**
 * Chaînes du code qui ne sont pas du texte publié et gardent leur signe.
 * Chaque entrée doit servir : une entrée qui ne couvre plus rien fait échouer
 * le test, pour que la liste ne grossisse pas en silence.
 */
const NON_PUBLIEES = [
  { motif: /^;$/, raison: "séparateur des CSV publiés, cité tel quel (format, pas du texte)" },
  { motif: /;\s*charset=utf-8$/, raison: "en-tête Content-Type" },
  { motif: /\{[^{}]*[a-z-]+\s*:[^{}]*;[^{}]*\}/, raison: "règle CSS en ligne" },
  { fichier: "app/layout.tsx", motif: /\bdefault-src\b/, raison: "directive CSP (balise meta http-equiv)" },
  { fichier: "lib/lecture.ts", motif: /getAttribute|setInterval/, raison: "script en ligne (JavaScript)" },
  { fichier: "lib/queries/elus.ts", motif: /^\s*SELECT\b/, raison: "requête SQL" },
];

test("aucune chaîne publiée du code ne contient de tiret long, de point-virgule ni de « … »", () => {
  const src = path.join(APP, "src");
  const fautes = [];
  const servies = new Set();
  for (const p of fichiers(src, /\.tsx?$/)) {
    const rel = path.relative(src, p).split(path.sep).join("/");
    for (const { texte, ligne } of textesDuSource(fs.readFileSync(p, "utf8"), p)) {
      if (!SIGNES_BANNIS.test(texte)) continue;
      const exception = NON_PUBLIEES.find((e) => (!e.fichier || e.fichier === rel) && e.motif.test(texte));
      if (exception) {
        servies.add(exception);
        continue;
      }
      fautes.push(`${rel}:${ligne} (${signesPresents(texte).join(", ")}) : ${texte.replace(/\s+/g, " ").trim().slice(0, 120)}`);
    }
  }
  assert.deepEqual(fautes, [], `textes publiés à reprendre :\n${fautes.join("\n")}`);
  const inutiles = NON_PUBLIEES.filter((e) => !servies.has(e)).map((e) => `${e.fichier ?? "*"} ${e.motif}`);
  assert.deepEqual(inutiles, [], "exception devenue inutile, à retirer de NON_PUBLIEES");
});

test("les fichiers publics (SVG, manifeste, textes) n'en contiennent pas non plus", () => {
  const publics = [
    ...fichiers(path.join(APP, "public"), /\.(svg|txt|json|webmanifest|xml)$/i),
    ...fichiers(path.join(APP, "src", "app"), /\.(svg|txt|json|webmanifest|xml)$/i),
  ];
  assert.ok(publics.some((p) => p.endsWith("og.svg")), "og.svg doit être lu");
  for (const p of publics) {
    const contenu = fs.readFileSync(p, "utf8");
    const textes = /\.(svg|xml)$/i.test(p) ? textesDuBalisage(contenu) : [contenu];
    for (const t of textes) assert.doesNotMatch(t, SIGNES_BANNIS, `${path.relative(APP, p)} : ${t.slice(0, 80)}`);
  }
});

test("la lecture du code ignore les commentaires et décode les entités JSX", () => {
  const code = [
    "// commentaire — libre ; …",
    "/* bloc — libre */",
    'const a = "texte — publié";',
    "const b = `gabarit ${a} ; suite`;",
    "const c = <p title=\"x&mdash;y\">Texte&nbsp;: rien</p>;",
    "const d = <p>Fin&hellip;</p>;",
  ].join("\n");
  const textes = textesDuSource(code, "x.tsx").map((t) => t.texte);
  assert.ok(textes.includes("texte — publié"));
  assert.ok(textes.includes(" ; suite"));
  assert.ok(textes.includes("x—y"), "entité d'attribut décodée");
  assert.ok(textes.includes("Texte : rien"), "&nbsp; n'est pas un point-virgule");
  assert.ok(textes.includes("Fin…"));
  assert.ok(!textes.some((t) => t.includes("libre")), "commentaires non lus");
});

test("la lecture de l'export ne lit ni scripts, ni styles, ni directive CSP, mais lit le JSON-LD", () => {
  const html = [
    '<html><head><meta http-equiv="Content-Security-Policy" content="default-src \'self\'; img-src data:">',
    '<meta name="description" content="Résumé — à reprendre">',
    "<style>a{color:red;margin:0}</style>",
    "<script>var x=1;self.__next_f.push([1,\"—\"])</script>",
    '<script type="application/ld+json">{"@type":"Dataset","name":"Jeu ; publié"}</script>',
    '</head><body><p class="a;b" aria-label="Fermer…">Un<!-- -->texte</p>',
    "<td>&mdash;</td><p>Séparateur <code>;</code>, UTF-8</p></body></html>",
  ].join("");
  const textes = textesDuBalisage(html);
  assert.ok(textes.includes("Résumé — à reprendre"), "attribut content d'une description");
  assert.ok(textes.includes("Jeu ; publié"), "JSON-LD lu");
  assert.ok(textes.includes("Fermer…"), "aria-label lu");
  assert.ok(textes.includes("—"), "entité décodée dans le texte");
  assert.ok(textes.includes("Un") && textes.includes("texte"), "un commentaire sépare deux nœuds");
  for (const t of textes) {
    assert.doesNotMatch(t, /default-src|color:red|__next_f/, "ni CSP, ni style, ni script");
    assert.notEqual(t, "a;b", "classe CSS ignorée");
    assert.notEqual(t, ";", "le contenu de <code> est un format, pas du texte");
  }
});

test("chaque colonne de COLONNES_SOURCES existe dans le schéma documenté", () => {
  const schema = fs.readFileSync(path.join(APP, "..", "docs", "SCHEMA-DB.md"), "utf8");
  const colonnes = new Map();
  for (const m of schema.matchAll(/CREATE TABLE (\w+) \(([\s\S]*?)\n\);/g)) {
    const noms = new Set();
    for (const ligne of m[2].split("\n")) {
      const c = ligne.replace(/--.*$/, "").trim().match(/^(\w+)\s+[A-Z]/);
      if (c) noms.add(c[1]);
    }
    colonnes.set(m[1], noms);
  }
  assert.ok(colonnes.size > 50, "lecture du schéma");
  const disparues = COLONNES_SOURCES.filter((tc) => {
    const [table, col] = tc.split(".");
    return !colonnes.get(table)?.has(col);
  });
  assert.deepEqual(disparues, [], "colonne listée absente de docs/SCHEMA-DB.md : la retirer ou la renommer");
  assert.equal(new Set(COLONNES_SOURCES).size, COLONNES_SOURCES.length, "doublon dans la liste");
  for (const tc of ["meta_sources.nom", "meta_sources.notes", "alertes.titre", "alertes.detail", "ue_registre_organisations.cout_libelle"]) {
    assert.ok(!COLONNES_SOURCES.includes(tc), `${tc} est écrit par nos pipelines, il reste bloquant`);
  }
});

test("une valeur courte d'une source sert de clé entière, mais pas un morceau de mot", () => {
  const cles = clesDeValeur("ENM–RI");
  assert.ok(cles.has("ENM–RI"));
  assert.equal(clesDeValeur(" – ").size, 0, "le signe seul n'est pas une clé");
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "ft-typo-court-"));
  try {
    fs.writeFileSync(path.join(tmp, "a.html"), "<p>Sigle : ENM–RI</p><p>Code XENM–RIZ</p>");
    const r = controlerTypographie(tmp, cles);
    assert.equal(r.sources.length, 1, "la valeur courte entière est reprise de la source");
    assert.deepEqual(r.app.map((o) => o.extrait), ["Code XENM–RIZ"], "collée à un mot, elle reste bloquante");
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});

test("le contrôle de l'export n'accepte que les colonnes sources, pas les textes de nos pipelines", (t) => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "ft-typo-"));
  t.after(() => fs.rmSync(tmp, { recursive: true, force: true }));
  const out = path.join(tmp, "out");
  fs.mkdirSync(path.join(out, "_next", "static"), { recursive: true });
  fs.mkdirSync(path.join(out, "api"), { recursive: true });
  fs.writeFileSync(path.join(out, "_next", "static", "a.json"), '{"x":"code — ignoré"}');
  fs.writeFileSync(
    path.join(out, "index.html"),
    "<html><body><h1>Accueil — site</h1><p>Décret n° 12 relatif au budget ; dispositions diverses</p></body></html>",
  );
  fs.writeFileSync(path.join(out, "index.txt"), '0:{"a":"charge React — ignorée"}\n1:I["x"]');
  fs.writeFileSync(path.join(out, "robots.txt"), "User-agent: *\nAllow: /\n");
  fs.writeFileSync(path.join(out, "api", "meta.json"), JSON.stringify({ sources: [{ nom: "HATVP — répertoire des représentants" }] }));
  fs.writeFileSync(path.join(out, "flux.xml"), "<feed><title>Alerte … ouverte</title></feed>");

  const cheminBase = path.join(tmp, "france.db");
  const db = new Database(cheminBase);
  db.exec("CREATE TABLE jorf_textes (titre TEXT, n INTEGER); CREATE TABLE meta_sources (nom TEXT)");
  db.prepare("INSERT INTO jorf_textes VALUES (?, 1)").run("Décret n° 12 relatif au budget ; dispositions diverses");
  db.prepare("INSERT INTO meta_sources VALUES (?)").run("HATVP — répertoire des représentants");
  db.close();

  const sansBase = controlerTypographie(out);
  assert.equal(sansBase.sources.length, 0);
  assert.deepEqual(
    sansBase.app.map((o) => `${o.fichier} ${o.signe}`).sort(),
    ["api/meta.json tiret cadratin", "flux.xml points de suspension", "index.html point-virgule", "index.html tiret cadratin"],
  );

  const { cles, absentes } = voisinagesSources(cheminBase, ["jorf_textes.titre", "jorf_textes.disparue"]);
  assert.deepEqual(absentes, ["jorf_textes.disparue"], "une colonne listée absente de la base est signalée");
  const avecBase = controlerTypographie(out, cles);
  assert.deepEqual(
    avecBase.app.map((o) => `${o.fichier} ${o.signe}`).sort(),
    ["api/meta.json tiret cadratin", "flux.xml points de suspension", "index.html tiret cadratin"],
    "les textes de l'app et ceux de nos pipelines (meta_sources) restent bloquants",
  );
  assert.deepEqual(avecBase.sources.map((o) => o.fichier), ["index.html"], "le titre du JO est repris tel quel");
  const defaut = voisinagesSources(cheminBase);
  assert.deepEqual([...defaut.cles], ["au budget ; dispositi"], "jorf_textes.titre est dans COLONNES_SOURCES, pas meta_sources");
  assert.equal(voisinagesSources(path.join(tmp, "absente.db")).cles.size, 0, "base absente : rien n'est accepté");
});
