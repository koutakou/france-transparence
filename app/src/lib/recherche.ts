/**
 * Correspondance de la recherche globale (SearchBox) sur l'index statique
 * `/data/recherche-index.json`.
 *
 * Module PUR (aucun import d'exécution) : testé par `npm test`
 * (tests/recherche.test.mjs).
 *
 * Règles :
 * - insensible aux accents et à la casse ;
 * - tirets, apostrophes typographiques et espaces multiples ne comptent pas :
 *   « braun pivet » trouve « Braun-Pivet », « marine  le pen » trouve
 *   « Le Pen », « l'économie » trouve « l’Économie » ;
 * - chaque mot de la requête doit figurer dans le nom complet, dans
 *   n'importe quel ordre : « le pen marine » et « marine le pen » se valent.
 */
import type { IndexRecherche } from "@/lib/recherche-index";

export interface ResultatRecherche {
  /** « Élu·e », « Ministère »… (affiché en préfixe discret). */
  type: string;
  libelle: string;
  sous_libelle?: string;
  href: string;
}

export const MIN_CARACTERES = 2;
export const MAX_ELUS = 8;
export const MAX_ENTITES = 4;

/**
 * Forme pliée : minuscules sans diacritiques, apostrophes unifiées, tirets
 * et soulignés lus comme des espaces, espaces repliées.
 */
export function plie(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[’‘ʼ`´]/g, "'")
    .replace(/[-‐‑‒–—_]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Clés pré-pliées d'un élu (calculées une fois au chargement de l'index). */
export interface ClesElu {
  nom: string;
  /** « prénom nom » — l'ordre usuel, sert au rang. */
  complet: string;
  /** « nom prénom » — l'ordre des listes, sert au rang. */
  inverse: string;
}

export interface ClesEntite {
  /** « nom sigle ». */
  texte: string;
}

export interface IndexPret {
  brut: IndexRecherche;
  elusCles: ClesElu[];
  entitesCles: ClesEntite[];
}

export function preparerIndex(brut: IndexRecherche): IndexPret {
  return {
    brut,
    elusCles: brut.elus.map((e) => {
      const nom = plie(e[0]);
      const prenom = plie(e[1]);
      return {
        nom,
        complet: prenom ? `${prenom} ${nom}` : nom,
        inverse: prenom ? `${nom} ${prenom}` : nom,
      };
    }),
    entitesCles: brut.entites.map((e) => {
      const nom = plie(e[0]);
      const sigle = plie(e[1]);
      return { texte: sigle ? `${nom} ${sigle}` : nom };
    }),
  };
}

/** Tous les mots de la requête sont présents dans `texte` (ET logique). */
function contientTous(texte: string, mots: string[]): boolean {
  for (const m of mots) if (!texte.includes(m)) return false;
  return true;
}

/**
 * Recherche locale : 8 élus + 4 entités au plus. Élus classés
 * parlementaires d'abord, puis nom commençant par la requête, puis requête
 * lue d'un seul tenant (dans un ordre ou l'autre), puis ordre de l'index
 * (alphabétique).
 */
export function rechercher(index: IndexPret, brutQ: string): ResultatRecherche[] {
  const q = plie(brutQ);
  if (q.length < MIN_CARACTERES) return [];
  const mots = q.split(" ");
  const { brut, elusCles, entitesCles } = index;

  type Candidat = { i: number; rang: number };
  const candidats: Candidat[] = [];
  for (let i = 0; i < brut.elus.length; i++) {
    const cles = elusCles[i];
    if (!contientTous(cles.complet, mots)) continue;
    const typeIdx = brut.elus[i][2];
    // 0/1 = député/sénateur en exercice, 7/8 = parlementaire du seul RNE.
    const parlementaire = typeIdx === 0 || typeIdx === 1 || typeIdx === 7 || typeIdx === 8;
    const proximite = cles.nom.startsWith(q)
      ? 0
      : cles.complet.includes(q) || cles.inverse.includes(q)
        ? 1
        : 2;
    candidats.push({ i, rang: (parlementaire ? 0 : 3) + proximite });
  }
  candidats.sort((a, b) => a.rang - b.rang || a.i - b.i);

  const resultats: ResultatRecherche[] = candidats.slice(0, MAX_ELUS).map(({ i }) => {
    const [nom, prenom, typeIdx, depIdx, id] = brut.elus[i];
    const mandat = brut.typesMandat[typeIdx] ?? "Élu·e";
    const dep = depIdx >= 0 ? brut.departements[depIdx] : undefined;
    const morceaux = [mandat];
    if (dep) morceaux.push(dep);
    if (!id) morceaux.push("dans les listes /elus");
    return {
      type: "Élu·e",
      libelle: `${prenom} ${nom}`.trim(),
      sous_libelle: morceaux.join(" · "),
      href: id ? `/elus/${encodeURIComponent(id)}` : "/elus",
    };
  });

  // Entités (ministères, institutions, collectivités, partis) : l'index est
  // déjà dans l'ordre de priorité voulu.
  let nbEntites = 0;
  for (let i = 0; i < brut.entites.length && nbEntites < MAX_ENTITES; i++) {
    if (!contientTous(entitesCles[i].texte, mots)) continue;
    const [nom, sigle, typeIdx, hrefIdx] = brut.entites[i];
    resultats.push({
      type: brut.typesEntite[typeIdx] ?? "Institution",
      libelle: nom,
      sous_libelle: sigle || undefined,
      href: brut.hrefs[hrefIdx] ?? "/elus",
    });
    nbEntites++;
  }

  return resultats;
}
