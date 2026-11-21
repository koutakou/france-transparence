// Routes statiques /api/*.csv, /api/*.provenance.txt et /flux/*.xml jouées
// sur une base jetable : requêtes, câblage et sortie réelle. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { baseDeTest, importer } from "./outils/charger.mjs";
import { SCHEMA } from "./outils/schema.mjs";

await baseDeTest((db) => {
  db.exec(SCHEMA.meta_sources);
  const meta = db.prepare(
    `INSERT INTO meta_sources (source_id, nom, url, licence, frequence, date_donnees, date_ingestion, lignes)
     VALUES (?, ?, ?, ?, 'quotidienne', ?, ?, 1)`,
  );
  meta.run("S1", "DECP consolidées", "https://www.data.gouv.fr/decp", "Licence Ouverte 2.0", "2026-11-20", "2026-11-21T04:00:00+00:00");
  meta.run("S3", "DILA JORF", "https://echanges.dila.gouv.fr/OPENDATA/JORF/", "Licence Ouverte", "2026-11-21", "2026-11-21T01:00:00+00:00");
  meta.run("S4", "HATVP AGORA", "https://www.hatvp.fr/agora/opendata/", "Licence Ouverte", "2026-11-20", "2026-11-21T04:24:27+00:00");
  meta.run("S14", "HATVP liste.csv", "https://www.hatvp.fr/livraison/opendata/liste.csv", "Licence Ouverte", "2026-11-14", "2026-11-21T04:00:00+00:00");
  meta.run("S17", "RNE", "https://www.data.gouv.fr/rne", "Licence Ouverte", "2026-11-20", "2026-11-21T03:00:00+00:00");
  meta.run("S25", "CNCCFP comptes des partis", "https://www.data.gouv.fr/partis", "Licence Ouverte", "2024-12-31", "2026-11-21T03:00:00+00:00");
  meta.run("S29", "CNCCFP comptes de campagne", "https://www.data.gouv.fr/campagnes", "Licence Ouverte", "2024-07-07", "2026-11-21T03:00:00+00:00");
  meta.run("S43", "DILA DOLE", "https://echanges.dila.gouv.fr/OPENDATA/DOLE/", "Licence Ouverte", "2026-11-20", "2026-11-21T02:00:00+00:00");
  db.exec(`CREATE TABLE jorf_textes (texte_id TEXT PRIMARY KEY, conteneur_id TEXT, num_jo TEXT,
    date_publi TEXT, date_texte TEXT, nature TEXT, nor TEXT, titre TEXT, ministere TEXT, rubrique TEXT,
    is_nomination INTEGER, lien_legifrance TEXT, id_eli TEXT, num_sequence INTEGER)`);
  const jo = db.prepare(
    "INSERT INTO jorf_textes (texte_id, date_publi, nor, titre, lien_legifrance, num_sequence) VALUES (?, ?, ?, ?, ?, ?)",
  );
  for (const [i, date] of ["2026-11-21", "2026-11-21", "2026-11-20", "2026-11-19", "2026-11-18"].entries()) {
    jo.run(`JORFTEXT${i}`, date, i === 1 ? null : `NOR${i}`, `Décret n° ${i} & arrêté`, `https://www.legifrance.gouv.fr/jorf/id/JORFTEXT${i}`, i);
  }
  db.exec(`CREATE TABLE alertes (id TEXT PRIMARY KEY, type TEXT, gravite TEXT, titre TEXT, detail TEXT,
    regle TEXT, base_legale TEXT, source_url TEXT, date_calcul TEXT, date_fait TEXT, date_detection TEXT)`);
  const al = db.prepare("INSERT INTO alertes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)");
  al.run("A1-ND-x", "A1_hatvp_non_deposee", "haute", "Déclaration non déposée (constat officiel HATVP)", "d", "r", "loi", "https://www.hatvp.fr/x", "2026-11-21", "2026-11-12", "2026-11-03");
  al.run("lob-1", "lobbying_defaut_declaration", "haute", "Défaut de déclaration lobbying ; test", "d", "r", "loi", null, "2026-11-21T04:24:27+00:00", null, "2026-11-05");
  al.run("FIN-PARTI-DEP-2024-P1", "financement_parti_dependance_aide", "info", "Parti financé à 80 % par l'aide publique", "d", "r", "loi", "https://www.data.gouv.fr/partis", "2026-11-21T03:10:00+00:00", null, "2026-11-21");
  // Type retiré : ni dans le CSV, ni dans le flux.
  al.run("cc-1", "financement_campagne_rejetee", "haute", "Candidat nommé", "d", "r", "loi", "https://x", "2026-11-21", "2026-11-01", "2026-11-01");
  db.exec(`CREATE TABLE dole_dossiers (dossier_id TEXT PRIMARY KEY, titre TEXT, type TEXT, date_creation TEXT,
    date_modif TEXT, legislature_num TEXT, legislature_libelle TEXT, derniere_etape TEXT,
    derniere_etape_url TEXT, lien_legifrance TEXT)`);
  const dole = db.prepare(
    "INSERT INTO dole_dossiers (dossier_id, titre, type, date_creation, date_modif, legislature_num, legislature_libelle, derniere_etape, lien_legifrance) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
  );
  dole.run("JORFDOLE1", "Proposition de loi A", "PROPOSITION_LOI", "2025-01-02", "2026-11-20", "17", "XVIIe législature", "Adoption", "https://www.vie-publique.fr/dossierlegislatif/JORFDOLE1");
  dole.run("JORFDOLE2", "Loi ancienne", "LOI_PUBLIEE", null, "2026-11-19", "17", "XVIIe législature", "Promulgation", "https://www.vie-publique.fr/dossierlegislatif/JORFDOLE2");
  dole.run("JORFDOLE3", "Projet de loi ancien", "PROJET_LOI", null, "2020-01-01", "15", "XVe législature", "Dépôt", "https://www.vie-publique.fr/dossierlegislatif/JORFDOLE3");
  dole.run("JORFDOLE4", "Proposition de loi B", "PROPOSITION_LOI", "2025-06-07", null, "17", "XVIIe législature", "Dépôt", "https://www.vie-publique.fr/dossierlegislatif/JORFDOLE4");
  dole.run("JORFDOLE5", "Proposition de loi sans date", "PROPOSITION_LOI", null, null, "17", "XVIIe législature", "Dépôt", "https://www.vie-publique.fr/dossierlegislatif/JORFDOLE5");
  const colonnesTop = `rang INTEGER, siren TEXT, nom TEXT, nb_etablissements INTEGER, nb_marches INTEGER,
    montant_total REAL, montant_hors_suspects REAL, nb_marches_suspects INTEGER, montant_suspects REAL`;
  db.exec(`CREATE TABLE decp_top_acheteurs (${colonnesTop})`);
  db.exec(`CREATE TABLE decp_top_titulaires (${colonnesTop}, categorie TEXT)`);
  db.prepare("INSERT INTO decp_top_acheteurs VALUES (1, '123456789', 'Ville; de \"Test\"', 3, 40, 9e9, 1234567.5, 2, 99000000)").run();
  db.prepare("INSERT INTO decp_top_titulaires VALUES (1, '987654321', 'Entreprise', 1, 5, 10, 2000, 0, 0, 'PME')").run();
});

