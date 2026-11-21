// Liens HATVP affichés (src/lib/lien-hatvp.ts) : un chemin mal formé de
// liste.csv n'est jamais publié comme lien, il renvoie à la liste. La clé de
// rattachement des déclarations garde l'URL brute et n'est jamais la liste.
// Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  URL_HATVP_LISTE,
  choisirLienHatvp,
  clesRattachementHatvp,
  estFicheHatvpBienFormee,
  lienHatvpAffichable,
} from "../src/lib/lien-hatvp.ts";

// Les 4 valeurs réelles de elus.hatvp_url, base du 21/11/2026 (PA793342,
// PA793944, PA794854, rne-e458de14ab5ae5e0) : le site de la HATVP ne les sert pas.
const MAL_FORMEES = [
  "https://www.hatvp.fr/pages_nominatives/martin-(alpes-maritimes)-alexandra",
  "https://www.hatvp.fr/pages_nominatives/martin-(gironde)-alexandra-26044",
  "https://www.hatvp.fr/pages_nominatives/echaniz-iñaki-24343",
  "https://www.hatvp.fr/pages_nominatives/capitanio-olivier[",
];
const BIEN_FORMEE = "https://www.hatvp.fr/pages_nominatives/gate-sylvie-23162";

test("un chemin mal formé renvoie à la liste", () => {
  for (const url of MAL_FORMEES) {
    assert.equal(estFicheHatvpBienFormee(url), false, url);
    assert.equal(lienHatvpAffichable(url), URL_HATVP_LISTE, url);
  }
});

test("une fiche bien formée et la liste passent telles quelles", () => {
  assert.equal(lienHatvpAffichable(BIEN_FORMEE), BIEN_FORMEE);
  assert.equal(lienHatvpAffichable(URL_HATVP_LISTE), URL_HATVP_LISTE);
  assert.equal(lienHatvpAffichable(null), null);
  assert.equal(lienHatvpAffichable(""), null);
  // Le motif est entier : un suffixe ou un autre hôte ne passe pas.
  assert.equal(lienHatvpAffichable(`${BIEN_FORMEE}/`), URL_HATVP_LISTE);
  assert.equal(lienHatvpAffichable("https://hatvp.fr/pages_nominatives/gate-sylvie-23162"), URL_HATVP_LISTE);
});

test("fiche d'élu : une fiche bien formée de l'AN passe devant un chemin mal formé", () => {
  assert.equal(choisirLienHatvp(MAL_FORMEES[1], BIEN_FORMEE), BIEN_FORMEE);
  assert.equal(choisirLienHatvp(BIEN_FORMEE, MAL_FORMEES[1]), BIEN_FORMEE);
  assert.equal(choisirLienHatvp(MAL_FORMEES[1], MAL_FORMEES[1]), URL_HATVP_LISTE);
  assert.equal(choisirLienHatvp(MAL_FORMEES[3], null), URL_HATVP_LISTE);
  assert.equal(choisirLienHatvp(null, undefined), null);
});

test("clés de rattachement : URL brutes gardées, jamais la liste", () => {
  assert.deepEqual(clesRattachementHatvp(MAL_FORMEES[1], MAL_FORMEES[1]), [MAL_FORMEES[1]]);
  assert.deepEqual(clesRattachementHatvp(MAL_FORMEES[3], null), [MAL_FORMEES[3]]);
  assert.deepEqual(clesRattachementHatvp(URL_HATVP_LISTE, undefined), []);
  assert.deepEqual(clesRattachementHatvp(URL_HATVP_LISTE, BIEN_FORMEE), [BIEN_FORMEE]);
});
