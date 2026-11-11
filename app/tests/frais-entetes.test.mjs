// En-têtes de catégorie de /frais (lib/queries/frais.ts) : « Institutions —
// dotations 2026 », « LFI pour 2026 », « DGCL au 01/01/2026 » étaient écrits
// en dur, alors que les faits viennent du pipeline (S31) et changent de
// millésime quand il est mis à jour. Périodes réelles de la base du
// 11/11/2026 (trainvie_faits). Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { importer } from "./outils/charger.mjs";

const { periodeCommune, dateSourceCommune } = await importer("lib/queries/frais");

test("une seule période dans le groupe : elle est rendue", () => {
  const institutions = [{ periode: "2026" }, { periode: "2026" }];
  assert.equal(periodeCommune(institutions), "2026");
  assert.equal(periodeCommune([{ periode: "2027" }]), "2027");
});

test("périodes mêlées ou groupe vide : aucun millésime n'est affirmé", () => {
  assert.equal(periodeCommune([{ periode: "2026" }, { periode: "2025" }]), null);
  assert.equal(periodeCommune([]), null);
});

test("cabinets : la date de situation est celle des faits (01/07/2025)", () => {
  assert.equal(dateSourceCommune([{ date_source: "2025-07-01" }, { date_source: "2025-07-01" }]), "2025-07-01");
  assert.equal(dateSourceCommune([{ date_source: "2025-07-01" }, { date_source: "2026-07-01" }]), null);
});
