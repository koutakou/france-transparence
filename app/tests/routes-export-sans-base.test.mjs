// Routes d'export sans base : le build échoue, il ne publie jamais un fichier
// vide (même règle que les routes JSON). Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import { importer } from "./outils/charger.mjs";

process.env.FRANCE_DB_PATH = path.join(os.tmpdir(), "ft-base-absente-inexistante", "france.db");

for (const route of [
  "api/meta.csv",
  "api/alertes.csv",
  "api/elus.csv",
  "api/budget-mensuel.csv",
  "api/marches-agregats-departements.csv",
  "api/marches-agregats-mois.csv",
  "api/lobbying-marches.csv",
  "api/marches-top-acheteurs.csv",
  "api/marches-top-titulaires.csv",
  "api/elus.provenance.txt",
  "flux/jo.xml",
  "flux/dossiers.xml",
  "flux/alertes.xml",
  "flux/sources.xml",
]) {
  test(`${route} : base absente, erreur franche`, async () => {
    const { GET, dynamic } = await importer(`app/${route}/route`);
    assert.equal(dynamic, "force-static");
    assert.throws(() => GET(), /Base absente au build/);
  });
}
