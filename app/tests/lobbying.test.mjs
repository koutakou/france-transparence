// Lobbying (lib/queries/lobbying.ts) : « N entités ont déclaré une
// fourchette, sur M » — lobby_agg_budgets ne compte que les entités
// ACTIVES ; le total doit avoir le même périmètre. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { baseDeTest, importer } from "./outils/charger.mjs";
import { ENTITES, META, inserer } from "./outils/fixtures.mjs";
import { creerTables } from "./outils/schema.mjs";

await baseDeTest((db) => {
  creerTables(db, [
    "meta_sources",
    "lobby_entites",
    "lobby_activites",
    "lobby_agg_institutions",
    "lobby_agg_top_entites",
    "lobby_agg_budgets",
    "lobby_agg_trimestres",
    "lobby_agg_ministeres",
    "alertes",
  ]);
  inserer(db, "meta_sources", META);
  inserer(db, "lobby_entites", ENTITES);
  // Agrégat tel que le pipeline le calcule sur ces trois entités : seule la
  // CCI (active, « < 10 000 € ») y entre ; l'entité 52, cessée, en est
  // exclue malgré sa fourchette ; SUNROCK n'en déclare pas.
  inserer(db, "lobby_agg_budgets", [
    { fourchette: "< 10 000 €", borne_min: 0, borne_max: 10000, nb_entites: 1 },
  ]);
});
const { getDonneesLobbying } = await importer("lib/queries/lobbying");
const donnees = getDonneesLobbying();

test("fourchettes déclarées : actives sur actives, les cessées hors des deux côtés", () => {
  assert.deepEqual(donnees.budgetsCouverture, { dansFourchettes: 1, totalActives: 2 });
});
