/**
 * Requêtes SQL du module « Élus & institutions » — /elus, /elus/[id], les
 * fragments statiques /data/elus/*.json et l'index de recherche. Fichier
 * PROPRE au module (NOTES-FRONT, design system) : aucune autre page ne doit
 * l'importer.
 *
 * Jointures exactes (NOTES-FRONT § Élus & intégrité) :
 * - `elus.uid_an ↔ deputes.uid_an ↔ votes_recents.uid_an` ;
 * - `deputes.groupe_ref ↔ groupes_an.organe_ref` ;
 * - `elus.matricule_senat ↔ senateurs.matricule ↔ votes_senat.matricule
 *   ↔ participation_senat.matricule`.
 *
 * Identifiant de fiche : `elus.id` tel quel (clé primaire) — `PAxxxx` pour
 * les députés (= uid_an), `SEN-<matricule>` pour les sénateurs, `rne-<hash>`
 * pour les autres élus du répertoire national.
 *
 * Toutes les fonctions renvoient `null` tant que la base n'est pas
 * construite (`getDb()` → null) : la page affiche alors un message honnête.
 * SQL 100 % paramétré — jamais d'interpolation de valeur ; les motifs LIKE
 * sont échappés via `echappeLike` (ESCAPE '\').
 */
import { getDb, type MetaSource } from "@/lib/db";

/* ------------------------------------------------------------------ */
/* Sources (FreshnessBadge)                                            */
/* ------------------------------------------------------------------ */

/** Sources du module (ids réels de `meta_sources`). */
export const SOURCES_ELUS = [
  "S5-AMO10", // AN — députés, mandats, organes (quotidien)
  "S5-SCRUTINS", // AN — scrutins publics et votes nominaux (quotidien)
  "S6-ODSEN", // Sénat — sénateurs en exercice (quotidien)
  "S6-DOSLEG", // Sénat — scrutins publics et votes nominaux (quotidien)
  "S7-DATAN", // Datan — scores des députés (crédité)
  "S14", // HATVP — liste des déclarations publiées (hebdomadaire)
  "S17", // RNE — répertoire national des élus (trimestriel)
] as const;

export type SourceEluId = (typeof SOURCES_ELUS)[number];

/** Fraîcheur des sources du module, indexée par source_id. */
export function getSourcesElus(): Partial<Record<SourceEluId, MetaSource>> | null {
  const db = getDb();
  if (!db) return null;
  const marques = SOURCES_ELUS.map(() => "?").join(", ");
  const lignes = db
    .prepare(`SELECT * FROM meta_sources WHERE source_id IN (${marques})`)
    .all(...SOURCES_ELUS) as MetaSource[];
  const parId: Partial<Record<SourceEluId, MetaSource>> = {};
  for (const ligne of lignes) parId[ligne.source_id as SourceEluId] = ligne;
  return parId;
}

/* ------------------------------------------------------------------ */
/* Agrégats de la page                                                 */
/* ------------------------------------------------------------------ */

export type GroupeAn = {
  organe_ref: string;
  legislature: number;
  sigle: string;
  nom: string;
  effectif: number;
  position: string | null;
};

/** Groupes politiques de l'AN, dans l'ordre de préséance (`position`). */
export function getGroupesAn(): GroupeAn[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT organe_ref, legislature, sigle, nom, effectif, position
       FROM groupes_an
       ORDER BY CAST(position AS INTEGER), sigle`,
    )
    .all() as GroupeAn[];
}

export type GroupeSenat = { groupe: string; effectif: number };

/** Composition du Sénat par groupe (comptée depuis `senateurs`). */
export function getGroupesSenat(): GroupeSenat[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT groupe, COUNT(*) AS effectif
       FROM senateurs
       GROUP BY groupe
       ORDER BY effectif DESC, groupe`,
    )
    .all() as GroupeSenat[];
}

export type StatsChambre = {
  nb: number;
  nb_femmes: number;
  /** Âge moyen en années (date_naissance du répertoire), 1 décimale. */
  age_moyen: number | null;
};

