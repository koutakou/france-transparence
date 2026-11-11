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

/* ---------- seuils recalibrés sur le calendrier amont (11/11/2026) ---------- */

const niveau = (id, d, le) => evalueFraicheur(id, d, new Date(`${le}T12:00:00Z`)).niveau;

test("S7 Datan publie chaque jour : figé depuis le 28/10, il n'est plus « à jour » le 08/11", () => {
  assert.equal(niveau("S7-DATAN", "2026-10-28", "2026-11-08"), "a_surveiller"); // 11 j
  assert.equal(niveau("S7-DATAN", "2026-10-28", "2026-11-11"), "a_surveiller"); // 14 j
  assert.equal(niveau("S7-DATAN", "2026-10-28", "2026-11-12"), "en_retard");
  assert.equal(niveau("S7-DATAN", "2026-10-27", "2026-10-28"), "a_jour");
});

test("S47 IRCOM : à jour jusqu'à la parution la plus tardive observée (juin N+2)", () => {
  assert.equal(niveau("S47", "2024-12-31", "2026-11-08"), "a_jour"); // était « à surveiller »
  // Revenus 2022, remplacés le 10/06/2024 : 892 jours, l'amont était à l'heure.
  assert.equal(niveau("S47", "2021-12-31", "2024-06-10"), "a_jour");
  assert.equal(niveau("S47", "2024-12-31", "2027-06-20"), "a_surveiller");
});

test("S45 DREES : l'année N paraît en décembre N+1, pas de signal avant", () => {
  assert.equal(niveau("S45", "2024-12-31", "2026-11-08"), "a_jour"); // était « à surveiller »
  assert.equal(niveau("S45", "2023-12-31", "2025-12-18"), "a_jour"); // parution 2024
  assert.equal(niveau("S45", "2024-12-31", "2027-01-05"), "a_surveiller");
});

test("S49 COFOG : diffusion principale en février t+2 (ESMS Eurostat)", () => {
  assert.equal(niveau("S49", "2024-12-31", "2026-11-08"), "a_jour"); // était « à surveiller »
  assert.equal(niveau("S49", "2024-12-31", "2027-02-28"), "a_jour"); // avant la diffusion
  assert.equal(niveau("S49", "2024-12-31", "2027-04-15"), "a_surveiller");
});

test("S48 REI : versé en mai N+1, un REI manquant se voit l'été suivant", () => {
  assert.equal(niveau("S48", "2025-12-31", "2026-11-08"), "a_jour");
  assert.equal(niveau("S48", "2024-12-31", "2026-05-12"), "a_jour"); // parution du REI 2025
  assert.equal(niveau("S48", "2025-12-31", "2027-07-20"), "a_surveiller"); // 650 : « à jour »
});
