"use client";

import { DataTable } from "@/components/ui/DataTable";
import { NomHatvp } from "@/components/ui/NomHatvp";

/**
 * Tableaux de /lobbying rendus en ÎLES CLIENT (budget de 500 Ko de HTML).
 * Rendu serveur, un tableau pèse deux fois : son HTML, et le même arbre
 * d'éléments sérialisé dans le payload RSC. Ici le HTML statique est le même
 * (lisible sans JavaScript) et seules les lignes traversent la frontière —
 * réduites par la page aux champs affichés, rien de plus. Colonnes reprises
 * telles quelles de la page.
 */

export type LigneDefautTitulaire = {
  siren: string;
  denomination: string;
  categorie: string | null;
  url_fiche: string | null;
  dans_sirene: number;
  nb_marches_tous: number;
  montant_tous_meur: number | null;
  nb_marches_hors_ac: number;
  montant_hors_ac_meur: number | null;
};

/** Entité du top 20 (12 mois) : champs affichés seulement. */
export type LigneTopEntite = {
  rang: number;
  denomination: string;
  categorie: string | null;
  nb_activites_12m: number;
  url_fiche: string | null;
  /** SIREN pour la puce Sirene, seulement s'il figure dans S18. */
  siren_annuaire: string | null;
};

export function TableDefautsTitulaires({ lignes }: { lignes: LigneDefautTitulaire[] }) {
  return (
    <DataTable<LigneDefautTitulaire>
      colonnes={[
        {
          cle: "denomination",
          entete: "Entité en défaut de déclaration",
          rendu: (l) => (
            <NomHatvp
              denomination={l.denomination}
              urlFiche={l.url_fiche}
              sirenPourAnnuaire={l.dans_sirene === 1 ? l.siren : null}
            />
          ),
        },
        { cle: "categorie", entete: "Catégorie (libellé natif HATVP)" },
        {
          cle: "nb_marches_tous",
          entete: "Marchés (tous)",
          type: "nombre",
          largeur: "6rem",
        },
        {
          cle: "montant_tous_meur",
          entete: "Montant (M€, tous)",
          type: "montant",
          decimales: 1,
          largeur: "7rem",
        },
        {
          cle: "nb_marches_hors_ac",
          entete: "Marchés (hors AC)",
          type: "nombre",
          largeur: "6rem",
        },
        {
          cle: "montant_hors_ac_meur",
          entete: "Montant (M€, hors AC)",
          type: "montant",
          decimales: 1,
          largeur: "7rem",
        },
      ]}
      lignes={lignes}
      cleLigne={(l) => l.siren}
      vide="Aucun représentant d'intérêts en défaut de déclaration n'est titulaire d'un marché public dans les DECP."
      hauteurMax="24rem"
    />
  );
}

export function TableTopEntites({ lignes }: { lignes: LigneTopEntite[] }) {
  return (
    <DataTable<LigneTopEntite>
      colonnes={[
        { cle: "rang", entete: "Rang", type: "nombre", largeur: "3.5rem" },
        {
          cle: "denomination",
          entete: "Entité",
          rendu: (l) => (
            <NomHatvp
              denomination={l.denomination}
              urlFiche={l.url_fiche}
              sirenPourAnnuaire={l.siren_annuaire}
            />
          ),
        },
        { cle: "categorie", entete: "Catégorie" },
        { cle: "nb_activites_12m", entete: "Activités (12 mois)", type: "nombre" },
      ]}
      lignes={lignes}
      cleLigne={(l) => String(l.rang)}
    />
  );
}
