/**
 * Requêtes de la page « Finances locales » (/collectivites) — source S16
 * (OFGL / DGFiP, data.ofgl.fr) : comptes des collectivités (communes
 * agrégées par département, régions, conseils départementaux, grandes
 * communes) et dotations DGF (national 2018-2026, département 2026,
 * communes ≥ 20 000 hab 2026).
 *
 * Règles (docs/NOTES-FRONT.md § Finances locales) :
 * - comptes 2025 chargés en juillet 2026, PROVISOIRES jusqu'en décembre ;
 * - `collectivites_departements.euros_par_hab` = (fonct + inv) / population ;
 * - régions / conseils départementaux en format long
 *   `(code, nom, exercice, agregat, montant, euros_par_hab, population)`
 *   → pivotés ici sur 3 agrégats clés ;
 * - « Epargne brute » peut être NÉGATIVE (donnée réelle, jamais maquillée) ;
 * - une DGF communale à 0 € est réelle (écrêtement), pas un manque.
 *
 * Chaque fonction renvoie `null` tant que la base n'existe pas (getDb()
 * null) — la page affiche alors un message honnête, jamais un montant vide.
 * Toutes les requêtes ont été testées sur data/france.db en lecture seule.
 */
import fs from "node:fs";
import path from "node:path";
import type { FeatureCollection, Geometry } from "geojson";
import { getDb, type MetaSource } from "@/lib/db";

/** Fraîcheur de la source S16 (badge de chaque bloc de la page). */
export function getMetaFinancesLocales(): MetaSource | null {
  const db = getDb();
  if (!db) return null;
  const ligne = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S16'")
    .get() as MetaSource | undefined;
  return ligne ?? null;
}

/* ------------------------------------------------------------------ */
/* Carte : dépenses communales agrégées par département (€/hab)        */
/* ------------------------------------------------------------------ */

export type DepartementDepenses = {
  code: string;
  nom: string;
  fonctionnement: number | null;
  investissement: number | null;
  /** (fonctionnement + investissement) / population — précalculé pipeline. */
  euros_par_hab: number | null;
  population: number | null;
  nb_communes: number | null;
  exercice: number;
};

/**
 * Les 101 départements (communes agrégées), dernier exercice disponible,
 * triés par €/hab décroissant (le tableau top/flop se découpe côté page).
 */
export function getDepartementsDepenses(): DepartementDepenses[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT code_dep AS code, nom,
              dep_fonctionnement AS fonctionnement,
              dep_investissement AS investissement,
              euros_par_hab, population, nb_communes, exercice
       FROM collectivites_departements
       WHERE exercice = (SELECT MAX(exercice) FROM collectivites_departements)
       ORDER BY euros_par_hab DESC`,
    )
    .all() as DepartementDepenses[];
}

/* ------------------------------------------------------------------ */
/* KPI nationaux (communes agrégées + DGF)                             */
/* ------------------------------------------------------------------ */

export type KpisCommunes = {
  exercice: number;
  nb_departements: number;
  nb_communes: number;
  total_fonctionnement: number;
  total_investissement: number;
};

/** Totaux nationaux des communes (somme des 101 agrégats départementaux). */
export function getKpisCommunes(): KpisCommunes | null {
  const db = getDb();
  if (!db) return null;
  const ligne = db
    .prepare(
      `SELECT exercice, COUNT(*) AS nb_departements,
              SUM(nb_communes) AS nb_communes,
              SUM(dep_fonctionnement) AS total_fonctionnement,
              SUM(dep_investissement) AS total_investissement
       FROM collectivites_departements
       WHERE exercice = (SELECT MAX(exercice) FROM collectivites_departements)
       GROUP BY exercice`,
    )
    .get() as KpisCommunes | undefined;
  return ligne ?? null;
}

export type DgfAnnee = { exercice: number; montant: number };

/** DGF nationale par exercice (2018 → 2026), ordre chronologique. */
export function getDgfNationale(): DgfAnnee[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT exercice, dgf_montant AS montant
       FROM dotations_dgf
       WHERE niveau = 'national'
       ORDER BY exercice`,
    )
    .all() as DgfAnnee[];
}

