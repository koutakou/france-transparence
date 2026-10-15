/**
 * Index de recherche statique — remplace l'ancienne route de recherche
 * paramétrique (impossible en site 100 % statique). Construit AU BUILD par la route
 * /data/recherche-index.json, chargé par la SearchBox à la première frappe,
 * interrogé côté client (insensible accents/casse).
 *
 * Couverture — la même que l'ancienne API :
 * - TOUS les élus (36 018) par nom/prénom, avec type de mandat principal et
 *   département ;
 * - les entités routables (ministères, institutions, collectivités, partis)
 *   par nom/sigle, vers leur module.
 *
 * CONTRAT FICHES (docs/deploiement/DECISION.md) : l'`id` n'est transporté que
 * pour les élus qui ont RÉELLEMENT une fiche statique /elus/<id> ; les autres
 * résultats renvoient vers la liste /elus — jamais vers une fiche 404. La
 * seule vérité est getIdsFichesStatiques(), celle-là même que consomme
 * generateStaticParams : tester ici les 4 types de mandat rendait la promesse
 * fausse pour les sénateurs, dont le JSON des mandats survit à la sortie de la
 * table `senateurs`. Aucun compte n'est écrit ici : il dérive à chaque
 * ingestion.
 *
 * Format compact (vise ≤ 1,5 Mo brut) : tableaux positionnels, libellés de
 * mandat et départements dédupliqués par index.
 */
import fs from "node:fs";
import { getDb } from "@/lib/db";
import { getIdsFichesStatiques, type MandatJson } from "@/lib/queries/elus";
import {
  GEOJSON_DEPARTEMENTS_PATH,
  type GeojsonDepartements,
} from "@/lib/queries/collectivites";

/** `[nom, prenom, typeIdx, depIdx, id?]` — 5ᵉ élément présent = fiche /elus/<id>. */
export type EluIndex = [nom: string, prenom: string, typeIdx: number, depIdx: number, id?: string];

/** `[nom, sigle, typeEntiteIdx, hrefIdx]`. */
export type EntiteIndex = [nom: string, sigle: string, typeIdx: number, hrefIdx: number];

export type IndexRecherche = {
  /** Libellés de mandat principal, indexés par `typeIdx`. */
  typesMandat: string[];
  /** Noms de départements, indexés par `depIdx` (-1 = inconnu). */
  departements: string[];
  elus: EluIndex[];
  /** Libellés de type d'entité, indexés par `typeIdx`. */
  typesEntite: string[];
  /** Cibles de navigation des entités, indexées par `hrefIdx`. */
  hrefs: string[];
  entites: EntiteIndex[];
};

/** Ordre de préférence du mandat principal (même ordre que l'ancienne API). */
const PRIORITE_MANDATS = [
  "depute",
  "senateur",
  "president_conseil_regional",
  "president_conseil_departemental",
  "president_epci",
  "maire",
] as const;

/**
 * Libellés de mandat, indexés — les variantes « (RNE, trimestriel) »
 * signalent un mandat parlementaire connu du seul répertoire trimestriel
 * (l'élu n'est pas dans les flux quotidiens AN/Sénat du jour), comme le
 * faisait l'ancienne API. « Ancien·ne » : élu qui porte l'identifiant de la
 * chambre (uid AN, matricule Sénat) mais qu'elle ne liste plus en exercice.
 */
const LIBELLES_MANDAT = [
  "Député·e", // 0
  "Sénateur·rice", // 1
  "Président·e de conseil régional", // 2
  "Président·e de conseil départemental", // 3
  "Président·e d’EPCI", // 4
  "Maire", // 5
  "Élu·e", // 6 (aucun mandat exploitable — réel dans le RNE)
  "Député·e (RNE, trimestriel)", // 7
  "Sénateur·rice (RNE, trimestriel)", // 8
  "Ancien·ne député·e", // 9 (la chambre ne liste plus cet élu)
  "Ancien·ne sénateur·rice", // 10 (idem)
] as const;

