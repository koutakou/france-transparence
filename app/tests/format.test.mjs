// Formats français (src/lib/format.ts) : arrondis aux bornes d'unité et zéro
// signé. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { estNulAffiche, formatEuros, formatPct } from "../src/lib/format.ts";

const F = " ";

test("formatEuros choisit l'unité sur la valeur arrondie", () => {
  assert.equal(formatEuros(999_950_000), `1${F}Md€`);
  assert.equal(formatEuros(999_400_000), `999${F}M€`);
  assert.equal(formatEuros(999_999.6), `1${F}M€`);
  assert.equal(formatEuros(999_999.4), `999${F}999${F}€`);
  assert.equal(formatEuros(1_300_000_000), `1,3${F}Md€`);
  assert.equal(formatEuros(4_235_000), `4,2${F}M€`);
  assert.equal(formatEuros(-999_950_000), `-1${F}Md€`);
});

test("formatEuros n'écrit jamais « -0 € »", () => {
  assert.equal(formatEuros(-0.4), `0${F}€`);
  assert.equal(formatEuros(-0), `0${F}€`);
  assert.equal(formatEuros(-12), `-12${F}€`);
});

test("formatPct signé : zéro sans signe, signe sinon", () => {
  assert.equal(formatPct(-0.04, 1, true), `0${F}%`);
  assert.equal(formatPct(0, 1, true), `0${F}%`);
  assert.equal(formatPct(0.04, 1, true), `0${F}%`);
  assert.equal(formatPct(4.2, 1, true), `+4,2${F}%`);
  assert.equal(formatPct(-2.1, 1, true), `-2,1${F}%`);
  assert.equal(formatPct(-0.04, 1), `0${F}%`);
});

test("un delta qui s'affiche « 0 » est nul (pas de ▼ dans DeltaPct)", () => {
  assert.equal(estNulAffiche(-0.04, 1), true);
  assert.equal(estNulAffiche(-0.05, 1), false);
  assert.equal(estNulAffiche(Number.NaN, 1), true);
});
