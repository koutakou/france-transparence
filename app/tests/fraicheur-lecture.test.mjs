// Ce qui est relatif à « maintenant » (lib/fraicheur.ts, lib/lecture.ts,
// lib/periodes.ts) : le site est un export statique, figé du 08/11/2026 04:26
// UTC au moins jusqu'au 11/11 (trois cycles serveur manqués). Tout âge, état
// « à jour » ou fenêtre « 30 derniers jours » calculé au build y restait
// affiché comme vrai. Dates réelles : /api/meta.json servi le 11/11/2026
// (genere_le 2026-11-08T04:26:01Z). Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import Database from "better-sqlite3";
import { importer } from "./outils/charger.mjs";

const { evalueFraicheur, phraseFraicheur, syntheseFraicheur, phraseSynthese, ancrageCalcul } =
  await importer("lib/fraicheur");
const {
  ageRevolu,
  formatInstantFr,
  htmlBandeauSiteFige,
  ID_BANDEAU_SITE_FIGE,
  instantDeLecture,
  SCRIPT_BANDEAU_SITE_FIGE,
  SEUIL_SITE_FIGE_HEURES,
} = await importer("lib/lecture");
const { fenetreArreteeSql } = await importer("lib/periodes");

const CONSTRUIT = Date.parse("2026-11-08T04:26:01.375Z"); // genere_le servi
const LECTURE = Date.parse("2026-11-11T14:09:00Z"); // relevé de l'audit
const H = 3_600_000;

/* ---------------------------- fraîcheur ----------------------------- */

// date_donnees servies le 11/11/2026 (site du 08/11), dont les deux sources
// dont l'état était devenu faux à la lecture.
const SERVIES = [
  { source_id: "S18", nom: "Sirene", date_donnees: "2026-09-30" },
  { source_id: "S40", nom: "Registre UE", date_donnees: "2026-11-03" },
  { source_id: "S2", nom: "BOAMP", date_donnees: "2026-11-08" },
  { source_id: "S46", nom: "Recettes PLF 2025", date_donnees: "2024-10-11" },
];

test("le même calcul dit « à jour » au build et « à surveiller » trois jours plus tard", () => {
  const auBuild = (id, d) => evalueFraicheur(id, d, new Date(CONSTRUIT)).niveau;
  const aLecture = (id, d) => evalueFraicheur(id, d, new Date(LECTURE)).niveau;
  assert.equal(auBuild("S18", "2026-09-30"), "a_jour"); // 39 j, seuil 40
  assert.equal(aLecture("S18", "2026-09-30"), "a_surveiller"); // 42 j
  assert.equal(auBuild("S40", "2026-11-03"), "a_jour"); // 5 j, seuil 6
  assert.equal(aLecture("S40", "2026-11-03"), "a_surveiller"); // 8 j
  // BOAMP, jours ouvrés : 0 au build, 2 le 11/11 (09 et 10/11 ; le 11/11 est férié).
  assert.equal(evalueFraicheur("S2", "2026-11-08", new Date(CONSTRUIT)).ageJours, 0);
  assert.equal(evalueFraicheur("S2", "2026-11-08", new Date(LECTURE)).ageJours, 2);
});

test("la synthèse se recompte à la date passée, et dit laquelle", () => {
  const auBuild = syntheseFraicheur(SERVIES, new Date(CONSTRUIT));
  const aLecture = syntheseFraicheur(SERVIES, new Date(LECTURE));
  assert.equal(auBuild.parNiveau.a_jour, 3);
  assert.equal(aLecture.parNiveau.a_jour, 1);
  assert.equal(aLecture.parNiveau.a_surveiller, 2);
  assert.deepEqual(aLecture.enAttente.map((e) => e.source.source_id), ["S46"]);
  assert.match(phraseSynthese(aLecture), /^1 source sur 4 est à jour .*, 2 à surveiller, 1 en attente/);
  assert.equal(
    ancrageCalcul(CONSTRUIT, CONSTRUIT),
    "État calculé le 08/11/2026, jour de construction du site",
  );
  assert.equal(
    ancrageCalcul(LECTURE, CONSTRUIT),
    "État recalculé le 11/11/2026, date de votre lecture (site construit le 08/11/2026)",
  );
});

test("la phrase du badge date son âge : vraie lue sans JavaScript après le build", () => {
  const f = evalueFraicheur("S18", "2026-09-30", new Date(CONSTRUIT));
  assert.match(phraseFraicheur("2026-09-30", f, new Date(CONSTRUIT)), /soit 39 jours au 08\/11\/2026/);
  const g = evalueFraicheur("S46", "2024-10-11", new Date(CONSTRUIT));
  assert.match(phraseFraicheur("2024-10-11", g, new Date(CONSTRUIT)), /— 758 jours au 08\/11\/2026,/);
});

