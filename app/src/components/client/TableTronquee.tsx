"use client";

import { useState } from "react";
import { DataTable, type Colonne, type ColonneType } from "@/components/ui/DataTable";
import { Money } from "@/components/ui/Money";
import { formatNombre } from "@/lib/format";

/**
 * Tableau volumineux au premier chargement honnête : seules les N premières
 * lignes sont RENDUES (dans le HTML statique comme à l'écran), le reste des
 * données voyage en props compactes (payload RSC) et s'affiche d'un clic
 * « Tout afficher » — aucun fetch, aucune perte, troncature ANNONCÉE.
 *
 * Pourquoi un composant client : rendu serveur, un tableau de 100 lignes
 * coûte deux fois son poids (HTML + arbre d'éléments dupliqué dans le
 * payload RSC). Ici l'arbre ne traverse pas la frontière — seules les
 * données brutes, bien plus compactes.
 *
 * Les colonnes sont un SPEC SÉRIALISABLE (pas de fonction de rendu : elles
 * ne traversent pas la frontière serveur→client) : les types de DataTable
 * plus « money » (montant compacté €, `—` si NULL avec explication).
 */

export type ColonneSpec = {
  cle: string;
  entete: string;
  /** Types DataTable + `money` (composant Money, NULL → « — » expliqué). */
  type?: ColonneType | "money";
  decimales?: number;
  largeur?: string;
  /** Pour `money` : title de la cellule « — » (ex. « Aucun montant connu »). */
  titreSiNull?: string;
};

export interface TableTronqueeProps {
  colonnes: ColonneSpec[];
  lignes: Record<string, unknown>[];
  /** Champ servant de clé React stable (ex. "code"). */
  cleChamp: string;
  /** Lignes rendues avant « Tout afficher » (défaut 20). */
  premierEcran?: number;
  /** Nom pluriel des lignes pour l'annonce honnête (ex. « départements »). */
  libellePluriel: string;
  /** Accord de « premiers/premières » (défaut : masculin). */
  feminin?: boolean;
  /** max-height CSS une fois tout affiché (en-tête sticky). */
  hauteurMax?: string;
  vide?: string;
}

function versColonne(spec: ColonneSpec): Colonne<Record<string, unknown>> {
  if (spec.type === "money") {
    return {
      cle: spec.cle,
      entete: spec.entete,
      type: "montant",
      largeur: spec.largeur,
      rendu: (l) => {
        const v = l[spec.cle];
        if (typeof v !== "number") {
          return spec.titreSiNull ? <span title={spec.titreSiNull}>—</span> : "—";
        }
        return <Money valeur={v} />;
      },
    };
  }
  return {
    cle: spec.cle,
    entete: spec.entete,
    type: spec.type,
    decimales: spec.decimales,
    largeur: spec.largeur,
  };
}

export function TableTronquee({
  colonnes,
  lignes,
  cleChamp,
  premierEcran = 20,
  libellePluriel,
  feminin = false,
  hauteurMax,
  vide,
}: TableTronqueeProps) {
  const [tout, setTout] = useState(false);
  const tronque = !tout && lignes.length > premierEcran;
  const affichees = tronque ? lignes.slice(0, premierEcran) : lignes;
  const specs = colonnes.map(versColonne);

  return (
    <div>
      <DataTable
        colonnes={specs}
        lignes={affichees}
        cleLigne={(l, i) => String(l[cleChamp] ?? i)}
        hauteurMax={tronque ? undefined : hauteurMax}
        vide={vide}
      />
      {tronque && (
        <p className="mt-2 flex flex-wrap items-center gap-3 text-xs text-ink-muted" aria-live="polite">
          <span>
            Affichage des {formatNombre(premierEcran)} {feminin ? "premières" : "premiers"}{" "}
            {libellePluriel} sur {formatNombre(lignes.length)} (même tri que le tableau complet).
          </span>
          <button
            type="button"
            onClick={() => setTout(true)}
            className="rounded-lg border border-card-border bg-raised px-2.5 py-1 text-ink transition-colors hover:bg-hover"
          >
            Tout afficher ({formatNombre(lignes.length)})
          </button>
        </p>
      )}
    </div>
  );
}
