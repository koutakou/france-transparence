/**
 * Requêtes de la page /donnees (« Données & API ») et des exports JSON
 * statiques (/api/meta.json, /api/elus.json, /api/marches-agregats.json,
 * /api/budget-mensuel.json) — générés au build, servis en fichiers.
 *
 * La table pivot est `meta_sources` (36 sources tracées) : chaque source y
 * porte sa date de données réelle, sa date d'ingestion, sa fréquence déclarée,
 * sa licence et ses notes — c'est le « moniteur de fraîcheur » du projet
 * (docs/SOURCES.md, alerte A11).
 *
 * Toutes les requêtes renvoient `null` si la base n'existe pas encore.
 */
import { getDb, type MetaSource } from "@/lib/db";

/* ------------------------------------------------------------------ */
/* Fraîcheur des sources — un seuil calibré PAR SOURCE                  */
/* ------------------------------------------------------------------ */

/**
 * État de fraîcheur d'une source, par gravité croissante.
 *
 * `attente_edition` ne décrit PAS un défaut du site : il dit qu'à la date
 * du build, aucune édition plus récente n'avait été publiée en amont. C'est
 * un fait daté et vérifiable — jamais une affirmation sur l'intention de
 * l'éditeur ni sur l'avenir : l'édition suivante peut paraître demain, et
 * la première ingestion qui la trouve la publiera.
 */
export type NiveauFraicheur =
  | "a_jour"
  | "a_surveiller"
  | "en_retard"
  | "attente_edition"
  | "non_calibre";

/** Unité de comptage de l'âge : jours ouvrés (« jo ») ou calendaires (« jc »). */
export type UniteAge = "jo" | "jc";

export type Fraicheur = {
  niveau: NiveauFraicheur;
  /** Âge de la donnée (aujourd'hui − date_donnees), dans l'unité `unite`. */
  ageJours: number;
  unite: UniteAge;
  /** Seuils appliqués, `null` si la source n'est pas calibrée. */
  seuilRetardJours: number | null;
  seuilAlerteJours: number | null;
};

type SeuilSource = { unite: UniteAge; retard: number; alerte: number };

/**
 * Seuils de fraîcheur, UN JEU PAR SOURCE.
 *
 * Pourquoi pas une règle générique dérivée de `meta_sources.frequence` :
 * elle produit exactement les deux erreurs que ce tableau corrige. Deux
 * sources déclarées « quotidiennes » n'ont pas le même âge normal — 2 jours
 * pour le Journal officiel, 60 pour les scrutins de l'Assemblée, silencieux
 * toute la trêve estivale sans que rien ne soit cassé ; et une source
 * « annuelle » peut avoir un décalage structurel de 12 à 13 mois entre la
 * clôture de l'exercice et sa publication (subventions aux associations),
 * qu'aucune règle tirée du mot « annuelle » ne peut deviner. Neutraliser
 * ces sources-là (l'ancien état « millésime ») revenait à ne jamais rien
 * signaler sur les seules sources dont l'édition manque réellement.
 *
 * ────────────────────────────────────────────────────────────────────────
 * POINT DE SYNCHRONISATION — à lire avant de toucher à ce tableau
 * ────────────────────────────────────────────────────────────────────────
 * Ces valeurs sont une COPIE du référentiel qui fait autorité côté serveur,
 * `/etc/france-transparence/fraicheur.conf`, lu par la supervision
 * quotidienne `ft-fraicheur`. Duplication assumée faute de mieux :
 *   1. ce fichier n'est pas lisible par l'utilisateur qui construit le site
 *      (`/etc/france-transparence` est en 0750 root:root) ;
 *   2. il n'existe ni dans un dépôt fraîchement cloné ni dans la CI, qui
 *      doivent pourtant produire la même page (`make ingest` puis build).
 * Tant que ces deux points tiennent : toute modification de
 * `fraicheur.conf` doit être reportée ici, et réciproquement.
 * `ft-fraicheur --json` affiche les seuils réellement appliqués côté
 * serveur — c'est la commande qui vérifie que les deux n'ont pas divergé.
 * Deux façons de supprimer cette copie, hors périmètre de ce correctif :
 * rendre `fraicheur.conf` lisible au build et le lire ici, ou porter les
 * seuils dans `meta_sources` (colonnes dédiées) via les pipelines.
 *
 * Ordre et valeurs repris ligne à ligne de `fraicheur.conf`.
 * Dernière synchronisation : 23/08/2026, 36 sources (ajout de S44, S22 et S45).
 */