/* ------------------------------------------------------------------ */
/* Régions et conseils départementaux (format long → pivot)            */
/* ------------------------------------------------------------------ */

export type CollectiviteAgregats = {
  code: string;
  nom: string;
  exercice: number;
  population: number | null;
  fonctionnement: number | null;
  investissement: number | null;
  /** Peut être négative — donnée réelle, à afficher signée. */
  epargne_brute: number | null;
};

export type RegionAgregats = CollectiviteAgregats & { est_ctu: number };

/** Les 17 régions (dont 3 CTU), dernier exercice, pivotées sur 3 agrégats. */
export function getRegions(): RegionAgregats[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT code_region AS code, nom, MAX(est_ctu) AS est_ctu, exercice,
              MAX(population) AS population,
              MAX(CASE WHEN agregat = 'Dépenses de fonctionnement' THEN montant END) AS fonctionnement,
              MAX(CASE WHEN agregat = 'Dépenses d''investissement' THEN montant END) AS investissement,
              MAX(CASE WHEN agregat = 'Epargne brute' THEN montant END) AS epargne_brute
       FROM collectivites_regions
       WHERE exercice = (SELECT MAX(exercice) FROM collectivites_regions)
       GROUP BY code_region, nom, exercice
       ORDER BY fonctionnement DESC`,
    )
    .all() as RegionAgregats[];
}

/** Les 97 conseils départementaux (67A = CEA, 691 = Métropole de Lyon, 75 = Paris). */
export function getConseilsDepartementaux(): CollectiviteAgregats[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT code_dep AS code, nom, exercice,
              MAX(population) AS population,
              MAX(CASE WHEN agregat = 'Dépenses de fonctionnement' THEN montant END) AS fonctionnement,
              MAX(CASE WHEN agregat = 'Dépenses d''investissement' THEN montant END) AS investissement,
              MAX(CASE WHEN agregat = 'Epargne brute' THEN montant END) AS epargne_brute
       FROM collectivites_conseils_departementaux
       WHERE exercice = (SELECT MAX(exercice) FROM collectivites_conseils_departementaux)
       GROUP BY code_dep, nom, exercice
       ORDER BY fonctionnement DESC`,
    )
    .all() as CollectiviteAgregats[];
}

export type SerieAnnuelle = {
  exercice: number;
  fonctionnement: number | null;
  investissement: number | null;
  epargne_brute: number | null;
};

/** Série pluriannuelle (2018 → 2025) des 3 agrégats clés d'une région. */
export function getSerieRegion(codeRegion: string): SerieAnnuelle[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT exercice,
              MAX(CASE WHEN agregat = 'Dépenses de fonctionnement' THEN montant END) AS fonctionnement,
              MAX(CASE WHEN agregat = 'Dépenses d''investissement' THEN montant END) AS investissement,
              MAX(CASE WHEN agregat = 'Epargne brute' THEN montant END) AS epargne_brute
       FROM collectivites_regions
       WHERE code_region = ?
       GROUP BY exercice
       ORDER BY exercice`,
    )
    .all(codeRegion) as SerieAnnuelle[];
}

/** Série pluriannuelle (2018 → 2025) des 3 agrégats clés d'un conseil départemental. */
export function getSerieConseilDepartemental(codeDep: string): SerieAnnuelle[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT exercice,
              MAX(CASE WHEN agregat = 'Dépenses de fonctionnement' THEN montant END) AS fonctionnement,
              MAX(CASE WHEN agregat = 'Dépenses d''investissement' THEN montant END) AS investissement,
              MAX(CASE WHEN agregat = 'Epargne brute' THEN montant END) AS epargne_brute
       FROM collectivites_conseils_departementaux
       WHERE code_dep = ?
       GROUP BY exercice
       ORDER BY exercice`,
    )
    .all(codeDep) as SerieAnnuelle[];
}

