// Libellés des types d'alerte (components/client/AlertesListe.tsx) :
// descriptifs, sans jugement, et fidèles à la règle du pipeline qui calcule
// l'alerte. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const lire = (chemin) => readFileSync(fileURLToPath(new URL(chemin, import.meta.url)), "utf8");
const LISTE = lire("../src/components/client/AlertesListe.tsx");
const PIPELINE = lire("../../pipelines/ingest_financement.py");

test("le libellé de l'alerte sur l'aide publique d'un parti dit le seuil du pipeline", () => {
  const seuil = /^SEUIL_DEPENDANCE_RATIO = ([\d.]+)/m.exec(PIPELINE);
  assert.ok(seuil, "SEUIL_DEPENDANCE_RATIO introuvable dans ingest_financement.py");
  const pct = Math.round(Number(seuil[1]) * 100);
  const libelle = /financement_parti_dependance_aide: "([^"]+)"/.exec(LISTE);
  assert.ok(libelle, "libellé du type financement_parti_dependance_aide introuvable");
  assert.match(libelle[1], new RegExp(`au moins ${pct} % des produits`));
  assert.doesNotMatch(libelle[1], /dépendance/i);
});