const SEUILS_SOURCES: Record<string, SeuilSource> = {
  // Quotidiennes strictes, calendrier ouvré
  S3: { unite: "jo", retard: 3, alerte: 7 },
  S2: { unite: "jo", retard: 3, alerte: 7 },
  S1: { unite: "jo", retard: 7, alerte: 20 },
  S4: { unite: "jo", retard: 6, alerte: 12 },
  S9: { unite: "jo", retard: 10, alerte: 20 },
  // Quotidiennes mais événementielles (le contenu ne bouge qu'à un événement)
  "S5-AMO10": { unite: "jc", retard: 20, alerte: 45 },
  "S6-ODSEN": { unite: "jc", retard: 20, alerte: 45 },
  "S7-DATAN": { unite: "jc", retard: 20, alerte: 45 },
  "S35-reforga-admin-etat": { unite: "jc", retard: 45, alerte: 90 },
  "S11-annuaire-administration": { unite: "jc", retard: 60, alerte: 120 },
  // Calendrier parlementaire (trêve estivale mi-juillet → début octobre)
  "S5-SCRUTINS": { unite: "jc", retard: 60, alerte: 95 },
  // DOLE (DILA) : livraisons du soir jusqu'à 5 fois/semaine selon
  // l'actualité parlementaire. date_donnees = max(DATE_DERNIERE_MODIFICATION),
  // jamais last_update data.gouv. Gap max observé 12 j (listing 22/08/2026).
  // 20/35 j couvre une quinzaine creuse sans attendre la trêve des scrutins.
  S43: { unite: "jc", retard: 20, alerte: 35 },
  // Hebdomadaire / mensuelle (lag de clôture comptable pour S13)
  S14: { unite: "jc", retard: 10, alerte: 18 },
  // Même génération hebdomadaire que S14 : les deux fichiers sont publiés à
  // une seconde d'écart par la HATVP, d'où des seuils identiques.
  S15: { unite: "jc", retard: 10, alerte: 18 },
  S13: { unite: "jc", retard: 65, alerte: 80 },
  // Mensuelle stricte : le stock Sirene paraît le 1er de chaque mois, et sa
  // date de donnée est celle du dernier traitement des unités retenues (la
  // veille de la publication). L'âge oscille donc de ~0 à ~32 jours en
  // régime normal ; 55 jours = un millésime entièrement sauté.
  S18: { unite: "jc", retard: 40, alerte: 55 },
  // Trimestrielle
  S17: { unite: "jc", retard: 110, alerte: 150 },
  // Trimestrielle GFS Eurostat t+113 ; date_donnees = fin du trimestre
  // de TIME max, jamais `updated` ; 220 j ≈ Q+1 en retard de ~2 sem. ;
  // 260 j ≈ Q+1 en retard d'~6 sem. (S17 110/150 sonnerait dès la parution).
  S41: { unite: "jc", retard: 220, alerte: 260 },
  // Annuelles « simples »
  S20: { unite: "jc", retard: 400, alerte: 440 },
  S37: { unite: "jc", retard: 400, alerte: 440 },
  S31: { unite: "jc", retard: 450, alerte: 550 },
  // Annuelle EDP (notification avril N+1). date_donnees = 31/12 du TIME
  // max, jamais `updated`. 400/440 sonnerait dès février, avant la
  // notification d'avril (~477 j après le 31/12). 520/600 = 17/20 mois.
  S42: { unite: "jc", retard: 520, alerte: 600 },
  // Annuelle GFS (juillet N+1). date_donnees = 31/12 du TIME max,
  // jamais `updated`. 400/440 sonnerait dès février, avant la
  // publication de juillet. 520/600 = 17/20 mois, comme S42 EDP.
  S44: { unite: "jc", retard: 520, alerte: 600 },
  // Annuelle CGE : millésime = 31/12 de la pièce de synthèse (xlsx),
  // jamais modified du catalogue. Les balances ligne à ligne peuvent
  // porter N+1 avant que la pièce ne l'ajoute ; 650/750 = 21,5/25 mois
  // couvre un exercice de retard de la pièce sans sonner dès février.
  S22: { unite: "jc", retard: 650, alerte: 750 },
  // Annuelle DREES, comptes de la protection sociale. date_donnees =
  // 31/12 de l'année max (2024 → 2024-12-31), jamais last_update
  // 2025-12-18. 650/750 comme S22 : millésime 2024 paru en décembre
  // 2025 ; 400/440 sonnerait dès l'été. Rupture à poser dans
  // fraicheur.conf (hors de ce fichier).
  S45: { unite: "jc", retard: 650, alerte: 750 },
  // Annuelles à décalage structurel documenté
  S21: { unite: "jc", retard: 400, alerte: 440 },
  S23: { unite: "jc", retard: 760, alerte: 850 },
  S25: { unite: "jc", retard: 850, alerte: 950 },
  S38: { unite: "jc", retard: 730, alerte: 820 },
  "S27-geo-api": { unite: "jc", retard: 400, alerte: 430 },
  S29: { unite: "jc", retard: 1500, alerte: 1800 },
  // « Par scrutin » comme S29 : l'âge reste élevé entre deux scrutins par
  // construction, l'alerting est donc quasi désactivé (~36/43 mois).
  S26: { unite: "jc", retard: 1100, alerte: 1300 },
  "S27-insee-populations": { unite: "jc", retard: 1500, alerte: 1650 },
  // Quasi statiques : l'âge n'est plus un signal, seul le volume l'est
  "S27-france-geojson": { unite: "jc", retard: 3650, alerte: 5475 },
  // Cadence composite (comptes locaux + dotations)
  S16: { unite: "jc", retard: 650, alerte: 750 },
  // Quotidienne, mais calendrier EUROPÉEN : l'export du registre de
  // transparence de l'Union est régénéré chaque soir par le secrétariat
  // commun Parlement européen / Commission, que le calendrier ouvré français
  // — jours fériés légaux compris — ne gouverne pas. D'où des jours
  // calendaires et non des jours ouvrés, contrairement à S4 (HATVP), avec
  // une marge suffisante pour absorber un week-end sans export.
  S40: { unite: "jc", retard: 6, alerte: 12 },
};

