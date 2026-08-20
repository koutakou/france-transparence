import {
  getOrganisationsFrance,
  type OrganisationUe,
} from "@/lib/queries/registre-ue";

/**
 * Fragment statique : liste COMPLÈTE des organisations à siège en France
 * inscrites au registre de transparence de l'Union européenne (source S40),
 * tri alphabétique — même requête et même tri que le bloc de /lobbying, qui
 * n'embarque que les premières lignes dans son HTML et charge ce fragment au
 * clic « Tout afficher ».
 *
 * POURQUOI un fragment et pas la table entière dans la page : /lobbying est
 * déjà la page la plus lourde du site. Rendre 1 638 lignes côté serveur y
 * ajouterait plusieurs centaines de kilo-octets, dupliqués dans le payload
 * RSC. Le HTML statique garde donc l'essentiel — compteurs, cadrage,
 * agrégats — et seule la liste nominative vit ici.
 *
 * L'URL est volontairement sous /data/registre-ue/ et non sous
 * /data/lobbying/ : le cloisonnement des deux registres vaut jusque dans
 * l'arborescence servie.
 *
 * `null` si la base n'est pas encore construite ou si la source n'est pas
 * ingérée — le composant client affiche alors un message honnête.
 */
export const dynamic = "force-static";

export type OrganisationsUeFragment = {
  organisations: OrganisationUe[];
};

export async function GET() {
  const organisations = getOrganisationsFrance();
  if (!organisations) return Response.json(null);
  const fragment: OrganisationsUeFragment = { organisations };
  return Response.json(fragment);
}