type LigneElu = {
  id: string;
  nom: string;
  prenom: string | null;
  uid_an: string | null;
  matricule_senat: string | null;
  mandats: string | null;
  dep_an: string | null;
  dep_senat: string | null;
  /** Non nul si l'élu figure parmi les députés EN EXERCICE (table `deputes`). */
  an_actif: string | null;
  /** Non nul si l'élu figure parmi les sénateurs EN EXERCICE (`senateurs`). */
  senat_actif: string | null;
};

type LigneEntite = {
  id: string;
  type: string;
  nom: string;
  sigle: string | null;
};

/** Construit l'index complet — `null` tant que la base n'existe pas. */
export function construireIndexRecherche(): IndexRecherche | null {
  const db = getDb();
  if (!db) return null;

  // Codes département (RNE) → noms. Source primaire : le GeoJSON S27
  // (« Ain », « Corse-du-Sud » — casse d'usage) ; complété par le
  // référentiel DGF (105 lignes dont OM, noms en capitales à la source).
  const nomsDep = new Map<string, string>();
  for (const l of db
    .prepare("SELECT code, nom FROM dotations_dgf WHERE niveau = 'departement'")
    .all() as { code: string; nom: string }[]) {
    nomsDep.set(l.code, l.nom);
  }
  if (fs.existsSync(GEOJSON_DEPARTEMENTS_PATH)) {
    try {
      const geo = JSON.parse(
        fs.readFileSync(GEOJSON_DEPARTEMENTS_PATH, "utf-8"),
      ) as GeojsonDepartements;
      for (const f of geo.features) {
        if (f.properties?.code && f.properties?.nom) {
          nomsDep.set(f.properties.code, f.properties.nom);
        }
      }
    } catch {
      // GeoJSON illisible : les noms DGF restent (jamais bloquant).
    }
  }

  const lignes = db
    .prepare(
      `SELECT e.id, e.nom, e.prenom, e.uid_an, e.matricule_senat, e.mandats,
              d.departement AS dep_an, s.circonscription AS dep_senat,
              d.uid_an AS an_actif, s.matricule AS senat_actif
       FROM elus e
       LEFT JOIN deputes d ON d.uid_an = e.uid_an
       LEFT JOIN senateurs s ON s.matricule = e.matricule_senat
       ORDER BY e.nom, e.prenom`,
    )
    .all() as LigneElu[];

  const departements: string[] = [];
  const depIdx = new Map<string, number>();
  const indexDep = (nom: string | null): number => {
    if (!nom) return -1;
    const connu = depIdx.get(nom);
    if (connu !== undefined) return connu;
    const i = departements.length;
    departements.push(nom);
    depIdx.set(nom, i);
    return i;
  };

  // Une seule construction pour les ~36 000 lignes : `has` en O(1), là où un
  // `includes` sur la liste des fiches serait quadratique.
  const idsFiches = new Set(getIdsFichesStatiques());

  const elus: EluIndex[] = lignes.map((e) => {
    let mandats: MandatJson[] = [];
    if (e.mandats) {
      try {
        const brut: unknown = JSON.parse(e.mandats);
        if (Array.isArray(brut)) mandats = brut as MandatJson[];
      } catch {
        mandats = [];
      }
    }

    // Mandat principal par priorité (même règle que l'ancienne API).
    let principal: MandatJson | undefined;
    // Un mandat daté d'une fin (député ou sénateur sorti : P9 date la fin
    // publiée par la chambre au lieu de retirer l'entrée) ne peut pas donner
    // son libellé à l'élu tant qu'un mandat en cours existe ; à défaut,
    // l'ordre de priorité s'applique à tous (libellé « Ancien·ne » ci-dessous).
    // Même règle pour un mandat parlementaire que les chambres ne confirment
    // pas, dès que l'élu leur est connu (uid AN ou matricule Sénat) : un
    // sénateur élu le 27/09/2026 que le RNE d'août dit encore député n'est
    // pas « Député·e ».
    const connuDesChambres = !!(e.uid_an || e.matricule_senat);
    const enCours = mandats.filter(
      (m) =>
        !m.date_fin &&
        !(connuDesChambres && m.type === "depute" && !e.an_actif) &&
        !(connuDesChambres && m.type === "senateur" && !e.senat_actif),
    );
    for (const vivier of [enCours, mandats]) {
      for (const type of PRIORITE_MANDATS) {
        principal = vivier.find((m) => m.type === type);
        if (principal) break;
      }
      if (principal) break;
    }
    principal = principal ?? mandats[0];

    // Fiche statique : l'id figure-t-il parmi les pages réellement générées ?
    const aFiche = idsFiches.has(e.id);

    // Libellé + département selon le mandat principal.
    let typeIdx = 6; // « Élu·e »
    let dep: string | null = null;
    const depDuMandat = (m: MandatJson | undefined): string | null => {
      if (!m) return null;
      if (m.departement) return nomsDep.get(m.departement) ?? m.libelle ?? m.departement;
      return m.libelle ?? m.region ?? null;
    };
    // « Député·e » / « Sénateur·rice » sans réserve seulement si la chambre
    // liste l'élu AUJOURD'HUI (tables `deputes` / `senateurs`). Porter un
    // uid_an ou un matricule ne le prouve pas : un sortant les garde, et la
    // chambre qui l'a connu ne le liste plus — elle fait foi sur le RNE
    // trimestriel, qui peut encore le dire parlementaire (« Ancien·ne »).
    // Sans identifiant de chambre, seul le RNE en parle (« RNE, trimestriel »).
    switch (principal?.type) {
      case "depute":
        typeIdx = e.an_actif ? 0 : e.uid_an ? 9 : 7;
        dep = e.dep_an ?? depDuMandat(principal);
        break;
      case "senateur":
        typeIdx = e.senat_actif ? 1 : e.matricule_senat ? 10 : 8;
        dep = e.dep_senat ?? depDuMandat(principal);
        break;
      case "president_conseil_regional":
        typeIdx = 2;
        dep = depDuMandat(principal);
        break;
      case "president_conseil_departemental":
        typeIdx = 3;
        dep = depDuMandat(principal);
        break;
      case "president_epci":
        typeIdx = 4;
        dep = depDuMandat(principal);
        break;
      case "maire":
        typeIdx = 5;
        dep = depDuMandat(principal);
        break;
      default:
        // Élu en exercice sans mandat JSON exploitable (défensif).
        if (e.an_actif) {
          typeIdx = 0;
          dep = e.dep_an;
        } else if (e.senat_actif) {
          typeIdx = 1;
          dep = e.dep_senat;
        }
    }

    return aFiche
      ? ([e.nom, e.prenom ?? "", typeIdx, indexDep(dep), e.id] as EluIndex)
      : ([e.nom, e.prenom ?? "", typeIdx, indexDep(dep)] as EluIndex);
  });

  // Entités routables — mêmes cibles que l'ancienne API.
  const typesEntite = ["Ministère", "Institution", "Collectivité", "Parti"];
  const hrefs = ["/depenses", "/frais", "/collectivites", "/financement", "/elus"];
  const entitesLignes = db
    .prepare(
      `SELECT id, type, nom, sigle FROM entites
       WHERE type IN ('ministere', 'institution', 'collectivite', 'parti')
       ORDER BY CASE type
                  WHEN 'institution' THEN 0
                  WHEN 'ministere' THEN 1
                  WHEN 'collectivite' THEN 2
                  ELSE 3
                END, nom`,
    )
    .all() as LigneEntite[];
  const entites: EntiteIndex[] = entitesLignes.map((e) => {
    let typeIdx = 1; // Institution
    let hrefIdx = 1; // /frais
    if (e.type === "ministere") {
      typeIdx = 0;
      hrefIdx = 0;
    } else if (e.type === "collectivite") {
      typeIdx = 2;
      hrefIdx = 2;
    } else if (e.type === "parti") {
      typeIdx = 3;
      hrefIdx = 3;
    } else if (e.id === "inst-assemblee-nationale" || e.id === "inst-senat") {
      hrefIdx = 4; // /elus
    }
    return [e.nom, e.sigle ?? "", typeIdx, hrefIdx];
  });

  return {
    typesMandat: [...LIBELLES_MANDAT],
    departements,
    elus,
    typesEntite,
    hrefs,
    entites,
  };
}
