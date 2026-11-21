// Flux Atom (src/lib/flux.ts) : XML bien formé, identifiants stables, dates
// du fait ou de la donnée, rien de plus que la page. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  FLUX,
  TYPES_ALERTES_FLUX,
  dateAlerte,
  dateAtom,
  debutPeriode,
  documentAtom,
  echapperXml,
  entreesAlertes,
  entreesDossiers,
  entreesJo,
  entreesSources,
  idTag,
  idTexteJo,
} from "../src/lib/flux.ts";

/**
 * Contrôle de bonne formation pour le sous-ensemble XML produit : balises
 * équilibrées, attributs entre guillemets, aucun « < » ni « & » brut dans le
 * texte, aucun caractère interdit. Renvoie l'arbre (nom, attributs, enfants, texte).
 */
function analyserXml(xml) {
  assert.match(xml, /^<\?xml version="1\.0" encoding="utf-8"\?>\n/);
  assert.doesNotMatch(xml, /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/);
  const corps = xml.replace(/^<\?xml[^>]*\?>\n/, "");
  const racine = { nom: "#document", attributs: {}, enfants: [], texte: "" };
  const pile = [racine];
  const jetons = corps.split(/(<[^>]*>)/);
  for (const j of jetons) {
    if (j === "") continue;
    if (j.startsWith("<")) {
      const m = j.match(/^<(\/?)([A-Za-z][\w:.-]*)((?:\s+[\w:.-]+="[^"<]*")*)\s*(\/?)>$/);
      assert.ok(m, `balise mal formée : ${j}`);
      const [, fermante, nom, attrs, autoFermante] = m;
      if (fermante) {
        const ouvert = pile.pop();
        assert.equal(ouvert.nom, nom, `fermeture ${nom} sans ouverture correspondante`);
        continue;
      }
      const attributs = {};
      for (const a of attrs.matchAll(/([\w:.-]+)="([^"]*)"/g)) {
        assert.ok(!(a[1] in attributs), `attribut répété ${a[1]}`);
        assert.doesNotMatch(a[2], /&(?!(amp|lt|gt|quot|apos);)/, `& brut dans ${a[1]}`);
        attributs[a[1]] = a[2];
      }
      const noeud = { nom, attributs, enfants: [], texte: "" };
      pile.at(-1).enfants.push(noeud);
      if (!autoFermante) pile.push(noeud);
    } else {
      assert.doesNotMatch(j, /&(?!(amp|lt|gt|quot|apos);)/, `& brut dans le texte : ${j}`);
      assert.doesNotMatch(j, />/, `> brut dans le texte : ${j}`);
      pile.at(-1).texte += j;
    }
  }
  assert.equal(pile.length, 1, "balises non refermées");
  const elements = racine.enfants;
  assert.equal(elements.length, 1, "un seul élément racine");
  return elements[0];
}

const enfant = (n, nom) => n.enfants.filter((e) => e.nom === nom);
const RFC3339 = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;

function verifierAtom(xml) {
  const feed = analyserXml(xml);
  assert.equal(feed.nom, "feed");
  assert.equal(feed.attributs.xmlns, "http://www.w3.org/2005/Atom");
  for (const n of [feed, ...enfant(feed, "entry")]) {
    assert.equal(enfant(n, "id").length, 1, `${n.nom} : un id`);
    assert.equal(enfant(n, "title").length, 1, `${n.nom} : un title`);
    assert.equal(enfant(n, "updated").length, 1, `${n.nom} : un updated`);
    assert.match(enfant(n, "updated")[0].texte, RFC3339);
    assert.ok(
      enfant(n, "link").some((l) => l.attributs.rel === "alternate" && l.attributs.href),
      `${n.nom} : un link rel="alternate"`,
    );
  }
  assert.ok(enfant(feed, "link").some((l) => l.attributs.rel === "self"));
  assert.equal(enfant(feed, "author").length, 1);
  const ids = enfant(feed, "entry").map((e) => enfant(e, "id")[0].texte);
  assert.equal(new Set(ids).size, ids.length, "identifiants d'entrée uniques");
  return feed;
}

const baseFlux = {
  id: idTag("flux", "/flux/test.xml"),
  titre: "Test & essai",
  sousTitre: "Sous-titre <b>",
  lienSelf: "https://francetransparence.fr/flux/test.xml",
  lienPage: "https://francetransparence.fr/test/",
  auteur: "France Transparence",
  droits: "Licence Ouverte",
  majSansEntree: "2026-11-01T00:00:00Z",
};

test("dateAtom : jour, instant sans fuseau, instant avec fuseau, illisible", () => {
  assert.equal(dateAtom("2026-11-12"), "2026-11-12T00:00:00Z");
  assert.equal(dateAtom("2026-11-21T04:24:29+00:00"), "2026-11-21T04:24:29+00:00");
  assert.equal(dateAtom("2026-11-21 04:24:29"), "2026-11-21T04:24:29Z");
  assert.equal(dateAtom("2026-11-21T04:24"), "2026-11-21T04:24:00Z");
  assert.equal(dateAtom("2026-11-21T04:24:29.123Z"), "2026-11-21T04:24:29.123Z");
  assert.equal(dateAtom("novembre 2026"), null);
  assert.equal(dateAtom(null), null);
  assert.equal(dateAtom(""), null);
});

test("échappement XML : entités et caractères interdits retirés", () => {
  assert.equal(echapperXml(`a & b < c > d "e" 'f'`), "a &amp; b &lt; c &gt; d &quot;e&quot; &apos;f&apos;");
  assert.equal(echapperXml("a\u0000b\u000Bc\td\ne"), "abc\td\ne");
});

test("identifiants : tag: fixe, NOR puis identifiant Légifrance, sans dépendre du build", () => {
  assert.equal(
    idTexteJo({ nor: "INTK2620387D", texte_id: "JORFTEXT000055075185" }),
    "tag:francetransparence.fr,2026:jo/INTK2620387D/JORFTEXT000055075185",
  );
  assert.equal(
    idTexteJo({ nor: null, texte_id: "JORFTEXT000055075185" }),
    "tag:francetransparence.fr,2026:jo/JORFTEXT000055075185",
  );
  assert.equal(idTexteJo({ nor: "  ", texte_id: "X" }), "tag:francetransparence.fr,2026:jo/X");
  assert.equal(idTag("alerte", "A1-ND-a b"), "tag:francetransparence.fr,2026:alerte/A1-ND-a%20b");
});

test("flux JO : titre et lien Légifrance, date du numéro", () => {
  const entrees = entreesJo([
    {
      texte_id: "JORFTEXT1",
      nor: "PRMI2617535A",
      date_publi: "2026-11-10",
      titre: "Arrêté du 6 novembre 2026 portant nomination (Premier ministre)",
      lien_legifrance: "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT1",
    },
  ]);
  assert.deepEqual(entrees, [
    {
      id: "tag:francetransparence.fr,2026:jo/PRMI2617535A/JORFTEXT1",
      titre: "Arrêté du 6 novembre 2026 portant nomination (Premier ministre)",
      lien: "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT1",
      maj: "2026-11-10T00:00:00Z",
    },
  ]);
  verifierAtom(documentAtom({ ...baseFlux, entrees }));
});

test("flux dossiers : numéro de dossier, date de mise à jour sinon de création, 100 au plus", () => {
  const ligne = (i, date, creation = null) => ({
    dossier_id: `JORFDOLE${i}`,
    titre: `Proposition de loi ${i}`,
    type: "PROPOSITION_LOI",
    date_modif: date,
    date_creation: creation,
    derniere_etape: "Adoption",
    lien_legifrance: `https://www.vie-publique.fr/dossierlegislatif/JORFDOLE${i}`,
  });
  const entrees = entreesDossiers([
    ligne(1, "2026-11-20", "2025-01-02"),
    ligne(2, null, "2025-03-04"),
    ligne(3, null, null),
  ]);
  assert.equal(entrees[0].id, "tag:francetransparence.fr,2026:dossier/JORFDOLE1");
  assert.equal(entrees[0].maj, "2026-11-20T00:00:00Z");
  // Sans mise à jour : la création du dossier, jamais la date des données.
  assert.equal(entrees[1].maj, "2025-03-04T00:00:00Z");
  assert.equal(entrees.length, 2, "un dossier sans aucune date est écarté");
  assert.ok(!entrees.some((e) => e.id.endsWith("JORFDOLE3")));
  assert.ok(!("lienRelie" in entrees[0]));
  const beaucoup = Array.from({ length: 150 }, (_, i) => ligne(i, i < 10 ? null : "2026-11-01"));
  const cent = entreesDossiers(beaucoup);
  assert.equal(cent.length, 100, "100 entrées datées, les dossiers écartés ne comptent pas");
  assert.equal(cent[0].id, "tag:francetransparence.fr,2026:dossier/JORFDOLE10");
  verifierAtom(documentAtom({ ...baseFlux, entrees }));
});

const alerte = (sur) => ({
  id: "A1-ND-x",
  type: "A1_hatvp_non_deposee",
  gravite: "haute",
  titre: "Déclaration non déposée (constat officiel HATVP)",
  detail: "détail affiché sur la page, absent du flux",
  regle: "règle",
  base_legale: "loi",
  source_url: "https://www.hatvp.fr/pages_nominatives/x",
  date_calcul: "2026-11-21T04:24:29+00:00",
  date_fait: "2026-11-12",
  ...sur,
});

test("alertes : seule une date du fait stable, jamais la date d'une source ni du calcul", () => {
  assert.deepEqual(TYPES_ALERTES_FLUX, ["financement_parti_dependance_aide"]);
  // Dépendance à l'aide publique : clôture de l'exercice lu dans l'identifiant.
  assert.equal(
    dateAlerte(alerte({ id: "FIN-PARTI-DEP-2024-PARTI-1378", type: "financement_parti_dependance_aide", date_fait: null })),
    "2024-12-31T00:00:00Z",
  );
  assert.equal(
    dateAlerte(alerte({ id: "FIN-PARTI-DEP-x", type: "financement_parti_dependance_aide", date_fait: null })),
    null,
    "identifiant sans exercice : pas de date inventée",
  );
  // A1 : date_fait = date du fichier liste.csv, qui change à chaque fichier.
  assert.equal(dateAlerte(alerte({})), null);
  assert.equal(dateAlerte(alerte({ type: "A1_hatvp_en_cours_delai_ecoule", id: "A1-EC-commune" })), null);
  for (const type of [
    "lobbying_defaut_declaration",
    "lobbying_declaration_incomplete",
    "financement_parti_prive_aide",
    "autre_type",
  ]) {
    assert.equal(dateAlerte(alerte({ type, date_fait: null })), null, type);
  }
});

test("alertes : une alerte datée du fait, les autres hors du flux, titre et liens seulement", () => {
  const page = "https://francetransparence.fr/alertes/";
  const dep = (id, source_url) =>
    alerte({
      id,
      type: "financement_parti_dependance_aide",
      gravite: "info",
      titre: "Parti financé à 80 % par l'aide publique",
      source_url,
      date_fait: null,
    });
  const entrees = entreesAlertes(
    [
      alerte({}),
      alerte({ id: "lob-1", type: "lobbying_defaut_declaration", source_url: null, date_fait: null }),
      dep("FIN-PARTI-DEP-2024-P1", "https://www.data.gouv.fr/partis"),
      dep("FIN-PARTI-DEP-2024-P2", null),
    ],
    page,
  );
  assert.equal(entrees.length, 2, "ni A1 ni lobbying dans le flux");
  assert.deepEqual(entrees[0], {
    id: "tag:francetransparence.fr,2026:alerte/FIN-PARTI-DEP-2024-P1",
    titre: "Parti financé à 80 % par l'aide publique",
    lien: "https://www.data.gouv.fr/partis",
    lienRelie: page,
    maj: "2024-12-31T00:00:00Z",
  });
  assert.equal(entrees[1].lien, page);
  assert.ok(!("lienRelie" in entrees[1]), "pas deux fois le même lien");
  const xml = documentAtom({ ...baseFlux, entrees });
  verifierAtom(xml);
  // Rien de la page au-delà du titre : ni détail, ni règle, ni gravité.
  assert.doesNotMatch(xml, /détail affiché|<summary|<content/);
});

test("sources : une entrée par source et date des données, plus récente d'abord", () => {
  const entrees = entreesSources(
    [
      { source_id: "S13", nom: "DGFiP", url: "https://data.economie.gouv.fr/s13", date_donnees: "2026-09-30" },
      { source_id: "S3", nom: "DILA JORF", url: "https://echanges.dila.gouv.fr/", date_donnees: "2026-11-21" },
      { source_id: "S41", nom: "Mensuelle", url: "https://x/m", date_donnees: "2026-10" },
      { source_id: "S42", nom: "Annuelle", url: "https://x/a", date_donnees: "2025" },
    ],
    "https://francetransparence.fr/donnees/",
  );
  assert.deepEqual(
    entrees.map((e) => [e.id, e.maj]),
    [
      ["tag:francetransparence.fr,2026:source/S3/2026-11-21", "2026-11-21T00:00:00Z"],
      ["tag:francetransparence.fr,2026:source/S41/2026-10", "2026-10-01T00:00:00Z"],
      ["tag:francetransparence.fr,2026:source/S13/2026-09-30", "2026-09-30T00:00:00Z"],
      ["tag:francetransparence.fr,2026:source/S42/2025", "2025-01-01T00:00:00Z"],
    ],
  );
  assert.equal(entrees[0].titre, "DILA JORF : données du 2026-11-21");
  assert.equal(entrees[1].titre, "Mensuelle : données du 2026-10");
  assert.equal(entrees[0].lien, "https://echanges.dila.gouv.fr/");
  verifierAtom(documentAtom({ ...baseFlux, entrees }));
});

test("sources : une date des données illisible fait échouer le build, jamais sautée", () => {
  assert.equal(debutPeriode("2026-11"), "2026-11-01");
  assert.equal(debutPeriode("2026"), "2026-01-01");
  assert.equal(debutPeriode("2026-11-21"), "2026-11-21");
  assert.throws(
    () =>
      entreesSources(
        [{ source_id: "S99", nom: "Date illisible", url: "https://x", date_donnees: "inconnue" }],
        "https://francetransparence.fr/donnees/",
      ),
    /S99.*inconnue/,
  );
});

test("updated du flux = entrée la plus récente, jamais l'heure du build", () => {
  const entrees = [
    { id: "tag:a", titre: "a", lien: "https://a", maj: "2026-11-10T00:00:00Z" },
    { id: "tag:b", titre: "b", lien: "https://b", maj: "2026-11-12T08:00:00+01:00" },
    { id: "tag:c", titre: "c", lien: "https://c", maj: "2026-11-11T23:00:00Z" },
  ];
  const feed = verifierAtom(documentAtom({ ...baseFlux, entrees }));
  assert.equal(enfant(feed, "updated")[0].texte, "2026-11-12T08:00:00+01:00");
  const vide = verifierAtom(documentAtom({ ...baseFlux, entrees: [] }));
  assert.equal(enfant(vide, "updated")[0].texte, "2026-11-01T00:00:00Z");
});

test("textes du flux échappés : un titre officiel avec & et < reste bien formé", () => {
  const xml = documentAtom({
    ...baseFlux,
    entrees: [
      { id: "tag:x", titre: "Arrêté relatif à « A & B » < C", lien: "https://x?a=1&b=2", maj: "2026-11-10T00:00:00Z" },
    ],
  });
  verifierAtom(xml);
  assert.match(xml, /<title>Arrêté relatif à « A &amp; B » &lt; C<\/title>/);
  assert.match(xml, /href="https:\/\/x\?a=1&amp;b=2"/);
});

test("quatre flux publiés, chacun avec sa page et son chemin /flux/*.xml", () => {
  assert.deepEqual(
    FLUX.map((f) => f.chemin),
    ["/flux/jo.xml", "/flux/dossiers.xml", "/flux/alertes.xml", "/flux/sources.xml"],
  );
  for (const f of FLUX) {
    assert.match(f.page, /^\/[\w/-]*\/$/);
    assert.doesNotMatch(`${f.titre} ${f.description}`, /[—–;]/, "style des textes publiés");
  }
});
