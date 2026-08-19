import type { NextRequest } from "next/server";
import {
  rechercheElus,
  rechercheEntites,
  type EluRecherche,
  type EntiteRecherche,
  type MandatJson,
} from "@/lib/queries/elus";

/**
 * Recherche globale (contrat SearchBox) :
 * `GET /api/recherche?q=…` → `{ resultats: [{ type, libelle, sous_libelle?, href }] }`
 *
 * - `q` < 2 caractères → `resultats` vides ;
 * - élus par nom/prénom (LIKE insensible à la casse, motif échappé, 8 max) ;
 * - entités par nom/sigle (4 max) vers le module pertinent ;
 * - base absente → `resultats` vides (la SearchBox reste silencieuse) ;
 * - SQL paramétré dans `@/lib/queries/elus` — jamais d'interpolation.
 */
export const dynamic = "force-dynamic";

type Resultat = {
  type: string;
  libelle: string;
  sous_libelle?: string;
  href: string;
};

/** Ordre de préférence du mandat affiché pour un élu local. */
const PRIORITE_MANDATS = [
  "depute",
  "senateur",
  "president_conseil_regional",
  "president_conseil_departemental",
  "president_epci",
  "maire",
] as const;

const LIBELLES_MANDAT: Record<string, string> = {
  depute: "Député·e",
  senateur: "Sénateur·rice",
  maire: "Maire",
  president_epci: "Président·e d’EPCI",
  president_conseil_departemental: "Président·e de conseil départemental",
  president_conseil_regional: "Président·e de conseil régional",
};

function lieuMandat(m: MandatJson): string | null {
  if (m.commune) return m.departement ? `${m.commune} (${m.departement})` : m.commune;
  if (m.epci) return m.departement ? `${m.epci} (${m.departement})` : m.epci;
  if (m.libelle) return m.libelle;
  if (m.region) return m.region;
  return m.departement ?? null;
}

/** Sous-libellé « mandat + département » d'un élu (jamais rien d'inventé). */
function sousLibelleElu(e: EluRecherche): string | undefined {
  if (e.uid_an) return e.dep_an ? `Député·e · ${e.dep_an}` : "Député·e";
  if (e.matricule_senat) {
    return e.dep_senat ? `Sénateur·rice · ${e.dep_senat}` : "Sénateur·rice";
  }
  if (!e.mandats) return undefined;
  let mandats: MandatJson[] = [];
  try {
    const brut: unknown = JSON.parse(e.mandats);
    if (Array.isArray(brut)) mandats = brut as MandatJson[];
  } catch {
    return undefined;
  }
  let choisi: MandatJson | undefined;
  for (const type of PRIORITE_MANDATS) {
    choisi = mandats.find((m) => m.type === type);
    if (choisi) break;
  }
  choisi = choisi ?? mandats[0];
  if (!choisi) return undefined;
  const libelle =
    LIBELLES_MANDAT[choisi.type ?? ""] ?? choisi.fonction ?? choisi.type ?? undefined;
  if (!libelle) return undefined;
  // Mandat « député/sénateur » connu du seul RNE (trimestriel) : le dire.
  const suffixeRne =
    choisi.type === "depute" || choisi.type === "senateur" ? " (RNE, trimestriel)" : "";
  const lieu = lieuMandat(choisi);
  return lieu ? `${libelle}${suffixeRne} · ${lieu}` : `${libelle}${suffixeRne}`;
}

function versResultatElu(e: EluRecherche): Resultat {
  return {
    type: "Élu·e",
    libelle: `${e.prenom ?? ""} ${e.nom}`.trim(),
    sous_libelle: sousLibelleElu(e),
    href: `/elus/${encodeURIComponent(e.id)}`,
  };
}

/** Module pertinent par type d'entité (l'AN et le Sénat pointent vers /elus). */
function versResultatEntite(e: EntiteRecherche): Resultat {
  let type = "Institution";
  let href = "/frais";
  if (e.type === "ministere") {
    type = "Ministère";
    href = "/depenses";
  } else if (e.type === "collectivite") {
    type = "Collectivité";
    href = "/collectivites";
  } else if (e.type === "parti") {
    type = "Parti";
    href = "/financement";
  } else if (e.id === "inst-assemblee-nationale" || e.id === "inst-senat") {
    href = "/elus";
  }
  return {
    type,
    libelle: e.nom,
    sous_libelle: e.sigle ?? undefined,
    href,
  };
}

export async function GET(request: NextRequest) {
  const q = (request.nextUrl.searchParams.get("q") ?? "").trim();
  if (q.length < 2) {
    return Response.json({ resultats: [] as Resultat[] });
  }
  const elus = rechercheElus(q, 8) ?? [];
  const entites = rechercheEntites(q, 4) ?? [];
  const resultats: Resultat[] = [
    ...elus.map(versResultatElu),
    ...entites.map(versResultatEntite),
  ];
  return Response.json({ resultats });
}
