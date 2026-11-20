// Textes faux, ton et promesse sur les sources (audit des pages du
// 20/11/2026, F1, F3, R3, R5 à R8, R11 ; décisions du propriétaire du même
// jour). Garde documentaire : lit les sources et appelle les modules purs.
// Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { mentionPatrimoine } from "../src/lib/mention-patrimoine.ts";
import { libelleCadre, sourceOfficielle } from "../src/lib/frais-textes.ts";
import { natureSource } from "../src/lib/nature-sources.ts";
import { perimetreMontantNotifie } from "../src/lib/phrases.ts";

const SRC = fileURLToPath(new URL("../src/", import.meta.url));
const lire = (chemin) => readFileSync(path.join(SRC, chemin), "utf8");
const aplati = (chemin) => lire(chemin).replace(/\s+/g, " ");

/** Texte servi d'un fichier : commentaires retirés (le code peut garder ses
 *  noms de colonne, comme `montant_suspect`, et ses notes internes). */
const sansCommentaires = (s) =>
  s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'\w])\/\/.*$/gm, "$1");

function fichiers(dossier) {
  const out = [];
  for (const nom of readdirSync(dossier)) {
    const p = path.join(dossier, nom);
    if (statSync(p).isDirectory()) out.push(...fichiers(p));
    else if (/\.tsx?$/.test(p)) out.push(p);
  }
  return out;
}

test("F1 : la fiche d'un exécutif local ne renvoie pas à la préfecture", () => {
  const local = mentionPatrimoine(false);
  assert.doesNotMatch(local, /préfecture/);
  assert.match(local, /ne rend pas publique la déclaration de patrimoine/);
  assert.match(local, /loi n° 2013-907 du 11 octobre 2013, art\. 11 et 12/);
  const parlementaire = mentionPatrimoine(true);
  assert.match(parlementaire, /qu’en préfecture/);
  assert.match(parlementaire, /art\. LO 135-2 du code électoral/);
  const fiche = lire("app/elus/[id]/page.tsx");
  assert.doesNotMatch(fiche, /il se consulte en préfecture/);
  assert.match(fiche, /mentionPatrimoine\(Boolean\(depute \|\| senateur\)\)/);
});

test("F3 : « Base du refus » seulement quand un refus daté est cité", () => {
  assert.equal(
    libelleCadre("Calendrier de publication de la Cour des comptes ; aucune obligation de délai ni de format ouvert."),
    "Cadre",
  );
  assert.equal(libelleCadre("Choix de publication du Sénat : agrégats seuls."), "Cadre");
  assert.equal(libelleCadre("Refus écrit de l'institution du 11/06/2026."), "Base du refus");
  // Mêmes cas que test_libelle_cadre_meme_regle_que_l_ecran (pipeline) :
  // une date dans une autre phrase, ou un refus nié, ne font pas un refus daté.
  assert.equal(libelleCadre("Refus. Rapport du 17/09/2026"), "Cadre");
  assert.equal(libelleCadre("aucun refus, calendrier du 17/09/2026"), "Cadre");
  const page = lire("app/frais/page.tsx");
  assert.doesNotMatch(page, /Base du refus/);
  assert.match(page, /libelleCadre\(o\.base_du_refus\)/);
});

