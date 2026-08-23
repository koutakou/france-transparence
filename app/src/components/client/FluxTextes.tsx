"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { DataTable, type Colonne } from "@/components/ui/DataTable";
import { formatNombre, formatPct } from "@/lib/format";
import { libelleNature } from "@/lib/jorf-libelles";
import { urlSite } from "@/lib/basePath";
import { majParamsUrl } from "@/lib/urlEtat";
import { useUrlInitiale } from "@/lib/useUrlInitiale";
import type { JorfTexteLigne } from "@/lib/queries/documents";
import type { TextesFragment } from "@/app/data/documents/textes.json/route";

/**
 * Flux des textes du Journal officiel — filtres (nature, nominations) et
 * pagination CÔTÉ CLIENT (site statique : plus de searchParams serveur).
 *
 * La première page (50 textes) est rendue dans le HTML statique ; au
 * premier geste, le fragment /data/documents/textes.json (toute la fenêtre
 * des 30 derniers JO, compact) est chargé une fois, puis tout est local.
 * Les URL historiques `?nature=…&nominations=1&page=…` sont restaurées.
 */

export const PAR_PAGE = 50;

type TexteVue = JorfTexteLigne & { is_nomination: 0 | 1 };

export interface FluxTextesProps {
  /** Natures présentes sur la fenêtre, avec volumes exacts (build). */
  natures: { code: string; nb: number }[];
  /** Première page du flux complet, rendue dans le HTML statique. */
  initiales: JorfTexteLigne[];
  /** Total de textes de la fenêtre (sans filtre). */
  total: number;
  /** Part de textes sans ministère émetteur (réel), pour le sous-titre. */
  pctSansMinistere: number;
  /** Nombre de JO parus dans la fenêtre (vient de la base, jamais figé). */
  nbJours: number;
}

let textesPromesse: Promise<TextesFragment | null> | null = null;

function chargerTextes(): Promise<TextesFragment | null> {
  textesPromesse ??= fetch(urlSite("/data/documents/textes.json"))
    .then((rep) => (rep.ok ? (rep.json() as Promise<TextesFragment | null>) : null))
    .catch(() => null);
  return textesPromesse;
}

/** Aplati le fragment (groupé par jour) en lignes du flux, ordre préservé. */
function aplatir(fragment: TextesFragment): TexteVue[] {
  const lignes: TexteVue[] = [];
  for (const [date, textes] of fragment.jours) {
    for (const [texteId, natureIdx, titre, ministereIdx, isNomination] of textes) {
      lignes.push({
        texte_id: texteId,
        date_publi: date,
        nature: natureIdx >= 0 ? (fragment.natures[natureIdx] ?? null) : null,
        titre,
        ministere: ministereIdx >= 0 ? (fragment.ministeres[ministereIdx] ?? null) : null,
        lien_legifrance: `${fragment.prefixeLegifrance}${texteId}`,
        is_nomination: isNomination,
      });
    }
  }
  return lignes;
}

const COLONNES_FLUX: Colonne<TexteVue>[] = [
  { cle: "date_publi", entete: "JO du", type: "date", largeur: "6.5rem" },
  {
    cle: "nature",
    entete: "Nature",
    largeur: "8.5rem",
    rendu: (l) => <span className="whitespace-nowrap">{libelleNature(l.nature)}</span>,
  },
  {
    cle: "titre",
    entete: "Titre",
    rendu: (l) => (
      <span title={l.titre} className="block max-w-[44ch] truncate xl:max-w-[62ch]">
        {l.titre}
      </span>
    ),
  },
  {
    cle: "ministere",
    entete: "Ministère",
    largeur: "13rem",
    rendu: (l) =>
      l.ministere ? (
        <span title={l.ministere} className="block max-w-[22ch] truncate">
          {l.ministere}
        </span>
      ) : (
        "—"
      ),
  },
  {
    cle: "lien_legifrance",
    entete: "Lien",
    rendu: (l) => (
      <a
        href={l.lien_legifrance}
        target="_blank"
        rel="noopener noreferrer"
        className="whitespace-nowrap text-ink-secondary underline decoration-dotted underline-offset-2 transition-colors hover:text-ink"
      >
        Légifrance<span aria-hidden="true"> ↗</span>
        <span className="sr-only"> (nouvelle fenêtre)</span>
      </a>
    ),
  },
];

