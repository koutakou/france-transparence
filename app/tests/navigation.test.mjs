// Onglet courant de la navigation (src/lib/navigation.ts). Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { estActif } from "../src/lib/navigation.ts";

test("/donnees-personnelles n'active pas l'onglet Données", () => {
  assert.equal(estActif("/donnees", "/donnees-personnelles/"), false);
  assert.equal(estActif("/donnees", "/donnees-personnelles"), false);
});

test("page et sous-pages activent leur onglet", () => {
  assert.equal(estActif("/donnees", "/donnees/"), true);
  assert.equal(estActif("/donnees", "/donnees"), true);
  assert.equal(estActif("/depenses", "/depenses/destination/"), true);
  assert.equal(estActif("/elus", "/elus/PA720614/"), true);
});

test("l'accueil n'est courant que sur /", () => {
  assert.equal(estActif("/", "/"), true);
  assert.equal(estActif("/", "/marches/"), false);
});
