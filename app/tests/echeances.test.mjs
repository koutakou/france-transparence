// Appels d'offres « proches de la clôture » (lib/echeances.ts) : la page est
// construite vers 05 h 20 et servie toute la journée ; une échéance passée à
// l'heure du visiteur ne s'affiche plus. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {
  AO_ACCUEIL_AFFICHEES,
  AO_AFFICHEES,
  RESERVE_HEURES,
  echeancesOuvertes,
  reserveEcheances,
} from "../src/lib/echeances.ts";

// Les quatre échéances de l'accueil servi le 15/10/2026, relevé à 12:26 UTC
// (« Clôture le 15/10 06:00 — CHU de la Réunion », puis trois à 10:00, heure
// de Paris, dont les avis CCAS de Gennevilliers 26-89918 et 26-89459), suivies
// des premières échéances de la base ingérée le même jour (idweb réels).
const LIGNES = [
  { id: "CHU de la Réunion", limite: "2026-10-15T04:00:00+00:00" },
  { id: "26-89918", limite: "2026-10-15T08:00:00+00:00" },
  { id: "26-89459", limite: "2026-10-15T08:00:00+00:00" },
  { id: "Ville de Cachan", limite: "2026-10-15T08:00:00+00:00" },
  { id: "26-90054", limite: "2026-10-15T13:00:00+00:00" },
  { id: "26-89099", limite: "2026-10-15T13:30:00+00:00" },
  { id: "26-94428", limite: "2026-10-15T14:00:00+00:00" },
];
const limite = (l) => l.limite;

test("à 14 h 26 (Paris), les échéances de 06:00 et de 10:00 ne sont plus affichées", () => {
  const releve = Date.parse("2026-10-15T12:26:00Z");
  const ids = echeancesOuvertes(LIGNES, limite, releve, 4).map((l) => l.id);
  assert.deepEqual(ids, ["26-90054", "26-89099", "26-94428"]);
});

test("à l'heure de la construction, la liste est celle de la construction", () => {
  const construction = Date.parse("2026-10-15T03:24:00Z");
  const ids = echeancesOuvertes(LIGNES, limite, construction, 4).map((l) => l.id);
  assert.deepEqual(ids, ["CHU de la Réunion", "26-89918", "26-89459", "Ville de Cachan"]);
});

test("une échéance à la minute exacte est close ; une date illisible n'est pas ouverte", () => {
  const t = Date.parse("2026-10-15T13:00:00Z");
  const lignes = [
    { id: "26-90054", limite: "2026-10-15T13:00:00+00:00" },
    { id: "illisible", limite: "?" },
  ];
  assert.deepEqual(echeancesOuvertes(lignes, limite, t, 4), []);
});

// Distribution RÉELLE des clôtures : base ingérée le 15/10/2026, annonces
// ouvertes à l'ingestion, comptées par date limite jusqu'au 19/10 (1 032
// lignes, dont 481 le 16/10 et 133 à midi pile, heure de Paris).
const FIXTURE = JSON.parse(
  fs.readFileSync(new URL("./fixtures/ao-echeances-15-10-2026.json", import.meta.url), "utf8"),
);
const TOUTES = FIXTURE.echeances.flatMap(([d, n]) =>
  Array.from({ length: n }, (_, i) => ({ id: `${d}#${i}`, limite: d })),
);

/** Construction à `construction`, visite à `visite` : lignes affichées. */
function affichees(construction, visite, maxi) {
  const c = Date.parse(construction);
  const ouvertesALaConstruction = TOUTES.filter((l) => Date.parse(l.limite) > c);
  const reserve = reserveEcheances(ouvertesALaConstruction, limite, c);
  return echeancesOuvertes(reserve, limite, Date.parse(visite), maxi);
}

test("le défaut : une réserve de 60 lignes est vide dès le lendemain midi", () => {
  // Construction le 16/10 à 07 h (Paris) : les 60 premières clôtures tombent
  // toutes au plus tard à midi. À 23 h le même jour, il n'en reste aucune.
  const c = Date.parse("2026-10-16T05:00:00Z");
  const soixante = TOUTES.filter((l) => Date.parse(l.limite) > c).slice(0, 60);
  assert.equal(echeancesOuvertes(soixante, limite, Date.parse("2026-10-16T21:00:00Z"), 20).length, 0);
});

test("construction à 07 h, visite à 23 h le lendemain : listes pleines", () => {
  // 15/10 07 h (Paris) n'est pas dans la fixture (elle commence à
  // l'ingestion, 14 h 28) : on construit le 16/10 à 07 h, jour de 481
  // clôtures, et on visite le 17/10 à 23 h, 40 h plus tard.
  assert.equal(affichees("2026-10-16T05:00:00Z", "2026-10-17T21:00:00Z", AO_AFFICHEES).length, AO_AFFICHEES);
  assert.equal(
    affichees("2026-10-16T05:00:00Z", "2026-10-17T21:00:00Z", AO_ACCUEIL_AFFICHEES).length,
    AO_ACCUEIL_AFFICHEES,
  );
});

test("construction réelle (15/10, 14 h 28), visite le 16/10 à 23 h : liste pleine", () => {
  assert.equal(affichees(FIXTURE.ingestion, "2026-10-16T21:00:00Z", AO_AFFICHEES).length, AO_AFFICHEES);
});

test("la réserve couvre la durée, puis s'arrête au-delà", () => {
  const c = Date.parse("2026-10-16T05:00:00Z");
  const ouvertes = TOUTES.filter((l) => Date.parse(l.limite) > c);
  const reserve = reserveEcheances(ouvertes, limite, c, RESERVE_HEURES, 20);
  const borne = c + RESERVE_HEURES * 3_600_000;
  const dedans = ouvertes.filter((l) => Date.parse(l.limite) <= borne).length;
  assert.equal(reserve.length, dedans + 20);
  assert.ok(dedans >= 481, `${dedans} clôtures dans la durée`);
  // Une date illisible n'entre pas dans la réserve.
  assert.deepEqual(reserveEcheances([{ id: "x", limite: "?" }], limite, c), []);
});
