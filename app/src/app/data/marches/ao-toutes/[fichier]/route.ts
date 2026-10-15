import { AO_AFFICHEES, contenuTranche, tranchesAEcrire } from "@/lib/echeances";
import { fichiersTranches, reponseTranche } from "@/lib/tranches";
import { getAoOuvertesTriees } from "@/lib/queries/marches";

/**
 * Fragments statiques : une TRANCHE HORAIRE d'appels d'offres « toutes
 * familles » de /marches par fichier, `<heure UTC>.json` (lib/echeances.ts).
 * Le navigateur charge de lui-même celle de l'heure qu'il vit, dès qu'une
 * échéance du HTML est passée : elle ne porte que les lignes affichables
 * pendant cette heure (AO_AFFICHEES au plus par date limite distincte),
 * au lieu de la réserve entière de RESERVE_HEURES.
 */
export const dynamic = "force-static";
export const dynamicParams = false;

export function generateStaticParams(): { fichier: string }[] {
  return fichiersTranches(getAoOuvertesTriees() !== null, tranchesAEcrire(Date.now()));
}

export async function GET(
  _requete: Request,
  { params }: { params: Promise<{ fichier: string }> },
) {
  const { fichier } = await params;
  return reponseTranche(fichier, (tranche) => {
    const lignes = getAoOuvertesTriees();
    return lignes === null
      ? null
      : contenuTranche(lignes, (a) => a.date_limite_reponse, tranche, AO_AFFICHEES);
  });
}
