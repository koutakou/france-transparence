// /donnees (lib/queries/donnees.ts) : l'état « En attente d'une édition » ne
// dépend que de l'âge de la donnée ; sa phrase ne peut donc affirmer qu'un
// fait que le site vérifie — ce qu'il a INGÉRÉ —, pas ce que l'amont a
// publié. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { importer } from "./outils/charger.mjs";

const { constatAttente, evalueFraicheur } = await importer("lib/queries/donnees");
const AUDIT = new Date("2026-10-15T12:00:00Z");

test("S46 (PLF 2025, données au 11/10/2024) : en attente, millésime figé", () => {
  const f = evalueFraicheur("S46", "2024-10-11", AUDIT);
  assert.equal(f.niveau, "attente_edition");
  assert.equal(f.editionFigee, true);
  const constat = constatAttente(f);
  assert.match(constat, /ingérée/);
  assert.match(constat, /millésime fixé par le pipeline/);
  assert.doesNotMatch(constat, /publiée/);
});

test("les pipelines dont le millésime est écrit en dur sont dits figés", () => {
  // S50/S51 : Insee Résultats 8988845 ; S20/S21/S23 : jeux « plf-2026-… » et
  // « plf25-… » ; S25 : EXERCICES 2021-2024 ; S29 : législatives 2024 ;
  // S37 : liste de décrets tenue à la main ; S16 : EXERCICE_COMPTES.
  for (const id of ["S16", "S20", "S21", "S23", "S25", "S29", "S37", "S50", "S51"]) {
    assert.equal(evalueFraicheur(id, "2025-12-31", AUDIT).editionFigee, true, id);
  }
});

test("une source dont le pipeline suit les éditions n'est pas dite figée", () => {
  // CGE (S22) : millésime lu dans la pièce de synthèse publiée, via l'API.
  const f = evalueFraicheur("S22", "2024-12-31", AUDIT);
  assert.equal(f.editionFigee, false);
  assert.equal(constatAttente(f), "aucune édition plus récente n’a été ingérée à ce jour");
  assert.equal(evalueFraicheur("INCONNUE", "2024-12-31", AUDIT).editionFigee, false);
});
