// Fiche d'élu (lib/queries/elus.ts) : un élu dont la HATVP publie un chemin
// mal formé garde ses déclarations, rattachées par l'URL brute. Le lien
// affiché renvoie à la liste. L'URL de la liste, commune à tous, ne rattache
// jamais rien. Lignes réelles de la base du 21/11/2026, sauf la dernière
// déclaration et le dernier élu, construits pour la garde. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { baseDeTest, importer } from "./outils/charger.mjs";
import { inserer } from "./outils/fixtures.mjs";
import { creerTables } from "./outils/schema.mjs";

const LISTE = "https://www.hatvp.fr/livraison/opendata/liste.csv";
const CAPITANIO = "https://www.hatvp.fr/pages_nominatives/capitanio-olivier[";
const MARTIN = "https://www.hatvp.fr/pages_nominatives/martin-(gironde)-alexandra-26044";

const declaration = (id, nom, prenom, type_document, url_fiche, date_depot) => ({
  id, nom, prenom, type_document, date_depot,
  statut_publication: "Livrée",
  url_dossier: url_fiche.replace("https://www.hatvp.fr", ""),
  url_fiche,
});

await baseDeTest((db) => {
  creerTables(db, ["elus", "deputes", "hatvp_declarations", "votes_recents", "scrutins"]);
  inserer(db, "elus", [
    { id: "rne-e458de14ab5ae5e0", nom: "CAPITANIO", prenom: "Olivier", uid_an: null,
      hatvp_flag: 1, hatvp_url: CAPITANIO },
    { id: "PA793944", nom: "Martin (Gironde)", prenom: "Alexandra", uid_an: "PA793944",
      hatvp_flag: 1, hatvp_url: MARTIN },
    // Élu renvoyé à la liste (chemin vide dans liste.csv).
    { id: "rne-garde-liste", nom: "DUPONT", prenom: "Jean", uid_an: null,
      hatvp_flag: 1, hatvp_url: LISTE },
  ]);
  inserer(db, "deputes", [
    { uid_an: "PA793944", legislature: 17, nom: "Martin (Gironde)", prenom: "Alexandra",
      url_fiche_an: "https://www.assemblee-nationale.fr/dyn/deputes/PA793944", url_hatvp: MARTIN },
  ]);
  inserer(db, "hatvp_declarations", [
    declaration(10124, "CAPITANIO", "Olivier", "di", CAPITANIO, "2021-08-28"),
    declaration(10125, "CAPITANIO", "Olivier", "dim", CAPITANIO, "2022-01-09"),
    declaration(10126, "CAPITANIO", "Olivier", "di", CAPITANIO, "2026-05-23"),
    declaration(261, "MARTIN (GIRONDE)", "Alexandra", "dia", MARTIN, "2026-07-13"),
    declaration(262, "MARTIN (GIRONDE)", "Alexandra", "dsp", MARTIN, "2026-07-13"),
    declaration(2410, "FAUBERT", "Christian", "di",
      "https://www.hatvp.fr/pages_nominatives/faubert-christian[1]", null),
    // Une ligne à l'URL de la liste, que le pipeline n'écrit jamais : la garde
    // de la requête doit l'ignorer quand même.
    declaration(99999, "AUTRE", "Personne", "di", LISTE, "2026-01-01"),
  ]);
});
const { getFicheElu, getDeputes } = await importer("lib/queries/elus");

const ids = (fiche) => fiche.declarations.map((d) => d.id);

test("chemin mal formé : les déclarations restent sur la fiche de leur élu, et seulement elles", () => {
  assert.deepEqual(ids(getFicheElu("rne-e458de14ab5ae5e0")), [10126, 10125, 10124]);
  assert.deepEqual(ids(getFicheElu("PA793944")), [261, 262]);
});

test("l'URL de la liste ne rattache aucune déclaration", () => {
  assert.deepEqual(ids(getFicheElu("rne-garde-liste")), []);
});

test("liste des députés : le lien affiché d'un chemin mal formé est la liste", () => {
  assert.deepEqual(
    getDeputes().map((d) => [d.elu_id, d.hatvp_url]),
    [["PA793944", LISTE]],
  );
});
