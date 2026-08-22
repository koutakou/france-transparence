/**
 * Requêtes du bloc « Participation électorale » — source S26 (résultats
 * agrégés du ministère de l'Intérieur, data.gouv.fr, licence lov2).
 * Lecture seule sur data/france.db, tables produites par
 * `pipelines/ingest_elections.py`.
 *
 * Ce que ce module expose, et RIEN d'autre : la PARTICIPATION (inscrits,
 * votants, blancs, nuls, exprimés) agrégée par commune et par département,
 * sur 7 scrutins. Aucune nuance politique, aucun nom de candidat, aucun
 * bureau de vote — décision documentée dans docs/ELECTIONS.md.
 *
 * Règles d'affichage tenues ici :
 * - **aucun taux n'est stocké en base** : tous les ratios sont calculés à la
 *   volée à partir des effectifs bruts, et valent `null` (jamais 0) quand le
 *   dénominateur manque — un taux stocké se lirait comme un zéro ;
 * - la somme des départements EXCLUT les Français établis hors de France
 *   (inscrits dans les consulats, ils ne relèvent d'aucun département) : elle
 *   est nommée « ensemble des départements », jamais « France entière », et
 *   diffère du taux national du ministère (74,9 % contre 73,7 % à la
 *   présidentielle 2022 T1) ;
 * - deux scrutins de nature différente ne se comparent pas naïvement : le
 *   libellé et la famille sont exposés pour que l'affichage le dise.
 *
 * Valeurs de contrôle, relevées le 20/08/2026 sur data/france.db en lecture
 * seule : 740 lignes départementales (7 scrutins × 102 à 107 collectivités),
 * 1 524 lignes communales, 234 communes suivies par le site
 * (`ref_villes` ∪ `collectivites_communes_top200` : préfectures et
 * communes de plus de 50 000 habitants, plus les 200 plus peuplées).
 *
 * Convention « base absente » : `getDonneesElections()` renvoie `null` tant
 * que `make ingest` n'a pas produit la base ou que S26 n'y est pas ingérée —
 * le composant affiche alors un message honnête, jamais un chiffre vide.
 *
 * ⚠ Module SERVEUR : il ouvre `data/france.db` via `@/lib/db` (better-sqlite3
 * et `node:fs`). Un composant client ne doit en importer que des TYPES
 * (`import type { … }`, effacé à la compilation) : une importation de valeur
 * embarquerait tout l'accès base dans le bundle navigateur et le build échoue
 * sur « Module not found: Can't resolve 'fs' ». Les formules d'affichage
 * (taux de participation, part des blancs et nuls, décodage des tuples) vivent
 * donc dans `@/components/client/ParticipationElectorale`, module pur.
 */
import { getDb, type MetaSource } from "@/lib/db";

/** Effectifs bruts d'un scrutin, tels qu'ils sortent des urnes. */
export type Effectifs = {
  inscrits: number;
  votants: number;
  blancs: number;
  nuls: number;
  exprimes: number;
};

/** Une collectivité (département ou commune) pour un scrutin donné. */
export type LigneParticipation = Effectifs & {
  code: string;
  nom: string;
};

/**
 * Ligne COMPACTE telle qu'elle traverse la frontière serveur → client :
 * `[code, inscrits, votants, blancs, nuls, exprimés]`.
 *
 * Pourquoi un tuple plutôt qu'un objet nommé : ces 2 264 lignes voyagent dans
 * le payload RSC de /collectivites, la page la plus lourde du site (1,85 Mo
 * bruts au dernier audit). Mesuré le 20/08/2026 sur les données réelles :
 * objets nommés avec libellé répété = 252 311 octets bruts (62 788 gzip) ;
 * libellés sortis dans `noms` + tuples = **92 438 octets bruts** (40 433
 * gzip), soit 63 % de moins à parser côté client. Le libellé d'une
 * collectivité ne varie pas d'un scrutin à l'autre : le répéter sept fois ne
 * transportait aucune information.
 *
 * `lireLigne()` la retraduit en objet nommé au moment du rendu.
 */
