// Ruptures de périmètre S13 (lib/queries/budget-ruptures.ts et ses lecteurs),
// jouées sur une base jetable remplie de lignes RÉELLES de la base du
// 11/11/2026 : la cellule « Total recettes nettes du budget général » du
// 30/09/2026 vaut fiscales + non fiscales − prélèvements sur recettes + fonds
// de concours, quand les 164 autres mois valent fiscales + non fiscales.
// Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { baseDeTest, importer } from "./outils/charger.mjs";
import { creerTables } from "./outils/schema.mjs";
import { inserer } from "./outils/fixtures.mjs";
import { BUDGET_MENSUEL, BUDGET_RUPTURES } from "./fixtures/budget-mensuel-11-11-2026.mjs";

await baseDeTest((db) => {
  creerTables(db, ["meta_sources", "budget_mensuel", "budget_mensuel_ruptures"]);
  inserer(db, "budget_mensuel", BUDGET_MENSUEL);
  inserer(db, "budget_mensuel_ruptures", BUDGET_RUPTURES);
});

const R = await importer("lib/queries/budget-ruptures");
const { getKpisRecettes, getSerieRecettesNettes } = await importer("lib/queries/recettes");
const { getKpisBudgetMensuel } = await importer("lib/queries/depenses");

const NETTES = "recettes/budget-general/total-recettes-nettes-du-budget-general";
const FISCALES = "recettes/budget-general/total-recettes-fiscales";
const DEPENSES = "depenses/budget-general/total-depenses-nettes-du-budget-general";

test("la rupture lue en base interdit la comparaison des deux côtés", () => {
  const ruptures = R.getRupturesBudget();
  assert.equal(ruptures.size, 1);
  assert.equal(R.comparaisonRompue(ruptures, NETTES, 2026, 9)?.cote, "mois");
  assert.equal(R.comparaisonRompue(ruptures, NETTES, 2027, 9)?.cote, "n1");
  assert.equal(R.comparaisonRompue(ruptures, NETTES, 2026, 8), null);
  assert.equal(R.comparaisonRompue(ruptures, FISCALES, 2026, 9), null);
});

test("la borne dit la définition constatée, ou la date de N−1", () => {
  const ruptures = R.getRupturesBudget();
  const ici = R.bornePerimetreRompu(R.comparaisonRompue(ruptures, NETTES, 2026, 9));
  assert.match(ici, /prélèvements sur recettes \+ fonds de concours/);
  assert.match(ici, /les autres mois : recettes fiscales \+ non fiscales/);
  assert.match(ici, /variation non calculée/);
  const apres = R.bornePerimetreRompu(R.comparaisonRompue(ruptures, NETTES, 2027, 9));
  assert.match(apres, /30\/09\/2026/);
});

test("/recettes : le total garde sa valeur publiée mais perd sa variation", () => {
  const k = getKpisRecettes();
  assert.equal(k.dateFinMois, "2026-09-30");
  assert.equal(k.totalNettes, 219136720375.64);       // jamais rectifié
  assert.equal(k.ruptureTotal?.cote, "mois");
  assert.equal(k.ruptureFiscales, null);               // les fiscales se comparent
});

test("/recettes : la cellule sort de la courbe et y est nommée", () => {
  const s = getSerieRecettesNettes(2);
  const a2026 = s.annees.find((a) => a.annee === 2026);
  assert.equal(a2026.valeurs[8], null);                // septembre retiré
  assert.equal(a2026.valeurs[7], 224863110362.91);     // août conservé
  assert.deepEqual(s.omises.map((o) => [o.annee, o.mois]), [[2026, 9]]);
  assert.equal(s.omises[0].rupture.montantPublie, 219136720375.64);
});

test("/depenses : la tuile des recettes est rompue, pas celle des dépenses", () => {
  const k = getKpisBudgetMensuel();
  assert.equal(k.ruptureRecettes?.cote, "mois");
  assert.equal(k.ruptureDepenses, null);
});

test("API : chaque ligne porte rupture_perimetre, sans toucher aux valeurs", () => {
  const ruptures = R.getRupturesBudget();
  const annotees = R.annoterRuptures(BUDGET_MENSUEL, ruptures);
  assert.equal(annotees.length, BUDGET_MENSUEL.length);
  assert.ok(annotees.every((l) => "rupture_perimetre" in l));
  const sept = annotees.find((l) => l.ligne_id === NETTES && l.date_fin_mois === "2026-09-30");
  assert.equal(sept.montant_cumul, 219136720375.64);
  assert.equal(sept.montant_cumul_n1, 258486937909.18);
  assert.deepEqual(sept.rupture_perimetre, {
    cote: "mois",
    date_fin_mois: "2026-09-30",
    identite: "recettes fiscales + non fiscales",
    definition_constatee:
      "recettes fiscales + non fiscales − prélèvements sur recettes + fonds de concours",
    comparable_n1: false,
  });
  const marquees = annotees.filter((l) => l.rupture_perimetre !== null);
  assert.equal(marquees.length, 1);
});
