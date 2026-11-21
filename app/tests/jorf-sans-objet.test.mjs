// Ministère « s.o. » (sans objet) ou « n.d. » (manque) selon la nature du texte.
import { test } from "node:test";
import assert from "node:assert/strict";
import { ministereSansObjet } from "../src/lib/jorf-sans-objet.ts";

test("« s.o. » pour une loi, une ordonnance ou une décision du Conseil constitutionnel", () => {
  assert.equal(ministereSansObjet("LOI", "LOI n° 2026-1 du 2 janvier 2026 relative à X"), true);
  assert.equal(ministereSansObjet("LOI_ORGANIQUE", "LOI organique n° 2026-2"), true);
  assert.equal(ministereSansObjet("ORDONNANCE", "Ordonnance n° 2026-3"), false);
  assert.equal(ministereSansObjet("DECISION", "Décision n° 2026-1225 QPC du 16 octobre 2026"), true);
  assert.equal(ministereSansObjet("DECISION", "Décision n° 2026-1230/1231 QPC du 23 octobre 2026"), true);
  assert.equal(ministereSansObjet("DECISION", "Décision n° 2026-901 DC du 5 août 2026"), true);
});

test("« n.d. » pour un décret, un arrêté ou une décision d'une autre autorité sans ministère", () => {
  assert.equal(ministereSansObjet("DECRET", "Décret n° 2026-10 du 3 mars 2026"), false);
  assert.equal(ministereSansObjet("ARRETE", "Arrêté du 26 octobre 2026 fixant le nombre de postes"), false);
  assert.equal(ministereSansObjet("DECISION", "Décision n° 2026-171 du 15 octobre 2026 portant délivrance de l'agrément"), false);
  assert.equal(ministereSansObjet("DECISION", "Décision du 12 novembre 2026 portant délégation de signature"), false);
  assert.equal(ministereSansObjet("AVIS", "Avis relatif à X"), false);
  assert.equal(ministereSansObjet(null, "Texte sans nature"), false);
});
