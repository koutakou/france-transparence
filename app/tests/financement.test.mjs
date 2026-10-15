// Financement (lib/queries/financement.ts) : les phrases de /financement qui
// comparent l'aide déclarée aux enveloppes des décrets se dérivent des
// données en base. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { importer } from "./outils/charger.mjs";

const { exercicesSansDecret, sensEcartEnveloppe } = await importer("lib/queries/financement");

// Base du 15/10/2026 : aide déclarée 2024 (fractions 1 + 2) 70 275 372,28 €,
// enveloppe du décret n° 2024-77 66 438 848,34 €.
test("2024 : les déclarations dépassent l'enveloppe", () => {
  assert.equal(sensEcartEnveloppe(70_275_372.28 - 66_438_848.34), "dessus");
});

test("le verbe suit le signe de l'écart, au centime", () => {
  assert.equal(sensEcartEnveloppe(-1_000), "dessous");
  assert.equal(sensEcartEnveloppe(0.004), "egal");
  assert.equal(sensEcartEnveloppe(-0.004), "egal");
});

test("exercices déclarés sans décret en base : 2021, 2022, 2023", () => {
  // v_partis_aide_publique_evolution : 2021 → 2024 ; partis_aide_annuelle :
  // décrets 2024 et 2026 seulement (série volontairement trouée).
  const aides = [2021, 2022, 2023, 2024].map((exercice) => ({ exercice }));
  const decrets = [2024, 2026].map((annee) => ({ annee }));
  assert.deepEqual(exercicesSansDecret(aides, decrets), [2021, 2022, 2023]);
  assert.deepEqual(exercicesSansDecret(aides, [2021, 2022, 2023, 2024].map((annee) => ({ annee }))), []);
});
