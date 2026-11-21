// Décomposition des montants suspects de /marches (lib/queries/marches.ts) :
// une classe vide vaut 0 €, jamais « n.d. », une classe non vide dont aucune
// part n'est connue reste NULL (« n.d. »). Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import Database from "better-sqlite3";
import { baseDeTest, importer } from "./outils/charger.mjs";
import { SCHEMA, creerTables } from "./outils/schema.mjs";

const chemin = await baseDeTest((db) => {
  creerTables(db, ["decp_marches"]);
  const ins = db.prepare(
    "INSERT INTO decp_marches (uid, objet, montant_retenu, montant_suspect, montant_anomalie, date_notification) VALUES (?, ?, ?, ?, ?, ?)",
  );
  ins.run("m1", "Travaux de voirie", 120000, 0, null, "2026-10-01");
  ins.run("m2", "Maximum d'accord-cadre", 150000000, 1, null, "2026-10-02");
  ins.run("m3", "Montant signalé par la source, non retenu", null, 1, "suspect", "2026-10-03");
});
const { SQL_DECOMPOSITION_SUSPECTS, ancresFenetre } = await importer("lib/queries/marches");

test("une classe de suspects vide vaut 0 €, une classe remplie garde sa somme ou reste NULL", () => {
  const db = new Database(chemin, { readonly: true });
  try {
    const l = db.prepare(SQL_DECOMPOSITION_SUSPECTS).get({ plafond: 100000000, jour: "2026-11-20", decalage: "+0 day" });
    assert.equal(l.nb_fenetre, 3);
    assert.equal(l.nb_aberrants, 0);
    assert.equal(l.montant_aberrants, 0, "aucun aberrant : 0 €, pas NULL");
    assert.equal(l.nb_suspects_source, 1);
    assert.equal(l.montant_suspects_source, null, "un suspect sans part connue : NULL (« n.d. »), pas 0 €");
    assert.equal(l.nb_hors_plafond, 1);
    assert.equal(l.montant_hors_plafond, 100000000, "le marché hors plafond compte pour le plafond");
  } finally {
    db.close();
  }
});

test("fenêtre 12 mois : la date des données d'abord, le jour d'ingestion ensuite", () => {
  // Base du 21/11/2026 : données au 20/11, ingestion le 21/11 à 04:21 UTC.
  // Ancrée à l'ingestion, la fenêtre perdait les 1 118 marchés du 21/11/2025.
  const s1 = { date_donnees: "2026-11-20", date_ingestion: "2026-11-21T04:21:14+00:00" };
  assert.deepEqual(ancresFenetre(s1), [
    { jour: "2026-11-20", decalage: "+0 day" },
    { jour: "2026-11-21", decalage: "+0 day" },
    { jour: "2026-11-21", decalage: "-1 day" },
    { jour: "2026-11-21", decalage: "+1 day" },
  ]);
  const db = new Database(":memory:");
  try {
    db.exec(SCHEMA.decp_marches);
    db.prepare(
      "INSERT INTO decp_marches (uid, objet, montant_retenu, montant_suspect, montant_anomalie, date_notification) VALUES (?, ?, ?, ?, ?, ?)",
    ).run("m0", "Premier jour de la fenêtre", 1000, 0, null, "2025-11-21");
    const [donnees, ingestion] = ancresFenetre(s1);
    const n = (a) => db.prepare(SQL_DECOMPOSITION_SUSPECTS).get({ plafond: 100000000, ...a }).nb_fenetre;
    assert.equal(n(donnees), 1);
    assert.equal(n(ingestion), 0);
  } finally {
    db.close();
  }
});
