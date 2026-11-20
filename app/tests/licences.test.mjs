// Licences : un libellé publié par licence (audit du 20/11/2026, C6). Les
// lignes meta_sources sont gardées côté pipelines
// (pipelines/tests/test_meta_sources_regles.py) ; ce test garde les mentions
// écrites en dur dans les pages, qui portaient les mêmes variantes.
// Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const RACINE = new URL("../src/", import.meta.url);

const VARIANTES_INTERDITES = [
  /Licence Ouverte 2\.0 \(Etalab\)/,
  /Licence Ouverte \/ Open Licence/,
  /Licence Ouverte v2/,
  /Licence Ouverte Etalab/,
  /Licence Ouverte \((fr-lo|lov2|AN|IGN\/Etalab)\)/,
];

test("les pages n'écrivent que les libellés canoniques des Licences Ouvertes", () => {
  const trouvees = [];
  for (const relatif of fs.readdirSync(RACINE, { recursive: true })) {
    if (!/\.(tsx?|mjs)$/.test(relatif)) continue;
    const texte = fs.readFileSync(new URL(relatif.split(path.sep).join("/"), RACINE), "utf8");
    for (const motif of VARIANTES_INTERDITES) {
      if (motif.test(texte)) trouvees.push(`${relatif} : ${motif}`);
    }
  }
  assert.deepEqual(trouvees, []);
});