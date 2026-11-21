// Lobbying (lib/queries/lobbying.ts) : sans la table des groupes comptés en
// activités distinctes (base écrite par un pipeline antérieur), la page sert
// les catégories sources telles quelles, et jamais une somme de catégories
// qui compterait deux fois une activité visant les deux. Jouer : npm test.
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
  inserer(db, "lobby_agg_institutions", [
    { institution: "Agent de l'État", groupe: "Administration de l'État",
      nb_activites_total: 17748, nb_activites_12m: 6045, nb_entites: 2068 },
    { institution: "Titulaire d'un emploi à la décision du Gouvernement", groupe: "Administration de l'État",
      nb_activites_total: 17595, nb_activites_12m: 3527, nb_entites: 1736 },
  ]);
});
const { getDonneesLobbying } = await importer("lib/queries/lobbying");
const donnees = getDonneesLobbying();

test("sans table des groupes : les catégories sources, sans regroupement", () => {
  assert.equal(donnees.institutionsRegroupees, false);
  assert.deepEqual(
    donnees.institutions.map((i) => [i.groupe, i.nb_activites_total]),
    [
      ["Agent de l'État", 17748],
      ["Titulaire d'un emploi à la décision du Gouvernement", 17595],
    ],
  );
  for (const i of donnees.institutions) assert.notEqual(i.nb_activites_total, 17748 + 17595);
});
