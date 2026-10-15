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