export type StatsElus = {
  deputes: StatsChambre;
  senateurs: StatsChambre;
  /** Mandats « maire » comptés dans `elus.mandats` (JSON, source RNE). */
  nb_maires: number;
  /** Total d'élus du répertoire (`elus`). */
  nb_elus: number;
  /** Élus avec fiche HATVP appariée par le pipeline (`hatvp_flag = 1`). */
  nb_elus_hatvp: number;
  /** Déclarations HATVP publiées référencées en base. */
  nb_declarations_hatvp: number;
};

/** Assemblée nationale en exercice — pas l’ensemble des élus. */
export const PERIMETRE_DEPUTES =
  "Assemblée nationale en exercice — ce n’est pas l’ensemble des élus";

/** Sénat en exercice — pas l’ensemble des élus. */
export const PERIMETRE_SENATEURS =
  "Sénat en exercice — ce n’est pas l’ensemble des élus";

/**
 * Mandats « maire » du RNE ingéré. Ce n’est pas tout le répertoire
 * (les conseillers municipaux n’y sont pas) et ce n’est pas « les élus
 * de France ».
 */
export const PERIMETRE_MAIRES =
  "mandats maire du RNE ingéré — hors conseillers municipaux, ce n’est pas tout le RNE";

/**
 * Personnes présentes dans le répertoire local. Une ligne n’est pas une
 * fiche : maires et présidences d’EPCI n’ont pas de page dédiée.
 */
export const PERIMETRE_ELUS_EN_BASE =
  "maires, présidences d’EPCI, de départements et de régions, parlementaires — pas les conseillers municipaux ; une fiche n’existe que pour les parlementaires et les exécutifs départementaux et régionaux";

/** Taux calculé ici : scrutins publics AN, fenêtre glissante. */
export const PERIMETRE_PARTICIPATION_FT =
  "scrutins publics de l’AN, 12 derniers mois depuis l’entrée en mandat — votes exprimés";

/** Même formule, chambre Sénat. Une délégation n'est pas une présence. */
export const PERIMETRE_PARTICIPATION_FT_SENAT =
  "scrutins publics du Sénat, 12 derniers mois depuis l’entrée en mandat — votes exprimés, pas une présence";

/** Même fenêtre que le taux — un tiret n’est pas un zéro. */
export const PERIMETRE_VOTES_12M =
  "même fenêtre que le taux — un tiret n’est pas un zéro";

/** Score Datan, autre méthode. */
export const PERIMETRE_SCORE_DATAN =
  "score publié par Datan, échelle 0 à 1 — ce n’est pas le taux calculé ici";

/** Agrégats réels : effectifs, parité, âge moyen, maires, appariement HATVP. */
export function getStatsElus(): StatsElus | null {
  const db = getDb();
  if (!db) return null;
  const deputes = db
    .prepare(
      `SELECT COUNT(*) AS nb,
              SUM(CASE WHEN e.sexe = 'F' THEN 1 ELSE 0 END) AS nb_femmes,
              ROUND(AVG((julianday('now') - julianday(e.date_naissance)) / 365.25), 1) AS age_moyen
       FROM deputes d JOIN elus e ON e.uid_an = d.uid_an`,
    )
    .get() as StatsChambre;
  const senateurs = db
    .prepare(
      `SELECT COUNT(*) AS nb,
              SUM(CASE WHEN sexe = 'F' THEN 1 ELSE 0 END) AS nb_femmes,
              ROUND(AVG((julianday('now') - julianday(date_naissance)) / 365.25), 1) AS age_moyen
       FROM senateurs`,
    )
    .get() as StatsChambre;
  const maires = db
    .prepare(
      `SELECT COUNT(*) AS nb
       FROM elus e, json_each(e.mandats) je
       WHERE json_extract(je.value, '$.type') = 'maire'`,
    )
    .get() as { nb: number };
  const totaux = db
    .prepare(
      `SELECT COUNT(*) AS nb_elus,
              SUM(CASE WHEN hatvp_flag = 1 THEN 1 ELSE 0 END) AS nb_elus_hatvp
       FROM elus`,
    )
    .get() as { nb_elus: number; nb_elus_hatvp: number };
  const declarations = db
    .prepare(`SELECT COUNT(*) AS nb FROM hatvp_declarations`)
    .get() as { nb: number };
  return {
    deputes,
    senateurs,
    nb_maires: maires.nb,
    nb_elus: totaux.nb_elus,
    nb_elus_hatvp: totaux.nb_elus_hatvp,
    nb_declarations_hatvp: declarations.nb,
  };
}

