// Accord en nombre des phrases à compte (src/lib/phrases.ts). Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import {
  compteEcheances,
  phraseEcheancesEpuisees,
  phraseMarchesSansMontant,
} from "../src/lib/phrases.ts";

test("zéro marché : « Aucun marché », jamais « 0 marchés sont »", () => {
  assert.equal(phraseMarchesSansMontant(0, "0"), "Aucun marché n’est notifié sans montant renseigné.");
});

test("singulier et pluriel accordés", () => {
  assert.match(phraseMarchesSansMontant(1, "1"), /^1 marché est notifié .* compté .* exclu /);
  assert.match(phraseMarchesSansMontant(12, "12"), /^12 marchés sont notifiés .* comptés .* exclus /);
});

// Accueil et /marches servis le 11/11/2026, trois jours après la dernière
// construction (08/11) : « 0 échéances encore ouvertes, les plus proches,
// affichées sur 7 551 appels d'offres en cours », et « les échéances de la
// liste arrêtée le 08/11 sont toutes passées », alors que plus de 6 000
// appels d'offres de l'instantané restaient ouverts — la page n'en avait reçu
// que 48 heures.
test("liste livrée épuisée : jamais « 0 échéances », jamais « aucun appel d’offres ouvert »", () => {
  assert.equal(
    compteEcheances(0, "0", 7551, "7 551"),
    "Aucune échéance encore ouverte dans la liste livrée avec la page, sur 7 551 appels d’offres en cours à la construction du site",
  );
  assert.equal(
    compteEcheances(1, "1", 7551, "7 551"),
    "1 échéance encore ouverte, la plus proche, affichée sur 7 551 appels d’offres en cours à la construction du site",
  );
  assert.equal(
    compteEcheances(20, "20", 7551, "7 551"),
    "20 échéances encore ouvertes, les plus proches, affichées sur 7 551 appels d’offres en cours à la construction du site",
  );
  const p = phraseEcheancesEpuisees("08/11/2026 à 05h26", 48);
  assert.match(p, /arrêtées à sa construction \(08\/11\/2026 à 05h26\) pour les 48 heures suivantes/);
  assert.match(p, /les appels d’offres qui clôturent plus tard n’y figurent pas/);
  assert.doesNotMatch(p, /aucun appel d’offres/i);
});

test("filtre sans aucun appel d’offres : ni « Aucune échéance… sur 0 », ni « 1 appels »", () => {
  assert.equal(compteEcheances(0, "0", 0, "0"), "Aucun appel d’offres en cours à la construction du site");
  assert.equal(
    compteEcheances(1, "1", 1, "1"),
    "1 échéance encore ouverte, la plus proche, affichée sur 1 appel d’offres en cours à la construction du site",
  );
});

// Libellés qui jugent (audit des pages du 20/11/2026, R8 ; décision du
// propriétaire du même jour, Ton). textes-ton.test.mjs garde app/ et
// components/ ; les phrases construites dans lib/ (requêtes, textes
// partagés) sont servies telles quelles et suivent la même liste. Les noms
// de colonne (`montant_suspect`) et les valeurs SQL ('suspect', classe de la
// source) ne sont pas des libellés.
const MOTS_QUI_JUGENT = [
  [/dépensi(er|ère)/i, "« dépenses par habitant les plus élevées »"],
  [/(?<![\w.'])suspect(e|s|es)?(?![\w'])/i, "« montant signalé »"],
  [/(?<!\w)verrous?(?!\w)/i, "« avis de la CADA par administration »"],
  [/boîte noire/i, "« ce que la loi ne publie pas »"],
  [/retard de versement/i, "un écart de publication n'est pas un retard imputable"],
];

const sansCommentaires = (s) =>
  s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'\w])\/\/.*$/gm, "$1");

function fichiersTs(dossier) {
  const out = [];
  for (const nom of readdirSync(dossier)) {
    const p = path.join(dossier, nom);
    if (statSync(p).isDirectory()) out.push(...fichiersTs(p));
    else if (/\.tsx?$/.test(p)) out.push(p);
  }
  return out;
}

const fautesDeTon = (texte) =>
  MOTS_QUI_JUGENT.filter(([motif]) => motif.test(texte)).map(([, pourquoi]) => pourquoi);

test("R8 : le contrôle voit les libellés qui jugent, pas les noms de colonne", () => {
  assert.equal(fautesDeTon("Top 10 : les plus dépensiers par habitant").length, 1);
  assert.equal(fautesDeTon("les communes les plus dépensières").length, 1);
  assert.equal(fautesDeTon("marchés au montant suspect").length, 1);
  assert.equal(fautesDeTon("La boîte noire des frais").length, 1);
  assert.deepEqual(fautesDeTon("WHERE montant_suspect = 1 AND montant_anomalie = 'suspect'"), []);
  assert.deepEqual(fautesDeTon("m.montant_suspect, nb_suspects_hors_ac"), []);
});

test("R8 : aucune phrase de lib/ ne porte un libellé qui juge", () => {
  const LIB = fileURLToPath(new URL("../src/lib/", import.meta.url));
  const fautes = [];
  for (const f of fichiersTs(LIB)) {
    const s = sansCommentaires(readFileSync(f, "utf8"));
    for (const pourquoi of fautesDeTon(s)) fautes.push(`${path.relative(LIB, f)} : ${pourquoi}`);
  }
  assert.deepEqual(fautes, []);
});
