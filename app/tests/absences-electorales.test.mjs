// Communes suivies absentes d'un scrutin (src/lib/absences-electorales.ts).
// Absences mesurées sur la base du 15/10/2026 (elections_participation_ville
// contre ref_villes ∪ collectivites_communes_top200). Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { codesAbsents, expliquerAbsences } from "../src/lib/absences-electorales.ts";

const nom = (c) => c;
const texte = (famille, tour, absents) => expliquerAbsences({ famille, tour }, absents, nom).join(" ");

test("codesAbsents : suivies moins présentes", () => {
  assert.deepEqual(codesAbsents(["75056", "97701", "98613"], ["75056", "97701"]), ["98613"]);
});

test("présidentielle 2022 T1 : seule Uvea manque, ni 97701 ni 97801 citées", () => {
  const t = texte("Présidentielle", 1, ["98613"]);
  assert.match(t, /Uvea \(98613\)/);
  assert.doesNotMatch(t, /97701|97801|conseil/);
});

test("municipales 2026 T1 : conseil territorial pour 97701 et 97801", () => {
  const t = texte("Municipales", 1, ["97701", "97801", "98613"]);
  assert.match(t, /Saint-Barthélemy \(97701\) et Saint-Martin \(97801\) élisent un conseil territorial/);
  assert.match(t, /Uvea/);
});

test("législatives 2024 T2 : jamais « conseil », la raison des circonscriptions", () => {
  const t = texte("Législatives", 2, ["02408", "93001", "98613"]);
  assert.doesNotMatch(t, /conseil/);
  assert.match(t, /Pour les 2 autres : à un second tour de législatives/);
});

test("municipales 2026 T2 : la raison du conseil élu au premier tour", () => {
  const t = texte("Municipales", 2, ["01053", "97701", "97801", "98613"]);
  assert.match(t, /Pour l’autre : à un second tour de municipales/);
});

test("absence sans raison structurelle connue : nommée, aucune raison inventée", () => {
  assert.equal(
    texte("Européennes", 1, ["98735"]),
    "Absente des résultats publiés par le ministère pour ce scrutin : 98735.",
  );
});