test("R3 : /frais ne cite que des producteurs officiels", () => {
  for (const url of [
    "https://www.conseil-etat.fr/fr/arianeweb/CE/decision/2019-06-27/427725",
    "https://www.assemblee-nationale.fr/dyn/15/questions/QANR5L15QE30813",
    "https://www.conseil-etat.fr/fr/arianeweb/CE/decision/2023-02-08/452521",
    "https://www.ccomptes.fr/fr/publications/x",
    "https://www.collectivites-locales.gouv.fr/files/x.pdf",
    "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000033218936",
    "https://www.hatvp.fr/x",
    "https://www.cada.fr/x",
    "https://www.vie-publique.fr/x",
  ]) {
    assert.equal(sourceOfficielle(url), true, url);
  }
  for (const url of [
    "https://www.lecourrierdesstrateges.fr/notes-de-frais-des-parlementaires/",
    "https://next.ink/6725/108060-frais-representation-ministres/",
    "https://www.seban-associes.avocat.fr/les-notes-de-frais/",
    "https://faux-senat.fr/x",
    "https://senat.fr.exemple.com/x",
    "http://www.senat.fr/x",
    "pas une url",
  ]) {
    assert.equal(sourceOfficielle(url), false, url);
  }
  const requetes = lire("lib/queries/frais.ts");
  assert.match(requetes, /faits\.filter\(\(f\) => sourceOfficielle\(f\.source_url\)\)/);
  assert.match(requetes, /opacites\.filter\(\(o\) => sourceOfficielle\(o\.source_url\)\)/);
  // Les refus du 11/06/2026 n'ont pas de source officielle : retirés.
  for (const f of ["app/frais/page.tsx", "app/comprendre/page.tsx", "app/donnees/page.tsx"]) {
    assert.doesNotMatch(aplati(f), /11 juin 2026|11\/06\/2026|CE mars 2025/, f);
  }
  // « Ni communicables » citait l'ordonnance 58-1100, qui ne le dit pas : la
  // source qui le juge est le Conseil d'État, 27/06/2019, n° 427725.
  for (const f of ["app/frais/page.tsx", "app/comprendre/page.tsx"]) {
    const s = aplati(f);
    assert.doesNotMatch(s, /ni publié(e)?s ni communicables/, f);
    assert.doesNotMatch(s, /refus d’accès aux justificatifs/, f);
    assert.match(s, /27&nbsp;juin 2019/, f);
  }
});

test("R5 : l'accueil dit que le PLF 2025 est une édition ancienne, à côté du PLF 2026", () => {
  const s = aplati("app/page.tsx");
  assert.match(s, /Budget par ministère \(PLF 2025, édition ancienne\)/);
  assert.match(s, /plus ancienne que le PLF 2026 du bloc des missions/);
});

test("R6 : les prélèvements sur recettes sortent du « Top 5 missions »", () => {
  const s = lire("lib/queries/accueil.ts");
  assert.match(s, /PRELEVEMENTS_SUR_RECETTES = \["PSRCT", "PSRUE"\]/);
  assert.match(s, /AND \$\{SQL_HORS_PRELEVEMENTS\}/);
  assert.match(aplati("app/page.tsx"), /hors prélèvements sur recettes/);
});

