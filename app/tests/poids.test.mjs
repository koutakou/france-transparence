// Garde du budget de poids des pages (scripts/poids-pages.mjs). Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { PLAFOND_OCTETS, controlerPoids } from "../scripts/poids-pages.mjs";

function exportFactice(fichiers) {
  const racine = fs.mkdtempSync(path.join(os.tmpdir(), "ft-poids-"));
  for (const [rel, octets] of Object.entries(fichiers)) {
    fs.mkdirSync(path.dirname(path.join(racine, rel)), { recursive: true });
    fs.writeFileSync(path.join(racine, rel), "x".repeat(octets));
  }
  return racine;
}

test("le plafond est de 500 000 octets, bornes comprises", () => {
  assert.equal(PLAFOND_OCTETS, 500_000);
  const racine = exportFactice({ "index.html": 500_000, "lobbying/index.html": 500_001 });
  const { depassements } = controlerPoids(racine);
  assert.deepEqual(depassements.map((p) => p.page), [path.join("lobbying", "index.html")]);
});

test("toute page .html compte, fiches profondes comprises", () => {
  const racine = exportFactice({ "elus/PA1/index.html": 600_000, "404.html": 10 });
  assert.equal(controlerPoids(racine).depassements.length, 1);
});

test("un fragment chargé sans geste compte avec sa page, le plus lourd retenu", () => {
  const racine = exportFactice({
    "marches/index.html": 480_000,
    "data/marches/ao-toutes/2026-10-15T14.json": 9_000,
    "data/marches/ao-toutes/2026-10-15T15.json": 25_000,
    // Chargé au clic : ne compte pas.
    "data/marches/ao.json": 236_000,
  });
  const { pages, depassements } = controlerPoids(racine);
  assert.equal(pages[0].total, 505_000);
  assert.equal(pages[0].fragment.chemin, "data/marches/ao-toutes/2026-10-15T15.json");
  assert.equal(depassements.length, 1);
});

test("un export sous le budget passe", () => {
  const racine = exportFactice({ "index.html": 220_000, "data/accueil/ao-cloture/2026-10-15T14.json": 2_000 });
  assert.equal(controlerPoids(racine).depassements.length, 0);
});
