"use client";

import { useState } from "react";
import { DataTable } from "@/components/ui/DataTable";
import { LienOfficiel } from "@/components/ui/LienOfficiel";
import { formatNombre } from "@/lib/format";
import { urlSite } from "@/lib/basePath";
import type { OrganisationUe } from "@/lib/queries/registre-ue";
import type { OrganisationsUeFragment } from "@/app/data/registre-ue/organisations.json/route";

/**
 * Fiche publique d'une organisation sur le site du registre de l'Union.
 *
 * Définie ICI et pas dans `@/lib/queries/registre-ue` bien que ce soit son
 * voisin naturel : ce module-là importe `better-sqlite3`, qu'un composant
 * client ne peut pas embarquer. Seuls les `import type` en sont sûrs, car ils
 * disparaissent à la compilation. L'URL est dérivée de l'identifiant plutôt
 * que stockée en base — 1 638 fois le même préfixe de 70 octets, c'est
 * 115 Ko de base pour zéro information.
 */
export function urlFicheRegistreUe(id: string): string {
  return (
    "https://transparency-register.europa.eu/search-register-or-update/" +
    `organisation-detail_en?organisationNumber=${encodeURIComponent(id)}`
  );
}

/**
 * Table des organisations à siège en France inscrites au registre de
 * transparence de l'Union européenne (source S40).
 *
 * Même motif que la table des défauts de déclaration HATVP : seules les
 * premières lignes (tri alphabétique) sont dans le HTML statique, la liste
 * complète est chargée d'un clic depuis /data/registre-ue/organisations.json.
 * /lobbying est la page la plus lourde du site ; y rendre 1 638 lignes côté
 * serveur coûterait plusieurs centaines de kilo-octets.
 *
 * Sans JavaScript, l'aperçu et TOUS les compteurs du bloc restent lisibles :
 * seule la liste nominative complète demande un clic, et le lien vers le
 * registre officiel reste disponible dans le bandeau de source du bloc.
 *
 * Honnêteté : troncature ANNONCÉE, même tri que la liste complète, re-fetch
 * en opacité réduite sans squelette ; si le fragment est indisponible, le
 * message le dit et l'aperçu reste affiché.
 */

let organisationsPromesse: Promise<OrganisationsUeFragment | null> | null = null;

function chargerOrganisations(): Promise<OrganisationsUeFragment | null> {
  organisationsPromesse ??= fetch(urlSite("/data/registre-ue/organisations.json"))
    .then((rep) =>
      rep.ok ? (rep.json() as Promise<OrganisationsUeFragment | null>) : null,
    )
    .catch(() => null);
  return organisationsPromesse;
}

export interface OrganisationsRegistreUeProps {
  /** Premières lignes (tri alphabétique), rendues dans le HTML statique. */
  premieres: OrganisationUe[];
  /** Nombre total d'organisations listables (compté au build, jamais estimé). */
  total: number;
}

export function OrganisationsRegistreUe({
  premieres,
  total,
}: OrganisationsRegistreUeProps) {
  const [toutes, setToutes] = useState<OrganisationUe[] | null>(null);
  const [chargement, setChargement] = useState(false);
  const [indisponible, setIndisponible] = useState(false);

  const affichees = toutes ?? premieres;
  const tronque = toutes === null && total > premieres.length;

  const toutAfficher = () => {
    setChargement(true);
    chargerOrganisations().then((fragment) => {
      setChargement(false);
      if (fragment === null) setIndisponible(true);
      else setToutes(fragment.organisations);
    });
  };

  return (
    <div>
      <div
        className={chargement ? "opacity-50 transition-opacity" : "transition-opacity"}
      >
        <DataTable<OrganisationUe>
          colonnes={[
            {
              cle: "nom",
              entete: "Organisation (raison sociale déclarée)",
              rendu: (l) => (
                <LienOfficiel href={urlFicheRegistreUe(l.id)} source="registre de l'Union">
                  {l.nom}
                </LienOfficiel>
              ),
            },
            { cle: "acronyme", entete: "Sigle", largeur: "7rem" },
            { cle: "categorie", entete: "Catégorie d'inscription (libellé natif)" },
            {
              cle: "cout_libelle",
              entete: "Coûts annuels déclarés (fourchette)",
              largeur: "12rem",
            },
          ]}
          lignes={affichees}
          cleLigne={(l) => l.id}
          hauteurMax="24rem"
        />
      </div>
      {tronque && !indisponible && (
        <p
          className="mt-2 flex flex-wrap items-center gap-3 text-xs text-ink-muted"
          aria-live="polite"
        >
          <span>
            Affichage des {formatNombre(premieres.length)} premières
            organisations sur {formatNombre(total)} (même tri alphabétique que
            la liste complète).
          </span>
          <button
            type="button"
            onClick={toutAfficher}
            disabled={chargement}
            className="inline-flex min-h-11 items-center rounded-lg border border-card-border bg-raised px-3 text-ink transition-colors hover:bg-hover disabled:cursor-wait"
          >
            {chargement ? "Chargement…" : `Tout afficher (${formatNombre(total)})`}
          </button>
        </p>
      )}
      {indisponible && (
        <p className="mt-2 text-xs text-ink-muted" role="status">
          Liste complète indisponible pour le moment — les{" "}
          {formatNombre(premieres.length)} premières organisations (sur{" "}
          {formatNombre(total)}) restent affichées ; le registre officiel est
          consultable en ligne (lien source de ce bloc).
        </p>
      )}
    </div>
  );
}
