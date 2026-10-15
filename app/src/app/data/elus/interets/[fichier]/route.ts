import {
  getIdsElusApparies,
  getInteretsElu,
} from "@/lib/queries/declarations";

/**
 * Fragment statique PAR ÉLU APPARIÉ : le contenu COMPLET de ses déclarations
 * d'intérêts HATVP (même forme que `getInteretsElu`, autoportant — il ne
 * dépend d'aucun état de la page qui le charge).
 *
 * POURQUOI ce fragment existe : la fiche `/elus/[id]` n'inline plus que ce
 * que la troncature visuelle affiche réellement (8 lignes par rubrique,
 * première déclaration seule dépliée — cf. `tronquerInterets`). La queue,
 * qui pesait jusqu'à 93 % du payload déclarations sans jamais entrer dans le
 * DOM initial, vit ici et n'est téléchargée qu'au premier
 * « Tout afficher » / « Déplier ».
 *
 * Un fichier PLAT par élu, jamais paramétré à la requête : seuls les élus
 * qui ont au moins une déclaration rattachée (appariés) ont un fragment, et
 * la page ne propose le chargement que pour eux. L'URL finit en `.json`
 * (le segment dynamique EST `<id>.json`) : c'est ce qui la fait entrer dans
 * la location nginx des fragments (`^/(api|data)/.*\.json$`) et servir le
 * bon type MIME. Généré au build, reconstruit chaque jour avec le site.
 */
export const dynamic = "force-static";

/** Tout id hors de cette liste est un 404 franc, jamais un rendu à la volée. */
export const dynamicParams = false;

/**
 * Fichier SENTINELLE, émis seulement quand aucun élu n'est apparié (base
 * absente, ou pipeline P15 jamais passé). En export (`output: "export"`),
 * Next REFUSE une route dynamique dont `generateStaticParams` rend un tableau
 * vide : « at least one route must be generated » fait échouer le build
 * entier. Le commentaire promettait « aucun fragment, pas de crash » ; c'était
 * vrai en `next build` simple, faux pour l'export servi (constaté le
 * 15/10/2026 : build mort sur une base sans `hatvp_decl_interets`).
 *
 * Le soulignement initial ne peut pas être un identifiant de fiche (`PA…`,
 * `SEN-…`, `rne-…`) : aucune fiche ne le demande, et il ne contient que
 * `null` — la même réponse que `getInteretsElu` sans tables P15.
 */
const SENTINELLE_AUCUN_APPARIE = "_aucun-elu-apparie.json";

export function generateStaticParams(): { fichier: string }[] {
  // Base absente ou pipeline P15 jamais passé : aucun fragment réel, pas de
  // crash — exactement comme la fiche, qui n'affiche alors aucun bouton de
  // chargement. Seule la sentinelle ci-dessus est écrite.
  const ids = getIdsElusApparies();
  if (ids.length === 0) return [{ fichier: SENTINELLE_AUCUN_APPARIE }];
  return ids.map((id) => ({ fichier: `${id}.json` }));
}

export async function GET(
  _requete: Request,
  { params }: { params: Promise<{ fichier: string }> },
) {
  const { fichier } = await params;
  if (fichier === SENTINELLE_AUCUN_APPARIE) return Response.json(null);
  const id = fichier.replace(/\.json$/, "");
  return Response.json(getInteretsElu(id));
}
