// Exports CSV (src/lib/csv.ts) : séparateur, BOM, guillemets RFC 4180,
// nombres pour le tableur français, provenance. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  BOM,
  celluleCsv,
  documentCsv,
  documentProvenance,
  ligneCsv,
  nombreCsv,
} from "../src/lib/csv.ts";

/** Lecteur RFC 4180 minimal (séparateur « ; ») pour vérifier l'aller-retour. */
function lireCsv(texte) {
  assert.ok(texte.startsWith(BOM), "BOM en tête");
  const s = texte.slice(1);
  const lignes = [];
  let ligne = [];
  let champ = "";
  let entreGuillemets = false;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (entreGuillemets) {
      if (c === '"' && s[i + 1] === '"') {
        champ += '"';
        i++;
      } else if (c === '"') entreGuillemets = false;
      else champ += c;
    } else if (c === '"') entreGuillemets = true;
    else if (c === ";") {
      ligne.push(champ);
      champ = "";
    } else if (c === "\r" && s[i + 1] === "\n") {
      ligne.push(champ);
      lignes.push(ligne);
      ligne = [];
      champ = "";
      i++;
    } else champ += c;
  }
  assert.equal(champ, "", "le document finit par CRLF");
  return lignes;
}

test("un champ avec « ; », guillemets ou saut de ligne est protégé, ses guillemets doublés", () => {
  assert.equal(celluleCsv("simple"), "simple");
  assert.equal(celluleCsv("a;b"), '"a;b"');
  assert.equal(celluleCsv('il dit "oui"'), '"il dit ""oui"""');
  assert.equal(celluleCsv("ligne 1\nligne 2"), '"ligne 1\nligne 2"');
  assert.equal(celluleCsv("ligne 1\r\nligne 2"), '"ligne 1\r\nligne 2"');
  // La virgule n'est pas le séparateur : pas de guillemets inutiles.
  assert.equal(celluleCsv("Dupont, Jean"), "Dupont, Jean");
});

test("vide, null et undefined donnent un champ vide, un booléen 1 ou 0", () => {
  assert.equal(celluleCsv(null), "");
  assert.equal(celluleCsv(undefined), "");
  assert.equal(celluleCsv(""), "");
  assert.equal(celluleCsv(true), "1");
  assert.equal(celluleCsv(false), "0");
});

test("montants : ni espace insécable, ni séparateur de milliers, virgule décimale", () => {
  assert.equal(nombreCsv(1234567), "1234567");
  assert.equal(nombreCsv(1234567.5), "1234567,5");
  assert.equal(nombreCsv(-98765432.25), "-98765432,25");
  assert.equal(nombreCsv(-0), "0");
  assert.equal(nombreCsv(0.0000001), "0,0000001");
  assert.equal(nombreCsv(Number.NaN), "");
  assert.equal(nombreCsv(Number.POSITIVE_INFINITY), "");
  for (const n of [1e9, 123456789.12, 100_000_000]) {
    assert.doesNotMatch(nombreCsv(n), /[\s  .]/, String(n));
  }
});

test("un texte qui commencerait une formule est neutralisé, jamais un nombre", () => {
  assert.equal(celluleCsv("=SOMME(A1:A3)"), "'=SOMME(A1:A3)");
  assert.equal(celluleCsv("+33 1 00"), "'+33 1 00");
  assert.equal(celluleCsv("-12"), "'-12");
  assert.equal(celluleCsv("@cmd"), "'@cmd");
  assert.equal(celluleCsv('=HYPERLINK("x";"y")'), `"'=HYPERLINK(""x"";""y"")"`);
  assert.equal(celluleCsv(-12), "-12");
  assert.equal(celluleCsv("Décret n° 2026-1"), "Décret n° 2026-1");
});

test("document : BOM, noms de colonnes en première ligne, CRLF, aller-retour exact", () => {
  const colonnes = [
    { cle: "nom", description: "", valeur: (l) => l.nom },
    { cle: "montant", description: "", valeur: (l) => l.montant },
    { cle: "note", description: "", valeur: (l) => l.note },
  ];
  const lignes = [
    { nom: "Société ; « Test »", montant: 1500000.5, note: 'a "b"\nc' },
    { nom: "Commune", montant: null, note: null },
  ];
  const texte = documentCsv(colonnes, lignes);
  assert.ok(texte.startsWith("﻿nom;montant;note\r\n"));
  assert.deepEqual(lireCsv(texte), [
    ["nom", "montant", "note"],
    ["Société ; « Test »", "1500000,5", 'a "b"\nc'],
    ["Commune", "", ""],
  ]);
  assert.equal(ligneCsv(["a", 1, null]), "a;1;");
});

test("document sans ligne : la ligne des colonnes seule", () => {
  const texte = documentCsv([{ cle: "x", description: "", valeur: () => 1 }], []);
  assert.equal(texte, "﻿x\r\n");
});

test("provenance : chaque source avec sa licence, sa date des données et son URL", () => {
  const texte = documentProvenance({
    fichier: "exemple.csv",
    titre: "Exemple",
    description: "Description de l'export.",
    mentions: ["Crédit : quelqu'un."],
    colonnes: [{ cle: "a", description: "colonne a" }],
    sources: [
      {
        source_id: "S1",
        nom: "DECP consolidées",
        url: "https://exemple.gouv.fr/decp",
        licence: "Licence Ouverte 2.0",
        date_donnees: "2026-11-20",
        date_ingestion: "2026-11-21T04:00:00+00:00",
        nature: "Consolidation reconnue, non officielle",
      },
    ],
    voirAussi: ["https://francetransparence.fr/api/exemple.csv"],
  });
  assert.ok(texte.startsWith(BOM));
  for (const attendu of [
    "Fichier décrit : exemple.csv",
    "S1 : DECP consolidées",
    "Nature : Consolidation reconnue, non officielle",
    "Licence : Licence Ouverte 2.0",
    "Date des données : 2026-11-20",
    "URL amont : https://exemple.gouv.fr/decp",
    "Crédit : quelqu'un.",
    "a : colonne a",
    "Licence des agrégats : Licence Ouverte 2.0",
  ]) {
    assert.ok(texte.includes(attendu), attendu);
  }
  // Aucune ligne de la provenance n'est faite pour être lue comme du CSV.
  assert.doesNotMatch(texte, /^#/m);
});

test("provenance sans source amont propre : la phrase de remplacement", () => {
  const texte = documentProvenance({
    fichier: "meta.csv",
    titre: "Catalogue",
    description: "d",
    colonnes: [],
    sources: [],
    sansSource: "Le fichier est lui-même le catalogue.",
  });
  assert.ok(texte.includes("Le fichier est lui-même le catalogue."));
});
