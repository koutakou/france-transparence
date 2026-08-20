/**
 * Requêtes SQL du module « Frais & train de vie » — source S31 : corpus
 * officiel « train de vie » (56 faits sourcés + 8 opacités documentées,
 * docs/NOTES-FRONT.md §« Frais & train de vie »).
 *
 * Fichier PROPRE à ce module (jamais partagé avec un autre module).
 * Chaque requête a été rejouée telle quelle le 19/08/2026 via
 * `sqlite3 "file:data/france.db?mode=ro"` — valeurs témoins :
 * ip-total-brut 7637.39 €/mois, dfp-metropole 7238.04 €/mois,
 * ctrl-an-total-reversements 276335 €, elysee-charges-2024 123300000 €,
 * lfi2026-an 607647569 €, lfi2026-senat 353470900 €.
 */
import { getDb, type MetaSource } from "@/lib/db";

/** Catégories de `trainvie_faits` (contrainte CHECK du schéma). */
export type TrainvieCategorie =
  | "indemnites_parlementaires"
  | "frais_mandat"
  | "controles"
  | "elysee"
  | "institutions"
  | "cabinets"
  | "elus_locaux";

/** Un fait sourcé de la table `trainvie_faits` (56 lignes). */
export interface TrainvieFait {
  id: string;
  categorie: TrainvieCategorie;
  libelle: string;
  /** Toujours > 0 (CHECK) — le déficit Élysée 2023 est stocké positif,
   *  son libellé porte le mot « Déficit ». */
  valeur: number;
  /** euros | euros_par_mois | pourcent | personnes | justificatifs | deplacements */
  unite: string;
  periode: string;
  institution: string;
  source_nom: string;
  source_url: string;
  /** Granularité variable : `2026-02-17`, `2026-01` ou `2025`. */
  date_source: string;
  notes: string | null;
}

/** Une opacité documentée de la table `trainvie_opacites` (8 lignes). */
export interface TrainvieOpacite {
  id: string;
  sujet: string;
  ce_qui_manque: string;
  base_du_refus: string;
  source_nom: string;
  source_url: string;
  /** Granularité variable : `2026-06-11`, `2026-01` ou `2025`. */
  date: string;
}

/** Données complètes du module — `null` tant que la base n'est pas construite. */
export interface FraisData {
  /** Ligne de fraîcheur S31 (peut manquer si l'ingestion est partielle). */
  meta: MetaSource | null;
  faits: TrainvieFait[];
  opacites: TrainvieOpacite[];
}

/** Ordre d'affichage des catégories (pédagogique, du barème au terrain). */
export const ORDRE_CATEGORIES: TrainvieCategorie[] = [
  "indemnites_parlementaires",
  "frais_mandat",
  "controles",
  "elysee",
  "institutions",
  "cabinets",
  "elus_locaux",
];

/**
 * Ordre d'affichage des faits DANS chaque catégorie (mise en avant d'abord,
 * puis lecture logique : composition, AN puis Sénat, barèmes décroissants).
 * Un id absent de ces listes est affiché après, par ordre alphabétique —
 * l'ajout d'un fait par le pipeline ne casse donc rien.
 */
