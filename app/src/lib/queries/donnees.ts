/**
 * Requêtes de la page /donnees (« Données & API ») et des routes JSON
 * locales (/api/meta, /api/elus, /api/marches/agregats, /api/budget/mensuel).
 *
 * La table pivot est `meta_sources` (25 sources tracées) : chaque source y
 * porte sa date de données réelle, sa date d'ingestion, sa fréquence promise,
 * sa licence et ses notes — c'est le « moniteur de fraîcheur » du projet
 * (docs/SOURCES.md, alerte A11).
 *
 * Toutes les requêtes renvoient `null` si la base n'existe pas encore.
 */
import { getDb, type MetaSource } from "@/lib/db";

/* ------------------------------------------------------------------ */
/* Fraîcheur relative des sources                                      */
/* ------------------------------------------------------------------ */

export type NiveauFraicheur = "verte" | "orange" | "rouge" | "millesime";

export type Fraicheur = {
  niveau: NiveauFraicheur;
  /** Âge de la donnée en jours entiers (aujourd'hui − date_donnees). */
  ageJours: number;
  /** Période attendue en jours (null pour les sources à millésime). */
  periodeJours: number | null;
};

/**
 * Période attendue (en jours) par fréquence promise. Les fréquences à
 * millésime (annuelle, par scrutin, statique, continue, à parution) n'ont
 * pas d'âge attendu pertinent : leurs données ont un décalage STRUCTUREL
 * documenté (ex. subventions aux associations : versements 2023 publiés fin
 * 2024) — le pipeline vérifie à chaque ingestion qu'il tient le dernier
 * millésime publié.
 */
const PERIODES_JOURS: [prefixe: string, jours: number][] = [
  ["quotidienne", 1],
  ["hebdomadaire", 7],
  ["mensuelle", 30],
  ["trimestrielle", 91],
];

/**
 * Règle simple, documentée sur la page /donnees :
 * âge = aujourd'hui − date_donnees, comparé à la période P de la fréquence
 * promise — verte si âge ≤ 2×P + 2 j (marge de publication), orange si
 * âge ≤ 4×P + 7 j, rouge au-delà ; « millésime » pour les fréquences sans
 * âge attendu pertinent. Un badge orange/rouge signale un ÉCART, pas
 * forcément une panne : le flux amont peut être réellement en pause
 * (ex. scrutins AN : vacances parlementaires depuis le 21/07/2026).
 */
export function evalueFraicheur(
  frequence: string,
  dateDonnees: string,
  maintenant: Date = new Date(),
): Fraicheur {
  const t = new Date(dateDonnees).getTime();
  const ageJours = Number.isNaN(t)
    ? 0
    : Math.max(Math.floor((maintenant.getTime() - t) / 86_400_000), 0);
  const freq = frequence.trim().toLowerCase();
  const periode = PERIODES_JOURS.find(([prefixe]) => freq.startsWith(prefixe));
  if (!periode) return { niveau: "millesime", ageJours, periodeJours: null };
  const p = periode[1];
  const niveau: NiveauFraicheur =
    ageJours <= 2 * p + 2 ? "verte" : ageJours <= 4 * p + 7 ? "orange" : "rouge";
  return { niveau, ageJours, periodeJours: p };
}

export type SourceCataloguee = MetaSource & { fraicheur: Fraicheur };

/** Les 25 sources tracées, avec leur fraîcheur relative calculée. */
export function getCatalogueSources(): SourceCataloguee[] | null {
  const db = getDb();
  if (!db) return null;
  const maintenant = new Date();
  const sources = db
    .prepare("SELECT * FROM meta_sources ORDER BY source_id")
    .all() as MetaSource[];
  return sources.map((s) => ({
    ...s,
    fraicheur: evalueFraicheur(s.frequence, s.date_donnees, maintenant),
  }));
}

export type LicenceAgregee = {
  licence: string;
  nb: number;
  /** Identifiants de sources concernées, séparés par ", ". */
  sources: string;
};

