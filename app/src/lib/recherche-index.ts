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
 * CONTRAT FICHES (docs/deploiement/DECISION.md) : seuls les élus portant un
 * mandat `depute`, `senateur`, `president_conseil_departemental` ou
 * `president_conseil_regional` ont une fiche statique /elus/<id> (1 053
 * fiches). L'`id` n'est transporté QUE pour eux ; les autres résultats
 * renvoient vers la liste /elus — jamais vers une fiche 404.
 *
 * Format compact (vise ≤ 1,5 Mo brut) : tableaux positionnels, libellés de
 * mandat et départements dédupliqués par index.
 */
import fs from "node:fs";
import { getDb } from "@/lib/db";
import type { MandatJson } from "@/lib/queries/elus";
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

/** Types de mandat ouvrant droit à une fiche statique (contrat DECISION.md). */
export const TYPES_MANDAT_FICHE = [
  "depute",
  "senateur",
  "president_conseil_departemental",
  "president_conseil_regional",
] as const;

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
 * (l'élu n'est plus dans les flux quotidiens AN/Sénat), comme le faisait
 * l'ancienne API.
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
              d.departement AS dep_an, s.circonscription AS dep_senat
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
    for (const type of PRIORITE_MANDATS) {
      principal = mandats.find((m) => m.type === type);
      if (principal) break;
    }
    principal = principal ?? mandats[0];

    // Fiche statique : au moins un mandat des 4 types du contrat.
    const aFiche = mandats.some((m) =>
      (TYPES_MANDAT_FICHE as readonly string[]).includes(m.type ?? ""),
    );

    // Libellé + département selon le mandat principal.
    let typeIdx = 6; // « Élu·e »
    let dep: string | null = null;
    const depDuMandat = (m: MandatJson | undefined): string | null => {
      if (!m) return null;
      if (m.departement) return nomsDep.get(m.departement) ?? m.libelle ?? m.departement;
      return m.libelle ?? m.region ?? null;
    };
    switch (principal?.type) {
      case "depute":
        typeIdx = e.uid_an ? 0 : 7;
        dep = e.dep_an ?? depDuMandat(principal);
        break;
      case "senateur":
        typeIdx = e.matricule_senat ? 1 : 8;
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
        // uid_an / matricule sans mandat JSON exploitable (défensif).
        if (e.uid_an) {
          typeIdx = 0;
          dep = e.dep_an;
        } else if (e.matricule_senat) {
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
