// En-têtes de catégorie de /frais (src/lib/frais-entetes.ts) : « Institutions —
// dotations 2026 », « LFI pour 2026 », « DGCL au 01/01/2026 » étaient écrits
// en dur, alors que les faits viennent du pipeline (S31) et changent de
// millésime quand il est mis à jour. On teste les PHRASES rendues : une
// période unique s'écrit, des périodes mêlées ne coupent jamais la phrase.
// Périodes et dates réelles de la base du 11/11/2026 (trainvie_faits).
// Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { importer } from "./outils/charger.mjs";

const { enTeteCategorie, periodeCommune, dateSourceCommune } = await importer("lib/frais-entetes");

const lfi = (periode) => ({ periode, date_source: `${periode}-02-19` });
const dgcl = (periode) => ({ periode, date_source: `${periode}-02-17` });
const jaune = (date_source) => ({ periode: date_source.slice(0, 4), date_source });

/** Une phrase coupée finit sur un mot-outil ou sur un tiret orphelin. */
const coupee = (s) => /(\bpour|\bbarème|\bau|\bde|—)\s*$|\s—\s—|barème —/.test(s);

test("base du 11/11/2026 : en-têtes identiques à l'ancien texte, mais dérivés", () => {
  const inst = enTeteCategorie("institutions", [lfi("2026"), lfi("2026")]);
  assert.equal(inst.titre, "Institutions — dotations 2026");
  assert.equal(inst.sousTitre, "Mission « Pouvoirs publics » de la loi de finances initiale pour 2026");
  assert.equal(
    enTeteCategorie("cabinets", [jaune("2025-07-01"), jaune("2025-07-01")]).sousTitre,
    "Jaune budgétaire « Personnels affectés dans les cabinets ministériels » — situation au 01/07/2025",
  );
  assert.equal(
    enTeteCategorie("elus_locaux", [dgcl("2026")]).sousTitre,
    "Indemnités maximales publiées par la DGCL, barème 2026 — les montants réellement versés ne sont pas centralisés",
  );
});

test("faits passés en 2027 : l'en-tête suit, rien de 2026 ne reste", () => {
  const inst = enTeteCategorie("institutions", [lfi("2027")]);
  assert.equal(inst.titre, "Institutions — dotations 2027");
  assert.match(inst.sousTitre, /initiale pour 2027$/);
  assert.match(enTeteCategorie("elus_locaux", [dgcl("2027")]).sousTitre, /barème 2027 —/);
  for (const e of [inst, enTeteCategorie("elus_locaux", [dgcl("2027")])]) {
    assert.doesNotMatch(`${e.titre} ${e.sousTitre}`, /2026/);
  }
});

test("périodes mêlées (un fait mis à jour avant les autres) : phrase complète, aucun millésime choisi", () => {
  const cas = [
    enTeteCategorie("institutions", [lfi("2026"), lfi("2027")]),
    enTeteCategorie("cabinets", [jaune("2025-07-01"), jaune("2026-07-01")]),
    enTeteCategorie("elus_locaux", [dgcl("2026"), dgcl("2027")]),
  ];
  for (const { titre, sousTitre } of cas) {
    assert.ok(!coupee(titre), titre);
    assert.ok(!coupee(sousTitre), sousTitre);
    assert.doesNotMatch(`${titre} ${sousTitre}`, /202[67]/);
    assert.match(sousTitre, /indiqu[ée]e? sur sa ligne/);
  }
  assert.equal(cas[0].titre, "Institutions — dotations");
});

test("periodeCommune / dateSourceCommune : une seule valeur, sinon null", () => {
  assert.equal(periodeCommune([{ periode: "2026" }, { periode: "2026" }]), "2026");
  assert.equal(periodeCommune([{ periode: "2026" }, { periode: "2025" }]), null);
  assert.equal(periodeCommune([]), null);
  assert.equal(dateSourceCommune([{ date_source: "2025-07-01" }, { date_source: "2026-07-01" }]), null);
});
