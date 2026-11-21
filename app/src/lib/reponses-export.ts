/**
 * Réponses des routes statiques d'export (/api/*.csv, /api/*.provenance.txt,
 * /flux/*.xml), générées au build.
 *
 * Base absente au build : erreur franche, comme les routes JSON. On ne publie
 * JAMAIS un fichier vide (le build échoue, `ft-deploy` ne bascule pas : la
 * release précédente reste servie telle quelle).
 */
import { documentCsv, documentProvenance } from "@/lib/csv";
import type { DefinitionCsv } from "@/lib/exports-csv";
import type { MetaSource } from "@/lib/db";
import {
  dateAtom,
  documentAtom,
  idTag,
  plusRecente,
  type EntreeAtom,
  type FluxAtom,
  type DefinitionFlux,
} from "@/lib/flux";
import { natureSource } from "@/lib/nature-sources";
import { getMetaSourcesParIds } from "@/lib/queries/donnees";
import { SITE_URL } from "@/lib/site";

export function erreurBaseAbsente(): Error {
  return new Error(
    "Base absente au build : lancer make ingest (ou poser FRANCE_DB_PATH) avant next build.",
  );
}

export function reponseCsv<T>(def: DefinitionCsv<T>, lignes: T[] | null): Response {
  if (lignes === null) throw erreurBaseAbsente();
  return new Response(documentCsv(def.colonnes, lignes), {
    headers: { "Content-Type": "text/csv; charset=utf-8" },
  });
}

export function reponseProvenance<T>(def: DefinitionCsv<T>): Response {
  const sources = getMetaSourcesParIds(def.sources);
  if (sources === null) throw erreurBaseAbsente();
  if (sources.length !== def.sources.length) {
    // Une provenance qui tait une source n'est pas publiée : le build échoue.
    const trouvees = new Set(sources.map((s) => s.source_id));
    const manquantes = def.sources.filter((id) => !trouvees.has(id));
    throw new Error(
      `Provenance ${def.fichier} : source(s) absente(s) de meta_sources : ${manquantes.join(", ")}.`,
    );
  }
  const texte = documentProvenance({
    fichier: def.fichier,
    titre: def.titre,
    description: def.description,
    mentions: def.mentions,
    colonnes: def.colonnes.map(({ cle, description }) => ({ cle, description })),
    sources: sources.map((s) => ({
      source_id: s.source_id,
      nom: s.nom,
      url: s.url,
      licence: s.licence,
      date_donnees: s.date_donnees,
      date_ingestion: s.date_ingestion,
      nature: natureSource(s.source_id)?.etiquette ?? null,
    })),
    sansSource: def.sansSource,
    voirAussi: [`${SITE_URL}/api/${def.fichier}`, ...def.voirAussi.map((c) => `${SITE_URL}${c}`)],
  });
  return new Response(texte, { headers: { "Content-Type": "text/plain; charset=utf-8" } });
}

/**
 * Un flux Atom complet. `sources` : lignes `meta_sources` dont viennent les
 * entrées (leur licence va dans `<rights>`, leur date des données la plus
 * récente date le flux s'il n'a aucune entrée). `null` = base absente.
 */
export function reponseFlux(
  flux: DefinitionFlux,
  entrees: EntreeAtom[],
  sources: Pick<MetaSource, "nom" | "licence" | "date_donnees">[] | null,
  droits?: string,
): Response {
  if (sources === null) throw erreurBaseAbsente();
  const majSansEntree = plusRecente(
    sources.map((s) => dateAtom(s.date_donnees)).filter((d): d is string => d !== null),
  );
  if (majSansEntree === null) {
    throw new Error(`Flux ${flux.chemin} : aucune date des données lisible dans meta_sources.`);
  }
  const atom: FluxAtom = {
    id: idTag("flux", flux.chemin.replace(/^\/flux\//, "")),
    titre: flux.titre,
    sousTitre: flux.description,
    lienSelf: `${SITE_URL}${flux.chemin}`,
    lienPage: `${SITE_URL}${flux.page}`,
    auteur: "France Transparence",
    droits:
      droits ??
      `Titres et liens repris tels quels de : ${sources.map((s) => `${s.nom} (${s.licence})`).join(", ")}.`,
    entrees,
    majSansEntree,
  };
  return new Response(documentAtom(atom), {
    headers: { "Content-Type": "application/atom+xml; charset=utf-8" },
  });
}