export type LigneCompacte = readonly [
  code: string,
  inscrits: number,
  votants: number,
  blancs: number,
  nuls: number,
  exprimes: number,
];

/**
 * `lireLigne()` (tuple + dictionnaire → objet nommé) vit dans le composant
 * client `ParticipationElectorale`, avec les formules de taux : ce module-ci
 * n'est pas importable en valeur depuis le navigateur (cf. en-tête).
 */

/**
 * Familles de scrutin — table FERMÉE, calquée sur les identifiants natifs du
 * ministère (`2026_muni_t1` = municipales 2026, 1er tour). Un code inconnu
 * s'affiche brut plutôt que traduit à tort (dégradation propre).
 */
const FAMILLES: Record<string, string> = {
  pres: "Présidentielle",
  legi: "Législatives",
  euro: "Européennes",
  muni: "Municipales",
  regi: "Régionales",
  dpmt: "Départementales",
  cant: "Cantonales",
};

/**
 * Dates de convocation des électeurs, par décret — table FERMÉE.
 *
 * POINT DE SYNCHRONISATION : ces dates sont la COPIE de `DATES_SCRUTINS`
 * dans `pipelines/ingest_elections.py`, qui les utilise pour renseigner
 * `meta_sources.date_donnees`. Le schéma des deux tables `elections_*` ne
 * porte volontairement aucune colonne de date (le périmètre arrêté est
 * « participation seulement ») : la date est un référentiel éditorial, pas
 * une donnée du parquet. Toute modification de l'une doit être reportée dans
 * l'autre. Un scrutin sans date ici s'affiche sans date, jamais avec une
 * date approchée.
 *   - présidentielle 2022 : décret n° 2022-107 du 02/02/2022 ;
 *   - européennes 2024 : décret n° 2024-217 du 12/03/2024 ;
 *   - législatives 2024 (dissolution) : décret n° 2024-527 du 09/06/2024 ;
 *   - municipales 2026 : décret n° 2025-848 du 27/08/2025.
 */
const DATES_SCRUTINS: Record<string, string> = {
  "2022_pres_t1": "2022-04-10",
  "2022_pres_t2": "2022-04-24",
  "2024_euro_t1": "2024-06-09",
  "2024_legi_t1": "2024-06-30",
  "2024_legi_t2": "2024-07-07",
  "2026_muni_t1": "2026-03-15",
  "2026_muni_t2": "2026-03-22",
};

/** Un scrutin : son identité, son agrégat, et ses deux niveaux de détail. */
export type Scrutin = {
  /** Identifiant natif du ministère (`2026_muni_t1`). */
  id: string;
  /** « Municipales 2026 · 1er tour ». */
  libelle: string;
  /** « Municipales » — deux familles ne se comparent pas naïvement. */
  famille: string;
  annee: number;
  tour: number;
  /** Date du tour (ISO) ; `null` si non déclarée — jamais approchée. */
  date: string | null;
  /**
   * Somme des départements ingérés. NOMMÉE « ensemble des départements » et
   * pas « France » : les électeurs inscrits hors de France n'y sont pas.
   */
  ensembleDepartements: Effectifs;
  /** 102 à 107 départements et collectivités, triés par nom. */
  departements: LigneCompacte[];
  /** Communes suivies par le site présentes à ce scrutin, triées par nom. */
  communes: LigneCompacte[];
};

export type DonneesElections = {
  /** Fraîcheur S26 (badge du bloc). */
  meta: MetaSource;
  /** Les scrutins ingérés, du plus récent au plus ancien. */
  scrutins: Scrutin[];
  /** Libellés par code (départements ET communes), une seule fois. */
  noms: Record<string, string>;
  /** Communes suivies par le site (ref_villes ∪ collectivites_communes_top200). */
  nbCommunesSuivies: number;
};

