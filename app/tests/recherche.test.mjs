// Recherche globale (src/lib/recherche.ts) : des élus et entités existants
// restaient introuvables (tirets, ordre « nom prénom », espaces doubles,
// apostrophe typographique). Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { plie, preparerIndex, rechercher } from "../src/lib/recherche.ts";

// Graphies et identifiants réels de la base (ingestion du 15/10/2026).
const INDEX = preparerIndex({
  typesMandat: ["Député·e", "Sénateur·rice", "", "", "", "Maire"],
  departements: ["Charente-Maritime"],
  elus: [
    ["Bernadeau", "Marie-Sophie", 0, -1, "PA793924"],
    ["Braun-Pivet", "Yaël", 0, -1, "PA721908"],
    ["CARPENTIER", "Ingrid", 5, 0],
    ["Le Pen", "Marine", 0, -1, "PA720614"],
  ],
  typesEntite: ["Ministère"],
  hrefs: ["/depenses"],
  entites: [
    ["Ministère de l’Économie, des Finances et de la Souveraineté industrielle, énergétique et numérique", "", 0, 0],
  ],
});

const libelles = (q) => rechercher(INDEX, q).map((r) => r.libelle);

test("plie : accents, casse, tirets, apostrophes, espaces", () => {
  assert.equal(plie("  Marie-Sophie   BERNADEAU "), "marie sophie bernadeau");
  assert.equal(plie("l’Économie"), "l'economie");
});

test("noms composés, ordre « nom prénom », espaces doubles", () => {
  assert.deepEqual(libelles("marie sophie bernadeau"), ["Marie-Sophie Bernadeau"]);
  assert.deepEqual(libelles("braun pivet"), ["Yaël Braun-Pivet"]);
  assert.deepEqual(libelles("le pen marine"), ["Marine Le Pen"]);
  assert.deepEqual(libelles("marine  le pen"), ["Marine Le Pen"]);
  assert.deepEqual(libelles("Braun-Pivet"), ["Yaël Braun-Pivet"]);
});

test("une requête d'un mot garde son comportement (sous-chaîne)", () => {
  // Parlementaire d'abord, puis l'ordre de l'index.
  assert.deepEqual(libelles("pen"), ["Marine Le Pen", "Ingrid CARPENTIER"]);
});

test("entité écrite avec une apostrophe typographique", () => {
  const r = rechercher(INDEX, "ministere de l'economie");
  assert.equal(r.length, 1);
  assert.equal(r[0].type, "Ministère");
});

test("en deçà de 2 caractères, rien", () => {
  assert.deepEqual(rechercher(INDEX, " a "), []);
});
