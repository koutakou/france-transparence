// Contrôles du source et, quand un module pur le permet, du rendu. ARIA 1.2 interdit
// `aria-label` sur un élément sans rôle (div, span… = rôle « generic »,
// règle axe `aria-prohibited-attr`) ; les lecteurs d'écran l'ignorent, et un
// graphique focalisable devient un arrêt de tabulation muet. Toute balise
// générique qui porte un nom doit aussi porter un `role=`.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { importer } from "./outils/charger.mjs";

const racine = fileURLToPath(new URL("../src", import.meta.url));
const fichiers = [];
const parcourir = (dossier) => {
  for (const nom of readdirSync(dossier)) {
    const chemin = join(dossier, nom);
    if (statSync(chemin).isDirectory()) parcourir(chemin);
    else if (chemin.endsWith(".tsx")) fichiers.push(chemin);
  }
};
parcourir(racine);

// Balises sans rôle implicite. `=>` est sauté pour ne pas couper une balise
// sur une fonction fléchée passée en attribut.
const BALISE = /<(div|span|p|li|b|i|em|strong|small)\b((?:=>|[^>])*?)>/g;

test("aucun aria-label sur une balise générique sans role", () => {
  const fautes = [];
  for (const f of fichiers) {
    const s = readFileSync(f, "utf8");
    for (const m of s.matchAll(BALISE)) {
      if (/\baria-label=/.test(m[2]) && !/\brole=/.test(m[2])) {
        const ligne = s.slice(0, m.index).split("\n").length;
        fautes.push(`${f.slice(racine.length + 1)}:${ligne} <${m[1]}>`);
      }
    }
  }
  assert.deepEqual(fautes, []);
});

// --ink-muted est le MINIMUM pour du texte (4,83:1 sur --surface-hover) :
// l'atténuer par une opacité le fait passer sous 4,5:1 (« ‹ Page
// précédente » inactive de /alertes : 2,47:1). Un état inactif se dit par
// aria-disabled et une forme (bordure tiretée), pas par l'opacité.
test("aucun texte --ink-muted atténué par une opacité", () => {
  const fautes = [];
  for (const f of fichiers) {
    const s = readFileSync(f, "utf8");
    for (const m of s.matchAll(/className="([^"]*)"/g)) {
      if (/\btext-ink-muted\b/.test(m[1]) && /\bopacity-\d+\b/.test(m[1])) {
        const ligne = s.slice(0, m.index).split("\n").length;
        fautes.push(`${f.slice(racine.length + 1)}:${ligne}`);
      }
    }
  }
  assert.deepEqual(fautes, []);
});

// Chaque tableau porte une légende : un lecteur d'écran qui passe de tableau
// en tableau (89 sur l'échantillon de l'audit, aucun légendé) doit savoir
// lequel il lit. DataTable la rend en <caption class="sr-only"> (prop
// `legende`, à défaut `libelle` ou les en-têtes).
test("chaque <table> a un <caption> ou un aria-labelledby", () => {
  const fautes = [];
  for (const f of fichiers) {
    const s = readFileSync(f, "utf8");
    for (const m of s.matchAll(/<table\b((?:=>|[^>])*?)>/g)) {
      const suite = s.slice(m.index + m[0].length).trimStart();
      if (!/\baria-labelledby=/.test(m[1]) && !suite.startsWith("<caption")) {
        const ligne = s.slice(0, m.index).split("\n").length;
        fautes.push(`${f.slice(racine.length + 1)}:${ligne}`);
      }
    }
  }
  assert.deepEqual(fautes, []);
});

// WCAG 2.2, 2.5.8 : une cible d'au moins 24 px de haut. Un <summary> ou un
// <button> dont les classes ne donnent pas cette hauteur tombe à celle de sa
// ligne de texte (« Vue tableau » : 16 px, noms de commune du tableau :
// 20 px). La hauteur se lit dans min-h ou h (un pas Tailwind = 4 px), ou
// dans le padding vertical ajouté à la plus petite ligne du site (text-xs :
// 16 px). `p-0`, `py-px` ou `h-0` ne donnent pas de cible de 24 px.
const PAS_PX = 4;
const LIGNE_MIN_PX = 16;
const CIBLE_MIN_PX = 24;

function taille(valeur) {
  const arbitraire = /^\[(\d+(?:\.\d+)?)(px|rem)\]$/.exec(valeur);
  if (arbitraire) return Number(arbitraire[1]) * (arbitraire[2] === "rem" ? 16 : 1);
  if (valeur === "px") return 1;
  return /^\d+(?:\.\d+)?$/.test(valeur) ? Number(valeur) * PAS_PX : 0;
}