/** `2026_muni_t1` → { annee: 2026, famille: 'Municipales', tour: 1 }. */
function decrireScrutin(id: string): Pick<Scrutin, "libelle" | "famille" | "annee" | "tour"> {
  const [anneeBrute, codeFamille, tourBrut] = id.split("_");
  const annee = Number(anneeBrute);
  const tour = Number((tourBrut ?? "").replace("t", ""));
  const famille = FAMILLES[codeFamille] ?? codeFamille ?? id;
  const mentionTour = tour === 1 ? "1er tour" : Number.isFinite(tour) ? `${tour}e tour` : "";
  return {
    famille,
    annee: Number.isFinite(annee) ? annee : 0,
    tour: Number.isFinite(tour) ? tour : 0,
    libelle: [famille, Number.isFinite(annee) ? annee : null].filter(Boolean).join(" ") +
      (mentionTour ? ` · ${mentionTour}` : ""),
  };
}

/** Somme des lignes compactes — l'agrégat « ensemble des départements ». */
function sommer(lignes: LigneCompacte[]): Effectifs {
  return lignes.reduce<Effectifs>(
    (acc, [, inscrits, votants, blancs, nuls, exprimes]) => ({
      inscrits: acc.inscrits + inscrits,
      votants: acc.votants + votants,
      blancs: acc.blancs + blancs,
      nuls: acc.nuls + nuls,
      exprimes: acc.exprimes + exprimes,
    }),
    { inscrits: 0, votants: 0, blancs: 0, nuls: 0, exprimes: 0 },
  );
}

/** Fraîcheur de la source S26 (badge du bloc). */
export function getMetaElections(): MetaSource | null {
  const db = getDb();
  if (!db) return null;
  const ligne = db
    .prepare("SELECT * FROM meta_sources WHERE source_id = 'S26'")
    .get() as MetaSource | undefined;
  return ligne ?? null;
}

type LigneBrute = Effectifs & { id_election: string; code: string; nom: string };

/**
 * Tout le bloc participation en trois requêtes (les deux tables + le compte
 * des communes suivies). `null` si la base n'existe pas ou si S26 n'y est
 * pas ingérée — la page affiche alors un message honnête.
 *
 * Le tri est fait en SQL (par nom) pour que l'ordre des tableaux soit
 * déterministe d'un build à l'autre.
 */
export function getDonneesElections(): DonneesElections | null {
  const db = getDb();
  if (!db) return null;
  const meta = getMetaElections();
  if (!meta) return null;

  const deps = db
    .prepare(
      `SELECT id_election, code_departement AS code, libelle_departement AS nom,
              inscrits, votants, blancs, nuls, exprimes
       FROM elections_participation_departement
       ORDER BY id_election DESC, libelle_departement`,
    )
    .all() as LigneBrute[];
  // Le libellé communal vient du RÉFÉRENTIEL DU SITE, avec repli sur celui de
  // la source — même principe que les libellés départementaux, résolus par le
  // pipeline depuis ref_departements. Deux raisons : (1) le ministère change
  // la casse d'un scrutin à l'autre (« Aix-En-Provence » aux municipales 2026
  // T1, « Aix-en-Provence » au T2) ; (2) la même commune est nommée ailleurs
  // sur /collectivites depuis ce référentiel — deux orthographes du même nom
  // sur une seule page se lisent comme deux communes. Aucun code n'a deux
  // libellés dans l'union (vérifié le 20/08/2026), la jointure ne duplique
  // donc aucune ligne.
  const villes = db
    .prepare(
      `SELECT e.id_election, e.code_commune AS code,
              COALESCE(r.nom, e.libelle_commune) AS nom,
              e.inscrits, e.votants, e.blancs, e.nuls, e.exprimes
       FROM elections_participation_ville e
       LEFT JOIN (SELECT code_insee, nom FROM ref_villes
                  UNION SELECT code_insee, nom FROM collectivites_communes_top200) r
              ON r.code_insee = e.code_commune
       ORDER BY e.id_election DESC, nom`,
    )
    .all() as LigneBrute[];
  const nbCommunesSuivies = (
    db
      .prepare(
        `SELECT count(*) AS n FROM (
           SELECT code_insee FROM ref_villes
           UNION SELECT code_insee FROM collectivites_communes_top200)`,
      )
      .get() as { n: number }
  ).n;

  const parScrutin = new Map<string, { deps: LigneCompacte[]; villes: LigneCompacte[] }>();
  const vide = () => ({ deps: [] as LigneCompacte[], villes: [] as LigneCompacte[] });
  const noms: Record<string, string> = {};
  const compacter = (l: LigneBrute): LigneCompacte => {
    noms[l.code] = l.nom;
    return [l.code, l.inscrits, l.votants, l.blancs, l.nuls, l.exprimes];
  };
  for (const l of deps) {
    const groupe =
      parScrutin.get(l.id_election) ?? parScrutin.set(l.id_election, vide()).get(l.id_election)!;
    groupe.deps.push(compacter(l));
  }
  for (const l of villes) {
    const groupe =
      parScrutin.get(l.id_election) ?? parScrutin.set(l.id_election, vide()).get(l.id_election)!;
    groupe.villes.push(compacter(l));
  }

  // Du plus récent au plus ancien : les identifiants natifs commencent par
  // l'année, un tri décroissant sur la chaîne suffit et reste stable.
  const scrutins: Scrutin[] = [...parScrutin.entries()]
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([id, { deps: d, villes: v }]) => ({
      id,
      ...decrireScrutin(id),
      date: DATES_SCRUTINS[id] ?? null,
      ensembleDepartements: sommer(d),
      departements: d,
      communes: v,
    }));

  return { meta, scrutins, noms, nbCommunesSuivies };
}