/* ------------------------------------------------------------------ */
/* Listes filtrables (searchParams server-side)                        */
/* ------------------------------------------------------------------ */

export type DeputeLigne = {
  /** Id de fiche = `elus.id` (ici égal à uid_an). */
  elu_id: string;
  uid_an: string;
  nom: string;
  prenom: string | null;
  groupe_sigle: string | null;
  groupe_nom: string | null;
  departement: string | null;
  /** Calcul France Transparence, 0–100 (%), 12 derniers mois. */
  taux_participation_12m: number | null;
  /** Score Datan tel que publié, 0–1. */
  datan_score_participation: number | null;
  /** Fiche producteur AN — NULL si absente en base, jamais inventée. */
  url_fiche_an: string | null;
  /** Fiche HATVP (AN en priorité, sinon `elus.hatvp_url`). */
  hatvp_url: string | null;
};

export type FiltresListe = { groupe?: string; departement?: string };

/** Députés (577), filtrables par groupe (sigle) et département (nom). */
export function getDeputes(filtres: FiltresListe = {}): DeputeLigne[] | null {
  const db = getDb();
  if (!db) return null;
  const conditions: string[] = [];
  const params: string[] = [];
  if (filtres.groupe) {
    conditions.push("d.groupe_sigle = ?");
    params.push(filtres.groupe);
  }
  if (filtres.departement) {
    conditions.push("d.departement = ?");
    params.push(filtres.departement);
  }
  const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";
  return db
    .prepare(
      `SELECT d.uid_an, e.id AS elu_id, d.nom, d.prenom, d.groupe_sigle,
              d.groupe_nom, d.departement,
              d.taux_participation_12m, d.datan_score_participation,
              d.url_fiche_an, COALESCE(NULLIF(TRIM(d.url_hatvp), ''), e.hatvp_url) AS hatvp_url
       FROM deputes d JOIN elus e ON e.uid_an = d.uid_an
       ${where}
       ORDER BY d.nom, d.prenom`,
    )
    .all(...params) as DeputeLigne[];
}

/** Départements d'élection des députés (noms, triés). */
export function getDepartementsDeputes(): string[] | null {
  const db = getDb();
  if (!db) return null;
  const lignes = db
    .prepare(
      `SELECT DISTINCT departement FROM deputes
       WHERE departement IS NOT NULL ORDER BY departement`,
    )
    .all() as { departement: string }[];
  return lignes.map((l) => l.departement);
}

export type SenateurLigne = {
  /** Id de fiche = `elus.id` (SEN-<matricule>). */
  elu_id: string;
  matricule: string;
  nom: string;
  prenom: string | null;
  groupe: string | null;
  groupe_appartenance: string | null;
  circonscription: string | null;
  commission: string | null;
  /** Calcul France Transparence, 0–100 (%), 12 derniers mois. Null = pas de scrutin éligible. */
  taux_participation_12m: number | null;
  /** Fiche producteur Sénat — NULL si absente en base, jamais inventée. */
  url_fiche_senat: string | null;
  /** Fiche HATVP (`elus.hatvp_url`). */
  hatvp_url: string | null;
};

/** Sénateurs (348), filtrables par groupe et circonscription (département). */
export function getSenateurs(filtres: FiltresListe = {}): SenateurLigne[] | null {
  const db = getDb();
  if (!db) return null;
  const conditions: string[] = [];
  const params: string[] = [];
  if (filtres.groupe) {
    conditions.push("s.groupe = ?");
    params.push(filtres.groupe);
  }
  if (filtres.departement) {
    conditions.push("s.circonscription = ?");
    params.push(filtres.departement);
  }
  const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";
  return db
    .prepare(
      `SELECT s.matricule, e.id AS elu_id, s.nom, s.prenom, s.groupe,
              s.groupe_appartenance, s.circonscription, s.commission,
              p.taux_participation_12m,
              s.url_fiche_senat, e.hatvp_url
       FROM senateurs s
       JOIN elus e ON e.matricule_senat = s.matricule
       LEFT JOIN participation_senat p ON p.matricule = s.matricule
       ${where}
       ORDER BY s.nom, s.prenom`,
    )
    .all(...params) as SenateurLigne[];
}

