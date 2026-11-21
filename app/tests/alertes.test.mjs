// Alertes (lib/queries/accueil.ts, lib/queries/alertes.ts) et carte des
// rejets de /financement (lib/rejets-campagne.ts) : l'accueil ne nomme
// aucune personne, aucun compte de campagne n'est servi comme alerte, et
// l'export porte la date du fait à côté de la date de calcul. Décisions du
// propriétaire des 20 et 21/11/2026. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
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
  // Représentant inscrit à titre individuel : sa dénomination AGORA est le
  // nom d'une personne physique (relecture du 21/11/2026).
  alerte("lobbying_defaut_declaration:H900000001", "lobbying_defaut_declaration", "haute",
    "Défaut de déclaration lobbying : DUPONT Jeanne"),
  alerte("A1-RP-depute", "A1_hatvp_retard_presume", "moyenne",
    "1 déclaration(s) HATVP présumée(s) en retard"),
  alerte("LOB-INC-1", "lobbying_declaration_incomplete", "moyenne", "Déclaration incomplète — SOCIÉTÉ Y"),
  alerte("FIN-PARTI-DEP-2024-1", "financement_parti_dependance_aide", "info",
    "Parti financé à 99 % par l'aide publique — ENSEMBLE !"),
];

const NOMINATIFS_PERSONNES = new Set([
  "A1_hatvp_non_deposee",
  "financement_campagne_rejetee",
  "financement_campagne_reformee",
  "lobbying_defaut_declaration",
]);

const RETIRES = ["financement_campagne_rejetee", "financement_campagne_reformee", "A1_hatvp_retard_presume"];

await baseDeTest((db) => {
  creerTables(db, ["alertes"]);
  inserer(db, "alertes", STOCK);
});
const { SQL_ALERTES_ACCUEIL, TYPES_ALERTES_ACCUEIL } = await importer("lib/queries/accueil");
const { getAlertesToutes, getAlertesPage, getAlertesStats, getAlertesTypes, getAlertesExport, TYPES_ALERTES_RETIRES } =
  await importer("lib/queries/alertes");
const { carteRejets, URL_SOURCE_REJETS, URL_DECISIONS_CONSEIL_CONSTITUTIONNEL } =
  await importer("lib/rejets-campagne");

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
    assert.doesNotMatch(l.titre, /KOUASSI|GUERAUD|FEROUSSIER|DUPONT/);
  }
  // Aucune haute ne reste (toutes peuvent nommer) : une moyenne, une info.
  assert.deepEqual(
    lignes.map((l) => l.id),
    ["LOB-INC-1", "A1-EC-commune"],
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
  assert.equal(parId.get("LOB-INC-1").date_fait, null);
  assert.equal(parId.get("LOB-INC-1").date_calcul, CALCUL);
  assert.ok(getAlertesPage({ page: 1 }).alertes.every((a) => "date_fait" in a));
});

test("accueil : un défaut de lobbying au nom d'une personne physique n'y entre pas", () => {
  const lignes = alertesAccueil([
    alerte("lobbying_defaut_declaration:H900000001", "lobbying_defaut_declaration", "haute",
      "Défaut de déclaration lobbying : DUPONT Jeanne"),
  ]);
  assert.deepEqual(lignes, []);
  assert.ok(!TYPES_ALERTES_ACCUEIL.includes("lobbying_defaut_declaration"));
});

test("lecture : un type retiré resté en base n'est servi nulle part", () => {
  // Un pipeline qui échoue avant sa purge laisse ses anciennes lignes : la
  // lecture les écarte quand même, liste, page, filtre, compteurs et export.
  assert.deepEqual([...TYPES_ALERTES_RETIRES].sort(), [...RETIRES].sort());
  const servis = [
    ...getAlertesToutes(),
    ...getAlertesPage({ page: 1 }).alertes,
    ...getAlertesExport().alertes,
  ];
  assert.ok(servis.length > 0);
  for (const a of servis) assert.ok(!RETIRES.includes(a.type), a.id);
  for (const type of RETIRES) {
    assert.equal(getAlertesPage({ type }).total, 0, type);
  }
  assert.ok(getAlertesTypes().every((t) => !RETIRES.includes(t.type)));
  assert.ok(getAlertesExport().types.every((t) => !RETIRES.includes(t.type)));
  const attendu = STOCK.filter((a) => !RETIRES.includes(a.type)).length;
  assert.equal(getAlertesStats().total, attendu);
  assert.equal(getAlertesToutes().length, attendu);
});

test("/financement : la carte des rejets est un agrégat sans nom, aux liens fixes", () => {
  // Valeurs de v_campagnes_2024_par_decision, famille « rejete » (base du
  // 20/11/2026 : 85 rejets sur 3 136 comptes déposés).
  const carte = carteRejets(
    { nb: 85, depenses_retenues: 31_000.5, remboursement_etat: 0 },
    3136,
    85 / 3136,
  );
  assert.match(carte.titre, /^85 comptes de campagne rejetés par la CNCCFP/);
  assert.match(carte.detail, /^85 comptes rejetés sur 3\s136 comptes déposés \(2,71\s?%\)/u);
  assert.match(carte.detail, /la CNCCFP saisit le juge de l'élection, le Conseil constitutionnel pour les législatives/);
  assert.match(carte.detail, /art\. L\. 52-15 et LO 136-1/);
  assert.match(carte.detail, /Ce fichier ne dit pas leur issue\./);
  assert.match(carte.baseLegale, /tous les candidats aux élections législatives/);
  const servi = [carte.titre, carte.detail, carte.regle, carte.baseLegale].join(" ");
  assert.doesNotMatch(servi, /non définitive|statue pour les députés|au total|fiche d.élu/);
  assert.doesNotMatch(servi, /[;—–]/);
  // Liens fixes, jamais pris dans une alerte nominative.
  assert.equal(carte.source.url, URL_SOURCE_REJETS);
  assert.match(URL_SOURCE_REJETS, /^https:\/\/www\.data\.gouv\.fr\/datasets\/elections-legislatives/);
  assert.equal(carte.juge.url, URL_DECISIONS_CONSEIL_CONSTITUTIONNEL);
  assert.match(URL_DECISIONS_CONSEIL_CONSTITUTIONNEL, /^https:\/\/www\.conseil-constitutionnel\.fr\//);
  // Aucune famille « rejete » : 0, sans montant inventé.
  const vide = carteRejets(null, 3136, 0);
  assert.match(vide.titre, /^0 comptes/);
  assert.doesNotMatch(vide.detail, /Dépenses retenues/);
});

test("/financement : la page lit la carte, ni alerte de rejet ni code de décision", () => {
  const page = readFileSync(new URL("../src/app/financement/page.tsx", import.meta.url), "utf8");
  const requetes = readFileSync(new URL("../src/lib/queries/financement.ts", import.meta.url), "utf8");
  assert.match(page, /carteRejets\(familleRejete, comptesDeposes/);
  assert.doesNotMatch(page, /alertesRejets|cle: "decision", entete: "Décision"/);
  assert.doesNotMatch(requetes, /FROM alertes\s+WHERE type = 'financement_campagne_rejetee'/);
  assert.doesNotMatch(requetes, /remboursement_etat, decision\b/);
});
