"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { DataTable, type Colonne } from "@/components/ui/DataTable";
import { formatNombre } from "@/lib/format";
import { urlSite } from "@/lib/basePath";
import { majParamsUrl } from "@/lib/urlEtat";
import { useUrlInitiale } from "@/lib/useUrlInitiale";
import type { DeputeLigne, SenateurLigne } from "@/lib/queries/elus";

/**
 * Tableau des députés OU des sénateurs — filtres et « tout afficher »
 * côté client (le site est statique : plus de searchParams serveur).
 *
 * - Le serveur n'embarque que les N premières lignes (ordre alphabétique) ;
 *   la troncature est ANNONCÉE à l'écran, jamais un total qui ment.
 * - Au premier geste (filtre ou « tout afficher »), la liste complète est
 *   chargée depuis un fragment statique /data/elus/*.json (une requête,
 *   mémoïsée), puis tout se passe en local.
 * - Les URL historiques `?gd=…&dd=…` / `?gs=…&ds=…` sont restaurées au
 *   montage et réécrites à chaque filtre (vue partageable).
 * - Chaque ligne garde son lien de fiche : tous les députés et sénateurs
 *   ont une fiche statique (contrat DECISION.md).
 */

export type VarianteParlement = "deputes" | "senateurs";

type LigneParlement = DeputeLigne | SenateurLigne;

export interface TableParlementairesProps {
  variante: VarianteParlement;
  /** Premier écran, rendu dans le HTML statique (ordre alphabétique). */
  initiaux: LigneParlement[];
  /** Effectif complet (le fragment en contient exactement autant). */
  total: number;
  /** Options du filtre groupe (valeur exacte + libellé affiché). */
  groupes: { valeur: string; libelle: string }[];
  /** Options du filtre département (valeurs exactes). */
  departements: string[];
}

const STYLE_SELECT =
  "rounded-lg border border-card-border bg-page px-3 py-1.5 text-[13px] text-ink focus:border-raised-border";
const STYLE_BOUTON =
  "rounded-lg border border-card-border bg-raised px-3 py-1.5 text-[13px] text-ink transition-colors hover:bg-hover";

/** Lien vers une fiche élu (id = `elus.id`). */
function LienFiche({ id, texte }: { id: string; texte: string }) {
  return (
    <Link
      href={`/elus/${encodeURIComponent(id)}`}
      className="text-ink underline decoration-dotted underline-offset-2 transition-colors hover:text-accent"
    >
      {texte}
    </Link>
  );
}

const CONFIG = {
  deputes: {
    fragment: "/data/elus/deputes.json",
    paramGroupe: "gd",
    paramDepartement: "dd",
    singulier: "député·e",
    pluriel: "député·es",
    vide: "Aucun député pour ces filtres",
  },
  senateurs: {
    fragment: "/data/elus/senateurs.json",
    paramGroupe: "gs",
    paramDepartement: "ds",
    singulier: "sénateur·rice",
    pluriel: "sénateur·rices",
    vide: "Aucun sénateur pour ces filtres",
  },
} as const;

const COLONNES_DEPUTES: Colonne<DeputeLigne>[] = [
  {
    cle: "nom",
    entete: "Député·e",
    rendu: (l) => <LienFiche id={l.elu_id} texte={`${l.prenom ?? ""} ${l.nom}`.trim()} />,
  },
  {
    cle: "groupe_sigle",
    entete: "Groupe",
    rendu: (l) =>
      l.groupe_sigle ? <span title={l.groupe_nom ?? undefined}>{l.groupe_sigle}</span> : "—",
  },
  { cle: "departement", entete: "Département" },
  {
    cle: "taux_participation_12m",
    entete: "Participation 12 mois ¹",
    type: "pourcent",
    decimales: 1,
  },
  {
    cle: "datan_score_participation",
    entete: "Score Datan (0–1) ²",
    type: "nombre",
    decimales: 2,
  },
];

const COLONNES_SENATEURS: Colonne<SenateurLigne>[] = [
  {
    cle: "nom",
    entete: "Sénateur·rice",
    rendu: (l) => <LienFiche id={l.elu_id} texte={`${l.prenom ?? ""} ${l.nom}`.trim()} />,
  },
  {
    cle: "groupe",
    entete: "Groupe",
    rendu: (l) =>
      l.groupe ? <span title={l.groupe_appartenance || undefined}>{l.groupe}</span> : "—",
  },
  { cle: "circonscription", entete: "Département" },
  {
    cle: "commission",
    entete: "Commission",
    rendu: (l) =>
      l.commission ? (
        <span className="block max-w-[18rem] truncate" title={l.commission}>
          {l.commission}
        </span>
      ) : (
        "—"
      ),
  },
];

/** Cache module : une seule requête de fragment par variante et par session. */
const fragments: Partial<Record<VarianteParlement, Promise<LigneParlement[] | null>>> = {};

function chargerFragment(variante: VarianteParlement): Promise<LigneParlement[] | null> {
  fragments[variante] ??= fetch(urlSite(CONFIG[variante].fragment))
    .then((rep) => (rep.ok ? (rep.json() as Promise<LigneParlement[] | null>) : null))
    .catch(() => null);
  return fragments[variante];
}

function champGroupe(variante: VarianteParlement, l: LigneParlement): string | null {
  return variante === "deputes" ? (l as DeputeLigne).groupe_sigle : (l as SenateurLigne).groupe;
}

