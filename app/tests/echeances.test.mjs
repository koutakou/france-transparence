// Appels d'offres « proches de la clôture » (lib/echeances.ts) : la page est
// construite vers 05 h 20 et servie toute la journée ; une échéance passée à
// l'heure du visiteur ne s'affiche plus. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  AO_ACCUEIL_AFFICHEES,
  AO_ACCUEIL_LIVREES,
  AO_AFFICHEES,
  AO_LIVREES,
  echeancesOuvertes,
} from "../src/lib/echeances.ts";

// Les quatre échéances de l'accueil servi le 15/10/2026, relevé à 12:26 UTC
// (« Clôture le 15/10 06:00 — CHU de la Réunion », puis trois à 10:00, heure
// de Paris, dont les avis CCAS de Gennevilliers 26-89918 et 26-89459), suivies
// des premières échéances de la base ingérée le même jour (idweb réels).
const LIGNES = [
  { id: "CHU de la Réunion", limite: "2026-10-15T04:00:00+00:00" },
  { id: "26-89918", limite: "2026-10-15T08:00:00+00:00" },
  { id: "26-89459", limite: "2026-10-15T08:00:00+00:00" },
  { id: "Ville de Cachan", limite: "2026-10-15T08:00:00+00:00" },
  { id: "26-90054", limite: "2026-10-15T13:00:00+00:00" },
  { id: "26-89099", limite: "2026-10-15T13:30:00+00:00" },
  { id: "26-94428", limite: "2026-10-15T14:00:00+00:00" },
];
const limite = (l) => l.limite;

test("à 14 h 26 (Paris), les échéances de 06:00 et de 10:00 ne sont plus affichées", () => {
  const releve = Date.parse("2026-10-15T12:26:00Z");
  const ids = echeancesOuvertes(LIGNES, limite, releve, 4).map((l) => l.id);
  assert.deepEqual(ids, ["26-90054", "26-89099", "26-94428"]);
});

test("à l'heure de la construction, la liste est celle de la construction", () => {
  const construction = Date.parse("2026-10-15T03:24:00Z");
  const ids = echeancesOuvertes(LIGNES, limite, construction, 4).map((l) => l.id);
  assert.deepEqual(ids, ["CHU de la Réunion", "26-89918", "26-89459", "Ville de Cachan"]);
});

test("une échéance à la minute exacte est close ; une date illisible n'est pas ouverte", () => {
  const t = Date.parse("2026-10-15T13:00:00Z");
  const lignes = [
    { id: "26-90054", limite: "2026-10-15T13:00:00+00:00" },
    { id: "illisible", limite: "?" },
  ];
  assert.deepEqual(echeancesOuvertes(lignes, limite, t, 4), []);
});

test("la construction livre plus de lignes qu'elle n'en affiche", () => {
  assert.ok(AO_LIVREES > AO_AFFICHEES);
  assert.ok(AO_ACCUEIL_LIVREES > AO_ACCUEIL_AFFICHEES);
});
