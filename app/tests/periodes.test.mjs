// Périodes relatives (lib/periodes.ts) : « J-1 », « trimestre en cours »,
// mois clos, mois incomplets — dérivés des dates, jamais écrits en dur.
// Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  estVeille,
  jourParis,
  moisClos,
  premierMoisIncomplet,
} from "../src/lib/periodes.ts";

test("jourParis : 23 h 30 UTC le 14/10 est déjà le 15/10 à Paris", () => {
  assert.equal(jourParis(new Date("2026-10-14T23:30:00Z")), "2026-10-15");
  assert.equal(jourParis(new Date("2026-10-15T03:24:00Z")), "2026-10-15");
});

test("« J-1 » seulement si la donnée est datée de la veille de la construction", () => {
  const construction = new Date("2026-10-15T03:24:00Z"); // 05:24 à Paris
  // Base ingérée le 15/10/2026 : DECP (S1) datées du 15/10, donc pas « J-1 ».
  assert.equal(estVeille("2026-10-15", construction), false);
  assert.equal(estVeille("2026-10-14", construction), true);
  // Donnée en retard de cinq jours : la mention serait fausse.
  assert.equal(estVeille("2026-10-10", construction), false);
  // Construction à 00 h 30 (Paris) le 16/10, 22 h 30 UTC le 15/10.
  assert.equal(estVeille("2026-10-15", new Date("2026-10-15T22:30:00Z")), true);
  assert.equal(estVeille("illisible", construction), false);
});

test("moisClos retire le mois civil inachevé à la date de donnée", () => {
  // decp_agg_mois de la base du 15/10/2026 : 2026-10 compte 2 366 marchés
  // en 15 jours, contre 9 343 en septembre.
  const serie = [
    { mois: "2026-08", nb_marches: 9464 },
    { mois: "2026-09", nb_marches: 9343 },
    { mois: "2026-10", nb_marches: 2366 },
  ];
  assert.deepEqual(
    moisClos(serie, "2026-10-15").map((m) => m.mois),
    ["2026-08", "2026-09"],
  );
  // Le dernier jour du mois, le mois est clos.
  assert.deepEqual(
    moisClos(serie, "2026-10-31").map((m) => m.mois),
    ["2026-08", "2026-09", "2026-10"],
  );
  assert.deepEqual(moisClos(serie, "illisible"), []);
});

test("premierMoisIncomplet : un marché sur dix publié après d9 jours", () => {
  // /marches servi le 15/10/2026 : 9e décile du délai = 557 jours.
  // 15/10/2026 − 557 j = 06/04/2025 : avril 2025 finit à moins de 557 jours.
  assert.equal(premierMoisIncomplet("2026-10-15", 557), "2025-04");
  // 3e quartile = 131 jours : 15/10/2026 − 131 j = 06/06/2026.
  assert.equal(premierMoisIncomplet("2026-10-15", 131), "2026-06");
  // Limite pile sur une fin de mois : ce mois a eu tout le délai.
  // 31/03/2026 + 30 j = 30/04/2026.
  assert.equal(premierMoisIncomplet("2026-04-30", 30), "2026-04");
  assert.equal(premierMoisIncomplet("2026-04-30", 31), "2026-03");
  assert.equal(premierMoisIncomplet("illisible", 30), null);
});