function champDepartement(variante: VarianteParlement, l: LigneParlement): string | null {
  return variante === "deputes"
    ? (l as DeputeLigne).departement
    : (l as SenateurLigne).circonscription;
}

export function TableParlementaires({
  variante,
  initiaux,
  total,
  groupes,
  departements,
}: TableParlementairesProps) {
  const cfg = CONFIG[variante];
  // Filtres : état initial restauré d'une URL partagée (?gd=…&dd=… /
  // ?gs=…&ds=…, validée contre les listes réelles) ; toute action
  // utilisateur le surcharge définitivement.
  const urlInitiale = new URLSearchParams(useUrlInitiale());
  const [surcharge, setSurcharge] = useState<{ groupe?: string; departement?: string }>({});
  const [toutAfficher, setToutAfficher] = useState(false);
  const [complets, setComplets] = useState<LigneParlement[] | null>(null);
  const [indisponible, setIndisponible] = useState(false);

  const gUrl = urlInitiale.get(cfg.paramGroupe) ?? "";
  const dUrl = urlInitiale.get(cfg.paramDepartement) ?? "";
  const groupe = surcharge.groupe ?? (groupes.some((o) => o.valeur === gUrl) ? gUrl : "");
  const departement = surcharge.departement ?? (departements.includes(dUrl) ? dUrl : "");

  const besoinComplets = toutAfficher || groupe !== "" || departement !== "";
  const chargement = besoinComplets && complets === null && !indisponible;

  // Chargement du fragment au premier geste qui le requiert.
  useEffect(() => {
    if (!besoinComplets || complets !== null) return;
    let monte = true;
    chargerFragment(variante).then((lignes) => {
      if (!monte) return;
      if (lignes === null) setIndisponible(true);
      else setComplets(lignes);
    });
    return () => {
      monte = false;
    };
  }, [besoinComplets, complets, variante]);

  const surGroupe = (valeur: string) => {
    setSurcharge((s) => ({ ...s, groupe: valeur }));
    majParamsUrl({ [cfg.paramGroupe]: valeur || null });
  };
  const surDepartement = (valeur: string) => {
    setSurcharge((s) => ({ ...s, departement: valeur }));
    majParamsUrl({ [cfg.paramDepartement]: valeur || null });
  };
  const reinitialiser = () => {
    setSurcharge({ groupe: "", departement: "" });
    majParamsUrl({ [cfg.paramGroupe]: null, [cfg.paramDepartement]: null });
  };

  const source = besoinComplets && complets !== null ? complets : initiaux;
  const lignes = source.filter(
    (l) =>
      (groupe === "" || champGroupe(variante, l) === groupe) &&
      (departement === "" || champDepartement(variante, l) === departement),
  );
  const tronque = !besoinComplets && initiaux.length < total;
  const filtreActif = groupe !== "" || departement !== "";

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-[11px] uppercase tracking-[0.04em] text-ink-muted">
          Groupe
          <select
            value={groupe}
            onChange={(e) => surGroupe(e.target.value)}
            className={STYLE_SELECT}
          >
            <option value="">Tous les groupes</option>
            {groupes.map((g) => (
              <option key={g.valeur} value={g.valeur}>
                {g.libelle}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[11px] uppercase tracking-[0.04em] text-ink-muted">
          Département
          <select
            value={departement}
            onChange={(e) => surDepartement(e.target.value)}
            className={STYLE_SELECT}
          >
            <option value="">Tous les départements</option>
            {departements.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        {tronque && (
          <button type="button" onClick={() => setToutAfficher(true)} className={STYLE_BOUTON}>
            Tout afficher ({formatNombre(total)})
          </button>
        )}
        {filtreActif && (
          <button
            type="button"
            onClick={reinitialiser}
            className="text-xs text-ink-muted underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
          >
            Réinitialiser
          </button>
        )}
      </div>

      <p className="mb-2 text-xs text-ink-muted" aria-live="polite">
        {tronque ? (
          <>
            Affichage des {formatNombre(initiaux.length)} premiers {cfg.pluriel} sur{" "}
            {formatNombre(total)} (ordre alphabétique) — filtrer ou tout afficher pour la liste
            complète.
          </>
        ) : (
          <>
            {formatNombre(lignes.length)} {lignes.length > 1 ? cfg.pluriel : cfg.singulier} affiché
            ·e{lignes.length > 1 ? "s" : ""}
            {groupe ? ` · groupe ${groupe}` : ""}
            {departement ? ` · ${departement}` : ""}
            {chargement ? " · chargement de la liste complète…" : ""}
          </>
        )}
      </p>

      {indisponible && (
        <p className="mb-2 text-xs text-ink-muted">
          Liste complète indisponible (fragment {cfg.fragment} non chargé) — les{" "}
          {formatNombre(initiaux.length)} premières lignes restent affichées.
        </p>
      )}

      <div className={chargement ? "opacity-50 transition-opacity" : "transition-opacity"}>
        {variante === "deputes" ? (
          <DataTable
            colonnes={COLONNES_DEPUTES}
            lignes={lignes as DeputeLigne[]}
            cleLigne={(l) => l.uid_an}
            hauteurMax="30rem"
            vide={cfg.vide}
          />
        ) : (
          <DataTable
            colonnes={COLONNES_SENATEURS}
            lignes={lignes as SenateurLigne[]}
            cleLigne={(l) => l.matricule}
            hauteurMax="30rem"
            vide={cfg.vide}
          />
        )}
      </div>
    </div>
  );
}
