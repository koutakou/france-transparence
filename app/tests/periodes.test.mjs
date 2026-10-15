// Périodes relatives (lib/periodes.ts) : « J-1 », « trimestre en cours »,
// mois clos, mois incomplets — dérivés des dates, jamais écrits en dur.
// Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { estVeille, jourParis } from "../src/lib/periodes.ts";

test("jourParis : 23 h 30 UTC le 14/10 est déjà le 15/10 à Paris", () => {
  assert.equal(jourParis(new Date("2026-10-14T23:30:00Z")), "2026-10-15");
  assert.equal(jourParis(new Date("2026-10-15T03:24:00Z")), "2026-10-15");
});

test("« J-1 » seulement si la donnée est datée de la veille de la construction", () => {
  const construction = new Date("2026-10-15T03:24:00Z"); // 05:24 à Paris
  // Base ingérée le 15/10/2026 : DECP (S1) datées du 15/10, donc pas « J-1 ».
  assert.equal(estVeille("2026-10-15", construction), false);
  assert.equal(estVeille("2026-10-14", construction), true);
  // Donnée en retard de cinq jours : la mention serait fausse.
  assert.equal(estVeille("2026-10-10", construction), false);
  // Construction à 00 h 30 (Paris) le 16/10, 22 h 30 UTC le 15/10.
  assert.equal(estVeille("2026-10-15", new Date("2026-10-15T22:30:00Z")), true);
  assert.equal(estVeille("illisible", construction), false);
});
