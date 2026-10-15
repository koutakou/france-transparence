import { LienOfficiel, PuceOfficielle } from "@/components/ui/LienOfficiel";
import { urlAnnuaireEntreprise } from "@/lib/urlOfficielle";

/**
 * Nom = fiche HATVP ; puce Sirene seulement si SIREN 9 chiffres déjà en S18.
 * Partagé par /lobbying (rendu serveur) et ses îles client
 * (components/client/TablesLobbying.tsx) : aucun import serveur.
 */
export function NomHatvp({
  denomination,
  urlFiche,
  sirenPourAnnuaire,
}: {
  denomination: string;
  urlFiche: string | null;
  sirenPourAnnuaire: string | null;
}) {
  const hrefSirene = urlAnnuaireEntreprise(sirenPourAnnuaire);
  return (
    <span>
      {urlFiche ? (
        <LienOfficiel href={urlFiche} source="HATVP">
          {denomination}
        </LienOfficiel>
      ) : (
        denomination
      )}
      {hrefSirene ? (
        <PuceOfficielle href={hrefSirene} libelle="Sirene" nom={denomination} />
      ) : null}
    </span>
  );
}
