/**
 * Requêtes de la page /donnees (« Données & API ») et des exports JSON
 * statiques (/api/meta.json, /api/elus.json, /api/marches-agregats.json,
 * /api/budget-mensuel.json) — générés au build, servis en fichiers.
 *
 * La table pivot est `meta_sources` (44 sources tracées) : chaque source y
 * porte sa date de données réelle, sa date d'ingestion, sa fréquence déclarée,
 * sa licence et ses notes — c'est le « moniteur de fraîcheur » du projet
 * (docs/SOURCES.md, alerte A11).
 *
 * Toutes les requêtes renvoient `null` si la base n'existe pas encore.
 */
import { getDb, type MetaSource } from "@/lib/db";
import { evalueFraicheur, type Fraicheur } from "@/lib/fraicheur";

// Seuils, niveaux et phrases de fraîcheur : module pur `lib/fraicheur.ts`,
// partagé avec le recalcul fait dans le navigateur à la date de lecture.
export {
  constatAttente,
  evalueFraicheur,
  type Fraicheur,
  type NiveauFraicheur,
  type UniteAge,
} from "@/lib/fraicheur";

export type SourceCataloguee = MetaSource & { fraicheur: Fraicheur };

/**
 * Les sources tracées, avec leur fraîcheur calculée à l'instant `maintenant`
 * — que l'appelant DATE là où il l'affiche (`genere_le` de /api/meta.json,
 * « état calculé le … » de /donnees) : un état sans sa date devient faux dès
 * qu'un cycle de publication saute.
 */