/** Licences réellement présentes en base, agrégées (section « Licences et crédits »). */
export function getLicences(): LicenceAgregee[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT licence, COUNT(*) AS nb,
              GROUP_CONCAT(source_id, ', ') AS sources
       FROM meta_sources GROUP BY licence ORDER BY nb DESC, licence`,
    )
    .all() as LicenceAgregee[];
}

/** Date d'ingestion la plus récente (en-tête de la page /donnees). */
export function getDerniereIngestion(): string | null {
  const db = getDb();
  if (!db) return null;
  const r = db
    .prepare("SELECT MAX(date_ingestion) AS d FROM meta_sources")
    .get() as { d: string | null };
  return r.d;
}

/**
 * Lignes meta_sources d'une liste de sources — le bloc `meta` de chaque
 * réponse d'API locale (source, date des données, licence).
 */
export function getMetaSourcesParIds(ids: string[]): MetaSource[] | null {
  const db = getDb();
  if (!db) return null;
  if (ids.length === 0) return [];
  const marques = ids.map(() => "?").join(", ");
  return db
    .prepare(`SELECT * FROM meta_sources WHERE source_id IN (${marques}) ORDER BY source_id`)
    .all(...ids) as MetaSource[];
}

/* ------------------------------------------------------------------ */
/* /api/elus — recherche dans le répertoire des élus (36 018 lignes)   */
/* ------------------------------------------------------------------ */

/** Types de mandat réellement présents dans `elus.mandats` (JSON). */
export const TYPES_MANDAT = [
  "maire",
  "president_epci",
  "depute",
  "senateur",
  "president_conseil_departemental",
  "president_conseil_regional",
] as const;
export type TypeMandat = (typeof TYPES_MANDAT)[number];

export function estTypeMandat(v: string): v is TypeMandat {
  return (TYPES_MANDAT as readonly string[]).includes(v);
}

/** Champs PUBLICS d'un élu exposés par l'API (tous issus de l'open data). */
export type EluPublic = {
  id: string;
  nom: string;
  prenom: string | null;
  profession: string | null;
  uid_an: string | null;
  matricule_senat: string | null;
  hatvp_url: string | null;
  /** JSON brut de la colonne `mandats` (parsé par la route avant envoi). */
  mandats: string | null;
};

/** Échappe `%`, `_` et `\` pour un motif LIKE … ESCAPE '\'. */
function echappeLike(texte: string): string {
  return texte.replace(/[\\%_]/g, (c) => `\\${c}`);
}

/**
 * Recherche d'élus : `q` sur nom/prénom (sous-chaîne, insensible à la
 * casse), `mandat` sur le type de mandat porté par le JSON `mandats`
 * (json_each). Tri nom/prénom, plafond `limite` (max 500 côté route).
 */
export function rechercheElus(options: {
  q?: string;
  mandat?: TypeMandat;
  limite: number;
}): EluPublic[] | null {
  const db = getDb();
  if (!db) return null;
  const conditions: string[] = [];
  const params: (string | number)[] = [];
  if (options.q) {
    conditions.push("(nom LIKE ? ESCAPE '\\' OR prenom LIKE ? ESCAPE '\\')");
    const motif = `%${echappeLike(options.q)}%`;
    params.push(motif, motif);
  }
  if (options.mandat) {
    conditions.push(
      `EXISTS (SELECT 1 FROM json_each(elus.mandats) j
               WHERE json_extract(j.value, '$.type') = ?)`,
    );
    params.push(options.mandat);
  }
  const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";
  return db
    .prepare(
      `SELECT id, nom, prenom, profession, uid_an, matricule_senat, hatvp_url, mandats
       FROM elus ${where}
       ORDER BY nom, prenom
       LIMIT ?`,
    )
    .all(...params, options.limite) as EluPublic[];
}

/* ------------------------------------------------------------------ */
/* /api/marches/agregats — agrégats DECP pré-calculés à l'ingestion    */
/* ------------------------------------------------------------------ */

export type DecpAggDepartement = {
  departement_code: string;
  departement_nom: string | null;
  nb_marches: number;
  /** Somme écrêtée (plafond 100 M€/marché) ; NULL = aucun montant connu. */
  montant_total: number | null;
  nb_marches_ecretes: number;
};

export type DecpAggMois = {
  mois: string; // 'AAAA-MM'
  nb_marches: number;
  montant_total: number | null;
};

/** Agrégats marchés publics : par département (12 mois) et par mois (36 mois). */
export function getMarchesAgregats():
  | { departements: DecpAggDepartement[]; mois: DecpAggMois[] }
  | null {
  const db = getDb();
  if (!db) return null;
  const departements = db
    .prepare(
      `SELECT departement_code, departement_nom, nb_marches, montant_total, nb_marches_ecretes
       FROM decp_agg_departement ORDER BY departement_code`,
    )
    .all() as DecpAggDepartement[];
  const mois = db
    .prepare("SELECT mois, nb_marches, montant_total FROM decp_agg_mois ORDER BY mois")
    .all() as DecpAggMois[];
  return { departements, mois };
}

/* ------------------------------------------------------------------ */
/* /api/budget/mensuel — situations mensuelles budgétaires (S13)       */
/* ------------------------------------------------------------------ */

export type BudgetMensuelLigne = {
  ligne_id: string;
  ordre: number;
  niveau: number;
  categorie: string;
  sous_categorie: string;
  ligne: string;
  date_fin_mois: string;
  annee: number;
  mois: number;
  /** Cumul depuis le 1er janvier (convention DGFiP — docs/NOTES-FRONT.md). */
  montant_cumul: number;
  /** Flux du mois seul (null sur janvier de certaines séries). */
  montant_mois: number | null;
  montant_cumul_n1: number | null;
  montant_mois_n1: number | null;
};

const COLONNES_BUDGET = `ligne_id, ordre, niveau, categorie, sous_categorie, ligne,
       date_fin_mois, annee, mois, montant_cumul, montant_mois,
       montant_cumul_n1, montant_mois_n1`;

/** Dernier mois publié (ex. '2026-06-30' au 19/08/2026). */
export function getBudgetDernierMois(): string | null {
  const db = getDb();
  if (!db) return null;
  const r = db
    .prepare("SELECT MAX(date_fin_mois) AS d FROM budget_mensuel")
    .get() as { d: string | null };
  return r.d;
}

/**
 * Série budgétaire mensuelle :
 * - sans filtre → photographie du DERNIER mois publié (26 lignes) ;
 * - `annee` → tous les mois publiés de l'année (≤ 312 lignes) ;
 * - `ligne` (ligne_id) → série complète 2013→courant de cette ligne ;
 * les deux filtres se combinent. Tri chronologique puis ordre de tableau.
 */
export function getBudgetMensuel(options: {
  annee?: number;
  ligne?: string;
}): BudgetMensuelLigne[] | null {
  const db = getDb();
  if (!db) return null;
  const conditions: string[] = [];
  const params: (string | number)[] = [];
  if (options.annee !== undefined) {
    conditions.push("annee = ?");
    params.push(options.annee);
  }
  if (options.ligne) {
    conditions.push("ligne_id = ?");
    params.push(options.ligne);
  }
  if (conditions.length === 0) {
    return db
      .prepare(
        `SELECT ${COLONNES_BUDGET} FROM budget_mensuel
         WHERE date_fin_mois = (SELECT MAX(date_fin_mois) FROM budget_mensuel)
         ORDER BY ordre`,
      )
      .all() as BudgetMensuelLigne[];
  }
  return db
    .prepare(
      `SELECT ${COLONNES_BUDGET} FROM budget_mensuel
       WHERE ${conditions.join(" AND ")}
       ORDER BY date_fin_mois, ordre`,
    )
    .all(...params) as BudgetMensuelLigne[];
}
