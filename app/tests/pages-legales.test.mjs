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
  // btmp, wtmp : weekly, rotate 4 depuis le 21/11/2026, transition dite.
  assert.match(TEXTE, /Les registres des connexions au serveur, refusées ou acceptées, suivent la même règle depuis le 21\/11\/2026\./);
  assert.match(TEXTE, /Les fichiers ouverts avant cette date ne sortent qu'au terme de quatre rotations hebdomadaires : d'ici là, ces registres contiennent aussi des connexions de plus de cinq semaines\./);
  // lastlog : sans rotation, comptes d'administration seulement.
  assert.match(TEXTE, /Le serveur garde enfin, sans limite de durée, la date et l'adresse de la dernière connexion de chaque compte d'administration\. Ce registre ne concerne aucun visiteur\./);
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
  assert.doesNotMatch(TEXTE, /très difficile/);
  assert.match(TEXTE, /Seule, l'adresse tronquée ne désigne plus un abonné\./);
  assert.match(TEXTE, /Surtout, pendant 52 jours, le journal de sécurité contient les mêmes requêtes avec l'adresse complète\. L'éditeur ne les rapproche pas, ce rapprochement reste pourtant possible, et le journal d'audience reste soumis au RGPD\./);
});

test("R9 : la troncature IPv6 est décrite comme la règle nginx l'applique", () => {
  // La map garde les trois premiers groupes ÉCRITS : avec « :: » dans ces
  // groupes, elle peut en garder un de plus que les 48 premiers bits.
  assert.doesNotMatch(TEXTE, /tout ce qui suit les 48 premiers bits/);
  assert.match(TEXTE, /et pour une adresse IPv6 tout ce qui suit ses trois premiers groupes écrits, qui en représentent en général les 48 premiers bits\)/);
});

test("R9 : le repli sur le journal de sécurité est dit retiré", () => {
  // Retiré sur le serveur le 21/11/2026 : ft-audience-serie et ft-audience ne
  // lisent plus que audience.log.
  assert.doesNotMatch(TEXTE, /restent réglés pour lire le journal de sécurité/);
  assert.match(TEXTE, /Aucun repli sur le journal de sécurité : depuis le 21\/11\/2026, les outils de statistiques ne lisent que le journal d'audience\. Une journée absente de ce journal n'est pas calculée\./);
  assert.match(TEXTE, /Seules les journées des 19 et 20 août 2026, antérieures à la mise en place du journal d'audience, restent dans la série avec les chiffres tirés à l'époque du journal de sécurité\./);
});

test("R9 : le périmètre des personnes concernées est complet", () => {
  assert.doesNotMatch(TEXTE, /exclusivement des données de responsables publics/);
  assert.match(TEXTE, /les responsables publics qui déposent des déclarations auprès de la HATVP, élus ou non/);
  assert.match(TEXTE, /les candidats aux élections législatives de 2024, élus ou non/);
  assert.match(TEXTE, /sans aucun nom, et aucune alerte ne nomme un candidat\./);
  assert.match(TEXTE, /les personnes nommées au Journal officiel, par le titre des mesures nominatives/);
  assert.match(TEXTE, /parfois des personnes qui exercent en nom propre\./);
  assert.match(TEXTE, /inscrits au répertoire de la HATVP ou au registre de transparence de l'Union européenne, sous la dénomination qu'ils y déclarent\./);
  assert.match(TEXTE, /les entrepreneurs individuels titulaires de marchés publics, sous le nom que publient les données essentielles de la commande publique \(DECP\)/);
  // L'en-tête annonce le même périmètre que la liste.
  assert.match(TEXTE, /personnes nommées au Journal officiel, représentants d'intérêts, entrepreneurs individuels titulaires de marchés publics\./);
});

test("B : les catégories de données publiées forment une liste à puces, sans en retirer aucune", () => {
  const items = BLOCS.map((b) => b.trim());
  for (const attendu of [
    "nom et prénom",
    "date de naissance et âge",
    "sexe",
    "profession ou catégorie socio-professionnelle",
    "mandats, fonctions et dates de mandat",
    "circonscription ou collectivité de rattachement",
    "groupe et appartenance politiques",
    "votes et activités parlementaires",
    "existence et date des déclarations HATVP, ainsi que les constats publiés par elle",
    "les montants déclarés dans les comptes de partis et de campagne",
  ]) {
    assert.ok(items.includes(attendu), `élément de liste manquant : ${attendu}`);
  }
  assert.ok(
    items.some((b) => /^le contenu des déclarations d'intérêts publiées par la HATVP \(mandats et fonctions électives, .* fonctions bénévoles et observations\)$/.test(b)),
    "contenu des déclarations d'intérêts, avec ses rubriques",
  );
  assert.ok(
    items.includes("les montants de rémunération déclarés dans ces déclarations, année par année, reproduits mot pour mot et datés"),
    "montants de rémunération",
  );
  assert.ok(!items.some((b) => /qui y figurent/.test(b)), "« y » sans antécédent dans la puce");
  assert.match(TEXTE, /Aucune coordonnée privée n'est publiée : ni adresse postale personnelle, ni téléphone, ni adresse électronique, ni donnée relevant de l'article 9 du RGPD\./);
  assert.ok(!BLOCS.some((b) => /nom et prénom.*comptes de partis/.test(b)), "plus d'énumération en une seule phrase");
});

test("Les phrases corrigées suivent le style du site", () => {
  const corrigees = BLOCS.filter((b) =>
    /plus la journée en cours|pseudonymisé|Aucun repli sur le journal|Statistiques produites|choix de l'éditeur|élus ou non|nommées au Journal officiel|exercent en nom propre|titulaires de marchés publics, sous le nom|registres des connexions au serveur/.test(b),
  );
  assert.ok(corrigees.length >= 9, `blocs corrigés trouvés : ${corrigees.length}`);
  for (const bloc of corrigees) {
    assert.doesNotMatch(bloc, /[—–;…]/, bloc);
  }
});