/* ------------- horloge du lecteur antérieure à la construction ------------- */

test("instantDeLecture : jamais avant la construction de la page", () => {
  assert.equal(instantDeLecture(LECTURE, CONSTRUIT), LECTURE);
  assert.equal(instantDeLecture(CONSTRUIT, CONSTRUIT), CONSTRUIT);
  const an2020 = Date.parse("2020-01-01T12:00:00Z");
  assert.equal(instantDeLecture(an2020, CONSTRUIT), CONSTRUIT);
  assert.equal(instantDeLecture(Number.NaN, CONSTRUIT), CONSTRUIT);
  // Lu au 01/01/2020 sans borne : « 4 sources sur 4 » à jour, 51 ans au lieu de 57.
  const lu = new Date(instantDeLecture(an2020, CONSTRUIT));
  assert.equal(syntheseFraicheur(SERVIES, lu).parNiveau.a_jour, 3);
  assert.equal(ageRevolu("1968-11-10", lu), 57);
  assert.equal(syntheseFraicheur(SERVIES, new Date(an2020)).parNiveau.a_jour, 4);
});

test("useHorloge borne l'horloge par instantDeLecture", () => {
  assert.match(lire("lib/useHorloge.ts"), /return instantDeLecture\(\s*useSyncExternalStore\(/);
});

/* ---------------------------- âge révolu ---------------------------- */

test("âge révolu : celui du jour de lecture, à l'heure de Paris", () => {
  // SEN-21674D, née le 10/11/1968 : « 57 ans » servis le 11/11/2026.
  assert.equal(ageRevolu("1968-11-10", new Date(CONSTRUIT)), 57);
  assert.equal(ageRevolu("1968-11-10", new Date(LECTURE)), 58);
  // 23 h 30 UTC le 09/11 : déjà le 10/11 à Paris.
  assert.equal(ageRevolu("1968-11-10", new Date("2026-11-09T23:30:00Z")), 58);
  assert.equal(ageRevolu("1968-11-10", new Date("2026-11-09T22:30:00Z")), 57);
  assert.equal(ageRevolu("2000-02-29", new Date("2026-02-28T12:00:00Z")), 25);
  assert.equal(ageRevolu("2000-02-29", new Date("2026-03-01T12:00:00Z")), 26);
  assert.equal(ageRevolu(null, new Date(LECTURE)), null);
  assert.equal(ageRevolu("2030-01-01", new Date(LECTURE)), null);
});

/* --------------------- bandeau « site non reconstruit » --------------------- */

/**
 * Joue le script EN LIGNE tel qu'il part dans la page, sur un DOM minimal et
 * une horloge réglable ; `minute()` rejoue la minuterie qu'il a posée.
 */
function bandeau(construitLe, maintenant) {
  const anciennete = { textContent: "" };
  const el = {
    hidden: true,
    getAttribute: (nom) => (nom === "data-construit-le" ? String(construitLe) : null),
    querySelector: (sel) => (sel === "[data-anciennete]" ? anciennete : null),
  };
  const horloge = { t: maintenant };
  const minuteries = [];
  vm.runInNewContext(SCRIPT_BANDEAU_SITE_FIGE, {
    document: { getElementById: (id) => (id === ID_BANDEAU_SITE_FIGE ? el : null) },
    Date: { now: () => horloge.t },
    setInterval: (f, ms) => minuteries.push([f, ms]),
    Number,
    Math,
  });
  const etat = () => ({ visible: !el.hidden, anciennete: anciennete.textContent });
  return {
    etat,
    minuteries,
    avancer(ms) {
      horloge.t += ms;
      for (const [f] of minuteries) f();
      return etat();
    },
  };
}
const jouerBandeau = (c, m) => bandeau(c, m).etat();

test("bandeau : affiché sur le site figé lu le 11/11, avec son ancienneté", () => {
  assert.deepEqual(jouerBandeau(CONSTRUIT, LECTURE), { visible: true, anciennete: "3 jours" });
});

test("bandeau : masqué en régime normal, affiché passé le seuil", () => {
  assert.equal(SEUIL_SITE_FIGE_HEURES, 36);
  assert.equal(jouerBandeau(CONSTRUIT, CONSTRUIT + 20 * H).visible, false);
  assert.equal(jouerBandeau(CONSTRUIT, CONSTRUIT + 36 * H - 1).visible, false);
  assert.deepEqual(jouerBandeau(CONSTRUIT, CONSTRUIT + 36 * H), { visible: true, anciennete: "1 jour" });
});

test("bandeau : horloge du lecteur antérieure au build — jamais affiché", () => {
  assert.equal(jouerBandeau(CONSTRUIT, CONSTRUIT - 72 * H).visible, false);
  assert.equal(jouerBandeau(CONSTRUIT, Date.parse("2020-01-01T12:00:00Z")).visible, false);
});

test("bandeau : un onglet resté ouvert le voit apparaître, puis vieillir", () => {
  const b = bandeau(CONSTRUIT, CONSTRUIT + 35 * H);
  assert.deepEqual(b.minuteries.map(([, ms]) => ms), [60_000]);
  assert.equal(b.etat().visible, false);
  assert.deepEqual(b.avancer(H), { visible: true, anciennete: "1 jour" });
  assert.deepEqual(b.avancer(13 * H), { visible: true, anciennete: "2 jours" });
});

test("bandeau : aucun appel réseau, aucun stockage, aucun cookie", () => {
  assert.doesNotMatch(
    SCRIPT_BANDEAU_SITE_FIGE,
    /fetch|XMLHttpRequest|sendBeacon|WebSocket|Storage|cookie|indexedDB|import\(|src=/i,
  );
});

test("bandeau : masqué dans le HTML, daté de la construction", () => {
  const html = htmlBandeauSiteFige(CONSTRUIT);
  assert.match(html, new RegExp(`<p id="${ID_BANDEAU_SITE_FIGE}" hidden data-construit-le="${CONSTRUIT}"`));
  assert.match(html, /Page construite le 08\/11\/2026 à 05h26/);
  assert.equal(formatInstantFr(CONSTRUIT), "08/11/2026 à 05h26");
  assert.ok(html.endsWith(`<script>${SCRIPT_BANDEAU_SITE_FIGE}</script>`));
});

/* ------------------------ fenêtre de 30 jours ------------------------ */

test("fenêtre de 30 jours arrêtée à la date des données, pas au jour du build", () => {
  const db = new Database(":memory:");
  db.exec("CREATE TABLE t (d TEXT)");
  const ins = db.prepare("INSERT INTO t VALUES (?)");
  // DECP au 07/11/2026 : bornes ]08/10 ; 07/11].
  for (const d of ["2026-10-08", "2026-10-09", "2026-11-07", "2026-11-08"]) ins.run(d);
  const n = db.prepare(`SELECT COUNT(*) AS n FROM t WHERE ${fenetreArreteeSql("d", 30)}`);
  assert.equal(n.get({ fin: "2026-11-07" }).n, 2);
});

/* -------- gardes documentaires : les formes d'avant ne reviennent pas -------- */

const lire = (chemin) => fs.readFileSync(new URL(`../src/${chemin}`, import.meta.url), "utf8");

/** [fichier, motif interdit, pourquoi] */
const INTERDITS = [
  ["app/donnees/page.tsx", /aujourd’hui − date des données/, "l'âge est daté du jour du calcul"],
  ["app/donnees/page.tsx", /reconstruits chaque matin|instantané\s+quotidien daté/, "un export daté n'affirme pas sa reconstruction"],
  ["app/donnees/page.tsx", /J−1|jour même/, "« fréquence déclarée », pas un relatif figé au build"],
  ["app/marches/page.tsx", /\(J-1\)|"jour même"|estJourDeConstruction/, "la date du badge suffit"],
  ["app/page.tsx", /estVeille|"J-1"/, "« J-1 » évalué au build restait affiché sur un site figé"],
  ["app/api/meta.json/route.ts", /aujourd'hui − date_donnees|publiée en amont/, "âge daté de genere_le, rien affirmé de l'amont"],
  ["app/comprendre/page.tsx", /n’était parue/, "le site ne vérifie pas l'amont"],
  ["lib/queries/accueil.ts", /date\('now'/, "fenêtres arrêtées à la date des données"],
  ["lib/queries/marches.ts", /date\('now'/, "fenêtres arrêtées à la date des données"],
  ["lib/queries/elus.ts", /julianday\('now'\)/, "âge moyen arrêté à la date des données"],
  ["app/elus/[id]/page.tsx", /calculeAge|new Date\(\)/, "l'âge se recalcule à la lecture"],
  ["lib/queries/donnees.ts", /new Date\(\)/, "l'instant du calcul est passé par l'appelant, qui le date"],
];

for (const [fichier, motif, pourquoi] of INTERDITS) {
  test(`${fichier} : ${pourquoi}`, () => {
    assert.doesNotMatch(lire(fichier), motif);
  });
}

test("titre d'accueil (titre par défaut) : 70 caractères au plus, comme tout titre de partage", async () => {
  const { LONGUEUR_TITRE_PARTAGE } = await importer("lib/seo");
  const titre = /const TITRE_DEFAUT =\s*"([^"]+)"/.exec(lire("app/layout.tsx"))?.[1];
  assert.ok(titre, "TITRE_DEFAUT introuvable dans layout.tsx");
  assert.ok(titre.length <= LONGUEUR_TITRE_PARTAGE, `${titre.length} caractères`);
});
