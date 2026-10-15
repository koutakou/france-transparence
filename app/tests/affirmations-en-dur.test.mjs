// Affirmations écrites en dur dans les pages, qui ont cessé d'être vraies
// quand les données ont bougé (CONTRIBUTING § 5 : pas de chiffre qui dérive
// écrit en dur). Chacune a été remplacée par une valeur ou une phrase
// dérivée des données ; ce test empêche qu'elle revienne telle quelle.
// Garde documentaire : il lit les sources, il ne rend pas les pages.
// Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const lire = (chemin) => fs.readFileSync(new URL(`../src/${chemin}`, import.meta.url), "utf8");

/** [fichier, motif interdit, pourquoi] */
const INTERDITS = [
  [
    "app/page.tsx",
    /mention="J-1"/,
    "« J-1 » ne vaut que si les DECP sont datées de la veille (estVeille)",
  ],
  [
    "app/marches/page.tsx",
    /les 2 derniers mois sont incomplets/,
    "les mois incomplets se déduisent du 9e décile du délai de publication",
  ],
  [
    "app/marches/page.tsx",
    /serieMensuelle\.slice\(-12\)/,
    "la tendance 12 mois ne finit pas sur un mois civil inachevé (moisClos)",
  ],
  [
    "components/client/SerieMensuelleMarches.tsx",
    /montant_total \?\? 0/,
    "un mois sans montant connu n'est pas une colonne à zéro",
  ],
  [
    "app/lobbying/page.tsx",
    /des activités rattachées à un destinataire/,
    "le dénominateur additionne des mentions de destinataire, pas des activités",
  ],
];

for (const [fichier, motif, pourquoi] of INTERDITS) {
  test(`${fichier} : ${pourquoi}`, () => {
    assert.doesNotMatch(lire(fichier), motif);
  });
}
