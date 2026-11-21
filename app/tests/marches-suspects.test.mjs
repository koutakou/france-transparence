// Décomposition des montants suspects de /marches (lib/queries/marches.ts) :
// une classe vide vaut 0 €, jamais « n.d. ». Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import Database from "better-sqlite3";
import { baseDeTest, importer } from "./outils/charger.mjs";
import { creerTables } from "./outils/schema.mjs";

const chemin = await baseDeTest((db) => {
  creerTables(db, ["decp_marches"]);
  const ins = db.prepare(
    "INSERT INTO decp_marches (uid, objet, montant_retenu, montant_suspect, montant_anomalie, date_notification) VALUES (?, ?, ?, ?, ?, ?)",
  );
  ins.run("m1", "Travaux de voirie", 120000, 0, null, "2026-10-01");
  ins.run("m2", "Maximum d'accord-cadre", 150000000, 1, null, "2026-10-02");
});
const { SQL_DECOMPOSITION_SUSPECTS } = await importer("lib/queries/marches");

test("une classe de suspects vide vaut 0 €, la classe remplie garde sa somme écrêtée", () => {
  const db = new Database(chemin, { readonly: true });
  try {
    const l = db.prepare(SQL_DECOMPOSITION_SUSPECTS).get({ plafond: 100000000, jour: "2026-11-20", decalage: "+0 day" });
    assert.equal(l.nb_fenetre, 2);
    assert.equal(l.nb_aberrants, 0);
    assert.equal(l.montant_aberrants, 0, "aucun aberrant : 0 €, pas NULL");
    assert.equal(l.nb_suspects_source, 0);
    assert.equal(l.montant_suspects_source, 0, "aucun suspect signalé par la source : 0 €, pas NULL");
    assert.equal(l.nb_hors_plafond, 1);
    assert.equal(l.montant_hors_plafond, 100000000, "le marché hors plafond compte pour le plafond");
  } finally {
    db.close();
  }
});
