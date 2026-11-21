// Routes d'export sans base : le build échoue, il ne publie jamais un fichier
// vide (même règle que les routes JSON). Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import { importer } from "./outils/charger.mjs";
import { EXPORTS_CSV, cheminProvenance } from "../src/lib/exports-csv.ts";

process.env.FRANCE_DB_PATH = path.join(os.tmpdir(), "ft-base-absente-inexistante", "france.db");

// Chaque CSV et son fichier de provenance, d'après la liste publiée sur /donnees.
const exportsCsv = EXPORTS_CSV.map((e) => e.fichier);
assert.equal(exportsCsv.length, 9);

for (const route of [
  ...exportsCsv.map((f) => `api/${f}`),
  ...exportsCsv.map((f) => cheminProvenance(f).replace(/^\//, "")),
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
