"use client";

import { useState } from "react";
import { DataTable } from "@/components/ui/DataTable";
import { formatNombre } from "@/lib/format";
import { urlSite } from "@/lib/basePath";
import type { EntiteEnDefaut } from "@/lib/queries/lobbying";
import type { DefautsFragment } from "@/app/data/lobbying/defauts.json/route";

/**
 * Table des entités en défaut de déclaration (lobbying) — premier
 * chargement honnête : seules les 50 premières lignes (tri alphabétique)
 * sont dans le HTML statique, la liste complète (316 entités) est chargée
 * d'un clic « Tout afficher » depuis le fragment /data/lobbying/defauts.json.
 *
 * Pourquoi un composant client : rendue côté serveur, la table complète
 * pesait ~154 Ko de HTML, dupliqués dans le payload RSC — la cause
 * principale du dépassement de budget (< 500 Ko) de /lobbying.
 *
 * Honnêteté : troncature ANNONCÉE (« Affichage des 50 premières … sur
 * 316 »), même tri que la liste complète, re-fetch en opacité 0,5 sans
 * skeleton (DATAVIZ « Re-fetch : garder le cadre ») ; si le fragment est
 * indisponible, message explicite — les 50 premières restent lisibles et la
 * liste officielle complète reste accessible chez la HATVP (lien source du
 * bloc).
 */

/** Lien sortant vers une fiche HATVP (même rendu que le reste de la page). */
function LienFiche({ url }: { url: string | null }) {
  if (!url) return <>—</>;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
    >
      Fiche HATVP
    </a>
  );
}

let defautsPromesse: Promise<DefautsFragment | null> | null = null;

function chargerDefauts(): Promise<DefautsFragment | null> {
  defautsPromesse ??= fetch(urlSite("/data/lobbying/defauts.json"))
    .then((rep) => (rep.ok ? (rep.json() as Promise<DefautsFragment | null>) : null))
    .catch(() => null);
  return defautsPromesse;
}

export interface DefautsLobbyingProps {
  /** Premières lignes (tri alphabétique), rendues dans le HTML statique. */
  premieres: EntiteEnDefaut[];
  /** Nombre total d'entités en défaut (compté au build — jamais estimé). */
  total: number;
}

export function DefautsLobbying({ premieres, total }: DefautsLobbyingProps) {
  const [toutes, setToutes] = useState<EntiteEnDefaut[] | null>(null);
  const [chargement, setChargement] = useState(false);
  const [indisponible, setIndisponible] = useState(false);

  const affichees = toutes ?? premieres;
  const tronque = toutes === null && total > premieres.length;

  const toutAfficher = () => {
    setChargement(true);
    chargerDefauts().then((f) => {
      setChargement(false);
      if (f === null) setIndisponible(true);
      else setToutes(f.entites);
    });
  };

  return (
    <div>
      <div className={chargement ? "opacity-50 transition-opacity" : "transition-opacity"}>
        <DataTable<EntiteEnDefaut>
          colonnes={[
            { cle: "denomination", entete: "Entité en défaut de déclaration" },
            { cle: "categorie", entete: "Catégorie" },
            { cle: "ville", entete: "Ville" },
            {
              cle: "url_fiche",
              entete: "Registre",
              rendu: (l) => <LienFiche url={l.url_fiche} />,
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
            Affichage des {formatNombre(premieres.length)} premières entités sur{" "}
            {formatNombre(total)} (même tri alphabétique que la liste complète).
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
          {formatNombre(premieres.length)} premières entités (sur {formatNombre(total)})
          restent affichées ; la liste officielle complète est consultable sur le site de
          la HATVP (lien source de ce bloc).
        </p>
      )}
    </div>
  );
}
