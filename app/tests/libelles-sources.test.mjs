// Badge de l'accueil (lib/libelles-sources.ts) : le libellé court
// « DILA · RefOrga État » ne vaut que si la ligne meta S35 décrit
// RefOrgaAdminEtat. Noms recopiés de pipelines/ingest_referentiels.py
// (meta_entites_etat, normal et secours). Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { libelleBadgeSource } from "../src/lib/libelles-sources.ts";

const COURTS = { "S35-reforga-admin-etat": "DILA · RefOrga État", S2: "BOAMP" };
const NOM_NORMAL = "Référentiel de l'organisation administrative de l'État (DILA)";
const NOM_SECOURS =
  "Ministères de l'État — liste vérifiée (secours : RefOrgaAdminEtat inexploitable)";

test("RefOrgaAdminEtat a servi : libellé court", () => {
  assert.equal(
    libelleBadgeSource({ source_id: "S35-reforga-admin-etat", nom: NOM_NORMAL }, COURTS),
    "DILA · RefOrga État",
  );
});

test("mode secours : le badge nomme la source réellement utilisée", () => {
  assert.equal(
    libelleBadgeSource({ source_id: "S35-reforga-admin-etat", nom: NOM_SECOURS }, COURTS),
    NOM_SECOURS,
  );
});

test("les autres sources gardent leur libellé court, ou leur nom à défaut", () => {
  assert.equal(libelleBadgeSource({ source_id: "S2", nom: "BOAMP (DILA)" }, COURTS), "BOAMP");
  assert.equal(libelleBadgeSource({ source_id: "S99", nom: "Autre" }, COURTS), "Autre");
});

test("le préfixe attendu est bien celui qu'écrit le pipeline", async () => {
  const fs = await import("node:fs");
  const { NOM_S35_REFORGA } = await import("../src/lib/libelles-sources.ts");
  const pipeline = fs.readFileSync(
    new URL("../../pipelines/ingest_referentiels.py", import.meta.url), "utf8");
  assert.ok(pipeline.includes(`"nom": "${NOM_S35_REFORGA}"`));
});
