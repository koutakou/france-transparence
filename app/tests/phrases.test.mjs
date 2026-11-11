// Accord en nombre des phrases à compte (src/lib/phrases.ts). Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  debutCompteEcheances,
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
    debutCompteEcheances(0, "0"),
    "Aucune échéance encore ouverte dans la liste livrée avec la page, sur",
  );
  assert.equal(debutCompteEcheances(1, "1"), "1 échéance encore ouverte, la plus proche, affichée sur");
  assert.match(debutCompteEcheances(20, "20"), /^20 échéances encore ouvertes, les plus proches, affichées sur$/);
  const p = phraseEcheancesEpuisees("08/11/2026 à 05h26", 48);
  assert.match(p, /arrêtées à sa construction \(08\/11\/2026 à 05h26\) pour les 48 heures suivantes/);
  assert.match(p, /les appels d’offres qui clôturent plus tard n’y figurent pas/);
  assert.doesNotMatch(p, /aucun appel d’offres/i);
});