export function getCatalogueSources(maintenant: Date): SourceCataloguee[] | null {
  const db = getDb();
  if (!db) return null;
  const sources = db
    .prepare("SELECT * FROM meta_sources ORDER BY source_id")
    .all() as MetaSource[];
  return sources.map((s) => ({
    ...s,
    fraicheur: evalueFraicheur(s.source_id, s.date_donnees, maintenant),
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
/* Couvertures temporelles réelles (balisage schema.org des exports)   */
/* ------------------------------------------------------------------ */

/**
 * Couverture temporelle d'une série mensuelle, au format d'intervalle
 * ISO 8601 attendu par `Dataset.temporalCoverage` (« 2013-01/2026-06 »).
 * Calculée sur la donnée RÉELLEMENT en base — jamais une borne codée en dur,
 * qui deviendrait fausse au premier mois publié.
 */
function intervalle(debut: string | null, fin: string | null): string | null {
  return debut && fin ? `${debut}/${fin}` : null;
}

/** Couverture réelle de la série budgétaire mensuelle (S13, DGFiP). */
export function getCouvertureBudgetMensuel(): string | null {
  const db = getDb();
  if (!db) return null;
  const r = db
    .prepare(
      `SELECT MIN(annee || '-' || printf('%02d', mois)) AS debut,
              MAX(annee || '-' || printf('%02d', mois)) AS fin
         FROM budget_mensuel`,
    )
    .get() as { debut: string | null; fin: string | null };
  return intervalle(r.debut, r.fin);
}

/** Couverture réelle des agrégats mensuels de marchés publics (S1, DECP). */
export function getCouvertureMarchesAgregats(): string | null {
  const db = getDb();
  if (!db) return null;
  const r = db
    .prepare("SELECT MIN(mois) AS debut, MAX(mois) AS fin FROM decp_agg_mois")
    .get() as { debut: string | null; fin: string | null };
  return intervalle(r.debut, r.fin);
}

/**
 * Date d'ingestion la plus récente parmi une liste de sources — c'est la
 * date de dernière modification RÉELLE d'un export qui les agrège
 * (`Dataset.dateModified`), et non la date du build.
 */
export function getDerniereIngestionParIds(ids: string[]): string | null {
  const sources = getMetaSourcesParIds(ids);
  if (!sources || sources.length === 0) return null;
  return sources.reduce(
    (max, s) => (s.date_ingestion > max ? s.date_ingestion : max),
    sources[0].date_ingestion,
  );
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

/** Ligne compacte de l'export /api/elus.json (clés absentes = non renseigné). */
export type EluExport = {
  id: string;
  nom: string;
  prenom?: string;
  uid_an?: string;
  matricule_senat?: string;
  hatvp_url?: string;
  /**
   * Types des mandats EN COURS portés par le JSON `mandats` : un mandat daté
   * d'une fin en est exclu, et `depute` / `senateur` ne figurent que si la
   * chambre liste l'élu aujourd'hui (tables `deputes` / `senateurs`). Un
   * sortant garde son entrée (datée), et le RNE trimestriel peut encore dire
   * parlementaire quelqu'un que la chambre ne liste plus : la chambre fait foi.
   */
  types_mandats?: string[];
};

/**
 * Dump complet du répertoire des élus pour l'export statique, en champs
 * COMPACTS : le dump intégral (mandats détaillés + profession) pèse ~14 Mo,
 * intenable en fichier statique — on garde l'identité, les identifiants
 * publics, le lien HATVP et les types de mandat (~3,9 Mo), en omettant les
 * clés vides. Le détail des mandats reste sur les fiches et dans le RNE.
 */
export function getElusExport(): EluExport[] | null {
  const db = getDb();
  if (!db) return null;
  const lignes = db
    .prepare(
      `SELECT e.id, e.nom, e.prenom, e.uid_an, e.matricule_senat, e.hatvp_url,
              e.mandats, d.uid_an AS an_actif, s.matricule AS senat_actif
       FROM elus e
       LEFT JOIN deputes d ON d.uid_an = e.uid_an
       LEFT JOIN senateurs s ON s.matricule = e.matricule_senat
       ORDER BY e.nom, e.prenom`,
    )
    .all() as {
    id: string;
    nom: string;
    prenom: string | null;
    uid_an: string | null;
    matricule_senat: string | null;
    hatvp_url: string | null;
    mandats: string | null;
    an_actif: string | null;
    senat_actif: string | null;
  }[];
  return lignes.map((l) => {
    const e: EluExport = { id: l.id, nom: l.nom };
    if (l.prenom) e.prenom = l.prenom;
    if (l.uid_an) e.uid_an = l.uid_an;
    if (l.matricule_senat) e.matricule_senat = l.matricule_senat;
    if (l.hatvp_url) e.hatvp_url = l.hatvp_url;
    if (l.mandats) {
      try {
        const brut: unknown = JSON.parse(l.mandats);
        if (Array.isArray(brut)) {
          const horsExercice = (t: string): boolean =>
            (t === "depute" && !l.an_actif) || (t === "senateur" && !l.senat_actif);
          const types = [
            ...new Set(
              brut
                .filter((m) => !(m as { date_fin?: unknown }).date_fin)
                .map((m) => (m as { type?: unknown }).type)
                .filter((t): t is string => typeof t === "string")
                .filter((t) => !horsExercice(t)),
            ),
          ].sort();
          if (types.length > 0) e.types_mandats = types;
        }
      } catch {
        /* JSON invalide : clé omise */
      }
    }
    return e;
  });
}

/* ------------------------------------------------------------------ */
/* /api/marches-agregats.json — agrégats DECP pré-calculés             */
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
/* /api/budget-mensuel.json — situations mensuelles budgétaires (S13)  */
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
 * Série budgétaire COMPLÈTE (2013 → dernier mois publié, ~4 200 lignes),
 * tri chronologique puis ordre de tableau — dump de l'export statique.
 */
export function getBudgetMensuelComplet(): BudgetMensuelLigne[] | null {
  const db = getDb();
  if (!db) return null;
  return db
    .prepare(
      `SELECT ${COLONNES_BUDGET} FROM budget_mensuel
       ORDER BY date_fin_mois, ordre`,
    )
    .all() as BudgetMensuelLigne[];
}