/** Départements (circonscriptions) des sénateurs, triés. */
export function getDepartementsSenat(): string[] | null {
  const db = getDb();
  if (!db) return null;
  const lignes = db
    .prepare(
      `SELECT DISTINCT circonscription FROM senateurs
       WHERE circonscription IS NOT NULL ORDER BY circonscription`,
    )
    .all() as { circonscription: string }[];
  return lignes.map((l) => l.circonscription);
}

/* ------------------------------------------------------------------ */
/* Scrutins récents                                                    */
/* ------------------------------------------------------------------ */

export type ScrutinLigne = {
  uid: string;
  numero: number;
  date_scrutin: string;
  titre: string | null;
  sort: string | null; // 'adopté' / 'rejeté'
  pour: number | null;
  contre: number | null;
  abstentions: number | null;
  adopte: number;
};

/** Les N derniers scrutins publics de l'AN présents en base. */
export function getDerniersScrutins(n = 10): ScrutinLigne[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT uid, numero, date_scrutin, titre, sort, pour, contre, abstentions, adopte
       FROM scrutins
       ORDER BY date_scrutin DESC, numero DESC
       LIMIT ?`,
    )
    .all(n) as ScrutinLigne[];
}

/** Les N derniers scrutins publics du Sénat (Dosleg), tables nouvelles. */
export function getDerniersScrutinsSenat(n = 10): ScrutinLigne[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT 'SCRSEN-' || sesann || '-' || numero AS uid,
              numero, date_scrutin, titre, sort, pour, contre, abstentions, adopte
       FROM scrutins_senat
       ORDER BY date_scrutin DESC, sesann DESC, numero DESC
       LIMIT ?`,
    )
    .all(n) as ScrutinLigne[];
}

/* ------------------------------------------------------------------ */
/* Fiche élu                                                           */
/* ------------------------------------------------------------------ */

/** Une entrée du JSON `elus.mandats` (champs observés, tous optionnels). */
export type MandatJson = {
  source?: string;
  type?: string;
  legislature?: number;
  date_debut?: string | null;
  date_fin?: string | null;
  date_debut_mandat?: string;
  date_debut_fonction?: string;
  departement?: string;
  circonscription?: string;
  groupe?: string;
  commune?: string;
  code_commune?: string;
  epci?: string;
  siren_epci?: string;
  region?: string;
  code_region?: string;
  libelle?: string;
  fonction?: string;
};

export type EluRow = {
  id: string;
  nom: string;
  prenom: string | null;
  sexe: string | null;
  date_naissance: string | null;
  profession: string | null;
  uid_an: string | null;
  matricule_senat: string | null;
  hatvp_flag: number;
  hatvp_url: string | null;
  mandats: string | null;
};

export type DeputeDetail = {
  uid_an: string;
  legislature: number;
  nom: string;
  prenom: string | null;
  departement: string | null;
  num_departement: string | null;
  num_circo: string | null;
  groupe_sigle: string | null;
  groupe_nom: string | null;
  commission: string | null;
  date_debut_mandat: string | null;
  url_fiche_an: string | null;
  url_hatvp: string | null;
  taux_participation_12m: number | null;
  nb_votes_12m: number | null;
  nb_scrutins_12m: number | null;
  participation_source: string | null;
  participation_maj: string | null;
  datan_score_participation: number | null;
  datan_score_participation_specialite: number | null;
  datan_score_loyaute: number | null;
  datan_score_majorite: number | null;
  datan_source: string | null;
  datan_date: string | null;
};

