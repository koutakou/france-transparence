// Textes coupés sans recours (audit du 21/11/2026) : sur la fiche d'élu, les
// titres de scrutins, et sur /frais en 390 px, les libellés de catégories
// étaient coupés par une ellipse CSS, sans attribut title. Le texte entier
// restait dans le DOM pour un lecteur d'écran, mais pas lisible à l'écran.
// Garde : dans ces pages, un élément coupé par `truncate` porte un title.
// Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const SRC = fileURLToPath(new URL("../src/", import.meta.url));
const PAGES = ["app/elus/[id]/page.tsx", "app/frais/page.tsx"];

/** Balises ouvrantes JSX dont le className contient `truncate`, sans title. */
function coupeesSansTitre(source) {
  const balises = source.match(/<[A-Za-z][^>]*\btruncate\b[^>]*>/g) ?? [];
  return balises.filter((b) => !/\btitle=/.test(b));
}

test("le repérage voit une ellipse sans title et accepte celle qui en a un", () => {
  assert.equal(coupeesSansTitre(`<span className="block truncate">{x}</span>`).length, 1);
  assert.equal(coupeesSansTitre(`<span\n  className="truncate"\n>{x}</span>`).length, 1);
  assert.equal(coupeesSansTitre(`<span className="truncate" title={x}>{x}</span>`).length, 0);
});

for (const page of PAGES) {
  test(`${page} : aucun texte coupé sans moyen de le lire en entier`, () => {
    const source = fs.readFileSync(SRC + page, "utf8");
    assert.deepEqual(coupeesSansTitre(source), []);
  });
}
