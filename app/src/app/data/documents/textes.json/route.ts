import { getTextesExport } from "@/lib/queries/documents";

/**
 * Fragment statique : TOUS les textes de la fenêtre des 30 derniers JO
 * (2 778 au 19/08/2026), format compact groupé par jour de parution.
 *
 * - `jours` : `[date_publi, lignes[]]` du plus récent au plus ancien ;
 *   chaque ligne `[texte_id, natureIdx, titre, ministereIdx, isNomination]`
 *   (natureIdx / ministereIdx = -1 quand absents — réel) ;
 * - le lien Légifrance n'est pas transporté : vérifié en base, il vaut
 *   toujours `prefixeLegifrance + texte_id` (2 778/2 778).
 */
export const dynamic = "force-static";

export type TexteCompact = [
  texteId: string,
  natureIdx: number,
  titre: string,
  ministereIdx: number,
  isNomination: 0 | 1,
];

export type TextesFragment = {
  prefixeLegifrance: string;
  natures: string[];
  ministeres: string[];
  jours: [date: string, textes: TexteCompact[]][];
};

const PREFIXE = "https://www.legifrance.gouv.fr/jorf/id/";

export async function GET() {
  const textes = getTextesExport();
  if (!textes) return Response.json(null);

  const natures: string[] = [];
  const natureIdx = new Map<string, number>();
  const ministeres: string[] = [];
  const ministereIdx = new Map<string, number>();
  const indexDe = (valeur: string | null, liste: string[], carte: Map<string, number>) => {
    if (!valeur) return -1;
    const connu = carte.get(valeur);
    if (connu !== undefined) return connu;
    const i = liste.length;
    liste.push(valeur);
    carte.set(valeur, i);
    return i;
  };

  const jours: TextesFragment["jours"] = [];
  for (const t of textes) {
    const ligne: TexteCompact = [
      t.texte_id,
      indexDe(t.nature, natures, natureIdx),
      t.titre,
      indexDe(t.ministere, ministeres, ministereIdx),
      t.is_nomination === 1 ? 1 : 0,
    ];
    const dernier = jours[jours.length - 1];
    if (dernier && dernier[0] === t.date_publi) {
      dernier[1].push(ligne);
    } else {
      jours.push([t.date_publi, [ligne]]);
    }
  }

  const fragment: TextesFragment = {
    prefixeLegifrance: PREFIXE,
    natures,
    ministeres,
    jours,
  };
  return Response.json(fragment);
}