const ORDRE_FAITS: Record<TrainvieCategorie, string[]> = {
  indemnites_parlementaires: [
    "ip-total-brut",
    "ip-base",
    "ip-residence",
    "ip-fonction",
    "ip-net-depute",
    "ip-net-senateur",
    "ip-ecretement-cumul",
    "isf-presidente-an",
    "isf-president-senat",
    "isf-questeur-an",
    "isf-questeur-senat",
  ],
  frais_mandat: [
    "dfp-metropole",
    "dfp-outremer-max",
    "dfp-hors-de-france-max",
    "credit-collaborateurs-an",
    "afm-senat",
    "afm-senat-hebergement",
    "afm-senat-informatique",
    "afm-senat-representation-autorites",
  ],
  controles: [
    "ctrl-an-pct-controles",
    "ctrl-an-demandes-renseignements",
    "ctrl-an-demandes-reversement",
    "ctrl-an-total-reversements",
    "ctrl-senat-controles",
    "ctrl-senat-approfondis",
    "ctrl-senat-frais-declares",
    "ctrl-senat-justificatifs-julia",
  ],
  elysee: [
    "elysee-charges-2024",
    "elysee-deplacements-nb-2024",
    "elysee-deplacements-cout-2024",
    "elysee-excedent-2024",
    "elysee-dotation-2024",
    "elysee-dotation-2026",
    "elysee-charges-2023",
    "elysee-deficit-2023",
  ],
  institutions: [
    "lfi2026-an",
    "lfi2026-senat",
    "lfi2026-conseil-constitutionnel",
    "lfi2026-chaines",
    "lfi2026-cjr",
    "lfi2026-mission-total",
  ],
  cabinets: ["cab-membres", "cab-support", "cab-total", "cab-isp-total"],
  elus_locaux: [
    "local-ib1027",
    "local-maire-100000-plus",
    "local-maire-50000-99999",
    "local-maire-20000-49999",
    "local-maire-10000-19999",
    "local-maire-3500-9999",
    "local-maire-1000-3499",
    "local-maire-500-999",
    "local-maire-moins-500",
    "local-adjoint-100000-max",
    "local-conseiller-municipal",
  ],
};

/**
 * Ordre d'affichage des opacités : le refus parlementaire d'abord (le cœur
 * de la « boîte noire »), le contraste élus locaux en clôture. Ids absents :
 * après, par ordre alphabétique.
 */
const ORDRE_OPACITES = [
  "justificatifs-parlementaires",
  "indemnites-parlementaires-versees",
  "reversements-senat",
  "frais-representation-ministres",
  "remunerations-cabinets",
  "elysee-exercice-2025-non-paru",
  "indemnites-locales-versees",
  "contraste-elus-locaux-communicables",
];

/** Tri stable selon une liste d'ids ; les absents après, en alphabétique. */
function trierParOrdre<T extends { id: string }>(lignes: T[], ordre: string[]): T[] {
  const rang = new Map(ordre.map((id, i) => [id, i]));
  return [...lignes].sort((a, b) => {
    const ra = rang.get(a.id) ?? Number.MAX_SAFE_INTEGER;
    const rb = rang.get(b.id) ?? Number.MAX_SAFE_INTEGER;
    return ra !== rb ? ra - rb : a.id.localeCompare(b.id, "fr");
  });
}

/**
 * Charge tout le module en une passe.
 * Testé le 19/08/2026 : 56 faits (7 catégories), 8 opacités,
 * meta S31 date_donnees = 2026-05-13.
 *
 * @returns `null` si la base n'existe pas encore (page → message honnête).
 */
export function getFraisData(): FraisData | null {
  const db = getDb();
  if (!db) return null;

  const meta =
    (db
      .prepare("SELECT * FROM meta_sources WHERE source_id = 'S31'")
      .get() as MetaSource | undefined) ?? null;

  const faits = db
    .prepare(
      `SELECT id, categorie, libelle, valeur, unite, periode, institution,
              source_nom, source_url, date_source, notes
       FROM trainvie_faits
       ORDER BY categorie, id`,
    )
    .all() as TrainvieFait[];

  const opacites = db
    .prepare(
      `SELECT id, sujet, ce_qui_manque, base_du_refus,
              source_nom, source_url, date
       FROM trainvie_opacites
       ORDER BY id`,
    )
    .all() as TrainvieOpacite[];

  return {
    meta,
    faits: trierParOrdre(faits, ORDRE_CATEGORIES.flatMap((c) => ORDRE_FAITS[c])),
    opacites: trierParOrdre(opacites, ORDRE_OPACITES),
  };
}

/** Faits regroupés par catégorie, dans l'ordre d'affichage du module. */
export function grouperParCategorie(
  faits: TrainvieFait[],
): { categorie: TrainvieCategorie; faits: TrainvieFait[] }[] {
  return ORDRE_CATEGORIES.map((categorie) => ({
    categorie,
    faits: faits.filter((f) => f.categorie === categorie),
  })).filter((g) => g.faits.length > 0);
}
