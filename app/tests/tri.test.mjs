// Ordre alphabétique des listes de parlementaires (src/lib/tri.ts). Noms
// réels des tables deputes et senateurs (base du 15/10/2026).
import { test } from "node:test";
import assert from "node:assert/strict";
import { comparerNomPrenom } from "../src/lib/tri.ts";

const trier = (noms) => noms.map((nom) => ({ nom, prenom: null })).sort(comparerNomPrenom).map((l) => l.nom);

test("particule en minuscule : rangée à sa lettre, pas après Y", () => {
  assert.deepEqual(trier(["Youssouffa", "de Courson", "Delannoy", "Courbon", "Davi"]), [
    "Courbon",
    "Davi",
    "de Courson",
    "Delannoy",
    "Youssouffa",
  ]);
});

test("initiale accentuée : « Éblé » à la lettre E, pas après Z", () => {
  assert.deepEqual(trier(["Ziane", "Éblé", "Estrosi Sassone"]), ["Éblé", "Estrosi Sassone", "Ziane"]);
});

test("à nom égal, le prénom départage", () => {
  const l = [
    { nom: "Martin", prenom: "Patrice" },
    { nom: "Martin", prenom: "Élisa" },
  ].sort(comparerNomPrenom);
  assert.deepEqual(l.map((x) => x.prenom), ["Élisa", "Patrice"]);
});
