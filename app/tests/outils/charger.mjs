// Outils des tests de l'app (`npm test`) : charger un module TypeScript de
// `src/` tel que Next le résout, et lui donner une base SQLite jetable.
//
// Node exécute le TypeScript des modules sans JSX (effacement des types) ; il
// ne connaît en revanche ni l'alias `@/` ni les imports sans extension. Le
// crochet de résolution ci-dessous les traduit, et rien d'autre. Les imports
// statiques étant résolus avant toute exécution, un module qui en dépend se
// charge par `importer()` (import dynamique), APRÈS l'installation du crochet.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { registerHooks } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const SRC = fileURLToPath(new URL("../../src/", import.meta.url));

registerHooks({
  resolve(specificateur, contexte, suivant) {
    let cible = null;
    if (specificateur.startsWith("@/")) {
      cible = path.join(SRC, specificateur.slice(2));
    } else if (
      specificateur.startsWith(".") &&
      contexte.parentURL?.startsWith("file:") &&
      fileURLToPath(contexte.parentURL).startsWith(SRC)
    ) {
      cible = path.resolve(path.dirname(fileURLToPath(contexte.parentURL)), specificateur);
    }
    if (cible !== null && !fs.existsSync(cible)) {
      const trouve = [".ts", "/index.ts"].map((e) => cible + e).find((c) => fs.existsSync(c));
      if (trouve) cible = trouve;
    }
    return suivant(cible !== null ? pathToFileURL(cible).href : specificateur, contexte);
  },
});

/** Importe un module de `src/` (chemin relatif à `src/`, sans extension). */
export function importer(chemin) {
  return import(pathToFileURL(path.join(SRC, `${chemin}.ts`)).href);
}

/**
 * Crée une base SQLite jetable remplie par `remplir(db)`, et la désigne à
 * `lib/db.ts` par FRANCE_DB_PATH. À appeler AVANT le premier `importer()`
 * d'un module de requêtes : `DB_PATH` est lu au chargement de `lib/db.ts`.
 * Un fichier de test = un processus (`node --test`) = une base.
 */
export async function baseDeTest(remplir) {
  const { default: Database } = await import("better-sqlite3");
  const dossier = fs.mkdtempSync(path.join(os.tmpdir(), "ft-app-test-"));
  const chemin = path.join(dossier, "france.db");
  const db = new Database(chemin);
  remplir(db);
  db.close();
  process.env.FRANCE_DB_PATH = chemin;
  return chemin;
}
