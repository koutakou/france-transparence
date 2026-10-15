// Budget de poids des pages de l'export statique (app/out). Jouer :
//   node scripts/poids-pages.mjs [dossier]      (défaut : out)
//
// Règle (docs : < 500 Ko de HTML brut par page au premier chargement) :
// 1. aucun fichier .html de l'export ne dépasse PLAFOND_OCTETS ;
// 2. une page qui charge un fragment D'ELLE-MÊME, sans geste du visiteur,
//    reste sous le plafond fragment compris (page + le plus lourd des
//    fragments qu'elle peut charger ainsi). Un fragment chargé au geste
//    (clic, « Tout afficher ») n'entre pas dans ce compte.
// Les pages les plus lourdes sont journalisées à CHAQUE passage, même au
// vert : un contrôle muet est indiscernable d'un contrôle débranché.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

/** 500 Ko = 500 000 octets (HTML brut, non compressé). */
export const PLAFOND_OCTETS = 500_000;

/**
 * Fragments que la page charge SANS GESTE, à déclarer ici quand on en ajoute
 * un : chemin de la page dans l'export → dossier de fragments (le plus lourd
 * compte). Aujourd'hui, les tranches horaires d'appels d'offres
 * (lib/echeances.ts), chargées dès qu'une échéance du HTML est passée.
 */
export const FRAGMENTS_SANS_GESTE = {
  "index.html": "data/accueil/ao-cloture",
  "marches/index.html": "data/marches/ao-toutes",
};

function* fichiersHtml(racine, dossier = racine) {
  for (const e of fs.readdirSync(dossier, { withFileTypes: true })) {
    const chemin = path.join(dossier, e.name);
    if (e.isDirectory()) yield* fichiersHtml(racine, chemin);
    else if (e.name.endsWith(".html")) yield path.relative(racine, chemin);
  }
}

/** Contrôle `racine` ; rend { pages, depassements } (pages triées, lourdes d'abord). */
export function controlerPoids(racine, plafond = PLAFOND_OCTETS, sansGeste = FRAGMENTS_SANS_GESTE) {
  const pages = [];
  for (const rel of fichiersHtml(racine)) {
    const octets = fs.statSync(path.join(racine, rel)).size;
    let fragment = null;
    const dossierFragments = sansGeste[rel.split(path.sep).join("/")];
    if (dossierFragments) {
      const d = path.join(racine, dossierFragments);
      const fichiers = fs.existsSync(d) ? fs.readdirSync(d).filter((f) => f.endsWith(".json")) : [];
      for (const f of fichiers) {
        const t = fs.statSync(path.join(d, f)).size;
        if (!fragment || t > fragment.octets) fragment = { chemin: `${dossierFragments}/${f}`, octets: t };
      }
    }
    pages.push({ page: rel, octets, fragment, total: octets + (fragment?.octets ?? 0) });
  }
  pages.sort((a, b) => b.total - a.total);
  return { pages, depassements: pages.filter((p) => p.total > plafond) };
}

function principal() {
  const racine = path.resolve(process.argv[2] ?? "out");
  if (!fs.existsSync(racine)) {
    console.error(`ÉCHEC : export introuvable (${racine})`);
    process.exit(1);
  }
  const { pages, depassements } = controlerPoids(racine);
  const fmt = (n) => n.toLocaleString("fr-FR");
  console.log(`Poids des pages (${pages.length} fichiers .html, plafond ${fmt(PLAFOND_OCTETS)} octets) — les plus lourdes :`);
  for (const p of pages.slice(0, 10)) {
    const frag = p.fragment ? ` + ${fmt(p.fragment.octets)} (${p.fragment.chemin}, sans geste)` : "";
    console.log(`  ${fmt(p.total).padStart(9)}  ${p.page}${frag}`);
  }
  for (const p of depassements) {
    console.error(`ÉCHEC : ${p.page} pèse ${fmt(p.total)} octets${p.fragment ? " fragment sans geste compris" : ""}, au-delà de ${fmt(PLAFOND_OCTETS)}`);
  }
  process.exit(depassements.length > 0 ? 1 : 0);
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) principal();
