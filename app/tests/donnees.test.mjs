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
  // S37 : liste de décrets tenue à la main ; S16 : EXERCICE_COMPTES ;
  // S31 : constantes relevées à la main (ingest_trainvie.py).
  for (const id of ["S16", "S20", "S21", "S23", "S25", "S29", "S31", "S37", "S50", "S51"]) {
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

/* ------------------- règle des niveaux, aux bornes exactes ------------------- */

const JOUR = 86_400_000;
/** Instant (midi UTC, donc même jour civil à Paris) `jours` après `debut`. */
const apres = (debut, jours) => new Date(Date.parse(`${debut}T12:00:00Z`) + jours * JOUR);
const evalue = (id, debut, jours) => evalueFraicheur(id, debut, apres(debut, jours));

test("niveaux : « à jour » JUSQU'AU seuil de retard inclus, puis chaque bande à son jour près", () => {
  // S18 Sirene, 40/55 jc : bande de surveillance de 15 jours.
  const n = (j) => evalue("S18", "2026-09-30", j).niveau;
  assert.equal(n(40), "a_jour");
  assert.equal(n(41), "a_surveiller");
  assert.equal(n(55), "a_surveiller");
  assert.equal(n(56), "en_retard");
  assert.equal(n(70), "en_retard"); // alerte + bande
  assert.equal(n(71), "attente_edition");
  assert.equal(evalue("S18", "2026-09-30", 0).ageJours, 0);
  // Donnée datée du futur (horloge du serveur amont en avance) : âge 0, pas négatif.
  assert.equal(evalueFraicheur("S18", "2026-10-02", apres("2026-09-30", 0)).ageJours, 0);
});

test("l'âge se compte au jour civil de PARIS, pas en UTC", () => {
  // S40, 6/12 jc. 09/11/2026 23 h 30 UTC = 10/11 00 h 30 à Paris : 7 jours.
  const f = evalueFraicheur("S40", "2026-11-03", new Date("2026-11-09T23:30:00Z"));
  assert.equal(f.ageJours, 7);
  assert.equal(f.niveau, "a_surveiller");
  assert.equal(evalueFraicheur("S40", "2026-11-03", new Date("2026-11-09T22:30:00Z")).ageJours, 6);
});

/* --------------------- jours ouvrés : week-ends et fériés --------------------- */

const ouvres = (debut, fin) => evalueFraicheur("S2", debut, new Date(`${fin}T12:00:00Z`)).ageJours;

test("jours ouvrés : ni le samedi ni le dimanche", () => {
  assert.equal(ouvres("2026-11-06", "2026-11-07"), 0); // vendredi → samedi
  assert.equal(ouvres("2026-11-06", "2026-11-08"), 0); // → dimanche
  assert.equal(ouvres("2026-11-06", "2026-11-09"), 1); // → lundi
  assert.equal(ouvres("2026-11-02", "2026-11-06"), 4); // lundi → vendredi
});

// Les onze fériés légaux, chacun pris un jour de semaine : de la veille
// ouvrée au férié, 0 jour ; au lendemain ouvré, 1. Pâques 2026 : 05/04 ;
// Pâques 2027 : 28/03 (Meeus/Butcher).
const FERIES = [
  ["Jour de l'an 2027 (vendredi)", "2026-12-31", "2027-01-01", "2027-01-04"],
  ["Lundi de Pâques 2026", "2026-04-03", "2026-04-06", "2026-04-07"],
  ["Lundi de Pâques 2027", "2027-03-26", "2027-03-29", "2027-03-30"],
  ["Fête du Travail 2026 (vendredi)", "2026-04-30", "2026-05-01", "2026-05-04"],
  ["Victoire 1945 2026 (vendredi)", "2026-05-07", "2026-05-08", "2026-05-11"],
  ["Ascension 2026 (jeudi 14/05)", "2026-05-13", "2026-05-14", "2026-05-15"],
  ["Lundi de Pentecôte 2026 (25/05)", "2026-05-22", "2026-05-25", "2026-05-26"],
  ["Fête nationale 2026 (mardi)", "2026-07-13", "2026-07-14", "2026-07-15"],
  ["Assomption 2025 (vendredi)", "2025-08-14", "2025-08-15", "2025-08-18"],
  ["Toussaint 2027 (lundi)", "2027-10-29", "2027-11-01", "2027-11-02"],
  ["Armistice 2026 (mercredi)", "2026-11-10", "2026-11-11", "2026-11-12"],
  ["Noël 2026 (vendredi)", "2026-12-24", "2026-12-25", "2026-12-28"],
];
for (const [nom, veille, ferie, lendemain] of FERIES) {
  test(`jours ouvrés : ${nom} n'est pas compté`, () => {
    assert.equal(ouvres(veille, ferie), 0);
    assert.equal(ouvres(veille, lendemain), 1);
  });
}

test("jours ouvrés : le dimanche de Pâques et le jeudi qui précède l'Ascension restent ce qu'ils sont", () => {
  assert.equal(ouvres("2026-05-12", "2026-05-13"), 1); // mercredi veille d'Ascension : ouvré
  assert.equal(ouvres("2026-04-02", "2026-04-03"), 1); // Vendredi saint : ouvré en droit commun
});

/* ------------- valeur de chaque seuil, et la raison de chacune ------------- */

/**
 * Les seuils recalibrés le 11/11/2026, chacun avec ce qui le fixe : le cas
 * amont réel qu'il doit laisser « à jour », et le jour exact où il sonne.
 */
function bornes(id, debut, retard, alerte) {
  const f = evalue(id, debut, 0);
  assert.deepEqual([f.unite, f.seuilRetardJours, f.seuilAlerteJours], ["jc", retard, alerte], id);
  assert.equal(evalue(id, debut, retard).niveau, "a_jour", `${id} à ${retard} j`);
  assert.equal(evalue(id, debut, retard + 1).niveau, "a_surveiller", `${id} à ${retard + 1} j`);
  assert.equal(evalue(id, debut, alerte).niveau, "a_surveiller", `${id} à ${alerte} j`);
  assert.equal(evalue(id, debut, alerte + 1).niveau, "en_retard", `${id} à ${alerte + 1} j`);
}

const niveau = (id, d, le) => evalueFraicheur(id, d, new Date(`${le}T12:00:00Z`)).niveau;

test("S7 Datan, 7/14 : publie chaque jour, week-ends compris — une semaine sans mise à jour se signale", () => {
  bornes("S7-DATAN", "2026-10-28", 7, 14);
  // dateMaj figée au 28/10/2026 pendant que l'AN publiait 606 scrutins.
  assert.equal(niveau("S7-DATAN", "2026-10-28", "2026-11-08"), "a_surveiller");
  assert.equal(niveau("S7-DATAN", "2026-10-28", "2026-11-12"), "en_retard");
});

test("S47 IRCOM, 910/970 : la parution la plus tardive observée (903 j) reste « à jour »", () => {
  bornes("S47", "2024-12-31", 910, 970);
  // Revenus 2020 versés le 21/06/2022 : l'édition remplacée (2019) avait 903 j.
  assert.equal(niveau("S47", "2019-12-31", "2022-06-21"), "a_jour");
  // Revenus 2022, versés le 10/06/2024 : 892 j.
  assert.equal(niveau("S47", "2021-12-31", "2024-06-10"), "a_jour");
  assert.equal(niveau("S47", "2024-12-31", "2026-11-08"), "a_jour"); // était « à surveiller »
});

test("S45 DREES, 730/800 : l'année N paraît en décembre N+1 (717 j), signal au 31/12 N+1", () => {
  bornes("S45", "2024-12-31", 730, 800);
  assert.equal(niveau("S45", "2023-12-31", "2025-12-18"), "a_jour"); // parution 2024 : 718 j
  assert.equal(niveau("S45", "2024-12-31", "2026-11-08"), "a_jour"); // était « à surveiller »
});

test("S49 COFOG, 820/900 : diffusion principale Eurostat en février t+2 (~790 j)", () => {
  bornes("S49", "2024-12-31", 820, 900);
  assert.equal(niveau("S49", "2024-12-31", "2027-02-28"), "a_jour"); // fin février t+2 : 789 j
  assert.equal(niveau("S49", "2024-12-31", "2026-11-08"), "a_jour"); // était « à surveiller »
});

test("S48 REI, 560/650 : versé en mai N+1 (~500 j), un REI manquant se voit à l'été", () => {
  bornes("S48", "2025-12-31", 560, 650);
  assert.equal(niveau("S48", "2024-12-31", "2026-05-12"), "a_jour"); // REI 2025 : 497 j
  assert.equal(niveau("S48", "2025-12-31", "2027-07-20"), "a_surveiller"); // 650 : « à jour »
});

/**
 * Les autres lignes : parité avec le référentiel serveur
 * (/etc/france-transparence/fraicheur.conf), dont SEUILS_SOURCES est la
 * copie — dernière synchronisation le 25/08/2026, raison de chaque valeur
 * en commentaire sur sa ligne de lib/fraicheur.ts. Le référentiel n'est pas
 * dans le dépôt : ce tableau en est l'image versionnée, à modifier dans le
 * MÊME geste que fraicheur.conf (docs/ACTIONS-HUMAINES.md).
 */
const PARITE_FRAICHEUR_CONF = [
  ["S3", "jo", 3, 7], ["S2", "jo", 3, 7], ["S1", "jo", 7, 20], ["S4", "jo", 6, 12],
  ["S9", "jo", 10, 20], ["S5-AMO10", "jc", 20, 45], ["S6-ODSEN", "jc", 20, 45],
  ["S35-reforga-admin-etat", "jc", 45, 90], ["S11-annuaire-administration", "jc", 60, 120],
  ["S5-SCRUTINS", "jc", 60, 95], ["S6-DOSLEG", "jc", 60, 95], ["S43", "jc", 20, 35],
  ["S14", "jc", 10, 18], ["S15", "jc", 10, 18], ["S13", "jc", 65, 80], ["S18", "jc", 40, 55],
  ["S17", "jc", 110, 150], ["S41", "jc", 220, 260], ["S20", "jc", 400, 440],
  ["S37", "jc", 400, 440], ["S31", "jc", 450, 550], ["S42", "jc", 520, 600],
  ["S44", "jc", 520, 600], ["S50", "jc", 520, 600], ["S51", "jc", 520, 600],
  ["S22", "jc", 650, 750], ["S21", "jc", 400, 440], ["S46", "jc", 400, 440],
  ["S23", "jc", 760, 850], ["S25", "jc", 850, 950], ["S38", "jc", 730, 820],
  ["S27-geo-api", "jc", 400, 430], ["S29", "jc", 1500, 1800], ["S26", "jc", 1100, 1300],
  ["S27-insee-populations", "jc", 1500, 1650], ["S27-france-geojson", "jc", 3650, 5475],
  ["S16", "jc", 650, 750], ["S40", "jc", 6, 12], ["S52", "jc", 200, 280],
];

test("les 39 autres seuils : parité avec fraicheur.conf (synchronisation du 25/08/2026)", () => {
  assert.equal(PARITE_FRAICHEUR_CONF.length, 39);
  for (const [id, unite, retard, alerte] of PARITE_FRAICHEUR_CONF) {
    const f = evalueFraicheur(id, "2026-01-01", new Date("2026-01-02T12:00:00Z"));
    assert.deepEqual([f.unite, f.seuilRetardJours, f.seuilAlerteJours], [unite, retard, alerte], id);
  }
});
