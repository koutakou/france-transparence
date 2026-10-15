import { AO_ACCUEIL_AFFICHEES, contenuTranche, tranchesAEcrire } from "@/lib/echeances";
import { fichiersTranches, reponseTranche } from "@/lib/tranches";
import { getAoClotureTriees } from "@/lib/queries/accueil";

/**
 * Fragments statiques : une TRANCHE HORAIRE d'appels d'offres « proches de
 * la clôture » de l'accueil par fichier, `<heure UTC>.json`
 * (lib/echeances.ts). L'accueil n'en affiche que AO_ACCUEIL_AFFICHEES ; dès
 * que l'une de celles de son HTML est passée à l'heure du visiteur, il
 * charge la tranche de cette heure, qui ne porte que les lignes affichables
 * pendant l'heure, et non plus la réserve entière de RESERVE_HEURES.
 */
export const dynamic = "force-static";
export const dynamicParams = false;

export function generateStaticParams(): { fichier: string }[] {
  return fichiersTranches(getAoClotureTriees() !== null, tranchesAEcrire(Date.now()));
}

export async function GET(
  _requete: Request,
  { params }: { params: Promise<{ fichier: string }> },
) {
  const { fichier } = await params;
  return reponseTranche(fichier, (tranche) => {
    const lignes = getAoClotureTriees();
    return lignes === null
      ? null
      : contenuTranche(lignes, (a) => a.dateLimite, tranche, AO_ACCUEIL_AFFICHEES);
  });
}