const corps = async (chemin) => {
  const { GET } = await importer(`app/${chemin}/route`);
  const r = GET();
  // Octets tels que l'export statique les écrit (Response.text() retirerait le BOM).
  const texte = new TextDecoder("utf-8", { ignoreBOM: true }).decode(await r.arrayBuffer());
  return { type: r.headers.get("content-type"), texte };
};

test("flux JO : les 3 derniers numéros, identifiant NOR, texte échappé", async () => {
  const { type, texte } = await corps("flux/jo.xml");
  assert.match(type, /application\/atom\+xml/);
  assert.match(texte, /<feed xmlns="http:\/\/www\.w3\.org\/2005\/Atom"/);
  assert.match(texte, /<id>tag:francetransparence\.fr,2026:flux\/jo\.xml<\/id>/);
  assert.equal((texte.match(/<entry>/g) ?? []).length, 4, "JO du 21, 20 et 19 seulement");
  assert.match(texte, /<id>tag:francetransparence\.fr,2026:jo\/NOR0\/JORFTEXT0<\/id>/);
  assert.match(texte, /<id>tag:francetransparence\.fr,2026:jo\/JORFTEXT1<\/id>/);
  assert.doesNotMatch(texte, /JORFTEXT4/);
  assert.match(texte, /<title>Décret n° 0 &amp; arrêté<\/title>/);
  // updated du flux = JO le plus récent, pas l'heure du build.
  assert.equal(texte.match(/<updated>([^<]*)<\/updated>/)[1], "2026-11-21T00:00:00Z");
});

test("flux dossiers : la navette de la législature courante seulement", async () => {
  const { texte } = await corps("flux/dossiers.xml");
  assert.match(texte, /dossier\/JORFDOLE1<\/id>[\s\S]*?<updated>2026-11-20T00:00:00Z<\/updated>/);
  assert.doesNotMatch(texte, /JORFDOLE2|JORFDOLE3/);
  // Sans mise à jour : la création du dossier, jamais la date des données (S43).
  assert.match(texte, /dossier\/JORFDOLE4<\/id>[\s\S]*?<updated>2025-06-07T00:00:00Z<\/updated>/);
  assert.doesNotMatch(texte, /JORFDOLE5/, "un dossier sans aucune date est écarté");
  assert.match(texte, /href="https:\/\/www\.vie-publique\.fr\/dossierlegislatif\/JORFDOLE1"/);
});

