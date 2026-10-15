// Accord en nombre des phrases à compte (src/lib/phrases.ts). Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { phraseMarchesSansMontant } from "../src/lib/phrases.ts";

test("zéro marché : « Aucun marché », jamais « 0 marchés sont »", () => {
  assert.equal(phraseMarchesSansMontant(0, "0"), "Aucun marché n’est notifié sans montant renseigné.");
});

test("singulier et pluriel accordés", () => {
  assert.match(phraseMarchesSansMontant(1, "1"), /^1 marché est notifié .* compté .* exclu /);
  assert.match(phraseMarchesSansMontant(12, "12"), /^12 marchés sont notifiés .* comptés .* exclus /);
});
