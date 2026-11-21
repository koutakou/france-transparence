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
    "lobby_agg_groupes_institutions",
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
  // Valeurs de la base du 21/11/2026 (catégories) et du calcul distinct du
  // pipeline sur l'export AGORA du même jour (groupe).
  inserer(db, "lobby_agg_institutions", [
    { institution: "Agent de l'État", groupe: "Administration de l'État",
      nb_activites_total: 17748, nb_activites_12m: 6045, nb_entites: 2068 },
    { institution: "Titulaire d'un emploi à la décision du Gouvernement", groupe: "Administration de l'État",
      nb_activites_total: 17595, nb_activites_12m: 3527, nb_entites: 1736 },
  ]);
  inserer(db, "lobby_agg_groupes_institutions", [
    { groupe: "Administration de l'État", nb_activites_total: 31081, nb_activites_12m: 8176, nb_entites: 2522 },
  ]);
  inserer(db, "lobby_agg_budgets", [
    { fourchette: "< 10 000 €", borne_min: 0, borne_max: 10000, nb_entites: 1 },
  ]);
});
const { getDonneesLobbying } = await importer("lib/queries/lobbying");
const donnees = getDonneesLobbying();

test("fourchettes déclarées : actives sur actives, les cessées hors des deux côtés", () => {
  assert.deepEqual(donnees.budgetsCouverture, { dansFourchettes: 1, totalActives: 2 });
});

test("institutions visées : un groupe compte ses activités distinctes, jamais la somme de ses catégories", () => {
  // Audit du 21/11/2026 : « Administration de l'État 35 343 » = 17 748 + 17 595.
  assert.equal(donnees.institutionsRegroupees, true);
  assert.deepEqual(donnees.institutions, [
    { groupe: "Administration de l'État", nb_activites_total: 31081, nb_activites_12m: 8176 },
  ]);
  assert.equal(donnees.institutionsDetail.length, 2);
});