test("flux alertes : date du fait stable, sinon date de détection, aucun type retiré", async () => {
  const { texte } = await corps("flux/alertes.xml");
  assert.equal((texte.match(/<entry>/g) ?? []).length, 3);
  assert.doesNotMatch(texte, /Candidat nommé|cc-1/);
  // A1 et lobbying : datés de leur détection, jamais de date_fait (fichier
  // HATVP) ni de date_calcul.
  assert.match(texte, /alerte\/A1-ND-x<\/id>[\s\S]*?<updated>2026-11-03T00:00:00Z<\/updated>/);
  assert.match(texte, /alerte\/lob-1<\/id>[\s\S]*?<updated>2026-11-05T00:00:00Z<\/updated>/);
  assert.doesNotMatch(texte, /2026-11-12T|2026-11-21T0[34]/);
  // Dépendance : clôture de l'exercice, même détectée plus tard.
  assert.match(texte, /alerte\/FIN-PARTI-DEP-2024-P1<\/id>[\s\S]*?<updated>2024-12-31T00:00:00Z<\/updated>/);
  // updated du flux = entrée la plus récente, ni la date d'une source, ni le calcul.
  assert.equal(texte.match(/<updated>([^<]*)<\/updated>/)[1], "2026-11-05T00:00:00Z");
  assert.match(texte, /CNCCFP comptes des partis \(Licence Ouverte\)/);
  assert.match(texte, /HATVP liste\.csv \(Licence Ouverte\)/);
  assert.match(texte, /HATVP AGORA \(Licence Ouverte\)/);
  assert.match(texte, /rel="related" type="text\/html" href="https:\/\/francetransparence\.fr\/alertes\/"/);
});

test("flux sources : une entrée par source datée", async () => {
  const { texte } = await corps("flux/sources.xml");
  assert.equal((texte.match(/<entry>/g) ?? []).length, 8);
  assert.match(texte, /source\/S3\/2026-11-21</);
});

test("alertes.csv : en-tête de colonnes en première ligne, aucun type retiré", async () => {
  const { type, texte } = await corps("api/alertes.csv");
  assert.match(type, /text\/csv; charset=utf-8/);
  const lignes = texte.slice(1).split("\r\n");
  assert.ok(texte.startsWith("﻿"));
  assert.equal(lignes[0], "id;type;gravite;titre;detail;regle;base_legale;source_url;date_calcul;date_fait");
  assert.equal(lignes.length, 5, "trois alertes, puis la fin de ligne finale");
  assert.match(texte, /"Défaut de déclaration lobbying ; test"/);
  assert.doesNotMatch(texte, /Candidat nommé/);
});

test("alertes.provenance.txt : sources, licence, date des données et URL amont", async () => {
  const { type, texte } = await corps("api/alertes.provenance.txt");
  assert.match(type, /text\/plain; charset=utf-8/);
  assert.match(texte, /S14 : HATVP liste\.csv/);
  assert.match(texte, /Date des données : 2026-11-14/);
  assert.match(texte, /URL amont : https:\/\/www\.hatvp\.fr\/livraison\/opendata\/liste\.csv/);
  assert.match(texte, /https:\/\/francetransparence\.fr\/api\/alertes\.csv/);
});

test("provenance : une source attendue absente de meta_sources fait échouer le build", async () => {
  // elus.csv attend S17, S5-AMO10, S6-ODSEN et S14 : la base de test n'a ni S5-AMO10 ni S6-ODSEN.
  const { GET } = await importer("app/api/elus.provenance.txt/route");
  assert.throws(() => GET(), /Provenance elus\.csv : source\(s\) absente\(s\) de meta_sources : S5-AMO10, S6-ODSEN\./);
});

test("tops : colonnes du tableau, montants pour le tableur, sans montant_total", async () => {
  const a = (await corps("api/marches-top-acheteurs.csv")).texte;
  assert.equal(
    a,
    "﻿rang;nom;siren;nb_etablissements;nb_marches;montant_hors_signales;montant_signales;nb_marches_signales\r\n" +
      '1;"Ville; de ""Test""";123456789;3;40;1234567,5;99000000;2\r\n',
  );
  const t = (await corps("api/marches-top-titulaires.csv")).texte;
  assert.equal(
    t,
    "﻿rang;nom;siren;categorie;nb_etablissements;nb_marches;montant_hors_signales;montant_signales;nb_marches_signales\r\n" +
      "1;Entreprise;987654321;PME;1;5;2000;;0\r\n",
  );
});
