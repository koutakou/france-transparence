// Définitions des exports CSV (src/lib/exports-csv.ts) : aucune colonne de
// plus que la page ou l'export JSON, une route statique et sa provenance par
// fichier. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {
  CSV_ALERTES,
  CSV_ELUS,
  CSV_TOP_ACHETEURS,
  CSV_TOP_TITULAIRES,
  EXPORTS_CSV,
  cheminProvenance,
} from "../src/lib/exports-csv.ts";
import { documentCsv } from "../src/lib/csv.ts";

const lire = (chemin) => fs.readFileSync(new URL(`../src/${chemin}`, import.meta.url), "utf8");
const cles = (def) => def.colonnes.map((c) => c.cle);

/** Clés `cle: "…"` d'un bloc de source, entre deux marqueurs. */
function clesDuBloc(source, debut, fin) {
  const i = source.indexOf(debut);
  assert.ok(i >= 0, debut);
  const bloc = source.slice(i, fin ? source.indexOf(fin, i + debut.length) : undefined);
  return [...bloc.matchAll(/cle: "(\w+)"/g)].map((m) => m[1]);
}

test("top acheteurs et titulaires : exactement les colonnes du tableau de /marches", () => {
  const tables = lire("components/client/TablesMarches.tsx");
  const cellules = lire("components/ui/CellulesMarches.tsx");
  const montants = clesDuBloc(cellules, "export const COLONNES_MONTANT_TOP", "];");
  const acheteurs = clesDuBloc(tables, "export function TableTopAcheteurs", "export function TableTopTitulaires");
  const titulaires = clesDuBloc(tables, "export function TableTopTitulaires", "export function TableProcedures");
  // Le tableau affiche nb_marches_suspects dans la cellule des montants signalés.
  assert.deepEqual(cles(CSV_TOP_ACHETEURS), [...acheteurs, ...montants, "nb_marches_suspects"]);
  assert.deepEqual(cles(CSV_TOP_TITULAIRES), [...titulaires, ...montants, "nb_marches_suspects"]);
  for (const def of [CSV_TOP_ACHETEURS, CSV_TOP_TITULAIRES]) {
    assert.ok(!cles(def).includes("montant_total"), "montant_total n'est pas affiché");
    assert.ok(!cles(def).includes("dans_sirene"), "dans_sirene n'est pas une colonne affichée");
  }
});

test("top : montant signalé vide quand aucun marché n'est signalé, comme le tableau", () => {
  const ligne = {
    rang: 1,
    siren: "123456789",
    nom: "Acheteur",
    nb_etablissements: 2,
    nb_marches: 10,
    montant_total: 5,
    montant_hors_suspects: 1500000.5,
    nb_marches_suspects: 0,
    montant_suspects: 0,
    dans_sirene: 1,
  };
  const texte = documentCsv(CSV_TOP_ACHETEURS.colonnes, [ligne]);
  assert.equal(
    texte,
    "﻿rang;nom;siren;nb_etablissements;nb_marches;montant_hors_suspects;montant_suspects;nb_marches_suspects\r\n" +
      "1;Acheteur;123456789;2;10;1500000,5;;0\r\n",
  );
});

test("élus : les champs publics compacts de /api/elus.json, rien de plus", () => {
  // Les seules clés que getElusExport écrit (src/lib/queries/donnees.ts).
  const donnees = lire("lib/queries/donnees.ts");
  const ecrites = new Set(["id", "nom", ...[...donnees.matchAll(/\be\.(\w+) = /g)].map((m) => m[1])]);
  assert.deepEqual(new Set(cles(CSV_ELUS)), ecrites);
});

test("alertes : les colonnes lues par getAlertesToutes, rien de plus", () => {
  const alertes = lire("lib/queries/alertes.ts");
  const i = alertes.indexOf("export function getAlertesToutes");
  const select = alertes.slice(i).match(/SELECT ([\s\S]*?)\s+FROM alertes/)[1];
  assert.deepEqual(
    cles(CSV_ALERTES),
    select.split(",").map((s) => s.trim()),
  );
});

test("chaque CSV a sa route statique et sa provenance, sources déclarées", () => {
  const noms = EXPORTS_CSV.map((e) => e.fichier);
  assert.equal(new Set(noms).size, noms.length);
  for (const e of EXPORTS_CSV) {
    assert.match(e.fichier, /^[a-z-]+\.csv$/);
    const base = e.fichier.replace(/\.csv$/, "");
    assert.equal(cheminProvenance(e.fichier), `/api/${base}.provenance.txt`);
    for (const route of [`app/api/${e.fichier}/route.ts`, `app/api/${base}.provenance.txt/route.ts`]) {
      const s = lire(route);
      assert.match(s, /export const dynamic = "force-static";/, route);
    }
    assert.match(lire(`app/api/${e.fichier}/route.ts`), /reponseCsv\(/);
    assert.match(lire(`app/api/${base}.provenance.txt/route.ts`), /reponseProvenance\(/);
    assert.doesNotMatch(`${e.titre} ${e.description}`, /[—–;]/, `style : ${e.fichier}`);
  }
});

test("colonnes : clés uniques et décrites dans chaque export", () => {
  for (const e of EXPORTS_CSV) {
    const k = e.colonnes.map((c) => c.cle);
    assert.equal(new Set(k).size, k.length, e.fichier);
    for (const c of e.colonnes) {
      assert.match(c.cle, /^[a-z0-9_]+$/, `${e.fichier} ${c.cle}`);
      assert.ok(c.description.length > 0, `${e.fichier} ${c.cle}`);
      assert.doesNotMatch(c.description, /[—–;]|(?<![\w_])suspect/, `${e.fichier} ${c.cle}`);
    }
  }
});
