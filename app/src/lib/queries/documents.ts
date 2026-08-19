/**
 * Requêtes SQL du module « Documents — Journal officiel » — source S3 :
 * dumps quotidiens DILA JORFSIMPLE, fenêtre glissante des 30 derniers JO
 * parus (docs/NOTES-FRONT.md §« JO / Documents »).
 *
 * Fichier PROPRE à ce module (jamais partagé avec un autre module).
 * Chaque requête a été rejouée telle quelle le 19/08/2026 via
 * `sqlite3 "file:data/france.db?mode=ro"` — valeurs témoins :
 * 2778 textes / 1065 nominations sur 30 JO ; JO du 2026-08-19 : 83 textes
 * dont 41 nominations ; nominations Justice 260, Intérieur 171 ;
 * natures ARRETE 1475, DECRET 534 ; 369 textes sans ministère (13,3 %).
 */
import { getDb, type MetaSource } from "@/lib/db";

/** Chiffres de cadrage de la fenêtre des 30 derniers JO. */
export interface JorfKpis {
  /** Textes publiés sur la fenêtre (2 778 au 19/08/2026). */
  textesFenetre: number;
  /** Dont nominations (1 065). */
  nominationsFenetre: number;
  /** Nombre de JO parus dans la fenêtre (30). */
  nbJours: number;
  /** Date du dernier JO paru (ISO, `2026-08-19`). */
  dernierJo: string;
  /** Premier JO de la fenêtre (ISO, `2026-07-14`). */
  premierJo: string;
  /** Textes du dernier JO (83). */
  textesJour: number;
  /** Nominations du dernier JO (41). */
  nominationsJour: number;
  /** Textes sans ministère émetteur sur la fenêtre (369, soit ~13 % — réel :
   *  lois, Conseil constitutionnel… docs/NOTES-FRONT.md). */
  sansMinistere: number;
}

/** Nombre de textes d'un JO paru (un point par jour de parution réelle). */
export interface ParutionJour {
  /** ISO `AAAA-MM-JJ`. */
  date_publi: string;
  nb: number;
}

/** Agrégat nominations par ministère (fenêtre 30 JO entière). */
export interface NominationsMinistere {
  ministere: string;
  nb: number;
}

/** Top ministères + cadrage pour restituer honnêtement le « reste ». */
export interface NominationsParMinistere {
  top: NominationsMinistere[];
  /** Nombre total de ministères présents dans l'agrégat (19 au 19/08/2026). */
  nbMinisteres: number;
  /** Somme de toutes les nominations de l'agrégat (1 065 — égale le KPI :
   *  aucune nomination sans ministère dans cette table, vérifié). */
  total: number;
}

/** Répartition des textes par nature (fenêtre 30 JO entière). */
export interface RepartitionNature {
  /** Code DILA (`ARRETE`, `DECRET`, `LOI`…) — `null` : nature non renseignée. */
  nature: string | null;
  nb: number;
}

/** Une ligne du flux des textes. */
export interface JorfTexteLigne {
  texte_id: string;
  date_publi: string;
  nature: string | null;
  titre: string;
  /** `null` sur ~13 % des textes (réel) — afficher « — ». */
  ministere: string | null;
  lien_legifrance: string;
}

/** Filtres du flux (searchParams, côté serveur). */
export interface FluxFiltres {
  /** Code nature exact (`DECRET`…) ou `null` = toutes. */
  nature: string | null;
  /** Ne garder que les textes de nomination. */
  nominationsSeules: boolean;
  /** Page demandée (1-indexée) — bornée côté requête. */
  page: number;
}

/** Résultat paginé du flux. */
export interface FluxResultat {
  lignes: JorfTexteLigne[];
  total: number;
  /** Page réellement servie (après bornage 1..nbPages). */
  page: number;
  nbPages: number;
  parPage: number;
}

/** Taille de page du flux. */
export const PAR_PAGE = 50;

/** Ligne de fraîcheur S3 — `null` si base absente ou ingestion partielle. */
export function getMetaJorf(): MetaSource | null {
  const db = getDb();
  if (!db) return null;
  return (
    (db
      .prepare("SELECT * FROM meta_sources WHERE source_id = 'S3'")
      .get() as MetaSource | undefined) ?? null
  );
}

/**
 * KPI de cadrage. Testé le 19/08/2026 : 2778 textes, 1065 nominations,
 * 30 JO du 2026-07-14 au 2026-08-19 ; dernier JO 83 textes / 41 nominations ;
 * 369 textes sans ministère.
 *
 * @returns `null` si la base n'existe pas encore, ou si la table est vide.
 */