export type SenateurDetail = {
  matricule: string;
  nom: string;
  prenom: string | null;
  circonscription: string | null;
  groupe: string | null;
  groupe_appartenance: string | null;
  commission: string | null;
  date_debut_mandat: string | null;
  profession: string | null;
  url_fiche_senat: string | null;
  taux_participation_12m: number | null;
  nb_votes_12m: number | null;
  nb_scrutins_12m: number | null;
  participation_source: string | null;
  participation_maj: string | null;
};

export type VoteLigne = {
  scrutin_uid: string;
  numero: number;
  date_scrutin: string;
  titre: string | null;
  sort: string | null;
  /** 'pour' | 'contre' | 'abstention' | 'nonVotant' | null (aucune position enregistrée). */
  position: string | null;
  par_delegation: number | null;
};

export type DeclarationHatvp = {
  id: number;
  type_document: string | null;
  type_mandat: string | null;
  qualite: string | null;
  date_depot: string | null;
  date_publication: string | null;
  statut_publication: string;
  url_fiche: string | null;
};

/**
 * Nombre de scrutins affichés sur une fiche député — plafond d'allègement
 * des fiches statiques (l'export génère ~1 000 fiches ; chaque ligne pèse
 * ~1,8 Ko, HTML + payload RSC). 30 tient la pire fiche (11 déclarations
 * HATVP) sous 150 Ko brut. Le total présent en base est retourné à côté
 * (`nb_scrutins_base`) pour une mention honnête « N derniers sur X ».
 */
export const VOTES_FICHE_MAX = 30;

export type FicheElu = {
  elu: EluRow;
  /** JSON `elus.mandats` parsé ([] si NULL ou invalide). */
  mandats: MandatJson[];
  depute: DeputeDetail | null;
  senateur: SenateurDetail | null;
  /** Positions du député sur les VOTES_FICHE_MAX derniers scrutins présents (null hors député). */
  votes: VoteLigne[] | null;
  /** Total de scrutins présents en base (null hors député). */
  nb_scrutins_base: number | null;
  /** Positions du sénateur sur les VOTES_FICHE_MAX derniers scrutins Sénat. */
  votes_senat: VoteLigne[] | null;
  /** Total de scrutins Sénat présents en détail (null hors sénateur). */
  nb_scrutins_senat_base: number | null;
  /** Déclarations HATVP appariées par fiche nominative (URL exacte). */
  declarations: DeclarationHatvp[];
};

/**
 * Fiche complète d'un élu par `elus.id`. `null` = introuvable OU base
 * absente (la page distingue les deux en testant `getDb()` d'abord).
 */
