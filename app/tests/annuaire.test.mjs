// Sections de /elus/annuaire/ (src/lib/annuaire.ts), jouées sur une base en
// mémoire. Lignes réelles de la base du 15/10/2026 (elus.mandats recopié tel
// quel) : Gabriel Amard, sénateur, garde dans le JSON le mandat de député
// que le RNE trimestriel n'a pas retiré ; la table `deputes` (AMO10) ne le
// liste plus. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import Database from "better-sqlite3";
import { SQL_SECTIONS_ANNUAIRE } from "../src/lib/annuaire.ts";

function base() {
  const db = new Database(":memory:");
  db.exec(`
    CREATE TABLE elus (id TEXT PRIMARY KEY, nom TEXT, prenom TEXT, uid_an TEXT,
                       matricule_senat TEXT, mandats TEXT);
    CREATE TABLE deputes (uid_an TEXT PRIMARY KEY);
    CREATE TABLE senateurs (matricule TEXT PRIMARY KEY);
  `);
  const elu = db.prepare("INSERT INTO elus VALUES (?, ?, ?, ?, ?, ?)");
  elu.run("SEN-20684B", "Amard", "Gabriel", null, "20684B", JSON.stringify([
    { type: "senateur", date_debut: null, date_fin: null, departement: "Rhône", groupe: "NI", source: "SENAT-P9" },
    { source: "RNE", type: "depute", departement: "69", circonscription: "6Ème Circonscription", date_debut_mandat: "2024-07-08" },
  ]));
  elu.run("PA721908", "Braun-Pivet", "Yaël", "PA721908", null, JSON.stringify([
    { type: "depute", legislature: 17, date_debut: "2024-07-07", date_fin: null, departement: "Yvelines", circonscription: "5", groupe: "EPR", source: "AN-P9" },
    { source: "RNE", type: "depute", departement: "78", circonscription: "5Ème Circonscription", date_debut_mandat: "2024-07-08" },
  ]));
  elu.run("SEN-17305A", "Le Mèner", "Dominique", null, "17305A", JSON.stringify([
    { type: "senateur", date_debut: null, date_fin: null, departement: "Sarthe", groupe: "Les Républicains", source: "SENAT-P9" },
    { source: "RNE", type: "president_conseil_departemental", departement: "72", libelle: "Sarthe", fonction: "Président du conseil départemental", date_debut_mandat: "2021-07-01", date_debut_fonction: "2021-07-01" },
  ]));
  db.prepare("INSERT INTO deputes VALUES (?)").run("PA721908");
  db.prepare("INSERT INTO senateurs VALUES (?)").run("20684B");
  db.prepare("INSERT INTO senateurs VALUES (?)").run("17305A");
  return db;
}

const sections = (db) => {
  const parId = {};
  for (const l of db.prepare(SQL_SECTIONS_ANNUAIRE).all()) (parId[l.id] ??= []).push(l.type);
  for (const id in parId) parId[id].sort();
  return parId;
};

test("un sénateur que le JSON dit encore député n'est rangé que parmi les sénateurs", () => {
  assert.deepEqual(sections(base())["SEN-20684B"], ["senateur"]);
});

test("un député de la table deputes est rangé parmi les députés, une seule fois", () => {
  assert.deepEqual(sections(base())["PA721908"], ["depute"]);
});

test("les exécutifs CD/CR restent lus dans le JSON des mandats", () => {
  assert.deepEqual(sections(base())["SEN-17305A"], ["president_conseil_departemental", "senateur"]);
});