export function getJorfKpis(): JorfKpis | null {
  const db = getDb();
  if (!db) return null;

  const fenetre = db
    .prepare(
      `SELECT COUNT(*)                              AS textesFenetre,
              COALESCE(SUM(is_nomination), 0)       AS nominationsFenetre,
              COUNT(DISTINCT date_publi)            AS nbJours,
              MAX(date_publi)                       AS dernierJo,
              MIN(date_publi)                       AS premierJo,
              SUM(CASE WHEN ministere IS NULL OR ministere = ''
                       THEN 1 ELSE 0 END)           AS sansMinistere
       FROM jorf_textes`,
    )
    .get() as {
    textesFenetre: number;
    nominationsFenetre: number;
    nbJours: number;
    dernierJo: string | null;
    premierJo: string | null;
    sansMinistere: number | null;
  };
  if (!fenetre.dernierJo || !fenetre.premierJo) return null;

  const jour = db
    .prepare(
      `SELECT COUNT(*)                        AS textesJour,
              COALESCE(SUM(is_nomination), 0) AS nominationsJour
       FROM jorf_textes
       WHERE date_publi = ?`,
    )
    .get(fenetre.dernierJo) as { textesJour: number; nominationsJour: number };

  return {
    textesFenetre: fenetre.textesFenetre,
    nominationsFenetre: fenetre.nominationsFenetre,
    nbJours: fenetre.nbJours,
    dernierJo: fenetre.dernierJo,
    premierJo: fenetre.premierJo,
    textesJour: jour.textesJour,
    nominationsJour: jour.nominationsJour,
    sansMinistere: fenetre.sansMinistere ?? 0,
  };
}

/**
 * Textes par JOUR DE PARUTION réelle (30 points — le JO ne paraît PAS tous
 * les jours : les trous du calendrier sont réels, la page les comble à 0
 * pour la sparkline). Testé : 2026-07-14 → 70, pic 2026-07-23 → 182,
 * 2026-08-19 → 83.
 */
export function getParutionsParJour(): ParutionJour[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT date_publi, COUNT(*) AS nb
       FROM jorf_textes
       GROUP BY date_publi
       ORDER BY date_publi`,
    )
    .all() as ParutionJour[];
}

/**
 * Top des ministères par nominations — agrégat pipeline
 * `jorf_nominations_ministere`, fenêtre 30 JO ENTIÈRE (NOTES-FRONT §JO).
 * Testé : Justice 260, Intérieur 171, Europe/affaires étrangères 106 ;
 * 19 ministères, somme 1065 (= total des nominations), top 10 = 950.
 */
export function getNominationsParMinistere(limite = 10): NominationsParMinistere | null {
  const db = getDb();
  if (!db) return null;

  const top = db
    .prepare(
      `SELECT ministere, nb
       FROM jorf_nominations_ministere
       ORDER BY nb DESC, ministere
       LIMIT ?`,
    )
    .all(limite) as NominationsMinistere[];

  const cadrage = db
    .prepare(
      `SELECT COUNT(*) AS nbMinisteres, COALESCE(SUM(nb), 0) AS total
       FROM jorf_nominations_ministere`,
    )
    .get() as { nbMinisteres: number; total: number };

  return { top, nbMinisteres: cadrage.nbMinisteres, total: cadrage.total };
}

/**
 * Répartition des textes par nature, ordre de grandeur décroissant
 * (donut ≤ 6 segments : le composant replie l'excédent en « Autre »).
 * Testé : ARRETE 1475, DECRET 534, AVIS 315, DECISION 239, LOI 14,
 * nature NULL 4.
 */
export function getRepartitionNatures(): RepartitionNature[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT nature, COUNT(*) AS nb
       FROM jorf_textes
       GROUP BY nature
       ORDER BY nb DESC, nature`,
    )
    .all() as RepartitionNature[];
}

/**
 * Flux paginé des textes, du plus récent au plus ancien (dans un même JO :
 * ordre de séquence du sommaire). Filtres optionnels : nature exacte,
 * nominations seules. Requêtes 100 % paramétrées.
 *
 * Testé le 19/08/2026 : sans filtre 2778 textes (56 pages de 50) ;
 * nature='DECRET' + nominations → 348 ; page hors bornes → ramenée à
 * [1..nbPages].
 *
 * @returns `null` si la base n'existe pas encore.
 */
export function getFluxTextes(filtres: FluxFiltres): FluxResultat | null {
  const db = getDb();
  if (!db) return null;

  const conditions: string[] = [];
  const params: string[] = [];
  if (filtres.nature) {
    conditions.push("nature = ?");
    params.push(filtres.nature);
  }
  if (filtres.nominationsSeules) conditions.push("is_nomination = 1");
  const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";

  const { total } = db
    .prepare(`SELECT COUNT(*) AS total FROM jorf_textes ${where}`)
    .get(...params) as { total: number };

  const nbPages = Math.max(1, Math.ceil(total / PAR_PAGE));
  const page = Math.min(Math.max(1, Math.trunc(filtres.page) || 1), nbPages);

  const lignes = db
    .prepare(
      `SELECT texte_id, date_publi, nature, titre, ministere, lien_legifrance
       FROM jorf_textes
       ${where}
       ORDER BY date_publi DESC, num_sequence ASC
       LIMIT ? OFFSET ?`,
    )
    .all(...params, PAR_PAGE, (page - 1) * PAR_PAGE) as JorfTexteLigne[];

  return { lignes, total, page, nbPages, parPage: PAR_PAGE };
}