/* ------------------------------------------------------------------ */
/* Grandes communes                                                    */
/* ------------------------------------------------------------------ */

export type GrandeCommune = {
  code_insee: string;
  nom: string;
  dep_code: string | null;
  population: number | null;
  fonctionnement: number | null;
  fonct_euros_par_hab: number | null;
  investissement: number | null;
  inv_euros_par_hab: number | null;
  exercice: number;
};

/** Top 50 des communes par population, dernier exercice. */
export function getGrandesCommunes(): GrandeCommune[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT code_insee, nom, dep_code, population,
              dep_fonctionnement AS fonctionnement, fonct_euros_par_hab,
              dep_investissement AS investissement, inv_euros_par_hab, exercice
       FROM collectivites_communes
       WHERE exercice = (SELECT MAX(exercice) FROM collectivites_communes)
       ORDER BY population DESC
       LIMIT 50`,
    )
    .all() as GrandeCommune[];
}

/* ------------------------------------------------------------------ */
/* Dotations DGF 2026 (communes ≥ 20 000 hab, départements)            */
/* ------------------------------------------------------------------ */

export type DgfCommune = {
  code: string;
  nom: string;
  dgf_montant: number;
  population: number | null;
  dgf_par_hab: number | null;
  exercice: number;
};

export type DgfCommunesTopFlop = {
  exercice: number | null;
  top: DgfCommune[];
  flop: DgfCommune[];
  /** Communes ≥ 20 000 hab à DGF strictement nulle (écrêtement réel). */
  nb_zero: number;
};

/**
 * Top 10 / flop 10 des communes ≥ 20 000 hab en DGF par habitant
 * (rangs `top` / `flop` posés par le pipeline — réels), dernier exercice.
 */
export function getDgfCommunesTopFlop(): DgfCommunesTopFlop | null {
  const db = getDb();
  if (!db) return null;
  const top = db
    .prepare(
      `SELECT code, nom, dgf_montant, population, dgf_par_hab, exercice
       FROM dotations_dgf
       WHERE niveau = 'commune'
         AND exercice = (SELECT MAX(exercice) FROM dotations_dgf WHERE niveau = 'commune')
         AND rang = 'top'
       ORDER BY dgf_par_hab DESC
       LIMIT 10`,
    )
    .all() as DgfCommune[];
  const flop = db
    .prepare(
      `SELECT code, nom, dgf_montant, population, dgf_par_hab, exercice
       FROM dotations_dgf
       WHERE niveau = 'commune'
         AND exercice = (SELECT MAX(exercice) FROM dotations_dgf WHERE niveau = 'commune')
         AND rang = 'flop'
       ORDER BY dgf_par_hab ASC, population DESC
       LIMIT 10`,
    )
    .all() as DgfCommune[];
  const zero = db
    .prepare(
      `SELECT COUNT(*) AS nb
       FROM dotations_dgf
       WHERE niveau = 'commune'
         AND exercice = (SELECT MAX(exercice) FROM dotations_dgf WHERE niveau = 'commune')
         AND dgf_montant = 0`,
    )
    .get() as { nb: number };
  return {
    exercice: top[0]?.exercice ?? flop[0]?.exercice ?? null,
    top,
    flop,
    nb_zero: zero.nb,
  };
}

export type DgfDepartement = {
  code: string;
  nom: string;
  dgf_montant: number;
  population: number | null;
  dgf_par_hab: number | null;
  nb_communes: number | null;
  exercice: number;
};

/**
 * DGF des communes agrégée par département (105 lignes dont outre-mer,
 * dernier exercice), triée par DGF/hab décroissante.
 */
export function getDgfDepartements(): DgfDepartement[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT code, nom, dgf_montant, population, dgf_par_hab, nb_communes, exercice
       FROM dotations_dgf
       WHERE niveau = 'departement'
         AND exercice = (SELECT MAX(exercice) FROM dotations_dgf WHERE niveau = 'departement')
       ORDER BY dgf_par_hab DESC`,
    )
    .all() as DgfDepartement[];
}

