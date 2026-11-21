// Contrôle STATIQUE du source (pas un rendu) : ARIA 1.2 interdit
// `aria-label` sur un élément sans rôle (div, span… = rôle « generic »,
// règle axe `aria-prohibited-attr`) ; les lecteurs d'écran l'ignorent, et un
// graphique focalisable devient un arrêt de tabulation muet. Toute balise
// générique qui porte un nom doit aussi porter un `role=`.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const racine = fileURLToPath(new URL("../src", import.meta.url));
const fichiers = [];
const parcourir = (dossier) => {
  for (const nom of readdirSync(dossier)) {
    const chemin = join(dossier, nom);
    if (statSync(chemin).isDirectory()) parcourir(chemin);
    else if (chemin.endsWith(".tsx")) fichiers.push(chemin);
  }
};
parcourir(racine);

// Balises sans rôle implicite. `=>` est sauté pour ne pas couper une balise
// sur une fonction fléchée passée en attribut.
const BALISE = /<(div|span|p|li|b|i|em|strong|small)\b((?:=>|[^>])*?)>/g;

test("aucun aria-label sur une balise générique sans role", () => {
  const fautes = [];
  for (const f of fichiers) {
    const s = readFileSync(f, "utf8");
    for (const m of s.matchAll(BALISE)) {
      if (/\baria-label=/.test(m[2]) && !/\brole=/.test(m[2])) {
        const ligne = s.slice(0, m.index).split("\n").length;
        fautes.push(`${f.slice(racine.length + 1)}:${ligne} <${m[1]}>`);
      }
    }
  }
  assert.deepEqual(fautes, []);
});

// --ink-muted est le MINIMUM pour du texte (4,83:1 sur --surface-hover) :
// l'atténuer par une opacité le fait passer sous 4,5:1 (« ‹ Page
// précédente » inactive de /alertes : 2,47:1). Un état inactif se dit par
// aria-disabled et une forme (bordure tiretée), pas par l'opacité.
test("aucun texte --ink-muted atténué par une opacité", () => {
  const fautes = [];
  for (const f of fichiers) {
    const s = readFileSync(f, "utf8");
    for (const m of s.matchAll(/className="([^"]*)"/g)) {
      if (/\btext-ink-muted\b/.test(m[1]) && /\bopacity-\d+\b/.test(m[1])) {
        const ligne = s.slice(0, m.index).split("\n").length;
        fautes.push(`${f.slice(racine.length + 1)}:${ligne}`);
      }
    }
  }
  assert.deepEqual(fautes, []);
});

// Chaque tableau porte une légende : un lecteur d'écran qui passe de tableau
// en tableau (89 sur l'échantillon de l'audit, aucun légendé) doit savoir
// lequel il lit. DataTable la rend en <caption class="sr-only"> (prop
// `legende`, à défaut `libelle` ou les en-têtes).
test("chaque <table> a un <caption> ou un aria-labelledby", () => {
  const fautes = [];
  for (const f of fichiers) {
    const s = readFileSync(f, "utf8");
    for (const m of s.matchAll(/<table\b((?:=>|[^>])*?)>/g)) {
      const suite = s.slice(m.index + m[0].length).trimStart();
      if (!/\baria-labelledby=/.test(m[1]) && !suite.startsWith("<caption")) {
        const ligne = s.slice(0, m.index).split("\n").length;
        fautes.push(`${f.slice(racine.length + 1)}:${ligne}`);
      }
    }
  }
  assert.deepEqual(fautes, []);
});

// WCAG 2.2, 2.5.8 : une cible d'au moins 24 px de haut. Un <summary> ou un
// <button> de composant dont les classes ne donnent aucune hauteur (ni
// min-h, ni h, ni padding vertical) tombe à la hauteur de sa ligne de texte
// (« Vue tableau » : 16 px, noms de commune du tableau : 20 px).
test("aucun summary ni bouton de composant sans hauteur minimale", () => {
  const fautes = [];
  for (const f of fichiers) {
    if (!f.slice(racine.length + 1).startsWith("components")) continue;
    const s = readFileSync(f, "utf8");
    for (const m of s.matchAll(/<(button|summary)\b((?:=>|[^>])*?)>/g)) {
      const classes = /className=(?:"([^"]*)"|\{`([^`]*)`)/.exec(m[2]);
      if (!classes) continue; // classes calculées ailleurs : hors de portée d'un contrôle statique
      const c = classes[1] ?? classes[2];
      if (!/(?:^|\s)(?:min-h-|h-|py-|p-)\S+/.test(c)) {
        const ligne = s.slice(0, m.index).split("\n").length;
        fautes.push(`${f.slice(racine.length + 1)}:${ligne} <${m[1]}>`);
      }
    }
  }
  assert.deepEqual(fautes, []);
});

// Sans JavaScript, rien ne doit annoncer un chargement qui n'aura pas lieu,
// ni une pagination sans suite.
test("sans JavaScript : pas de faux chargement de carte, et les listes paginées renvoient à l'export", () => {
  const carte = readFileSync(join(racine, "components/client/CarteDepartements.tsx"), "utf8");
  assert.doesNotMatch(carte, /role="status"/);
  assert.match(carte, /scriptActif \? "Chargement du fond de carte…" : TEXTE_SANS_SCRIPT/);
  assert.match(carte, /useSyncExternalStore\(\s*abonnementInerte,\s*\(\) => true,\s*\(\) => false,?\s*\)/);
  const alertes = readFileSync(join(racine, "components/client/AlertesListe.tsx"), "utf8");
  assert.match(alertes, /<noscript>[\s\S]*?urlSite\("\/donnees\/"\)[\s\S]*?<\/noscript>/);
  const elus = readFileSync(join(racine, "app/elus/page.tsx"), "utf8");
  assert.match(elus, /<noscript>[\s\S]*?href="\/donnees\/"[\s\S]*?<\/noscript>/);
  assert.equal((elus.match(/<SansScript\b/g) ?? []).length, 2);
});
