import { getAlertesExport } from "@/lib/queries/alertes";

/**
 * Fragment statique : les 1 590 alertes, format compact (la règle et la
 * base légale — identiques pour toutes les alertes d'un même type, vérifié
 * en base — sont dédupliquées dans `types` ; les URL sources dans `urls`).
 *
 * `alertes` : lignes `[typeIdx, graviteIdx, titre, detail, urlIdx]` dans
 * l'ORDRE canonique de la liste (gravité haute → info, date décroissante,
 * id) — le client filtre/pagine sans jamais retrier.
 */
export const dynamic = "force-static";

export type AlerteCompacte = [
  typeIdx: number,
  graviteIdx: number,
  titre: string,
  detail: string | null,
  urlIdx: number,
];

export type AlertesFragment = {
  types: { code: string; nb: number; regle: string | null; base_legale: string | null }[];
  gravites: string[];
  urls: string[];
  alertes: AlerteCompacte[];
};

export async function GET() {
  const exporte = getAlertesExport();
  if (!exporte) return Response.json(null);

  const gravites = ["haute", "moyenne", "info"];
  const typeIdx = new Map(exporte.types.map((t, i) => [t.type, i]));
  const urls: string[] = [];
  const urlIdx = new Map<string, number>();

  const alertes: AlerteCompacte[] = exporte.alertes.map((a) => {
    let iUrl = -1;
    if (a.source_url) {
      const connu = urlIdx.get(a.source_url);
      if (connu === undefined) {
        iUrl = urls.length;
        urls.push(a.source_url);
        urlIdx.set(a.source_url, iUrl);
      } else {
        iUrl = connu;
      }
    }
    return [
      typeIdx.get(a.type) ?? -1,
      Math.max(gravites.indexOf(a.gravite), 0),
      a.titre,
      a.detail,
      iUrl,
    ];
  });

  const fragment: AlertesFragment = {
    types: exporte.types.map((t) => ({
      code: t.type,
      nb: t.nb,
      regle: t.regle,
      base_legale: t.base_legale,
    })),
    gravites,
    urls,
    alertes,
  };
  return Response.json(fragment);
}