export function getFicheElu(id: string): FicheElu | null {
  const db = getDb();
  if (!db) return null;
  const elu = db
    .prepare(
      `SELECT id, nom, prenom, sexe, date_naissance, profession, uid_an,
              matricule_senat, hatvp_flag, hatvp_url, mandats
       FROM elus WHERE id = ?`,
    )
    .get(id) as EluRow | undefined;
  if (!elu) return null;

  let mandats: MandatJson[] = [];
  if (elu.mandats) {
    try {
      const brut: unknown = JSON.parse(elu.mandats);
      if (Array.isArray(brut)) mandats = brut as MandatJson[];
    } catch {
      mandats = [];
    }
  }

  let depute: DeputeDetail | null = null;
  let votes: VoteLigne[] | null = null;
  let nbScrutinsBase: number | null = null;
  if (elu.uid_an) {
    depute =
      (db
        .prepare(
          `SELECT uid_an, legislature, nom, prenom, departement, num_departement,
                  num_circo, groupe_sigle, groupe_nom, commission, date_debut_mandat,
                  url_fiche_an, url_hatvp,
                  taux_participation_12m, nb_votes_12m, nb_scrutins_12m,
                  participation_source, participation_maj,
                  datan_score_participation, datan_score_participation_specialite,
                  datan_score_loyaute, datan_score_majorite, datan_source, datan_date
           FROM deputes WHERE uid_an = ?`,
        )
        .get(elu.uid_an) as DeputeDetail | undefined) ?? null;
    if (depute) {
      // Les VOTES_FICHE_MAX derniers scrutins présents en base
      // (votes_recents), avec la position du député — LEFT JOIN : NULL =
      // aucune position enregistrée. Le total sert à la mention honnête.
      nbScrutinsBase = (
        db
          .prepare("SELECT COUNT(DISTINCT scrutin_uid) AS nb FROM votes_recents")
          .get() as { nb: number }
      ).nb;
      votes = db
        .prepare(
          `SELECT s.uid AS scrutin_uid, s.numero, s.date_scrutin, s.titre, s.sort,
                  v.position, v.par_delegation
           FROM (SELECT DISTINCT scrutin_uid FROM votes_recents) sc
           JOIN scrutins s ON s.uid = sc.scrutin_uid
           LEFT JOIN votes_recents v ON v.scrutin_uid = s.uid AND v.uid_an = ?
           ORDER BY s.date_scrutin DESC, s.numero DESC
           LIMIT ?`,
        )
        .all(elu.uid_an, VOTES_FICHE_MAX) as VoteLigne[];
    }
  }

  let senateur: SenateurDetail | null = null;
  let votesSenat: VoteLigne[] | null = null;
  let nbScrutinsSenatBase: number | null = null;
  if (elu.matricule_senat) {
    senateur =
      (db
        .prepare(
          `SELECT s.matricule, s.nom, s.prenom, s.circonscription, s.groupe,
                  s.groupe_appartenance, s.commission, s.date_debut_mandat,
                  s.profession, s.url_fiche_senat,
                  p.taux_participation_12m, p.nb_votes_12m, p.nb_scrutins_12m,
                  p.participation_source, p.participation_maj
           FROM senateurs s
           LEFT JOIN participation_senat p ON p.matricule = s.matricule
           WHERE s.matricule = ?`,
        )
        .get(elu.matricule_senat) as SenateurDetail | undefined) ?? null;
    if (senateur) {
      nbScrutinsSenatBase = (
        db
          .prepare("SELECT COUNT(*) AS nb FROM (SELECT DISTINCT sesann, numero FROM votes_senat)")
          .get() as { nb: number }
      ).nb;
      votesSenat = db
        .prepare(
          `SELECT 'SCRSEN-' || s.sesann || '-' || s.numero AS scrutin_uid,
                  s.numero, s.date_scrutin, s.titre, s.sort,
                  v.position, v.par_delegation
           FROM (SELECT DISTINCT sesann, numero FROM votes_senat) sc
           JOIN scrutins_senat s ON s.sesann = sc.sesann AND s.numero = sc.numero
           LEFT JOIN votes_senat v
             ON v.sesann = s.sesann AND v.numero = s.numero AND v.matricule = ?
           ORDER BY s.date_scrutin DESC, s.sesann DESC, s.numero DESC
           LIMIT ?`,
        )
        .all(elu.matricule_senat, VOTES_FICHE_MAX) as VoteLigne[];
    }
  }

  // Appariement HATVP par URL de fiche nominative — clé forte, jamais par
  // simple homonymie (règle A1 : rien de présumé nominatif).
  const urls = [...new Set([elu.hatvp_url, depute?.url_hatvp].filter((u): u is string => !!u))];
  let declarations: DeclarationHatvp[] = [];
  if (urls.length > 0) {
    const marques = urls.map(() => "?").join(", ");
    declarations = db
      .prepare(
        `SELECT id, type_document, type_mandat, qualite, date_depot,
                date_publication, statut_publication, url_fiche
         FROM hatvp_declarations
         WHERE url_fiche IN (${marques})
         ORDER BY COALESCE(date_depot, date_publication) DESC, id`,
      )
      .all(...urls) as DeclarationHatvp[];
  }

  return {
    elu,
    mandats,
    depute,
    senateur,
    votes,
    nb_scrutins_base: nbScrutinsBase,
    votes_senat: votesSenat,
    nb_scrutins_senat_base: nbScrutinsSenatBase,
    declarations,
  };
}

/**
 * Identifiants des fiches statiques : députés et exécutifs CD/CR depuis
 * le JSON des mandats ; sénateurs depuis la table `senateurs` (ODSEN
 * ACTIF), pas depuis `json_extract(type)='senateur'` (353 fusionnés /
 * 349 SEN-* dont 1 ANCIEN).
 */
