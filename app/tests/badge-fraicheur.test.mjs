// Badge de fraîcheur des modules (components/ui/FreshnessBadge.tsx) : il
// dit, daté du jour du build, l'état calculé par lib/fraicheur.ts quand la
// donnée a dépassé son seuil d'alerte, et il dit qu'il ouvre une nouvelle
// fenêtre. Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { importer } from "./outils/charger.mjs";

const { evalueFraicheur, libelleBadgeFraicheur, mentionBadgeFraicheur } =
  await importer("lib/fraicheur");

const SRC = fileURLToPath(new URL("../src", import.meta.url));
const BADGE = readFileSync(join(SRC, "components/ui/FreshnessBadge.tsx"), "utf8");
const BUILD = new Date("2026-11-21T12:00:00Z");

test("une source en attente d'édition porte sa mention datée, sans rien affirmer de l'amont", () => {
  // S21 (PLF 2025 par destination, seuils 400/440) au 21/11/2026 : 771 jours.
  const f = evalueFraicheur("S21", "2024-10-11", BUILD);
  assert.equal(f.niveau, "attente_edition");
  const mention = mentionBadgeFraicheur(f, BUILD);
  assert.equal(
    mention,
    "au 21/11/2026, âge au-delà du seuil d’alerte, aucune édition plus récente ingérée",
  );
  // « édition plus récente non ingérée » supposerait qu'une édition a paru :
  // le site ne le vérifie pas (lib/fraicheur.ts, NiveauFraicheur).
  assert.doesNotMatch(mention, /non ingérée/);
});

test("une source au-delà de son seuil d'alerte le dit, une source à jour ne dit rien de plus", () => {
  // S21 : 441 jours = au-delà de l'alerte (440), en deçà de 480 (alerte + bande).
  const enRetard = evalueFraicheur("S21", "2025-09-06", BUILD);
  assert.equal(enRetard.niveau, "en_retard");
  assert.equal(mentionBadgeFraicheur(enRetard, BUILD), "au 21/11/2026, âge au-delà du seuil d’alerte");
  for (const niveau of ["a_jour", "a_surveiller", "non_calibre"]) {
    assert.equal(mentionBadgeFraicheur({ niveau }, BUILD), null, niveau);
  }
});

test("la mention est datée du jour civil de Paris du calcul", () => {
  // 23h30 UTC le 21/11 = 00h30 le 22/11 à Paris.
  const nuit = new Date("2026-11-21T23:30:00Z");
  assert.match(mentionBadgeFraicheur({ niveau: "en_retard" }, nuit), /^au 22\/11\/2026, /);
});

test("le libellé du badge ajoute l'état daté de la source, seulement quand sourceId est donné", () => {
  const base = { dateDonnees: "2024-10-11", source: "PLF 2025", frequence: "annuelle" };
  assert.equal(libelleBadgeFraicheur(base, BUILD), "Données au 11/10/2024 · PLF 2025 · annuelle");
  assert.equal(
    libelleBadgeFraicheur({ ...base, mention: "PLF", sourceId: "S21" }, BUILD),
    "Données au 11/10/2024 · PLF 2025 · annuelle · PLF · au 21/11/2026, âge au-delà du seuil d’alerte, aucune édition plus récente ingérée",
  );
  // Une source à jour, ou sans seuil calibré, n'ajoute rien.
  assert.equal(
    libelleBadgeFraicheur({ ...base, dateDonnees: "2026-11-20", sourceId: "S21" }, BUILD),
    "Données au 20/11/2026 · PLF 2025 · annuelle",
  );
  assert.equal(
    libelleBadgeFraicheur({ ...base, sourceId: "S_INCONNUE" }, BUILD),
    "Données au 11/10/2024 · PLF 2025 · annuelle",
  );
});

test("le badge affiche ce libellé, calculé à l'instant de la construction", () => {
  assert.match(BADGE, /libelleBadgeFraicheur\([\s\S]*?instantDeConstruction\(\)/);
  assert.match(BADGE, /\{libelle\}/);
});

test("le badge, qui ouvre un nouvel onglet, le dit aux lecteurs d'écran", () => {
  assert.match(BADGE, /target="_blank"/);
  assert.match(BADGE, /className="sr-only">[^<]*nouvelle fenêtre/);
});

test("chaque badge serveur qui lit une ligne meta_sources lui passe son sourceId", () => {
  // Sans sourceId, le badge tait qu'une source a dépassé son seuil d'alerte
  // (S21 sur /depenses/destination, S46 sur /recettes, S38 sur /frais).
  const fautes = [];
  let vus = 0;
  const parcourir = (dossier) => {
    for (const nom of readdirSync(dossier)) {
      const chemin = join(dossier, nom);
      if (statSync(chemin).isDirectory()) parcourir(chemin);
      else if (chemin.endsWith(".tsx")) {
        const s = readFileSync(chemin, "utf8");
        if (/^["']use client["']/.test(s)) continue;
        for (const m of s.matchAll(/<FreshnessBadge\b((?:=>|[^>])*?)\/>/g)) {
          const meta = /\bdateDonnees=\{([\w.]+)\.date_donnees\}/.exec(m[1]);
          if (!meta) continue;
          vus += 1;
          if (!m[1].includes(`sourceId={${meta[1]}.source_id}`)) {
            const ligne = s.slice(0, m.index).split("\n").length;
            fautes.push(`${chemin.slice(SRC.length + 1)}:${ligne}`);
          }
        }
      }
    }
  };
  parcourir(SRC);
  assert.ok(vus >= 40, `${vus} badges vus seulement`);
  assert.deepEqual(fautes, []);
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
