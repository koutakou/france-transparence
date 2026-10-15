// Gravité d'une alerte dans le fragment /data/alertes.json (src/lib/gravites.ts).
import { test } from "node:test";
import assert from "node:assert/strict";
import { GRAVITES_ALERTE, indiceGravite } from "../src/lib/gravites.ts";

test("une gravité hors liste retombe sur « info », jamais sur « haute »", () => {
  assert.equal(GRAVITES_ALERTE[indiceGravite("x")], "info");
  assert.equal(GRAVITES_ALERTE[indiceGravite(null)], "info");
});

test("les gravités connues gardent leur rang", () => {
  assert.deepEqual(["haute", "moyenne", "info"].map(indiceGravite), [0, 1, 2]);
});
