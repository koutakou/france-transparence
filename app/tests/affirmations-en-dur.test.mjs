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
    "app/page.tsx",
    /échéances passées retirées/,
    "sans JavaScript rien n'est retiré : le sous-titre date la liste, il ne promet pas le re-filtre",
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
  [
    "app/financement/page.tsx",
    /formatNombre\(kpi\.depots2024\)\} partis ont\s+déclaré avoir perçu/,
    "les partis qui déclarent une aide sont nb_partis_aides, pas tous les dépôts",
  ],
  [
    "app/financement/page.tsx",
    /ordre de grandeur des enveloppes|aucune hausse de l&apos;enveloppe/,
    "aucune comparaison à une enveloppe absente de la base",
  ],
  [
    "app/financement/page.tsx",
    /les déclarations dépassent l&apos;enveloppe/,
    "le verbe suit le signe de l'écart calculé",
  ],
  [
    "app/financement/page.tsx",
    /aucun compte de campagne n’est publié à ce jour/,
    "pas d'affirmation d'inexistence sur l'amont",
  ],
  [
    "app/donnees/page.tsx",
    /n’a été publiée|première\s+ingestion qui la trouve/,
    "« en attente » dit ce qui a été ingéré, pas ce que l'amont a publié",
  ],
  [
    "app/elus/page.tsx",
    /\d+,\d+\s*%\s+de la présidente/,
    "le taux de la présidence se recalcule chaque jour : pas de valeur en dur",
  ],
  [
    "app/collectivites/page.tsx",
    /jusqu&apos;en décembre 20\d\d/,
    "l'année de fin du provisoire se déduit de l'exercice",
  ],
  [
    "app/collectivites/page.tsx",
    /environ \d+ communes manquent/,
    "le nombre de communes se lit en base",
  ],
  [
    "app/depenses/page.tsx",
    /formatValeur=\{\(v\) => formatEuros\(v, "Md"\)\}/,
    "un montant en Md€ s'arrondit à une décimale fixe, comme sur l'accueil",
  ],
  [
    "app/depenses/destination/page.tsx",
    /formatValeur=\{\(v\) => formatEuros\(v, "Md"\)\}/,
    "un montant en Md€ s'arrondit à une décimale fixe, comme sur l'accueil",
  ],
];

for (const [fichier, motif, pourquoi] of INTERDITS) {
  test(`${fichier} : ${pourquoi}`, () => {
    assert.doesNotMatch(lire(fichier), motif);
  });
}