const JOUR_MS = 86_400_000;

/**
 * Dimanche de Pâques (minuit UTC) par l'algorithme de Meeus/Butcher —
 * même calcul que la supervision serveur, pour que les deux comptent
 * exactement les mêmes jours ouvrés.
 */
function paquesUTC(annee: number): number {
  const a = annee % 19;
  const b = Math.floor(annee / 100);
  const c = annee % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const mois = Math.floor((h + l - 7 * m + 114) / 31);
  const jour = ((h + l - 7 * m + 114) % 31) + 1;
  return Date.UTC(annee, mois - 1, jour);
}

const FERIES = new Map<number, Set<number>>();

/** Les 11 jours fériés légaux français d'une année (minuits UTC). */
function joursFeries(annee: number): Set<number> {
  const connu = FERIES.get(annee);
  if (connu) return connu;
  const p = paquesUTC(annee);
  const feries = new Set<number>([
    Date.UTC(annee, 0, 1), // Jour de l'an
    p + 1 * JOUR_MS, // Lundi de Pâques
    Date.UTC(annee, 4, 1), // Fête du Travail
    Date.UTC(annee, 4, 8), // Victoire 1945
    p + 39 * JOUR_MS, // Ascension
    p + 50 * JOUR_MS, // Lundi de Pentecôte
    Date.UTC(annee, 6, 14), // Fête nationale
    Date.UTC(annee, 7, 15), // Assomption
    Date.UTC(annee, 10, 1), // Toussaint
    Date.UTC(annee, 10, 11), // Armistice
    Date.UTC(annee, 11, 25), // Noël
  ]);
  FERIES.set(annee, feries);
  return feries;
}

