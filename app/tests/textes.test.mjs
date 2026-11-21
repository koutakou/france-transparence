// Contrôles STATIQUES de textes publics écrits dans le source (pas un rendu) :
// des affirmations fausses ou des formes cassées déjà publiées une fois.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const lire = (chemin) => readFileSync(new URL(`../src/${chemin}`, import.meta.url), "utf8");
// JSX replie les retours à la ligne en une espace : on compare sur ce texte-là.
const aplati = (chemin) => lire(chemin).replace(/\s*\n\s*/g, " ");

test("/comprendre : S.1311 est l'administration centrale, pas « l'État seul » (S13111)", () => {
  const s = aplati("app/comprendre/page.tsx");
  assert.doesNotMatch(s, /État seul \((sous-secteur )?S\.?1311\)/);
});

test("/elus : « affiché·es » d'un seul tenant (JSX joint deux lignes par une espace)", () => {
  const s = aplati("components/client/TableParlementaires.tsx");
  assert.doesNotMatch(s, /affiché ·e/);
});

test("fragment indisponible : « (filtrés) » n'est jamais dit d'une liste non filtrée", () => {
  const s = aplati("components/client/FluxTextes.tsx");
  assert.doesNotMatch(s, /filtreActif \? " \(filtrés\)" : ""/);
});

test("/donnees : pas de somme des volumes (unités différentes d'une source à l'autre)", () => {
  const s = aplati("app/donnees/page.tsx");
  assert.doesNotMatch(s, /lignes ingérées/);
});

test("/donnees : les pipelines renvoient à PIPELINES, l'ADLC est créditée", () => {
  const s = aplati("app/donnees/page.tsx");
  assert.match(s, /PIPELINES/);
  assert.match(s, /Autorité de la concurrence/);
});

test("/collectivites : le « Flop 10 » ne range pas un département sans valeur", () => {
  const s = aplati("app/collectivites/page.tsx");
  assert.doesNotMatch(s, /flop10Dep = departements/);
});

test("élections : pas de « 1er tour » pour les européennes (un seul tour)", () => {
  const s = aplati("lib/queries/elections.ts");
  assert.match(s, /codeFamille === "euro"/);
});

test("Licence Ouverte : aucun lien vers l'adresse etalab.gouv.fr redirigée vers l'accueil de data.gouv.fr", async () => {
  const { readdirSync, statSync } = await import("node:fs");
  const { join } = await import("node:path");
  const racine = fileURLToPath(new URL("../src", import.meta.url));
  const fautes = [];
  const parcourir = (d) => {
    for (const n of readdirSync(d)) {
      const p = join(d, n);
      if (statSync(p).isDirectory()) parcourir(p);
      else if (/\.tsx?$/.test(p) && readFileSync(p, "utf8").includes("etalab.gouv.fr/licence-ouverte")) fautes.push(p);
    }
  };
  parcourir(racine);
  assert.deepEqual(fautes, []);
});

test("/recettes et /comprendre : deux phrases liées par « mais » et « et », sans virgule de juxtaposition", () => {
  const r = aplati("app/recettes/page.tsx");
  assert.match(r, /ne les contient pas, mais celui du \$\{formatDateFr\(kpis\.dateFinMois\)\} a un autre périmètre/);
  const c = aplati("app/comprendre/page.tsx");
  assert.match(c, /Ce site les republie et n’estime pas ce qui n’y figure pas\./);
  assert.doesNotMatch(c, /les republie, il n’estime/);
});

test("« n.d. » seulement pour un manque : ministère sans objet, vote sans position dit en clair", () => {
  const flux = aplati("components/client/FluxTextes.tsx");
  // « s.o. » selon la nature du texte (tests/jorf-sans-objet.test.mjs), jamais pour tous.
  assert.match(flux, /<Vide sansObjet=\{ministereSansObjet\(l\.nature, l\.titre\)\} \/>/);
  assert.doesNotMatch(flux, /<Vide sansObjet \/>/);
  assert.match(flux, /affiché « \$\{SANS_OBJET\} » \(sans objet\) pour une loi, une ordonnance ou une décision du Conseil constitutionnel, « \$\{VIDE\} » \(non disponible\) sinon/);
  const vide = lire("components/ui/Vide.tsx");
  assert.match(vide, /<abbr title="sans objet">\{SANS_OBJET\}<\/abbr>/);
  const elu = aplati("app/elus/[id]/page.tsx");
  assert.match(elu, /if \(!l\.position\) return <span className="text-ink-muted">Sans position enregistrée<\/span>;/);
  // Les légendes sous les tableaux de votes décrivent la cellule affichée.
  assert.doesNotMatch(elu, /« n\.d\. » : aucune position/);
  assert.match(elu, /Sans position enregistrée : aucune position au scrutin public, donnée de l’Assemblée telle quelle\./);
  assert.match(elu, /Sans position enregistrée : aucune position au scrutin public, donnée du Sénat telle quelle\./);
});

test("libellé PLF 2025 : la copie de l'app est le texte exact du pipeline, sans tiret long", () => {
  const py = readFileSync(new URL("../../pipelines/ingest_recettes_plf.py", import.meta.url), "utf8");
  const bloc = py.match(/^ETIQUETTE = \(\r?\n([\s\S]*?)\r?\n\)/m);
  assert.ok(bloc, "constante ETIQUETTE du pipeline introuvable");
  const pipeline = [...bloc[1].matchAll(/"([^"]*)"/g)].map((m) => m[1]).join("");
  assert.equal(pipeline, "PLF 2025 déposé en octobre 2024 : projet, pas la LFI 2025 votée, pas l'exécution (S13)");
  const app = lire("lib/queries/recettes-plf.ts").match(/export const ETIQUETTE_PLF = \(\s*"([^"]*)"\s*\)/);
  assert.ok(app, "ETIQUETTE_PLF introuvable");
  assert.equal(app[1], pipeline);
});

test("/comprendre : aucune phrase datée figée (« au 24 août 2026 », « mesuré le … »)", () => {
  const s = aplati("app/comprendre/page.tsx");
  assert.doesNotMatch(s, /en données au \d{1,2} \w+ 20\d\d/);
  assert.doesNotMatch(s, /Millésime mesuré le/);
});
