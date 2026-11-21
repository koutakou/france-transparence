// Ligne de compte de la liste /alertes : la synthèse des défauts de lobbying
// est listée mais nommée à part, pour que la liste dise le même nombre
// d'alertes que la tuile « Alertes au total » (relecture de la PR 171).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { libelleCompteAlertes } from "../src/lib/alertes-compte.ts";

test("280 lignes dont 1 synthèse : la liste dit 279 alertes, comme la tuile", () => {
  assert.equal(libelleCompteAlertes(280, 1, 1, 6), "279 alertes et 1 synthèse, page 1 sur 6");
});

test("sans synthèse, le compte reste celui des lignes", () => {
  assert.equal(libelleCompteAlertes(7, 0, 1, 1), "7 alertes, page 1 sur 1");
  assert.equal(libelleCompteAlertes(1, 0, 1, 1), "1 alerte, page 1 sur 1");
});

test("filtre qui ne garde que la synthèse", () => {
  assert.equal(libelleCompteAlertes(1, 1, 1, 1), "1 synthèse, page 1 sur 1");
});

test("liste vide", () => {
  assert.equal(libelleCompteAlertes(0, 0, 1, 1), "Aucune alerte ne correspond à ces filtres.");
});

test("le format des nombres vient de l'appelant", () => {
  const f = (n) => `<${n}>`;
  assert.equal(libelleCompteAlertes(1300, 2, 3, 9, f), "<1298> alertes et <2> synthèses, page <3> sur <9>");
});

test("la page /alertes passe les synthèses à la liste, qui s'en sert pour son compte", () => {
  const page = readFileSync(new URL("../src/app/alertes/page.tsx", import.meta.url), "utf8");
  assert.match(page, /typesSyntheses=\{TYPES_SYNTHESES\}/);
  assert.match(page, /syntheses=\{stats\.syntheses\}/);
  const liste = readFileSync(new URL("../src/components/client/AlertesListe.tsx", import.meta.url), "utf8");
  assert.match(liste, /libelleCompteAlertes\(totalFiltre, synthesesFiltre,/);
  assert.doesNotMatch(liste, /alerte\$\{totalFiltre > 1/);
});
