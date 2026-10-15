// Date de comparaison N−1 de l'accueil (src/lib/dates.ts). Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { finDeMoisAnneePrecedente } from "../src/lib/dates.ts";

test("après un 29 février, N−1 est le 28 février", () => {
  assert.equal(finDeMoisAnneePrecedente("2028-02-29"), "2027-02-28");
});

test("un 28 février précédant une année bissextile mène au 29", () => {
  assert.equal(finDeMoisAnneePrecedente("2029-02-28"), "2028-02-29");
});

test("fin de mois ordinaire", () => {
  assert.equal(finDeMoisAnneePrecedente("2026-06-30"), "2025-06-30");
  assert.equal(finDeMoisAnneePrecedente("2026-12-31"), "2025-12-31");
});
