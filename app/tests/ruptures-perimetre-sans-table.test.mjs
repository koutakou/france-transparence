// Base antérieure au contrôle des ruptures (pas de table
// budget_mensuel_ruptures) : rien n'est supposé, la lecture ne lève pas.
// Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { baseDeTest, importer } from "./outils/charger.mjs";
import { creerTables } from "./outils/schema.mjs";
import { inserer } from "./outils/fixtures.mjs";
import { BUDGET_MENSUEL } from "./fixtures/budget-mensuel-11-11-2026.mjs";

await baseDeTest((db) => {
  creerTables(db, ["meta_sources", "budget_mensuel"]);
  inserer(db, "budget_mensuel", BUDGET_MENSUEL);
});

const R = await importer("lib/queries/budget-ruptures");
const { getKpisRecettes } = await importer("lib/queries/recettes");

test("sans table : aucune rupture, aucune exception", () => {
  assert.equal(R.getRupturesBudget().size, 0);
  assert.equal(getKpisRecettes().ruptureTotal, null);
});
