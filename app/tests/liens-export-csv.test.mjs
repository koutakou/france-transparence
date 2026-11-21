// Liens « Télécharger (CSV) » sous les tableaux (components/ui/LienExportCsv) :
// chacun pointe vers une route statique qui existe, avec sa provenance à
// côté. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { importer } from "./outils/charger.mjs";

const exportsCsv = await importer("lib/exports-csv");
const { cheminCsv, cheminProvenance, EXPORTS_CSV } = exportsCsv;

const SRC = fileURLToPath(new URL("../src", import.meta.url));
const COMPOSANT = readFileSync(join(SRC, "components/ui/LienExportCsv.tsx"), "utf8");

/** Fichier de route statique qui publie le chemin du site `/api/<nom>`. */
const route = (chemin) => join(SRC, "app", chemin.replace(/^\//, ""), "route.ts");

/** Chaque usage du lien : page, ligne et constante de définition passée. */
function usages() {
  const trouves = [];
  const parcourir = (dossier) => {
    for (const nom of readdirSync(dossier)) {
      const chemin = join(dossier, nom);
      if (statSync(chemin).isDirectory()) parcourir(chemin);
      else if (chemin.endsWith(".tsx")) {
        const s = readFileSync(chemin, "utf8");
        for (const m of s.matchAll(/<LienExportCsv\b((?:=>|[^>])*?)\/>/g)) {
          const def = /\bdefinition=\{(\w+)\}/.exec(m[1]);
          trouves.push({
            page: chemin.slice(SRC.length + 1).split("\\").join("/"),
            ligne: s.slice(0, m.index).split("\n").length,
            constante: def?.[1] ?? null,
          });
        }
      }
    }
  };
  parcourir(SRC);
  return trouves;
}

test("les chemins du CSV et de sa provenance", () => {
  assert.equal(cheminCsv("elus.csv"), "/api/elus.csv");
  assert.equal(cheminProvenance("elus.csv"), "/api/elus.provenance.txt");
});

test("le composant tire ses deux liens de la définition de l'export", () => {
  assert.match(COMPOSANT, /href=\{urlSite\(cheminCsv\(definition\.fichier\)\)\}/);
  assert.match(COMPOSANT, /href=\{urlSite\(cheminProvenance\(definition\.fichier\)\)\}/);
});

test("chaque lien « Télécharger (CSV) » pointe vers une route qui existe, provenance comprise", () => {
  const fautes = [];
  for (const u of usages()) {
    const def = u.constante ? exportsCsv[u.constante] : undefined;
    const ou = `${u.page}:${u.ligne}`;
    if (!def || !EXPORTS_CSV.includes(def)) {
      fautes.push(`${ou} : ${u.constante ?? "définition calculée"} n'est pas un export de EXPORTS_CSV`);
      continue;
    }
    for (const chemin of [cheminCsv(def.fichier), cheminProvenance(def.fichier)]) {
      if (!existsSync(route(chemin))) fautes.push(`${ou} : aucune route pour ${chemin}`);
    }
  }
  assert.deepEqual(fautes, []);
});

test("les tableaux principaux qui ont un export portent leur lien", () => {
  const attendus = {
    "app/marches/page.tsx": ["CSV_TOP_ACHETEURS", "CSV_TOP_TITULAIRES"],
    "app/alertes/page.tsx": ["CSV_ALERTES"],
    "app/depenses/page.tsx": ["CSV_BUDGET_MENSUEL"],
    "app/lobbying/page.tsx": ["CSV_LOBBYING_MARCHES"],
    "app/elus/page.tsx": ["CSV_ELUS"],
  };
  const vus = usages();
  for (const [page, constantes] of Object.entries(attendus)) {
    const surPage = vus.filter((u) => u.page === page).map((u) => u.constante);
    for (const c of constantes) assert.ok(surPage.includes(c), `${page} : lien ${c} absent`);
  }
});
