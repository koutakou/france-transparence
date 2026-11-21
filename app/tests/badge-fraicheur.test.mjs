// Badge de fraîcheur des modules (components/ui/FreshnessBadge.tsx) : il
// dit l'état calculé par lib/fraicheur.ts quand la donnée a dépassé son
// seuil d'alerte, et il dit qu'il ouvre une nouvelle fenêtre. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { importer } from "./outils/charger.mjs";

const { evalueFraicheur, mentionBadgeFraicheur } = await importer("lib/fraicheur");

const SRC = fileURLToPath(new URL("../src", import.meta.url));
const BADGE = readFileSync(join(SRC, "components/ui/FreshnessBadge.tsx"), "utf8");

test("une source en attente d'édition porte sa mention, sans rien affirmer de l'amont", () => {
  // S21 (PLF 2025 par destination, seuils 400/440) au 21/11/2026 : 771 jours.
  const f = evalueFraicheur("S21", "2024-10-11", new Date("2026-11-21T12:00:00Z"));
  assert.equal(f.niveau, "attente_edition");
  const mention = mentionBadgeFraicheur(f);
  assert.equal(mention, "âge au-delà du seuil d’alerte, aucune édition plus récente ingérée");
  // « édition plus récente non ingérée » supposerait qu'une édition a paru :
  // le site ne le vérifie pas (lib/fraicheur.ts, NiveauFraicheur).
  assert.doesNotMatch(mention, /non ingérée/);
});

test("une source au-delà de son seuil d'alerte le dit, une source à jour ne dit rien de plus", () => {
  // S21 : 441 jours = au-delà de l'alerte (440), en deçà de 480 (alerte + bande).
  const enRetard = evalueFraicheur("S21", "2025-09-06", new Date("2026-11-21T12:00:00Z"));
  assert.equal(enRetard.niveau, "en_retard");
  assert.equal(mentionBadgeFraicheur(enRetard), "âge au-delà du seuil d’alerte");
  for (const niveau of ["a_jour", "a_surveiller", "non_calibre"]) {
    assert.equal(mentionBadgeFraicheur({ niveau }), null, niveau);
  }
});

test("le badge calcule l'état au jour de la construction et l'ajoute à son libellé", () => {
  assert.match(BADGE, /mentionBadgeFraicheur\(\s*evalueFraicheur\(sourceId, dateDonnees, new Date\(instantDeConstruction\(\)\)\)/);
  assert.match(BADGE, /\$\{etat \? ` · \$\{etat\}` : ""\}/);
});

test("le badge, qui ouvre un nouvel onglet, le dit aux lecteurs d'écran", () => {
  assert.match(BADGE, /target="_blank"/);
  assert.match(BADGE, /<span className="sr-only"> \(nouvelle fenêtre\)<\/span>/);
});

test("aucun composant client ne passe sourceId au badge (l'hydratation recalculerait l'état à une autre date)", () => {
  const fautes = [];
  const parcourir = (dossier) => {
    for (const nom of readdirSync(dossier)) {
      const chemin = join(dossier, nom);
      if (statSync(chemin).isDirectory()) parcourir(chemin);
      else if (chemin.endsWith(".tsx")) {
        const s = readFileSync(chemin, "utf8");
        if (/^["']use client["']/.test(s) && /<FreshnessBadge\b[^>]*\bsourceId=/.test(s)) {
          fautes.push(chemin.slice(SRC.length + 1));
        }
      }
    }
  };
  parcourir(SRC);
  assert.deepEqual(fautes, []);
});
