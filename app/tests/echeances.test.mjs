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
  TRANCHE_MS,
  contenuTranche,
  echeancesOuvertes,
  nomTranche,
  reserveEcheances,
  trancheAConsulter,
  trancheDeNom,
  tranchesAEcrire,
  tranchesDeLaPage,
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

// --- Tranches horaires : ce que le navigateur charge de lui-même ---------
//
// La réserve entière se chargeait sans geste dès la première échéance passée
// (ao.json : 445 748 octets le 15/10/2026 à 16 h 38, dont la vue « Toutes »).
// Le navigateur ne charge plus que la tranche de l'heure qu'il vit. Garantie
// exigée : pour TOUTE minute des RESERVE_HEURES qui suivent la construction,
// la liste affichée depuis la tranche est IDENTIQUE à celle que donnerait la
// liste complète des appels d'offres ouverts à la construction.

/** Simule une construction à `c` (page) et un fragment rendu à `cFragment`. */
function simuler(c, cFragment, maxi) {
  const ouvertes = TOUTES.filter((l) => Date.parse(l.limite) > cFragment);
  const ecrites = new Map(
    tranchesAEcrire(cFragment).map((t) => [t, contenuTranche(ouvertes, limite, t, maxi)]),
  );
  return { ouvertes, ecrites };
}

for (const [nom, construction] of [
  ["construction réelle (15/10, 14 h 28)", FIXTURE.ingestion],
  ["construction le 16/10 à 07 h (Paris)", "2026-10-16T05:00:00Z"],
]) {
  for (const maxi of [AO_AFFICHEES, AO_ACCUEIL_AFFICHEES]) {
    test(`${nom}, ${maxi} lignes : chaque minute de la réserve, la tranche affiche ce qu'afficherait tout`, () => {
      const c = Date.parse(construction);
      // Le fragment est rendu quelques minutes après la page, dans la même construction.
      const { ouvertes, ecrites } = simuler(c, c + 7 * 60_000, maxi);
      let minutes = 0;
      for (let t = c + 7 * 60_000; t <= c + RESERVE_HEURES * 3_600_000; t += 60_000) {
        const tranche = trancheAConsulter(t, c);
        assert.ok(ecrites.has(tranche), `tranche ${nomTranche(tranche)} demandée, non écrite`);
        const vu = echeancesOuvertes(ecrites.get(tranche), limite, t, maxi).map((l) => l.id);
        const attendu = echeancesOuvertes(ouvertes, limite, t, maxi).map((l) => l.id);
        assert.deepEqual(vu, attendu, new Date(t).toISOString());
        minutes++;
      }
      assert.equal(minutes, RESERVE_HEURES * 60 - 7 + 1);
    });
  }
}

test("construction à 07 h, visite à 23 h le lendemain : la tranche chargée remplit la liste", () => {
  const c = Date.parse("2026-10-16T05:00:00Z");
  const visite = Date.parse("2026-10-17T21:00:00Z");
  for (const maxi of [AO_AFFICHEES, AO_ACCUEIL_AFFICHEES]) {
    const { ecrites } = simuler(c, c, maxi);
    const lignes = echeancesOuvertes(ecrites.get(trancheAConsulter(visite, c)), limite, visite, maxi);
    assert.equal(lignes.length, maxi);
  }
});

test("au-delà de la réserve, la dernière tranche en montre au moins autant que l'ancienne réserve", () => {
  const c = Date.parse("2026-10-16T05:00:00Z");
  const { ouvertes, ecrites } = simuler(c, c, AO_AFFICHEES);
  const reserve = reserveEcheances(ouvertes, limite, c);
  for (let t = c + RESERVE_HEURES * 3_600_000; t <= c + 60 * 3_600_000; t += 15 * 60_000) {
    const vu = echeancesOuvertes(ecrites.get(trancheAConsulter(t, c)), limite, t, AO_AFFICHEES);
    const avant = echeancesOuvertes(reserve, limite, t, AO_AFFICHEES);
    assert.ok(vu.length >= avant.length, new Date(t).toISOString());
  }
});