/** Jours ouvrés strictement après `debut`, jusqu'à `fin` inclus. */
function ageJoursOuvres(debut: number, fin: number): number {
  let total = 0;
  for (let j = debut + JOUR_MS; j <= fin; j += JOUR_MS) {
    const d = new Date(j);
    const jourSemaine = d.getUTCDay();
    if (jourSemaine === 0 || jourSemaine === 6) continue;
    if (joursFeries(d.getUTCFullYear()).has(j)) continue;
    total += 1;
  }
  return total;
}

/** Le jour civil parisien d'un instant, au format AAAA-MM-JJ. */
const FORMAT_JOUR = new Intl.DateTimeFormat("fr-CA", {
  timeZone: "Europe/Paris",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/** Minuit UTC du jour AAAA-MM-JJ ; `null` si la date est illisible. */
function jourUTC(iso: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso.trim());
  if (!m) return null;
  const t = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return Number.isNaN(t) ? null : t;
}

/**
 * Fraîcheur d'une source : son âge comparé à SES deux seuils.
 *
 * - `a_jour` sous le seuil de retard — l'âge est celui d'un cycle normal ;
 * - `a_surveiller` entre les deux seuils — l'écart peut encore être un
 *   simple décalage de calendrier ;
 * - `en_retard` au-delà du seuil d'alerte ;
 * - `attente_edition` quand le dépassement excède à son tour la largeur de
 *   la bande de surveillance (seuil d'alerte + [alerte − retard]) : la
 *   source a alors dépassé son seuil d'alerte d'autant que toute la marge
 *   qui le précédait, ce qui ne se rattrape plus par un décalage de
 *   publication de quelques semaines ;
 * - `non_calibre` si la source n'a pas de ligne dans le référentiel — on
 *   affiche alors l'absence de seuil, jamais un état inventé.
 */
export function evalueFraicheur(
  sourceId: string,
  dateDonnees: string,
  maintenant: Date = new Date(),
): Fraicheur {
  const debut = jourUTC(dateDonnees);
  const fin = jourUTC(FORMAT_JOUR.format(maintenant));
  const ageCalendaire =
    debut !== null && fin !== null ? Math.max(Math.round((fin - debut) / JOUR_MS), 0) : 0;
  const seuil = SEUILS_SOURCES[sourceId];
  if (!seuil || debut === null || fin === null) {
    return {
      niveau: "non_calibre",
      ageJours: ageCalendaire,
      unite: "jc",
      seuilRetardJours: null,
      seuilAlerteJours: null,
    };
  }
  const ageJours = seuil.unite === "jo" ? ageJoursOuvres(debut, fin) : ageCalendaire;
  const bande = Math.max(seuil.alerte - seuil.retard, 1);
  const niveau: NiveauFraicheur =
    ageJours <= seuil.retard
      ? "a_jour"
      : ageJours <= seuil.alerte
        ? "a_surveiller"
        : ageJours <= seuil.alerte + bande
          ? "en_retard"
          : "attente_edition";
  return {
    niveau,
    ageJours,
    unite: seuil.unite,
    seuilRetardJours: seuil.retard,
    seuilAlerteJours: seuil.alerte,
  };
}

export type SourceCataloguee = MetaSource & { fraicheur: Fraicheur };

/** Les 36 sources tracées, avec leur fraîcheur calculée. */
export function getCatalogueSources(): SourceCataloguee[] | null {
  const db = getDb();
  if (!db) return null;
  const maintenant = new Date();
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

/** Ligne compacte de l'export /api/elus.json (clés absentes = non renseigné). */
export type EluExport = {
  id: string;
  nom: string;
  prenom?: string;
  uid_an?: string;
  matricule_senat?: string;
  hatvp_url?: string;
  /** Types de mandat distincts portés par le JSON `mandats`. */
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
      `SELECT id, nom, prenom, uid_an, matricule_senat, hatvp_url, mandats
       FROM elus ORDER BY nom, prenom`,
    )
    .all() as {
    id: string;
    nom: string;
    prenom: string | null;
    uid_an: string | null;
    matricule_senat: string | null;
    hatvp_url: string | null;
    mandats: string | null;
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
          const types = [
            ...new Set(
              brut
                .map((m) => (m as { type?: unknown }).type)
                .filter((t): t is string => typeof t === "string"),
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
