// JSON-LD des fiches d'élus (lib/seo.ts) : un mandat terminé porte sa date
// de fin quand la chambre la publie, et seulement alors. Cas réel : le
// sénateur 14133K, non réélu, clos au 2026-09-30 par clore_mandats_sortis
// (dump export_sens, table elusen). Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { importer } from "./outils/charger.mjs";

const { fusionnerFinMandat, jsonLdFicheElu } = await importer("lib/seo");

test("la fin publiée par la chambre l'emporte sur le RNE muet", () => {
  // SENAT-P9 : date_fin 2026-09-30 ; RNE : aucun champ date_fin.
  assert.equal(fusionnerFinMandat("2026-09-30", undefined), "2026-09-30");
  assert.equal(fusionnerFinMandat(undefined, "2026-09-30"), "2026-09-30");
});

test("une source qui dit le mandat en cours l'emporte sur une date", () => {
  assert.equal(fusionnerFinMandat(null, "2026-09-30"), null);
  assert.equal(fusionnerFinMandat("2026-09-30", null), null);
});

test("aucune source ne dit la fin : rien n'est inventé", () => {
  assert.equal(fusionnerFinMandat(undefined, undefined), undefined);
});

function personne(roles) {
  const g = jsonLdFicheElu({
    chemin: "/elus/SEN-14133K/", nomComplet: "Prénom Nom", nom: "Nom",
    roles, groupes: [], sameAs: [], description: "",
  });
  return g["@graph"].find((n) => n["@type"] === "Person");
}

test("mandat terminé : endDate = date publiée", () => {
  const p = personne([{ roleName: "Sénateur", organisation: "Sénat", debut: null, fin: "2026-09-30" }]);
  assert.equal(p.memberOf[0].endDate, "2026-09-30");
});

test("mandat en cours ou fin inconnue : pas d'endDate", () => {
  const p = personne([
    { roleName: "Sénateur", organisation: "Sénat", debut: "2023-10-02", fin: null },
    { roleName: "Maire", organisation: "Commune — X", debut: "2020-05-23" },
  ]);
  assert.equal(p.memberOf[0].endDate, undefined);
  assert.equal(p.memberOf[1].endDate, undefined);
});
