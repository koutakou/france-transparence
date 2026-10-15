import { getDb } from "@/lib/db";
import { getIdsFichesStatiques } from "@/lib/queries/elus";
import { comparerNomPrenom } from "@/lib/tri";

/**
 * Annuaire des fiches /elus/<id> : un lien HTML vers CHACUNE, pour qu'aucune
 * fiche ne soit atteignable par le seul sitemap ou la seule recherche
 * JavaScript (les tableaux de /elus ne portent que leur premier écran).
 *
 * L'ensemble des fiches reste celui de getIdsFichesStatiques(), SEULE
 * VÉRITÉ (generateStaticParams, sitemap, index de recherche, et ici) : on
 * ne liste que des identifiants qu'elle rend, et chacun d'eux est listé au
 * moins une fois — une fiche qu'aucun type ne rattacherait irait dans
 * « Autres fiches », jamais nulle part.
 */
export type FicheAnnuaire = { id: string; nom: string; prenom: string | null };

export type SectionAnnuaire = { titre: string; fiches: FicheAnnuaire[] };

const SECTIONS: { type: string; titre: string }[] = [
  { type: "depute", titre: "Député·es" },
  { type: "senateur", titre: "Sénateur·rices" },
  { type: "president_conseil_regional", titre: "Président·es de conseil régional" },
  { type: "president_conseil_departemental", titre: "Président·es de conseil départemental" },
];

export function getAnnuaireFiches(): SectionAnnuaire[] | null {
  const db = getDb();
  if (!db) return null;
  const ids = new Set(getIdsFichesStatiques());
  const lignes = db
    .prepare(
      `SELECT e.id, e.nom, e.prenom, json_extract(je.value, '$.type') AS type
         FROM elus e, json_each(e.mandats) je
        WHERE json_extract(je.value, '$.type') IN
              ('depute', 'president_conseil_departemental', 'president_conseil_regional')
       UNION
       SELECT e.id, e.nom, e.prenom, 'senateur' AS type
         FROM senateurs s JOIN elus e ON e.matricule_senat = s.matricule`,
    )
    .all() as (FicheAnnuaire & { type: string })[];

  const parType = new Map<string, Map<string, FicheAnnuaire>>();
  const listes = new Set<string>();
  for (const l of lignes) {
    if (!ids.has(l.id)) continue;
    const section = parType.get(l.type) ?? parType.set(l.type, new Map()).get(l.type)!;
    section.set(l.id, { id: l.id, nom: l.nom, prenom: l.prenom });
    listes.add(l.id);
  }
  const sections: SectionAnnuaire[] = SECTIONS.map(({ type, titre }) => ({
    titre,
    fiches: [...(parType.get(type)?.values() ?? [])].sort(comparerNomPrenom),
  })).filter((s) => s.fiches.length > 0);

  const orphelins = [...ids].filter((id) => !listes.has(id));
  if (orphelins.length > 0) {
    const noms = db
      .prepare(
        `SELECT id, nom, prenom FROM elus WHERE id IN (${orphelins.map(() => "?").join(", ")})`,
      )
      .all(...orphelins) as FicheAnnuaire[];
    sections.push({ titre: "Autres fiches", fiches: noms.sort(comparerNomPrenom) });
  }
  return sections;
}
