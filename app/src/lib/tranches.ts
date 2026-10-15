import { nomTranche, trancheDeNom } from "@/lib/echeances";

/**
 * Route des tranches horaires d'échéances (fragments `<heure UTC>.json`).
 *
 * Fichier SENTINELLE quand la base est absente : en export, Next refuse une
 * route dynamique dont `generateStaticParams` rend un tableau vide (« at
 * least one route must be generated »), ce qui ferait échouer `next build`
 * sans base. Le soulignement initial n'est le nom d'aucune heure : la page,
 * qui n'a alors aucune échéance à compléter, ne le demande jamais.
 */
const SENTINELLE_SANS_BASE = "_sans-base.json";

export function fichiersTranches(baseOuverte: boolean, tranches: number[]): { fichier: string }[] {
  if (!baseOuverte) return [{ fichier: SENTINELLE_SANS_BASE }];
  return tranches.map((t) => ({ fichier: `${nomTranche(t)}.json` }));
}

export function reponseTranche<T>(
  fichier: string,
  contenu: (tranche: number) => T[] | null,
): Response {
  const nom = fichier.replace(/\.json$/, "");
  const tranche = trancheDeNom(nom);
  if (tranche === null) return Response.json(null);
  const lignes = contenu(tranche);
  return Response.json(lignes === null ? null : { tranche: nom, lignes });
}