export function FluxTextes({
  natures,
  initiales,
  total,
  pctSansMinistere,
  nbJours,
}: FluxTextesProps) {
  // Filtres : état initial restauré d'une URL partagée
  // `?nature=…&nominations=1&page=…` (validée), surchargé par toute action.
  const urlInitiale = new URLSearchParams(useUrlInitiale());
  const [surcharge, setSurcharge] = useState<{
    nature: string;
    nominations: boolean;
    page: number;
  } | null>(null);
  const [fragment, setFragment] = useState<TextesFragment | null>(null);
  const [indisponible, setIndisponible] = useState(false);

  const nUrl = urlInitiale.get("nature");
  const pUrl = Number.parseInt(urlInitiale.get("page") ?? "1", 10);
  const nature = surcharge
    ? surcharge.nature
    : nUrl && natures.some((x) => x.code === nUrl)
      ? nUrl
      : "";
  const nominationsSeules = surcharge
    ? surcharge.nominations
    : urlInitiale.get("nominations") === "1";
  const page = surcharge ? surcharge.page : Number.isFinite(pUrl) && pUrl > 1 ? pUrl : 1;

  const besoinFragment = nature !== "" || nominationsSeules || page > 1;
  const chargement = besoinFragment && fragment === null && !indisponible;

  useEffect(() => {
    if (!besoinFragment || fragment !== null) return;
    let monte = true;
    chargerTextes().then((f) => {
      if (!monte) return;
      if (f === null) setIndisponible(true);
      else setFragment(f);
    });
    return () => {
      monte = false;
    };
  }, [besoinFragment, fragment]);

  const appliquer = (maj: { nature?: string; nominations?: boolean; page?: number }) => {
    const n = maj.nature ?? nature;
    const nom = maj.nominations ?? nominationsSeules;
    const p = maj.page ?? 1;
    setSurcharge({ nature: n, nominations: nom, page: p });
    majParamsUrl({
      nature: n || null,
      nominations: nom ? "1" : null,
      page: p > 1 ? String(p) : null,
    });
  };

  // Lignes filtrées : fragment si dispo, sinon la première page embarquée.
  let filtrees: TexteVue[];
  let totalFiltre: number;
  let depuisFragment = false;
  if (fragment !== null) {
    depuisFragment = true;
    filtrees = aplatir(fragment).filter(
      (l) =>
        (nature === "" || l.nature === nature) && (!nominationsSeules || l.is_nomination === 1),
    );
    totalFiltre = filtrees.length;
  } else {
    filtrees = initiales.map((l) => ({ ...l, is_nomination: 0 as const }));
    totalFiltre = total;
  }

  const nbPages = Math.max(Math.ceil(totalFiltre / PAR_PAGE), 1);
  // Sans fragment, seule la page 1 embarquée est affichable — l'étiquette
  // dit toujours la page réellement affichée.
  const pageAffichee = depuisFragment ? Math.min(Math.max(page, 1), nbPages) : 1;
  const affichees = depuisFragment
    ? filtrees.slice((pageAffichee - 1) * PAR_PAGE, pageAffichee * PAR_PAGE)
    : filtrees;
  const filtreActif = nature !== "" || nominationsSeules;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-[11px] font-medium uppercase tracking-[0.04em] text-ink-muted">
          Nature
          <select
            value={nature}
            onChange={(e) => appliquer({ nature: e.target.value })}
            className="h-8 rounded-lg border border-card-border bg-card px-2 text-[13px] text-ink"
          >
            <option value="">Toutes les natures</option>
            {natures.map((n) => (
              <option key={n.code} value={n.code}>
                {libelleNature(n.code)} — {formatNombre(n.nb)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex h-8 items-center gap-2 text-[13px] text-ink-secondary">
          <input
            type="checkbox"
            checked={nominationsSeules}
            onChange={(e) => appliquer({ nominations: e.target.checked })}
            className="size-4 accent-accent"
          />
          Nominations seulement
        </label>
        {filtreActif && (
          <button
            type="button"
            onClick={() => appliquer({ nature: "", nominations: false })}
            className="flex h-8 items-center text-xs text-ink-muted underline decoration-dotted underline-offset-2 transition-colors hover:text-ink-secondary"
          >
            Réinitialiser
          </button>
        )}
      </div>

      <Card
        titre="Flux des textes"
        sousTitre={`Fenêtre des ${formatNombre(nbJours)} derniers JO parus, JORF « Lois et décrets » — ce n’est pas le fonds DOLE. Du plus récent au plus ancien — ministère absent sur ${formatPct(
          pctSansMinistere,
        )} des textes (lois, Conseil constitutionnel… — réel), affiché « — »`}
      >
        {indisponible && besoinFragment && (
          <p className="mb-2 text-xs text-ink-muted">
            Flux complet indisponible (fragment /data/documents/textes.json non chargé) — les{" "}
            {formatNombre(initiales.length)} textes les plus récents restent affichés.
          </p>
        )}
        <div className={chargement ? "opacity-50 transition-opacity" : "transition-opacity"}>
          <DataTable
            colonnes={COLONNES_FLUX}
            lignes={affichees}
            cleLigne={(l) => l.texte_id}
            vide="Aucun texte ne correspond à ces filtres."
          />
        </div>
        <nav
          aria-label="Pagination du flux"
          className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs text-ink-muted"
        >
          <span aria-live="polite">
            Page {formatNombre(pageAffichee)} sur {formatNombre(nbPages)} ·{" "}
            {formatNombre(totalFiltre)} textes
            {filtreActif ? " (filtrés)" : ""} · {formatNombre(PAR_PAGE)} par page
            {chargement ? " · chargement du flux complet…" : ""}
          </span>
          <span className="flex gap-2">
            {pageAffichee > 1 ? (
              <button
                type="button"
                onClick={() => appliquer({ page: pageAffichee - 1 })}
                className="rounded-lg border border-card-border px-2.5 py-1 text-ink-secondary transition-colors hover:bg-hover hover:text-ink"
              >
                ← Page précédente
              </button>
            ) : (
              <span
                aria-disabled="true"
                className="rounded-lg border border-card-border px-2.5 py-1 opacity-40"
              >
                ← Page précédente
              </span>
            )}
            {pageAffichee < nbPages ? (
              <button
                type="button"
                onClick={() => appliquer({ page: pageAffichee + 1 })}
                className="rounded-lg border border-card-border px-2.5 py-1 text-ink-secondary transition-colors hover:bg-hover hover:text-ink"
              >
                Page suivante →
              </button>
            ) : (
              <span
                aria-disabled="true"
                className="rounded-lg border border-card-border px-2.5 py-1 opacity-40"
              >
                Page suivante →
              </span>
            )}
          </span>
        </nav>
      </Card>
    </div>
  );
}
