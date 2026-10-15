// Contrastes WCAG des jetons de src/app/globals.css (thème sombre unique,
// DATAVIZ § 9 et annexe A). Le calcul lit le fichier : un jeton modifié est
// re-validé à chaque `npm test`.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");
const racine = css.slice(css.indexOf(":root {"), css.indexOf("@theme inline"));
const jeton = (nom) => {
  const m = racine.match(new RegExp(`--${nom}:\\s*(#[0-9a-fA-F]{6})\\b`));
  assert.ok(m, `jeton --${nom} introuvable ou non hexadécimal`);
  return m[1];
};

const lin = (c) => {
  c /= 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
};
const lum = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
};
const contraste = (a, b) => {
  const [h, l] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (h + 0.05) / (l + 0.05);
};
const auMoins = (premier, second, seuil) => {
  const [a, b] = [jeton(premier), jeton(second)];
  const r = contraste(a, b);
  assert.ok(r >= seuil, `--${premier} ${a} sur --${second} ${b} : ${r.toFixed(2)}:1 < ${seuil}:1`);
};

test("formule de référence (annexe A) : #2f96f7 sur #0f1d33 = 5,49:1", () => {
  assert.equal(contraste("#2f96f7", "#0f1d33").toFixed(2), "5.49");
});

test("encres de texte ≥ 4,5:1 sur le fond le plus clair (--surface-hover)", () => {
  for (const encre of ["ink-primary", "ink-secondary", "ink-muted"]) {
    auMoins(encre, "surface-hover", 4.5);
  }
});

test("couleurs de marques ≥ 3:1 sur --surface-card", () => {
  for (let i = 1; i <= 8; i++) auMoins(`viz-serie-${i}`, "surface-card", 3);
  auMoins("viz-autre", "surface-card", 3);
});

test("--viz-autre ≥ 3:1 jusque sur --surface-hover (sparklines, survols)", () => {
  auMoins("viz-autre", "surface-hover", 3);
});

test("donnée manquante sur la carte : hachure ≥ 3:1 sur la carte et sur son propre fond", () => {
  auMoins("map-manquant-hachure", "surface-card", 3);
  auMoins("map-manquant-hachure", "map-manquant", 3);
});
