// Budget vert (lib/budget-vert.ts, lib/queries/depenses.ts) : les crédits
// par mission du PLF 2026 sont ceux du périmètre des dépenses de l'État
// (PDE) retenu par la notice du jeu, et les deux prélèvements sur recettes
// (PSRCT, PSRUE) ne sont ni classés ni additionnés comme des missions.
// Audit du 21/11/2026 : « PSRCT 49,5 Md€ » au rang 4 du top 10 de /depenses,
// et « total toutes missions : 479,5 Md€ » sur l'accueil, prélèvements
// compris. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { baseDeTest, importer } from "./outils/charger.mjs";
import { inserer } from "./outils/fixtures.mjs";
import { creerTables } from "./outils/schema.mjs";

const ETIQUETTE = "PLF 2026 déposé le 14/10/2025";

// Sommes RÉELLES par mission de la base du 21/11/2026 (crédits budgétaires),
// une ligne par mission, plus une dépense fiscale qui ne doit compter nulle part.
function ligne(type_depense, mission, exec, lfi, plf) {
  return {
    type_depense,
    mission,
    execution_2024_cp: exec,
    lfi_2025_cp: lfi,
    plf_2026_cp: plf,
    etiquette_2026: ETIQUETTE,
  };
}
const CB = "Crédits budgétaires";
const LIGNES = [
  ligne(CB, "Pensions", 66534249612, 68089854053, 68156628203),
  ligne(CB, "Enseignement scolaire", 64044890102, 64268845315, 64484505460),
  ligne(CB, "Défense", 47838437501, 50478179466, 57149258489),
  ligne(CB, "PSRCT", 50667966634, 50415579140, 49514696624),
  ligne(CB, "PSRUE", 22276393818, 23098097974, 28781025011),
  ligne("Dépenses fiscales", "Défense", null, null, 126000000),
];

await baseDeTest((db) => {
  creerTables(db, ["budget_vert"]);
  inserer(db, "budget_vert", LIGNES);
});
const { getMissionsPlf2026 } = await importer("lib/queries/depenses");
const { PERIMETRE_BUDGET_VERT, SQL_MISSIONS_SEULES, SQL_PRELEVEMENTS_SEULS } =
  await importer("lib/budget-vert");
const { PRELEVEMENTS_SUR_RECETTES } = await importer("lib/queries/accueil");

test("/depenses : le top des missions ne classe aucun prélèvement sur recettes", () => {
  const m = getMissionsPlf2026(10);
  assert.deepEqual(
    m.missions.map((x) => x.mission),
    ["Pensions", "Enseignement scolaire", "Défense"],
  );
});

test("/depenses : le total des missions exclut les prélèvements et les dépenses fiscales", () => {
  const m = getMissionsPlf2026(10);
  assert.equal(m.totalMissionsPlf2026Cp, 68156628203 + 64484505460 + 57149258489);
});

test("/depenses : les prélèvements sont servis à part, sous leur nom complet", () => {
  const m = getMissionsPlf2026(10);
  assert.deepEqual(
    m.prelevements.map((p) => [p.mission, p.plf2026Cp, p.lfi2025Cp]),
    [
      ["Prélèvements sur recettes au profit des collectivités territoriales", 49514696624, 50415579140],
      ["Prélèvements sur recettes au profit de l’Union européenne", 28781025011, 23098097974],
    ],
  );
  for (const p of m.prelevements) assert.doesNotMatch(p.mission, /^PSR/);
});

test("accueil et /depenses écartent la même liste de prélèvements", () => {
  assert.deepEqual([...PRELEVEMENTS_SUR_RECETTES], ["PSRCT", "PSRUE"]);
  assert.match(SQL_MISSIONS_SEULES, /^mission NOT IN \('PSRCT', 'PSRUE'\)$/);
  assert.match(SQL_PRELEVEMENTS_SEULS, /^mission IN \('PSRCT', 'PSRUE'\)$/);
});

test("le périmètre servi est celui que dit la notice, sans total du PLF", () => {
  assert.match(PERIMETRE_BUDGET_VERT, /périmètre des dépenses de l’État \(PDE\)/);
  assert.match(PERIMETRE_BUDGET_VERT, /pas l’ensemble des crédits du PLF/);
});

test("accueil et /depenses disent le périmètre, et plus aucun « total toutes missions »", () => {
  for (const page of ["app/page.tsx", "app/depenses/page.tsx"]) {
    const source = readFileSync(new URL(`../src/${page}`, import.meta.url), "utf8");
    assert.match(source, /PERIMETRE_BUDGET_VERT/, page);
    assert.doesNotMatch(source.replace(/\s+/g, " "), /total toutes missions/, page);
  }
});

test("accueil : la carte par ministère (823 Md€) dit « tous budgets », comme /depenses", () => {
  // Audit du 21/11/2026 : 229,0 Md€ (27,8 %) hors budget général, sans le dire.
  const source = readFileSync(new URL("../src/app/page.tsx", import.meta.url), "utf8");
  const carte = source.slice(source.indexOf('titre="Budget par ministère'));
  const bloc = carte.slice(0, carte.indexOf("</Card>")).replace(/\s+/g, " ");
  assert.match(bloc, /Crédits de paiement BRUTS tous budgets \(budget général, budgets annexes et comptes spéciaux\)/);
  assert.match(bloc, /inclut budgets annexes et comptes spéciaux/);
  assert.match(source, /entete: "CP tous budgets \(Md€\)"/);
});