test("une tranche ne porte que l'affichable : bien moins que la réserve, même le lundi midi", () => {
  // Construction le 16/10 à 07 h : 481 clôtures ce jour-là, 133 à midi pile.
  const c = Date.parse("2026-10-16T05:00:00Z");
  const { ouvertes, ecrites } = simuler(c, c, AO_AFFICHEES);
  const reserve = reserveEcheances(ouvertes, limite, c);
  const plusGrosse = Math.max(...[...ecrites.values()].map((l) => l.length));
  // Borne structurelle : au plus `maxi` lignes par date limite distincte de
  // l'heure, plus la fenêtre de départ.
  for (const [t, lignes] of ecrites) {
    const dates = new Set(
      ouvertes
        .map((l) => Date.parse(l.limite))
        .filter((d) => d > t * TRANCHE_MS && d < (t + 1) * TRANCHE_MS),
    );
    assert.ok(lignes.length <= (dates.size + 1) * AO_AFFICHEES, nomTranche(t));
  }
  assert.ok(plusGrosse * 10 < reserve.length, `${plusGrosse} lignes contre ${reserve.length}`);
  // La 21e des 133 clôtures de midi n'est jamais affichable : elle ne voyage pas.
  const midi = ecrites.get(trancheAConsulter(Date.parse("2026-10-16T09:30:00Z"), c));
  const aMidi = midi.filter((l) => l.limite === "2026-10-16T10:00:00+00:00").length;
  assert.equal(aMidi, AO_AFFICHEES);
});

test("tranches : nom = heure UTC, aller-retour, plage de la page bornée", () => {
  const t = Date.parse("2026-10-15T14:59:59Z");
  const tranche = Math.floor(t / TRANCHE_MS);
  assert.equal(nomTranche(tranche), "2026-10-15T14");
  assert.equal(trancheDeNom("2026-10-15T14"), tranche);
  assert.equal(trancheDeNom("2026-10-15T24"), null);
  assert.equal(trancheDeNom("../etc"), null);
  const c = Date.parse("2026-10-15T03:24:00Z");
  const { premiere, derniere } = tranchesDeLaPage(c);
  assert.equal(derniere - premiere, RESERVE_HEURES);
  // Horloge du visiteur en retard, ou très en avance : bornée à la plage.
  assert.equal(trancheAConsulter(c - 5 * 3_600_000, c), premiere);
  assert.equal(trancheAConsulter(c + 99 * 3_600_000, c), derniere);
});

test("page et fragments rendus de part et d'autre d'une heure pleine : toute tranche demandée existe", () => {
  // La page et chaque fragment évaluent leur propre Date.now() pendant la même
  // construction : quelques minutes d'écart, dans un sens ou dans l'autre.
  for (const [page, fragment] of [
    ["2026-10-16T04:58:00Z", "2026-10-16T05:03:00Z"],
    ["2026-10-16T05:03:00Z", "2026-10-16T04:58:00Z"],
  ]) {
    const c = Date.parse(page);
    const { ouvertes, ecrites } = simuler(c, Date.parse(fragment), AO_AFFICHEES);
    const debut = Math.max(c, Date.parse(fragment));
    // Dès 30 min avant la construction : une horloge de visiteur en retard
    // demande la première tranche de la page, qui doit exister aussi.
    for (let t = c - 30 * 60_000; t <= c + 60 * 3_600_000; t += 10 * 60_000) {
      const tranche = trancheAConsulter(t, c);
      assert.ok(ecrites.has(tranche), `${page} / ${fragment} : ${nomTranche(tranche)} manquante`);
      if (t >= debut && t <= c + RESERVE_HEURES * 3_600_000) {
        assert.deepEqual(
          echeancesOuvertes(ecrites.get(tranche), limite, t, AO_AFFICHEES),
          echeancesOuvertes(ouvertes, limite, t, AO_AFFICHEES),
        );
      }
    }
  }
});
