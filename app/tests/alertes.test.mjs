// Alertes (lib/queries/accueil.ts, lib/queries/alertes.ts) : l'accueil ne
// nomme aucune personne, et l'export porte la date du fait à côté de la date
// de calcul. Décisions du propriétaire du 20/11/2026. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import Database from "better-sqlite3";
import { baseDeTest, importer } from "./outils/charger.mjs";
import { inserer } from "./outils/fixtures.mjs";
import { SCHEMA, creerTables } from "./outils/schema.mjs";

const CALCUL = "2026-11-20T23:10:00+00:00";

function alerte(id, type, gravite, titre, dateFait = null) {
  return {
    id,
    type,
    gravite,
    titre,
    detail: null,
    regle: "r",
    base_legale: "b",
    source_url: null,
    date_calcul: CALCUL,
    date_fait: dateFait,
  };
}

// Le stock tel que l'accueil le voyait le 20/11/2026 (titres réels), plus
// les types neufs. Les identifiants nominatifs passent AVANT les autres dans
// l'ordre de tri (`date_calcul DESC, id`) : c'est ainsi que trois candidats
// se retrouvaient en première page.
const STOCK = [
  alerte("A1-ND-feroussier-dsp", "A1_hatvp_non_deposee", "haute",
    "Déclaration non déposée (constat officiel HATVP) — Mme FEROUSSIER", "2026-11-19"),
  alerte("FIN-CAMP-REJ-202409066", "financement_campagne_rejetee", "haute",
    "Compte de campagne rejeté par la CNCCFP, M. KOUASSI Fulgence (décision non définitive : le juge de l'élection statue)"),
  alerte("FIN-CAMP-REF-202408091", "financement_campagne_reformee", "moyenne",
    "Compte de campagne réformé — M. GUERAUD Sébastien"),
  alerte("A1-EC-commune", "A1_hatvp_en_cours_delai_ecoule", "info",
    "12 déclarations au statut « En cours » à la HATVP plus de 2 mois après l'entrée en fonction, mandat « commune »",
    "2026-11-19"),
  alerte("LOB-DEF-1", "lobbying_defaut_declaration", "haute", "Défaut de déclaration — SOCIÉTÉ X"),
  alerte("LOB-INC-1", "lobbying_declaration_incomplete", "moyenne", "Déclaration incomplète — SOCIÉTÉ Y"),
  alerte("FIN-PARTI-DEP-2024-1", "financement_parti_dependance_aide", "info",
    "Parti financé à 99 % par l'aide publique — ENSEMBLE !"),
];

const NOMINATIFS_PERSONNES = new Set([
  "A1_hatvp_non_deposee",
  "financement_campagne_rejetee",
  "financement_campagne_reformee",
]);

await baseDeTest((db) => {
  creerTables(db, ["alertes"]);
  inserer(db, "alertes", STOCK);
});
const { SQL_ALERTES_ACCUEIL, TYPES_ALERTES_ACCUEIL } = await importer("lib/queries/accueil");
const { getAlertesToutes, getAlertesPage } = await importer("lib/queries/alertes");

function alertesAccueil(stock) {
  const db = new Database(":memory:");
  db.exec(SCHEMA.alertes);
  inserer(db, "alertes", stock);
  const lignes = db.prepare(SQL_ALERTES_ACCUEIL).all(...TYPES_ALERTES_ACCUEIL);
  db.close();
  return lignes;
}

test("accueil : aucune alerte nominative de personne physique", () => {
  const lignes = alertesAccueil(STOCK);
  assert.ok(lignes.length > 0);
  for (const l of lignes) {
    assert.ok(!NOMINATIFS_PERSONNES.has(l.type), `${l.type} sur l'accueil`);
    assert.doesNotMatch(l.titre, /KOUASSI|GUERAUD|FEROUSSIER/);
  }
  // Les gravités restent mélangées : 2 hautes au plus, puis moyenne et info.
  assert.deepEqual(
    lignes.map((l) => l.id),
    ["LOB-DEF-1", "LOB-INC-1", "A1-EC-commune"],
  );
});

test("accueil : un stock fait de seuls noms ne montre rien, plutôt qu'un nom", () => {
  const lignes = alertesAccueil(STOCK.filter((a) => NOMINATIFS_PERSONNES.has(a.type)));
  assert.deepEqual(lignes, []);
});

test("accueil : liste blanche, un type inconnu n'y entre pas", () => {
  const lignes = alertesAccueil([alerte("X-1", "nouveau_type_nominatif", "haute", "M. DUPONT")]);
  assert.deepEqual(lignes, []);
  for (const type of NOMINATIFS_PERSONNES) assert.ok(!TYPES_ALERTES_ACCUEIL.includes(type));
});

test("export : date du fait à côté de la date de calcul, null quand la source ne la donne pas", () => {
  const toutes = getAlertesToutes();
  const parId = new Map(toutes.map((a) => [a.id, a]));
  assert.equal(parId.get("A1-EC-commune").date_fait, "2026-11-19");
  assert.equal(parId.get("FIN-CAMP-REJ-202409066").date_fait, null);
  assert.equal(parId.get("FIN-CAMP-REJ-202409066").date_calcul, CALCUL);
  assert.ok(getAlertesPage({ page: 1 }).alertes.every((a) => "date_fait" in a));
});