/* ------------------------------------------------------------------ */
/* Fragment statique /data/collectivites/series.json                   */
/* ------------------------------------------------------------------ */

export type ToutesSeries = {
  /** Séries pluriannuelles par code région (17 clés). */
  regions: Record<string, SerieAnnuelle[]>;
  /** Séries pluriannuelles par code de conseil départemental (97 clés). */
  departements: Record<string, SerieAnnuelle[]>;
};

/**
 * Toutes les séries pluriannuelles (régions + conseils départementaux) en
 * une passe — pré-générées dans un fragment statique que la page charge au
 * premier clic sur une collectivité (aucune requête à l'affichage).
 */
export function getToutesSeries(): ToutesSeries | null {
  const db = getDb();
  if (!db) return null;
  type LigneSerie = SerieAnnuelle & { code: string };
  const regrouper = (lignes: LigneSerie[]): Record<string, SerieAnnuelle[]> => {
    const par: Record<string, SerieAnnuelle[]> = {};
    for (const { code, ...serie } of lignes) {
      (par[code] ??= []).push(serie);
    }
    return par;
  };
  const regions = db
    .prepare(
      `SELECT code_region AS code, exercice,
              MAX(CASE WHEN agregat = 'Dépenses de fonctionnement' THEN montant END) AS fonctionnement,
              MAX(CASE WHEN agregat = 'Dépenses d''investissement' THEN montant END) AS investissement,
              MAX(CASE WHEN agregat = 'Epargne brute' THEN montant END) AS epargne_brute
       FROM collectivites_regions
       GROUP BY code_region, exercice
       ORDER BY code_region, exercice`,
    )
    .all() as LigneSerie[];
  const departements = db
    .prepare(
      `SELECT code_dep AS code, exercice,
              MAX(CASE WHEN agregat = 'Dépenses de fonctionnement' THEN montant END) AS fonctionnement,
              MAX(CASE WHEN agregat = 'Dépenses d''investissement' THEN montant END) AS investissement,
              MAX(CASE WHEN agregat = 'Epargne brute' THEN montant END) AS epargne_brute
       FROM collectivites_conseils_departementaux
       GROUP BY code_dep, exercice
       ORDER BY code_dep, exercice`,
    )
    .all() as LigneSerie[];
  return { regions: regrouper(regions), departements: regrouper(departements) };
}

/* ------------------------------------------------------------------ */
/* Fond de carte (référentiel S27)                                     */
/* ------------------------------------------------------------------ */

export type GeojsonDepartements = FeatureCollection<
  Geometry,
  { code?: string; nom?: string } & Record<string, unknown>
>;

/** Chemin du GeoJSON départements (S27) — même racine data/ que la base. */
export const GEOJSON_DEPARTEMENTS_PATH = path.resolve(
  process.cwd(),
  "..",
  "data",
  "geo",
  "departements.geojson",
);

let geojsonCache: GeojsonDepartements | null = null;

/**
 * FeatureCollection des 101 départements (`properties.code` = code INSEE).
 * `null` si le fichier n'existe pas encore (référentiel non ingéré) —
 * la page garde alors le tableau et signale l'absence de carte.
 */
export function getGeojsonDepartements(): GeojsonDepartements | null {
  if (geojsonCache) return geojsonCache;
  if (!fs.existsSync(GEOJSON_DEPARTEMENTS_PATH)) return null;
  try {
    geojsonCache = JSON.parse(
      fs.readFileSync(GEOJSON_DEPARTEMENTS_PATH, "utf-8"),
    ) as GeojsonDepartements;
    return geojsonCache;
  } catch {
    return null;
  }
}
