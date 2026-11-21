// Libellés des types d'alerte (components/client/AlertesListe.tsx) :
// descriptifs, sans jugement, et fidèles à la règle du pipeline qui calcule
// l'alerte. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const APP = fileURLToPath(new URL("..", import.meta.url));
const LISTE = readFileSync(join(APP, "src/components/client/AlertesListe.tsx"), "utf8");

/**
 * Le dossier `pipelines/` de la racine du dépôt (à côté de `app/`), résolu
 * depuis l'emplacement de l'application et non du dossier courant, ou `null`
 * quand l'application est jouée seule, sans le reste du dépôt. On ne remonte
 * pas plus haut : un autre `pipelines/` ne dirait rien de ce dépôt.
 */
function dossierPipelines() {
  const candidat = join(dirname(APP.replace(/[\\/]$/, "")), "pipelines");
  return existsSync(candidat) && statSync(candidat).isDirectory() ? candidat : null;
}

const PIPELINES = dossierPipelines();

test(
  "le libellé de l'alerte sur l'aide publique d'un parti dit le seuil du pipeline",
  { skip: PIPELINES === null && "dossier pipelines/ absent : application jouée hors du dépôt" },
  () => {
    const PIPELINE = readFileSync(join(PIPELINES, "ingest_financement.py"), "utf8");
    const seuil = /^SEUIL_DEPENDANCE_RATIO = ([\d.]+)/m.exec(PIPELINE);
    assert.ok(seuil, "SEUIL_DEPENDANCE_RATIO introuvable dans ingest_financement.py");
    const pct = Math.round(Number(seuil[1]) * 100);
    const libelle = /financement_parti_dependance_aide: "([^"]+)"/.exec(LISTE);
    assert.ok(libelle, "libellé du type financement_parti_dependance_aide introuvable");
    assert.match(libelle[1], new RegExp(`au moins ${pct} % des produits`));
    assert.doesNotMatch(libelle[1], /dépendance/i);
  },
);
