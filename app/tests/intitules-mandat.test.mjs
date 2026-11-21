// Intitulés de mandat des fiches d'élus (lib/intitules-mandat.ts) : accordés
// à l'écran comme dans le balisage, et codes HATVP rendus lisibles.
// Jouer : npm test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { importer } from "./outils/charger.mjs";

const { intituleMandat, libelleMandatHatvp, titreMandat } = await importer("lib/intitules-mandat");

test("la fonction RNE, toujours au masculin, est accordée pour une élue", () => {
  // Fonctions relevées dans la base du 21/11/2026, identiques pour tous les sexes.
  assert.equal(
    intituleMandat("president_conseil_regional", "Président du conseil régional", "F"),
    "Présidente du conseil régional",
  );
  assert.equal(
    intituleMandat("president_epci", "Président du conseil communautaire", "F"),
    "Présidente du conseil communautaire",
  );
  assert.equal(
    intituleMandat("president_conseil_regional", "Président du conseil régional", "M"),
    "Président du conseil régional",
  );
  // Sexe non publié : la fonction est reprise telle que la source l'écrit.
  assert.equal(
    intituleMandat("president_conseil_departemental", "Président du conseil départemental", null),
    "Président du conseil départemental",
  );
});

test("sans fonction, l'intitulé du type, accordé ou épicène", () => {
  assert.equal(intituleMandat("depute", undefined, "F"), "Députée");
  assert.equal(intituleMandat("senateur", null, "M"), "Sénateur");
  assert.equal(intituleMandat("depute", undefined, null), "Député·e");
  assert.equal(intituleMandat(undefined, undefined, "F"), null);
  assert.equal(titreMandat("maire", "F"), "Maire");
});

test("les codes de mandat HATVP sont lisibles, un code inconnu reste tel quel", () => {
  assert.equal(libelleMandatHatvp("region"), "Mandat régional");
  assert.equal(libelleMandatHatvp("epci"), "Intercommunalité (EPCI)");
  assert.equal(libelleMandatHatvp("president"), "Présidence de la République");
  assert.equal(libelleMandatHatvp("code_inexistant"), "code_inexistant");
  assert.equal(libelleMandatHatvp(null), "—");
});

test("la fiche d'élu affiche les intitulés accordés et le libellé du code HATVP", () => {
  const fiche = readFileSync(
    fileURLToPath(new URL("../src/app/elus/[id]/page.tsx", import.meta.url)),
    "utf8",
  );
  assert.doesNotMatch(fiche, /\.fonction \?\?/);
  assert.doesNotMatch(fiche, /TYPES_MANDAT\[/);
  assert.match(fiche, /rendu: \(l\) => libelleMandatHatvp\(l\.type_mandat\)/);
});
