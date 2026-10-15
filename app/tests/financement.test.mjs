// Financement (lib/queries/financement.ts) : les phrases de /financement qui
// comparent l'aide déclarée aux enveloppes des décrets se dérivent des
// données en base. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import Database from "better-sqlite3";
import { importer } from "./outils/charger.mjs";

const { exercicesSansDecret, sensEcartEnveloppe, SQL_TOP_PRODUITS, SQL_NB_SANS_PRODUITS } =
  await importer("lib/queries/financement");

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

// Classement « Partis par produits » : un compte sans produits publiés
// devenait une barre à 0 € (`produits_total ?? 0` dans la page). Lignes
// réelles de v_partis_top_produits (base du 15/10/2026, exercice 2024) ; la
// base du jour n'a AUCUN produits_total NULL (575 sur 575 chiffrés) : la
// quatrième ligne est celle de RENAISSANCE, produits mis à NULL pour le cas.
function baseProduits() {
  const db = new Database(":memory:");
  db.exec(`CREATE TABLE v_partis_top_produits (parti_id TEXT, nom TEXT, sigle TEXT,
    exercice INTEGER, produits_total REAL, aide_publique REAL, dons REAL, cotisations REAL)`);
  const ins = db.prepare("INSERT INTO v_partis_top_produits VALUES (?, ?, ?, ?, ?, ?, ?, ?)");
  // Ordre de la vue : produits_total DESC, NULL en dernier.
  ins.run("PARTI-60", "PARTI COMMUNISTE FRANÇAIS", null, 2024, 31609023.7, 2176418.51, 5648087.3, 11794033.58);
  ins.run("PARTI-910", "RENAISSANCE", null, 2024, 19487435.0, 9533.0, 1848379.0, 795647.0);
  ins.run("PARTI-340", "LA DROITE POPULAIRE - LA FRANCE EN TÊTE", null, 2024, 0.0, 0.0, 0.0, 0.0);
  ins.run("PARTI-910-NULL", "RENAISSANCE", null, 2024, null, 9533.0, 1848379.0, 795647.0);
  return db;
}

test("un compte sans produits publiés n'est pas classé par produits, il est compté", () => {
  const db = baseProduits();
  const top = db.prepare(SQL_TOP_PRODUITS).all();
  assert.deepEqual(top.map((l) => l.parti_id), ["PARTI-60", "PARTI-910", "PARTI-340"]);
  assert.ok(top.every((l) => typeof l.produits_total === "number"));
  assert.equal(db.prepare(SQL_NB_SANS_PRODUITS).get().nb, 1);
});

test("un vrai zéro publié reste classé (manquant ≠ zéro, et zéro ≠ manquant)", () => {
  const top = baseProduits().prepare(SQL_TOP_PRODUITS).all();
  assert.equal(top.find((l) => l.parti_id === "PARTI-340").produits_total, 0);
});