export function getIdsFichesStatiques(): string[] {
  const db = getDb();
  if (!db) return [];
  const typesHorsSenat = [
    "depute",
    "president_conseil_departemental",
    "president_conseil_regional",
  ];
  const marques = typesHorsSenat.map(() => "?").join(", ");
  const autres = db
    .prepare(
      `SELECT DISTINCT e.id
       FROM elus e, json_each(e.mandats) je
       WHERE json_extract(je.value, '$.type') IN (${marques})`,
    )
    .all(...typesHorsSenat) as { id: string }[];
  const sen = db
    .prepare(
      `SELECT e.id
       FROM senateurs s
       JOIN elus e ON e.matricule_senat = s.matricule`,
    )
    .all() as { id: string }[];
  const ids = new Set<string>();
  for (const r of autres) ids.add(r.id);
  for (const r of sen) ids.add(r.id);
  return [...ids].sort();
}

/* ------------------------------------------------------------------ */
/* Recherche (héritage de l'ancienne route serveur)                    */
/* ------------------------------------------------------------------ */

/** Échappe `\`, `%` et `_` pour un motif LIKE … ESCAPE '\'. */
export function echappeLike(brut: string): string {
  return brut.replace(/[\\%_]/g, (c) => `\\${c}`);
}

export type EluRecherche = {
  id: string;
  nom: string;
  prenom: string | null;
  uid_an: string | null;
  matricule_senat: string | null;
  /** Département AN (nom) si député. */
  dep_an: string | null;
  /** Département Sénat (circonscription) si sénateur. */
  dep_senat: string | null;
  mandats: string | null;
};

/**
 * Recherche d'élus par nom/prénom — LIKE insensible à la casse (ASCII),
 * motif échappé. Parlementaires d'abord, puis préfixe de nom, puis alpha.
 */
export function rechercheElus(q: string, limite = 8): EluRecherche[] | null {
  const db = getDb();
  if (!db) return null;
  const motif = `%${echappeLike(q)}%`;
  const prefixe = `${echappeLike(q)}%`;
  return db
    .prepare(
      `SELECT e.id, e.nom, e.prenom, e.uid_an, e.matricule_senat,
              d.departement AS dep_an, s.circonscription AS dep_senat, e.mandats
       FROM elus e
       LEFT JOIN deputes d ON d.uid_an = e.uid_an
       LEFT JOIN senateurs s ON s.matricule = e.matricule_senat
       WHERE e.nom LIKE ? ESCAPE '\\' OR e.prenom LIKE ? ESCAPE '\\'
       ORDER BY CASE WHEN e.uid_an IS NOT NULL OR e.matricule_senat IS NOT NULL THEN 0 ELSE 1 END,
                CASE WHEN e.nom LIKE ? ESCAPE '\\' THEN 0 ELSE 1 END,
                e.nom, e.prenom
       LIMIT ?`,
    )
    .all(motif, motif, prefixe, limite) as EluRecherche[];
}

export type EntiteRecherche = {
  id: string;
  type: "ministere" | "institution" | "collectivite" | "parti";
  nom: string;
  sigle: string | null;
};

/**
 * Recherche d'entités par nom/sigle (4 types routables : ministère,
 * institution, collectivité, parti). Institutions d'abord (peu nombreuses
 * et très demandées), puis ministères, collectivités, partis.
 */
export function rechercheEntites(q: string, limite = 4): EntiteRecherche[] | null {
  const db = getDb();
  if (!db) return null;
  const motif = `%${echappeLike(q)}%`;
  return db
    .prepare(
      `SELECT id, type, nom, sigle
       FROM entites
       WHERE (nom LIKE ? ESCAPE '\\' OR sigle LIKE ? ESCAPE '\\')
         AND type IN ('ministere', 'institution', 'collectivite', 'parti')
       ORDER BY CASE type
                  WHEN 'institution' THEN 0
                  WHEN 'ministere' THEN 1
                  WHEN 'collectivite' THEN 2
                  ELSE 3
                END, nom
       LIMIT ?`,
    )
    .all(motif, motif, limite) as EntiteRecherche[];
}
