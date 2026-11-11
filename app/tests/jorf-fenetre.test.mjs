// Fenêtre du Journal officiel (lib/jorf-fenetre.ts) : le libellé au contact
// du chiffre dit ce que la fenêtre contient. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {
  ECART_NORMAL_ENTRE_JO,
  MARQUES_FENETRE_SIGNALEE,
  libelleFenetreJo,
  mentionFenetreJo,
  noteFenetreSignalee,
  perimetreJo30j,
  phraseFenetreJo,
  trousEntreJo,
} from "../src/lib/jorf-fenetre.ts";

// Les 30 JO réels parus du 14/07 au 19/08/2026 : la fixture des tests du
// pipeline (un texte réel par JO), relue ici pour ses dates.
const TRENTE_JO = fs
  .readFileSync(
    new URL(
      "../../pipelines/tests/fixtures/jorf/un_texte_par_jo_20260714_20260819.tsv",
      import.meta.url,
    ),
    "utf8",
  )
  .trim()
  .split("\n")
  .map((l) => l.split("\t")[0]);

// Scénario « trou » : base arrêtée au JO du 31/07, reprise au 19/08.
const TROUEE = TRENTE_JO.filter((d) => d <= "2026-07-31" || d === "2026-08-19");

test("30 JO réels consécutifs : aucun trou, libellés de fenêtre pleine", () => {
  assert.equal(TRENTE_JO.length, 30);
  assert.deepEqual(trousEntreJo(TRENTE_JO), []);
  assert.equal(mentionFenetreJo(TRENTE_JO), "30 derniers JO parus");
  assert.equal(libelleFenetreJo(TRENTE_JO), "30 derniers JO");
  assert.equal(
    phraseFenetreJo(TRENTE_JO),
    "les 30 derniers JO parus, du 14/07/2026 au 19/08/2026",
  );
});

test("le seuil est celui du pipeline, éprouvé à ses deux bords", () => {
  const pipeline = fs.readFileSync(
    new URL("../../pipelines/ingest_jorf.py", import.meta.url),
    "utf8",
  );
  assert.match(pipeline, new RegExp(`^ECART_NORMAL_ENTRE_JO = ${ECART_NORMAL_ENTRE_JO}$`, "m"));
  // 15/08 → 18/08 : trois jours, normal. Sans le 15/08 : quatre, signalé.
  assert.deepEqual(trousEntreJo(["2026-08-15", "2026-08-18"]), []);
  assert.deepEqual(trousEntreJo(TRENTE_JO.filter((d) => d !== "2026-08-15")), [
    { avant: "2026-08-14", apres: "2026-08-18", jours: 4 },
  ]);
});

test("fenêtre trouée : aucun libellé ne dit « derniers JO parus »", () => {
  assert.deepEqual(trousEntreJo(TROUEE), [
    { avant: "2026-07-31", apres: "2026-08-19", jours: 19 },
  ]);
  assert.equal(mentionFenetreJo(TROUEE), "16 JO, aucun entre le 31/07/2026 et le 19/08/2026");
  assert.equal(libelleFenetreJo(TROUEE), "16 JO, série interrompue");
  assert.equal(
    phraseFenetreJo(TROUEE),
    "16 JO parus entre le 14/07/2026 et le 19/08/2026, aucun entre le 31/07/2026 et le 19/08/2026",
  );
  for (const texte of [mentionFenetreJo(TROUEE), libelleFenetreJo(TROUEE), phraseFenetreJo(TROUEE)]) {
    assert.doesNotMatch(texte, /derniers JO/);
  }
});

test("fenêtre réduite sans trou : le compte lu en base suffit", () => {
  const deux = ["2026-11-10", "2026-11-11"];
  assert.equal(mentionFenetreJo(deux), "2 derniers JO parus");
  assert.equal(phraseFenetreJo(deux), "les 2 derniers JO parus, du 10/11/2026 au 11/11/2026");
});

test("tuile d'accueil « 30 j » : trois périmètres, selon ce que la base porte", () => {
  // Construction du 19/08/2026 : le seuil des 30 jours est le 20/07.
  const seuil = "2026-07-20";
  assert.equal(perimetreJo30j(TRENTE_JO, seuil), "JORF Lois et décrets, 30 derniers jours");
  // Trou dans les 30 jours : le compte ne porte que sur une partie.
  assert.equal(
    perimetreJo30j(TROUEE, seuil),
    "JORF Lois et décrets, 30 derniers jours — aucun JO repris ici entre le 31/07/2026 et le 19/08/2026",
  );
  // Trou qui COMMENCE avant le seuil et finit dedans (base arrêtée au 04/10,
  // reprise au 10/11, seuil au 12/10) : nommé aussi.
  assert.equal(
    perimetreJo30j(["2026-10-03", "2026-10-04", "2026-11-10", "2026-11-11"], "2026-10-12"),
    "JORF Lois et décrets, 30 derniers jours — aucun JO repris ici entre le 04/10/2026 et le 10/11/2026",
  );
  // Un trou entièrement antérieur aux 30 jours ne concerne pas la tuile.
  assert.equal(
    perimetreJo30j(TROUEE, "2026-08-19"),
    "JORF Lois et décrets, 30 derniers jours",
  );
  // Base neuve : deux JO, le premier postérieur au seuil.
  assert.equal(
    perimetreJo30j(["2026-11-10", "2026-11-11"], "2026-10-12"),
    "JORF Lois et décrets — seulement les JO parus depuis le 10/11/2026 : moins de 30 jours repris ici",
  );
  // Premier JO exactement au seuil : les 30 jours sont couverts.
  assert.equal(
    perimetreJo30j(["2026-10-12", "2026-10-14"], "2026-10-12"),
    "JORF Lois et décrets, 30 derniers jours",
  );
  assert.equal(perimetreJo30j([], seuil), "JORF Lois et décrets, 30 derniers jours");
});

test("la note du pipeline n'est affichée que si elle signale la fenêtre", () => {
  const pipeline = fs.readFileSync(
    new URL("../../pipelines/ingest_jorf.py", import.meta.url),
    "utf8",
  );
  for (const marque of MARQUES_FENETRE_SIGNALEE) {
    assert.ok(pipeline.includes(`= "${marque}"`), marque);
  }
  const reduite =
    "Fenêtre réduite : 2 JO sur les 30 visés, du 10/11/2026 au 11/11/2026 (constat du 11/11/2026) ; le dépôt public de la DILA propose 2 éditions quotidiennes du JO depuis son renouvellement du 08/11/2026, les JO plus anciens ne sont pas affichés ici";
  assert.equal(noteFenetreSignalee(reduite), reduite);
  assert.equal(noteFenetreSignalee(`  ${reduite}\n`), reduite);
  assert.ok(noteFenetreSignalee("Fenêtre discontinue : aucun JO entre le …"));
  assert.equal(
    noteFenetreSignalee(
      "30 JO, du 08/10/2026 au 11/11/2026 ; le dépôt public de la DILA propose 2 éditions quotidiennes du JO",
    ),
    null,
  );
  assert.equal(noteFenetreSignalee(null), null);
  assert.equal(noteFenetreSignalee(""), null);
});
