/**
 * Requêtes SQL du module « Frais & train de vie » — deux sources :
 * S31, corpus officiel « train de vie » (faits sourcés et opacités
 * documentées, docs/NOTES-FRONT.md §« Frais & train de vie ») ; S38, avis
 * et conseils de la CADA en agrégats, qui alimentent la carte des verrous.
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
  /**
   * Assiette d'une rémunération telle que la source l'énonce : `"brut"`,
   * `"net"`, ou `null` quand la question ne se pose pas (enveloppe de frais,
   * dotation, effectif, total). À AFFICHER dès qu'elle est renseignée : la
   * page met des barèmes bruts et des montants nets dans la même colonne.
   */
  assiette: "brut" | "net" | null;
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

/* ------------------------------------------------------------------ */
/* Périmètres des chiffres clés (StatStrip)                            */
/* ------------------------------------------------------------------ */

/** Barème publié, identique aux deux chambres — pas un montant versé. */
export const PERIMETRE_IP_BRUT =
  "barème publié, identique AN et Sénat — ce n’est pas un montant dépensé";

/** Enveloppe forfaitaire d’un député de métropole — pas les dépenses. */
export const PERIMETRE_DFP_METROPOLE =
  "barème DFP métropole, dotation créée au 01/01/2026 — pas le détail des dépenses";

/** Total anonymisé du déontologue — un agrégat, pas un nom. */
export const PERIMETRE_REVERSEMENTS_AN =
  "agrégat anonymisé du déontologue, exercice 2024 — ne désigne personne";

/** Comptes de la présidence, exercice audité — pas une dotation LFI. */
export const PERIMETRE_ELYSEE_CHARGES =
  "comptes audités par la Cour des comptes, exercice 2024";

/** Dotation votée en LFI — pas le projet de loi de finances. */
export const PERIMETRE_LFI2026_AN =
  "LFI 2026, mission Pouvoirs publics — loi votée, pas le PLF";

/** Même LFI ; le Sénat inclut le jardin et le musée du Luxembourg. */
export const PERIMETRE_LFI2026_SENAT =
  "LFI 2026, mission Pouvoirs publics — jardin et musée du Luxembourg compris, pas le PLF";

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
      `SELECT id, categorie, libelle, valeur, unite, assiette, periode,
              institution, source_nom, source_url, date_source, notes
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

/* ------------------------------------------------------------------ */
/* Carte des verrous — source S38 (avis et conseils de la CADA)        */
/* ------------------------------------------------------------------ */

/**
 * Le complément factuel de la « boîte noire » : la boîte noire dit ce que
 * la loi ne publie pas, la carte des verrous dit ce que l'administration
 * refuse de communiquer quand on le lui demande, et sur quel fondement la
 * CADA lui donne — ou non — raison.
 *
 * Toutes les requêtes ci-dessous portent sur `type_saisine = 'Avis'` : un
 * « conseil » est une administration qui interroge elle-même la CADA en
 * amont, pas un citoyen à qui l'on a opposé un refus. Les mélanger
 * fausserait la lecture.
 */

/** Sens que la CADA peut donner à un avis (vocabulaire fermé du schéma). */
export const SENS_REFUS = ["Défavorable", "Incompétence", "Irrecevable"] as const;

export interface CadaSens {
  sens: string;
  dossiers: number;
}

export interface CadaMotif {
  sens: string;
  /** `null` quand la CADA publie un sens sans motivation. */
  motivation: string | null;
  dossiers: number;
}

export interface CadaCategorie {
  categorie: string;
  /** Nombre de libellés distincts rangés dans cette catégorie. */
  libelles: number;
  /** Dossiers de type « Avis » visant une administration de la catégorie. */
  dossiers: number;
  /** Dossiers où la CADA a rendu un avis défavorable. */
  defavorable: number;
}

export interface VerrousCadaData {
  meta: MetaSource;
  /** Dossiers de type « Avis » (le refus opposé à un demandeur). */
  avis: number;
  /** Dossiers de type « Conseil » (l'administration interroge la CADA). */
  conseils: number;
  premiereAnnee: number;
  derniereAnnee: number;
  /** Libellés d'administration distincts — pas un référentiel, cf. pipeline. */
  administrations: number;
  sens: CadaSens[];
  motifs: CadaMotif[];
  categories: CadaCategorie[];
}

/**
 * Charge la carte des verrous en une passe (5 requêtes, toutes agrégées).
 *
 * @returns `null` si la base ou la source S38 manquent — la page se replie
 *          alors silencieusement sur le reste du module.
 */
export function getVerrousCada(): VerrousCadaData | null {
  const db = getDb();
  if (!db) return null;

  const meta =
    (db
      .prepare("SELECT * FROM meta_sources WHERE source_id = 'S38'")
      .get() as MetaSource | undefined) ?? null;
  if (!meta) return null;

  const volumes = db
    .prepare(
      `SELECT type_saisine,
              SUM(nb_dossiers) AS dossiers,
              MIN(annee)       AS premiere,
              MAX(annee)       AS derniere
         FROM cada_saisines
        GROUP BY type_saisine`,
    )
    .all() as { type_saisine: string; dossiers: number; premiere: number; derniere: number }[];
  if (volumes.length === 0) return null;

  const avis = volumes.find((v) => v.type_saisine === "Avis");
  if (!avis) return null;

  const administrations = (
    db.prepare("SELECT COUNT(*) AS n FROM cada_administrations").get() as { n: number }
  ).n;

  const sens = db
    .prepare(
      `SELECT sens, SUM(nb_dossiers) AS dossiers
         FROM cada_sens
        WHERE type_saisine = 'Avis'
        GROUP BY sens
        ORDER BY dossiers DESC`,
    )
    .all() as CadaSens[];

  const motifs = db
    .prepare(
      `SELECT sens, motivation, SUM(nb_dossiers) AS dossiers
         FROM cada_motifs
        WHERE type_saisine = 'Avis'
          AND sens IN ('Défavorable', 'Incompétence', 'Irrecevable')
        GROUP BY sens, motivation
        ORDER BY dossiers DESC
        LIMIT 8`,
    )
    .all() as CadaMotif[];

  // « defavorable » ne retient QUE le sens défavorable : additionner les
  // trois sens de refus double-compterait les dossiers qui en portent
  // plusieurs (la CADA rend souvent un avis composite).
  const categories = db
    .prepare(
      `SELECT a.categorie,
              COUNT(*)                   AS libelles,
              COALESCE(SUM(s.nb_dossiers), 0) AS dossiers,
              (SELECT COALESCE(SUM(x.nb_dossiers), 0)
                 FROM cada_sens x
                 JOIN cada_administrations b ON b.id = x.administration_id
                WHERE b.categorie = a.categorie
                  AND x.type_saisine = 'Avis'
                  AND x.sens = 'Défavorable') AS defavorable
         FROM cada_administrations a
         LEFT JOIN cada_saisines s
                ON s.administration_id = a.id AND s.type_saisine = 'Avis'
        GROUP BY a.categorie
        ORDER BY dossiers DESC`,
    )
    .all() as CadaCategorie[];

  return {
    meta,
    avis: avis.dossiers,
    conseils: volumes.find((v) => v.type_saisine === "Conseil")?.dossiers ?? 0,
    premiereAnnee: Math.min(...volumes.map((v) => v.premiere)),
    derniereAnnee: Math.max(...volumes.map((v) => v.derniere)),
    administrations,
    sens,
    motifs,
    categories,
  };
}