test("R7 : la tuile de /marches dit accords-cadres au maximum et part signalée", () => {
  const p = perimetreMontantNotifie("26 %");
  assert.match(p, /accords-cadres comptés à leur montant maximum/);
  assert.match(p, /26 % du montant porte le drapeau « montant signalé »/);
  assert.match(p, /Ce que vaut ce total/);
  assert.match(perimetreMontantNotifie(null), /une part du montant porte le drapeau/);
  assert.match(lire("app/marches/page.tsx"), /perimetre: perimetreMontantNotifie\(/);
});

test("R8 : montants vedettes en couleur neutre, pas dans le rouge du « mauvais »", () => {
  const css = lire("app/globals.css");
  const montant = css.match(/--montant:\s*([^;]+);/)[1].trim();
  const mauvais = css.match(/--delta-mauvais:\s*([^;]+);/)[1].trim();
  assert.notEqual(montant, mauvais);
  assert.equal(montant, "var(--ink-primary)");
});

test("R8 et R11 : aucun libellé qui juge, aucun texte interne dans les pages", () => {
  const INTERDITS = [
    [/dépensier/i, "« plus dépensiers » : « dépenses par habitant les plus élevées »"],
    [/(?<![\w.])suspect(e|s|es)?(?!\w)/i, "« suspect » : « montant signalé »"],
    [/(?<!\w)verrous?(?!\w)/i, "« verrous » : « avis de la CADA par administration »"],
    [/boîte noire/i, "« boîte noire » : « ce que la loi ne publie pas »"],
    [/retard de versement/i, "un écart de publication n'est pas un retard imputable"],
    [/SOURCES\.md\s*§/, "référence interne sans lien"],
    [/à déclencher/i, "consigne d'exploitation"],
    [/anti-bot/i, "note d'exploitation"],
  ];
  const fautes = [];
  for (const dossier of ["app", "components"]) {
    for (const f of fichiers(path.join(SRC, dossier))) {
      // Les alertes ont leur propre lot (textes produits par le pipeline).
      if (/AlertesListe\.tsx$/.test(f)) continue;
      const s = sansCommentaires(readFileSync(f, "utf8"));
      for (const [motif, pourquoi] of INTERDITS) {
        const m = s.match(motif);
        if (m) fautes.push(`${path.relative(SRC, f)} : « ${m[0]} » (${pourquoi})`);
      }
    }
  }
  assert.deepEqual(fautes, []);
});

test("Promesse : sources publiques officielles, plus des consolidations créditées", () => {
  const PROMESSE = "sources publiques officielles, plus quelques consolidations reconnues et créditées";
  for (const f of [
    "app/page.tsx",
    "app/donnees/page.tsx",
    "app/comprendre/page.tsx",
    "app/mentions-legales/page.tsx",
    "app/elus/page.tsx",
    "app/elus/[id]/page.tsx",
    "lib/seo.ts",
  ]) {
    assert.ok(aplati(f).includes(PROMESSE), f);
  }
  // Texte alternatif de l'image de partage : il décrit l'image, qui porte
  // la même promesse (public/og.svg, source de public/og.png).
  const alt = aplati("lib/seo.ts").match(/alt: "([^"]*)"/)[1];
  assert.ok(alt.includes(PROMESSE), alt);
  const svg = readFileSync(new URL("../public/og.svg", import.meta.url), "utf8").replace(/\s+/g, " ");
  assert.ok(svg.includes("Sources publiques officielles, plus quelques consolidations reconnues et créditées"), "og.svg");
  assert.match(svg, /francetransparence\.fr/);
  assert.doesNotMatch(svg, /koutakou\.github\.io|données publiques officielles/i);
  const ANCIENNES = [
    /seules sources publiques officielles/,
    /exclusivement de publications officielles/,
    /uniquement à partir de données publiques officielles/,
    /données publiques réelles uniquement/,
  ];
  // Promesse tronquée dans un texte servi (texte alternatif, /elus, fiches
  // d'élu) : « à partir des données (publiques) officielles », sans les
  // consolidations. Tout src/, lib/ compris, hors commentaires.
  const TRONQUEE = /(à partir|issues?|proviennent) (des|de) données (publiques )?officielles/i;
  for (const f of fichiers(SRC)) {
    const brut = readFileSync(f, "utf8");
    const s = brut.replace(/\s+/g, " ");
    for (const motif of ANCIENNES) assert.doesNotMatch(s, motif, path.relative(SRC, f));
    assert.doesNotMatch(sansCommentaires(brut).replace(/\s+/g, " "), TRONQUEE, path.relative(SRC, f));
  }
  const readme = readFileSync(new URL("../../README.md", import.meta.url), "utf8");
  assert.ok(readme.includes(PROMESSE), "README");
  assert.doesNotMatch(readme, /100 % données publiques réelles/);
});

test("/donnees : S1, S7 (Datan) et S31 portent leur étiquette", () => {
  assert.equal(natureSource("S1").etiquette, "Consolidation reconnue, non officielle");
  assert.equal(natureSource("S7-DATAN").etiquette, "Consolidation reconnue, non officielle");
  assert.equal(natureSource("S31").etiquette, "Officielle, recopiée à la main");
  assert.equal(natureSource("S10"), null);
  assert.match(natureSource("S1").detail, /Colin Maudry/);
  assert.match(natureSource("S7-DATAN").detail, /Datan/);
  assert.match(natureSource("S31").detail, /recopiés à la main de documents officiels \(textes de loi, rapports, PDF publics\)/);
  assert.match(natureSource("S31").detail, /sans jeu de données ouvert lisible par machine/);
  assert.match(lire("app/donnees/page.tsx"), /natureSource\(s\.source_id\)/);
});
