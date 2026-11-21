// Page /donnees-personnelles : durées réelles et formulations exactes (audit
// des pages du 20/11/2026, F2 et R9). Les durées figées ici sont celles
// relevées sur le serveur le 21/11/2026 (logrotate de nginx, de fail2ban, du
// pare-feu et de rsyslog, RETENTION_JOURS de ft-audience-serie,
// RETENTION_RAPPORTS_JOURS de ft-audience). Si l'une change sur le serveur,
// la page et ce test changent ensemble.
// Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const SOURCE = readFileSync(
  new URL("../src/app/donnees-personnelles/page.tsx", import.meta.url),
  "utf8",
);

/** Texte servi : commentaires, balises et espaces JSX retirés. */
const TEXTE = SOURCE.replace(/\/\*[\s\S]*?\*\//g, "")
  .replace(/(^|[^:"'\w])\/\/.*$/gm, "$1")
  .replace(/\{" "\}/g, " ")
  .replace(/<[^>]+>/g, " ")
  .replace(/&apos;/g, "'")
  .replace(/\s+/g, " ")
  .replace(/ ([,.)])/g, "$1");

/** Paragraphes et éléments de liste, en texte servi. */
const BLOCS = SOURCE.split(/<\/?(?:p|li)>/).map((b) =>
  b
    .replace(/\{" "\}/g, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&apos;/g, "'")
    .replace(/\s+/g, " "),
);

test("F2 : aucune durée de plus d'un an n'est dite inférieure à la fourchette de la CNIL", () => {
  assert.doesNotMatch(TEXTE, /inférieure à la fourchette/);
  assert.doesNotMatch(TEXTE, /2021-122/);
  for (const bloc of BLOCS) {
    if (/400 jours|cinq ans|deux ans/.test(bloc)) {
      assert.doesNotMatch(bloc, /six mois|un an admise/);
    }
  }
});

test("F2 : chaque durée publiée est celle relevée sur le serveur", () => {
  // access.log et error.log : daily, rotate 52.
  assert.match(TEXTE, /Conservation : 52 jours, plus la journée en cours, puis suppression automatique\./);
  // fail2ban, ufw, rsyslog : weekly, rotate 4 ; journald : 1 mois.
  assert.match(TEXTE, /Ils sont conservés cinq semaines au plus\./);
  // audience.log : daily, rotate 400.
  assert.match(TEXTE, /Conservation : 400 jours, plus la journée en cours, puis suppression automatique\./);
  // serie.sqlite : RETENTION_JOURS=1825 ; rapports : RETENTION_RAPPORTS_JOURS=730.
  assert.match(TEXTE, /sont conservés cinq ans dans une base qui ne contient aucune adresse IP ni aucun identifiant de navigateur de visiteur\./);
  assert.match(TEXTE, /Les rapports quotidiens tirés de la même mesure sont conservés deux ans\./);
  assert.match(TEXTE, /Les durées ci-dessus sont des choix de l'éditeur/);
});

test("R9 : le journal tronqué est dit pseudonymisé, pas anonyme", () => {
  assert.doesNotMatch(TEXTE, /par construction/);
  assert.doesNotMatch(TEXTE, /ne permet plus de remonter/);
  assert.match(TEXTE, /Ce journal est pseudonymisé, il n'est pas anonyme : croisée avec l'heure, la page demandée et l'identifiant du navigateur, l'adresse tronquée peut encore rapprocher les requêtes d'un même appareil\./);
  assert.match(TEXTE, /est pseudonymisé et non anonyme : les mêmes droits s'y exercent\./);
});

test("R9 : le repli sur le journal de sécurité est décrit tel qu'il est", () => {
  assert.match(TEXTE, /Ils restent réglés pour lire le journal de sécurité à sa place/);
  assert.match(TEXTE, /Ce repli n'a servi que pour les 19 et 20 août 2026, avant la mise en place du journal d'audience\./);
});

test("R9 : le périmètre des personnes concernées est complet", () => {
  assert.doesNotMatch(TEXTE, /exclusivement des données de responsables publics/);
  assert.match(TEXTE, /les responsables publics qui déposent des déclarations auprès de la HATVP, élus ou non/);
  assert.match(TEXTE, /les candidats aux élections législatives de 2024, élus ou non/);
  assert.match(TEXTE, /sans aucun nom, et aucune alerte ne nomme un candidat\./);
  assert.match(TEXTE, /les personnes nommées au Journal officiel, par le titre des mesures nominatives/);
  assert.match(TEXTE, /parfois des personnes qui exercent en nom propre\./);
});

test("Les phrases corrigées suivent le style du site", () => {
  const corrigees = BLOCS.filter((b) =>
    /plus la journée en cours|pseudonymisé|Repli sur le journal|Statistiques produites|choix de l'éditeur|élus ou non|nommées au Journal officiel|exercent en nom propre/.test(b),
  );
  assert.ok(corrigees.length >= 8, `blocs corrigés trouvés : ${corrigees.length}`);
  for (const bloc of corrigees) {
    assert.doesNotMatch(bloc, /[—–;…]/, bloc);
  }
});
