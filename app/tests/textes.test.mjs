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

test("/elus : « affiché·es » d'un seul tenant (JSX joint deux lignes par une espace)", () => {
  const s = aplati("components/client/TableParlementaires.tsx");
  assert.doesNotMatch(s, /affiché ·e/);
});

test("fragment indisponible : « (filtrés) » n'est jamais dit d'une liste non filtrée", () => {
  const s = aplati("components/client/FluxTextes.tsx");
  assert.doesNotMatch(s, /filtreActif \? " \(filtrés\)" : ""/);
});

test("/donnees : pas de somme des volumes (unités différentes d'une source à l'autre)", () => {
  const s = aplati("app/donnees/page.tsx");
  assert.doesNotMatch(s, /lignes ingérées/);
});

test("/donnees : les pipelines renvoient à PIPELINES, l'ADLC est créditée", () => {
  const s = aplati("app/donnees/page.tsx");
  assert.match(s, /PIPELINES/);
  assert.match(s, /Autorité de la concurrence/);
});

test("/collectivites : le « Flop 10 » ne range pas un département sans valeur", () => {
  const s = aplati("app/collectivites/page.tsx");
  assert.doesNotMatch(s, /flop10Dep = departements/);
});

test("élections : pas de « 1er tour » pour les européennes (un seul tour)", () => {
  const s = aplati("lib/queries/elections.ts");
  assert.match(s, /codeFamille === "euro"/);
});

test("Licence Ouverte : aucun lien vers l'adresse etalab.gouv.fr redirigée vers l'accueil de data.gouv.fr", async () => {
  const { readdirSync, statSync } = await import("node:fs");
  const { join } = await import("node:path");
  const racine = new URL("../src", import.meta.url).pathname;
  const fautes = [];
  const parcourir = (d) => {
    for (const n of readdirSync(d)) {
      const p = join(d, n);
      if (statSync(p).isDirectory()) parcourir(p);
      else if (/\.tsx?$/.test(p) && readFileSync(p, "utf8").includes("etalab.gouv.fr/licence-ouverte")) fautes.push(p);
    }
  };
  parcourir(racine);
  assert.deepEqual(fautes, []);
});

test("/comprendre : aucune phrase datée figée (« au 24 août 2026 », « mesuré le … »)", () => {
  const s = aplati("app/comprendre/page.tsx");
  assert.doesNotMatch(s, /en données au \d{1,2} \w+ 20\d\d/);
  assert.doesNotMatch(s, /Millésime mesuré le/);
});