/** Hauteur minimale (px) que garantissent des classes Tailwind sans variante. */
function hauteurCible(classes) {
  let hauteur = 0;
  for (const c of classes.split(/\s+/)) {
    const boite = /^(?:min-h|h)-(.+)$/.exec(c);
    if (boite) hauteur = Math.max(hauteur, taille(boite[1]));
    const marge = /^(?:py|p)-(.+)$/.exec(c);
    if (marge) hauteur = Math.max(hauteur, LIGNE_MIN_PX + 2 * taille(marge[1]));
  }
  return hauteur;
}

test("le contrôle de hauteur refuse une classe qui ne donne pas 24 px", () => {
  for (const c of ["p-0 text-xs", "py-px h-0", "w-fit cursor-pointer text-xs", "hover:min-h-11", "min-h-5"]) {
    assert.ok(hauteurCible(c) < CIBLE_MIN_PX, c);
  }
  for (const c of ["min-h-6", "min-h-11", "h-8", "py-1", "py-1.5", "min-h-[24px]", "p-2"]) {
    assert.ok(hauteurCible(`flex ${c} text-xs`) >= CIBLE_MIN_PX, c);
  }
});

test("aucun summary ni bouton sans hauteur minimale de 24 px", () => {
  const fautes = [];
  let vus = 0;
  for (const f of fichiers) {
    const s = readFileSync(f, "utf8");
    for (const m of s.matchAll(/<(button|summary)\b((?:=>|[^>])*?)>/g)) {
      const classes = /className=(?:"([^"]*)"|\{`([^`]*)`)/.exec(m[2]);
      if (!classes) continue; // classes calculées ailleurs : hors de portée d'un contrôle statique
      vus += 1;
      if (hauteurCible(classes[1] ?? classes[2]) < CIBLE_MIN_PX) {
        const ligne = s.slice(0, m.index).split("\n").length;
        fautes.push(`${f.slice(racine.length + 1)}:${ligne} <${m[1]}>`);
      }
    }
  }
  assert.ok(vus >= 20, `${vus} cibles vues seulement`);
  assert.deepEqual(fautes, []);
});

// Sans JavaScript, rien ne doit annoncer un chargement qui n'aura pas lieu,
// ni une pagination sans suite.
const { cadreAttenteCarte, useScriptActif } = await importer("lib/useScriptActif");
const { suiteMasqueeSansScript } = await importer("lib/sans-script");

test("sans JavaScript, le cadre de la carte n'annonce aucun chargement", () => {
  // Le HTML statique est le rendu serveur : le hook y vaut false.
  const Sonde = () => createElement("span", null, useScriptActif() ? "actif" : "inerte");
  assert.equal(renderToStaticMarkup(createElement(Sonde)), "<span>inerte</span>");
  const sansScript = cadreAttenteCarte(false);
  assert.equal(sansScript.role, undefined);
  assert.doesNotMatch(sansScript.texte, /chargement/i);
  const avecScript = cadreAttenteCarte(true);
  assert.equal(avecScript.role, "status");
  assert.match(avecScript.texte, /chargement/i);
  // La carte prend son cadre de ces deux fonctions, sans texte à elle.
  const carte = readFileSync(join(racine, "components/client/CarteDepartements.tsx"), "utf8");
  assert.match(carte, /cadreAttenteCarte\(useScriptActif\(\)\)/);
  assert.doesNotMatch(carte, /role="status"/);
});

test("sans JavaScript, une liste tronquée renvoie à l'export, et seulement s'il existe une suite", () => {
  assert.equal(suiteMasqueeSansScript(50, 1590), true);
  assert.equal(suiteMasqueeSansScript(25, 25), false);
  assert.equal(suiteMasqueeSansScript(12, 12), false);
  assert.equal(suiteMasqueeSansScript(0, 0), false);
  // Les deux listes concernées gardent leur <noscript> derrière cette garde.
  const alertes = readFileSync(join(racine, "components/client/AlertesListe.tsx"), "utf8");
  assert.match(
    alertes,
    /\{suiteMasqueeSansScript\(initiales\.length, total\) && \(\s*<noscript>[\s\S]*?urlSite\("\/donnees\/"\)[\s\S]*?<\/noscript>\s*\)\}/,
  );
  assert.equal((alertes.match(/<noscript>/g) ?? []).length, 1);
  const elus = readFileSync(join(racine, "app/elus/page.tsx"), "utf8");
  assert.match(
    elus,
    /if \(!suiteMasqueeSansScript\(affiches, total\)\) return null;\s*return \(\s*<noscript>[\s\S]*?href="\/donnees\/"[\s\S]*?<\/noscript>/,
  );
  assert.equal((elus.match(/<noscript>/g) ?? []).length, 1);
  assert.equal((elus.match(/<SansScript\b/g) ?? []).length, 2);
});
