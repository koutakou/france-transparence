// Contrôles STATIQUES de textes publics écrits dans le source (pas un rendu) :
// des affirmations fausses ou des formes cassées déjà publiées une fois.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const lire = (chemin) => readFileSync(new URL(`../src/${chemin}`, import.meta.url), "utf8");
// JSX replie les retours à la ligne en une espace : on compare sur ce texte-là.
const aplati = (chemin) => lire(chemin).replace(/\s*\n\s*/g, " ");

test("/comprendre : S.1311 est l'administration centrale, pas « l'État seul » (S13111)", () => {
  const s = aplati("app/comprendre/page.tsx");
  assert.doesNotMatch(s, /État seul \((sous-secteur )?S\.?1311\)/);
});