/** L'identité d'un scrutin sans ses lignes — de quoi dessiner un bouton. */
export type ScrutinResume = Pick<Scrutin, "id" | "libelle" | "famille" | "annee" | "tour" | "date">;

/**
 * Ce que le HTML de /collectivites embarque : le scrutin initial COMPLET
 * (rendu serveur intact, lisible sans JavaScript) et les seuls résumés des
 * autres — leurs lignes (~119 Ko inline avant découpage, mesuré le
 * 20/08/2026) vivent dans le fragment statique /data/elections.json, chargé
 * au premier changement de scrutin. `noms` reste complet : les libellés
 * servent aux deux niveaux et ne pèsent qu'une fois.
 */
export type DonneesElectionsInline = {
  /** Fraîcheur S26 (badge du bloc). */
  meta: MetaSource;
  /** Libellés par code (départements ET communes), une seule fois. */
  noms: Record<string, string>;
  /** Communes suivies par le site (ref_villes ∪ collectivites_communes_top200). */
  nbCommunesSuivies: number;
  /** Les scrutins ingérés, du plus récent au plus ancien — SANS leurs lignes. */
  resumes: ScrutinResume[];
  /** Le scrutin affiché au chargement, seul rendu côté serveur. */
  scrutinInitial: Scrutin;
};

/**
 * Sous-ensemble de `getDonneesElections()` embarqué dans le HTML.
 *
 * RÈGLE DU SCRUTIN INITIAL (une seule vérité, ici et pas dans le composant) :
 * le dernier PREMIER tour — c'est le seul où toutes les communes votent.
 * Ouvrir sur un second tour donnerait à voir un tableau amputé des trois
 * quarts des communes pour une raison qui n'a rien à voir avec la donnée.
 */
export function getDonneesElectionsInline(): DonneesElectionsInline | null {
  const donnees = getDonneesElections();
  if (!donnees || donnees.scrutins.length === 0) return null;
  const scrutinInitial = donnees.scrutins.find((s) => s.tour === 1) ?? donnees.scrutins[0];
  return {
    meta: donnees.meta,
    noms: donnees.noms,
    nbCommunesSuivies: donnees.nbCommunesSuivies,
    resumes: donnees.scrutins.map(({ id, libelle, famille, annee, tour, date }) => ({
      id,
      libelle,
      famille,
      annee,
      tour,
      date,
    })),
    scrutinInitial,
  };
}
