// « Provisoire » sur /collectivites (src/lib/comptes-locaux.ts). La page
// écrivait « montants provisoires jusqu'en décembre 2026 » sans condition :
// le 01/01/2027, elle aurait dit à la fois que les comptes 2025 étaient
// provisoires et qu'ils ne l'étaient que jusqu'en décembre 2026.
// Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { comptesProvisoires, textesComptesLocaux } from "../src/lib/comptes-locaux.ts";
import { formatDateFr } from "../src/lib/format.ts";

test("comptes 2025 lus le 11/11/2026 (base de ce jour) : provisoires", () => {
  assert.equal(comptesProvisoires(2025, "2026-11-11T14:17:27+00:00"), true);
});

test("dernier jour certain : 30/11 de N+1 ; dès le 1er décembre, plus « provisoires »", () => {
  assert.equal(comptesProvisoires(2025, "2026-11-30T04:17:00+00:00"), true);
  assert.equal(comptesProvisoires(2025, "2026-12-01T04:17:00+00:00"), false);
  assert.equal(comptesProvisoires(2025, "2027-01-01"), false);
});

test("l'exercice suivant repart de zéro : comptes 2026 lus en juillet 2027", () => {
  assert.equal(comptesProvisoires(2026, "2027-07-20T04:17:00+00:00"), true);
});

// Les textes de la page tirés de la règle : badge, qualificatif, périmètre
// des tuiles et en-tête. Lectures réelles : base du 11/11/2026, puis un cycle
// du 02/12/2026 (après le 1er décembre N+1).
test("lu le 11/11/2026 : tous les textes disent « provisoire »", () => {
  const t = textesComptesLocaux(2025, "2026-11-11T14:17:27+00:00", formatDateFr);
  assert.equal(t.luLe, "11/11/2026");
  assert.equal(t.mention, "comptes 2025 provisoires");
  assert.equal(t.qualif, " (provisoire)");
  assert.match(t.perimetre, /^budgets principaux, comptes provisoires — /);
  assert.match(t.suiteEntete, /^ : provisoires jusqu’à l’intégration des balances définitives de la DGFiP, fin décembre 2026/);
});

test("lu le 02/12/2026 : plus aucun « provisoire », jamais « définitif », lecture datée", () => {
  const t = textesComptesLocaux(2025, "2026-12-02T04:17:00+00:00", formatDateFr);
  assert.equal(t.mention, "comptes 2025 lus le 02/12/2026");
  assert.equal(t.qualif, "");
  assert.match(t.perimetre, /^budgets principaux — /);
  for (const texte of Object.values(t)) {
    assert.doesNotMatch(texte, /provisoires? (jusqu|$)|\(provisoire\)|comptes provisoires|définitifs/);
  }
  assert.match(t.suiteEntete, /ne distingue pas les deux versions$/);
});
