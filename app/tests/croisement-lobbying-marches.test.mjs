// Croisement lobbying × marchés (lib/queries/croisement-lobbying-marches.ts) :
// la phrase « Lecture » de /lobbying rapporte les SIREN inscrits titulaires
// d'un marché HORS accords-cadres à un dénominateur qui doit avoir le même
// périmètre. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { baseDeTest, importer } from "./outils/charger.mjs";
import { ENTITES, MARCHES, META, inserer } from "./outils/fixtures.mjs";
import { creerTables } from "./outils/schema.mjs";

await baseDeTest((db) => {
  creerTables(db, ["meta_sources", "lobby_entites", "decp_marches"]);
  inserer(db, "meta_sources", META);
  inserer(db, "lobby_entites", ENTITES);
  inserer(db, "decp_marches", MARCHES);
});
const { getCroisementLobbyingMarches } = await importer("lib/queries/croisement-lobbying-marches");
const croisement = getCroisementLobbyingMarches();

test("le numérateur : un SIREN inscrit, titulaire hors accord-cadre", () => {
  assert.equal(croisement.agregats.sirensHorsAc, 1);
});

test("le dénominateur a le périmètre du numérateur : hors AC, préfixe de 9 chiffres", () => {
  // CCI de Bourgogne et DNM ALUMINIUM. Ni AGRIRAM (accord-cadre seul), ni
  // « 00001 », ni « 391 902 0… » (préfixes qui ne sont pas des SIREN).
  // L'ancienne requête comptait les cinq.
  assert.equal(croisement.ensemble.sirensTitulairesHorsAc, 2);
});

test("l'export garde sirensTitulaires avec son sens d'origine", () => {
  // Toutes techniques, tout préfixe : les cinq titulaires de la fixture.
  assert.equal(croisement.ensemble.sirensTitulaires, 5);
});

test("le numérateur est inclus dans le dénominateur", () => {
  assert.ok(croisement.agregats.sirensHorsAc <= croisement.ensemble.sirensTitulairesHorsAc);
});
