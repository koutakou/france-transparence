// Taux de participation aux scrutins (décision du 20/11/2026) : il reste sur
// les fiches avec sa réserve au contact du chiffre, les motions de censure
// sortent du calcul, et aucun tableau ne se trie par ce taux.
// Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {
  METHODE_CENSURE,
  RESERVE_PARTICIPATION_AN,
  RESERVE_PARTICIPATION_SENAT,
} from "../src/lib/participation.ts";
import {
  TRIS_PARLEMENTAIRES,
  lireTriParlementaires,
  reinitialisationParlementaires,
  triApplicable,
  trierParlementaires,
} from "../src/lib/tri.ts";

const lire = (chemin) => fs.readFileSync(new URL(`../src/${chemin}`, import.meta.url), "utf8");

test("les tris proposés sont le nom et le groupe, rien d'autre", () => {
  assert.deepEqual(
    TRIS_PARLEMENTAIRES.map((t) => t.valeur),
    ["nom", "groupe"],
  );
  // une URL forgée ne réintroduit pas de tri par le taux
  assert.equal(lireTriParlementaires("taux_participation_12m"), "nom");
  assert.equal(lireTriParlementaires(null), "nom");
  assert.equal(lireTriParlementaires("groupe"), "groupe");
});

test("tri par groupe : groupe, puis nom, sans groupe en dernier", () => {
  const lignes = [
    { nom: "Martin", prenom: "A", g: "RN" },
    { nom: "Abad", prenom: "B", g: null },
    { nom: "Éblé", prenom: "C", g: "EPR" },
    { nom: "Bernard", prenom: "D", g: "RN" },
  ];
  const noms = (tri) => trierParlementaires(lignes, tri, (l) => l.g).map((l) => l.nom);
  assert.deepEqual(noms("groupe"), ["Éblé", "Bernard", "Martin", "Abad"]);
  assert.deepEqual(noms("nom"), ["Abad", "Bernard", "Éblé", "Martin"]);
  // copie : l'ordre d'origine n'est pas modifié
  assert.equal(lignes[0].nom, "Martin");
});

test("tri des parlementaires : un taux dans la ligne ne change jamais l'ordre", () => {
  // Même noms et groupes, taux inversés : l'ordre est identique, par nom
  // comme par groupe. Seuls le nom et le groupe comptent.
  const base = [
    { nom: "Durand", prenom: "A", g: "LFI", taux: 12 },
    { nom: "Abad", prenom: "B", g: "RN", taux: 98 },
    { nom: "Abad", prenom: "A", g: "RN", taux: 40 },
    { nom: "Colin", prenom: "C", g: "LFI", taux: 77 },
  ];
  const inverse = base.map((l) => ({ ...l, taux: 100 - l.taux }));
  for (const tri of ["nom", "groupe"]) {
    const ordre = (lignes) =>
      trierParlementaires(lignes, tri, (l) => l.g).map((l) => `${l.nom} ${l.prenom}`);
    assert.deepEqual(ordre(base), ordre(inverse), tri);
    assert.deepEqual(ordre(base), ordre([...base].reverse()), `${tri} : stable selon l'entrée`);
  }
  const ordre = (tri) =>
    trierParlementaires(base, tri, (l) => l.g).map((l) => `${l.nom} ${l.prenom}`);
  assert.deepEqual(ordre("nom"), ["Abad A", "Abad B", "Colin C", "Durand A"]);
  assert.deepEqual(ordre("groupe"), ["Colin C", "Durand A", "Abad A", "Abad B"]);
});

test("sans la liste complète, le tri par groupe n'est pas appliqué aux premières lignes", () => {
  assert.equal(triApplicable("groupe", false), "nom");
  assert.equal(triApplicable("groupe", true), "groupe");
  assert.equal(triApplicable("nom", false), "nom");
});

test("réinitialiser remet le tri par nom et efface td et ts de l'URL", () => {
  assert.deepEqual(reinitialisationParlementaires("deputes"), {
    surcharge: { groupe: "", departement: "", tri: "nom" },
    url: { gd: null, dd: null, td: null },
  });
  assert.deepEqual(reinitialisationParlementaires("senateurs").url, {
    gs: null,
    ds: null,
    ts: null,
  });
});

test("les réserves disent ce que le taux ne mesure pas", () => {
  assert.match(RESERVE_PARTICIPATION_AN, /pas un jugement/);
  assert.match(RESERVE_PARTICIPATION_AN, /commission/);
  assert.match(RESERVE_PARTICIPATION_AN, /absence justifiée/);
  assert.match(RESERVE_PARTICIPATION_AN, /délégation/);
  assert.match(METHODE_CENSURE, /motions de censure/);
  assert.match(RESERVE_PARTICIPATION_SENAT, /ensemble de son groupe/);
  assert.match(RESERVE_PARTICIPATION_SENAT, /ne se compare pas/);
  for (const texte of [RESERVE_PARTICIPATION_AN, METHODE_CENSURE, RESERVE_PARTICIPATION_SENAT]) {
    assert.doesNotMatch(texte, /[—–;]/, "style du site : ni tiret long ni point-virgule");
  }
});

test("la réserve est affichée au contact du chiffre, sur les fiches et sur /elus", () => {
  const fiche = lire("app/elus/[id]/page.tsx");
  const an = fiche.slice(fiche.indexOf('titre="Participation aux scrutins publics"'));
  assert.ok(an.indexOf("{RESERVE_PARTICIPATION_AN}") > 0);
  assert.ok(
    an.indexOf("{RESERVE_PARTICIPATION_AN}") < an.indexOf("</Card>"),
    "la réserve AN est dans la carte Participation",
  );
  const senat = fiche.slice(fiche.indexOf('titre="Participation aux scrutins publics du Sénat"'));
  assert.ok(senat.indexOf("{RESERVE_PARTICIPATION_SENAT}") > 0);
  assert.ok(senat.indexOf("{RESERVE_PARTICIPATION_SENAT}") < senat.indexOf("</Card>"));

  const elus = lire("app/elus/page.tsx");
  assert.match(elus, /\{RESERVE_PARTICIPATION_AN\}/);
  assert.match(elus, /\{RESERVE_PARTICIPATION_SENAT\}/);
  assert.match(elus, /\{METHODE_CENSURE\}/);

  const comprendre = lire("app/comprendre/page.tsx");
  assert.match(comprendre, /id="participation"/);
  assert.match(comprendre, /\{METHODE_CENSURE\}/);
  assert.match(comprendre, /\{RESERVE_PARTICIPATION_SENAT\}/);
});
