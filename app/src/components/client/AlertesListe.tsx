"use client";

import { useEffect, useState, type ReactNode } from "react";
import { AlertItem, type Gravite } from "@/components/ui/AlertItem";
import { formatNombre } from "@/lib/format";
import { urlSite } from "@/lib/basePath";
import { majParamsUrl } from "@/lib/urlEtat";
import { useUrlInitiale } from "@/lib/useUrlInitiale";
import type { Alerte, GraviteAlerte } from "@/lib/queries/alertes";
import type { AlertesFragment } from "@/app/data/alertes.json/route";

/**
 * Liste des alertes — filtres (gravité, type) et pagination CÔTÉ CLIENT
 * (site statique : plus de searchParams serveur).
 *
 * La première page (50 alertes, ordre canonique) est rendue dans le HTML
 * statique ; au premier geste (filtre ou changement de page), le fragment
 * /data/alertes.json (les 1 590 alertes, règles/bases légales dédupliquées
 * par type) est chargé une fois, puis tout est local. Les compteurs des
 * pilules viennent des agrégats exacts calculés au build — jamais un total
 * qui ment. URL `?type=…&gravite=…&page=…` restaurée et réécrite.
 */

export const ALERTES_PAR_PAGE = 50;

const GRAVITES: GraviteAlerte[] = ["haute", "moyenne", "info"];

/** Gravité base → statut AlertItem (ordre préservé) + libellé = mot de la base. */
const GRAVITE_UI: Record<GraviteAlerte, { statut: Gravite; libelle: string }> = {
  haute: { statut: "critique", libelle: "Gravité haute" },
  moyenne: { statut: "serieux", libelle: "Gravité moyenne" },
  info: { statut: "attention", libelle: "Information" },
};

/** Libellés courts des types d'alerte présents en base (fallback : le code). */
const LIBELLES_TYPE: Record<string, string> = {
  A1_hatvp_non_deposee: "HATVP — non-déposée (constat officiel)",
  A1_hatvp_retard_presume: "HATVP — retard présumé (agrégat)",
  lobbying_defaut_declaration: "Lobbying — défaut de déclaration",
  lobbying_declaration_incomplete: "Lobbying — déclaration incomplète",
  financement_campagne_reformee: "Campagne 2024 — compte réformé",
  financement_campagne_rejetee: "Campagne 2024 — compte rejeté",
  financement_parti_dependance_aide: "Parti — dépendance à l'aide publique",
  financement_parti_prive_aide: "Partis privés d'aide (avis CNCCFP)",
};

function libelleType(type: string): string {
  return LIBELLES_TYPE[type] ?? type;
}

/** Source des données ayant déclenché l'alerte, par domaine (préfixe du type). */
function sourceAlerte(type: string, url: string | null): { libelle: string; url?: string } {
  const u = url ?? undefined;
  if (type.startsWith("A1_")) return { libelle: "HATVP (liste.csv) × RNE", url: u };
  if (type.startsWith("lobbying_")) return { libelle: "HATVP — répertoire AGORA", url: u };
  if (type.startsWith("financement_campagne")) {
    return { libelle: "CNCCFP — comptes de campagne", url: u };
  }
  if (type.startsWith("financement_parti")) {
    return { libelle: "CNCCFP — comptes des partis", url: u };
  }
  return { libelle: "Source", url: u };
}

function estGravite(v: string | null): v is GraviteAlerte {
  return v !== null && (GRAVITES as string[]).includes(v);
}

/** Pilule de filtre (la sélection porte une coche, DATAVIZ §5). */
function Pilule({
  actif,
  surClic,
  children,
}: {
  actif: boolean;
  surClic: () => void;
  children: ReactNode;
}) {
  if (actif) {
    return (
      <span
        aria-current="true"
        className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold text-ink"
        style={{ borderColor: "var(--viz-serie-1)" }}
      >
        <span aria-hidden="true" className="font-bold">
          ✓
        </span>
        {children}
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={surClic}
      className="inline-flex items-center rounded-full border border-card-border px-2.5 py-1 text-xs text-ink-secondary transition-colors hover:bg-hover hover:text-ink"
    >
      {children}
    </button>
  );
}

/** Vue minimale d'une alerte à l'affichage (reconstruite depuis le fragment). */
type AlerteVue = {
  cle: string;
  type: string;
  gravite: string;
  titre: string;
  detail: string | null;
  regle: string | null;
  base_legale: string | null;
  source_url: string | null;
};

let alertesPromesse: Promise<AlertesFragment | null> | null = null;

function chargerAlertes(): Promise<AlertesFragment | null> {
  alertesPromesse ??= fetch(urlSite("/data/alertes.json"))
    .then((rep) => (rep.ok ? (rep.json() as Promise<AlertesFragment | null>) : null))
    .catch(() => null);
  return alertesPromesse;
}

export interface AlertesListeProps {
  /** Types présents en base avec leur volume exact (agrégats build). */
  types: { type: string; nb: number }[];
  /** Répartition exacte par gravité (agrégats build). */
  parGravite: { gravite: string; nb: number }[];
  total: number;
  /** Première page (ordre canonique), rendue dans le HTML statique. */
  initiales: Alerte[];
}

export function AlertesListe({ types, parGravite, total, initiales }: AlertesListeProps) {
  // Filtres : état initial restauré d'une URL partagée
  // `?type=…&gravite=…&page=…` (validée), surchargé par toute action.
  const urlInitiale = new URLSearchParams(useUrlInitiale());
  const [surcharge, setSurcharge] = useState<{
    gravite: GraviteAlerte | undefined;
    type: string | undefined;
    page: number;
  } | null>(null);
  const [fragment, setFragment] = useState<AlertesFragment | null>(null);
  const [indisponible, setIndisponible] = useState(false);

  const gUrl = urlInitiale.get("gravite");
  const tUrl = urlInitiale.get("type");
  const pUrl = Number.parseInt(urlInitiale.get("page") ?? "1", 10);
  const gravite = surcharge ? surcharge.gravite : estGravite(gUrl) ? gUrl : undefined;
  const type = surcharge
    ? surcharge.type
    : tUrl && types.some((x) => x.type === tUrl)
      ? tUrl
      : undefined;
  const page = surcharge ? surcharge.page : Number.isFinite(pUrl) && pUrl > 1 ? pUrl : 1;

  const besoinFragment = gravite !== undefined || type !== undefined || page > 1;
  const chargement = besoinFragment && fragment === null && !indisponible;

  useEffect(() => {
    if (!besoinFragment || fragment !== null) return;
    let monte = true;
    chargerAlertes().then((f) => {
      if (!monte) return;
      if (f === null) setIndisponible(true);
      else setFragment(f);
    });
    return () => {
      monte = false;
    };
  }, [besoinFragment, fragment]);

  const appliquer = (filtres: {
    gravite?: GraviteAlerte | undefined;
    type?: string | undefined;
    page?: number;
  }) => {
    const g = "gravite" in filtres ? filtres.gravite : gravite;
    const t = "type" in filtres ? filtres.type : type;
    const p = filtres.page ?? 1;
    setSurcharge({ gravite: g, type: t, page: p });
    majParamsUrl({
      gravite: g ?? null,
      type: t ?? null,
      page: p > 1 ? String(p) : null,
    });
  };

  // Liste filtrée : fragment si dispo, sinon la première page embarquée.
  let filtrees: AlerteVue[];
  let totalFiltre: number;
  let depuisFragment = false;
  if (fragment !== null) {
    depuisFragment = true;
    const typesF = fragment.types;
    const toutes = fragment.alertes;
    const vues: AlerteVue[] = [];
    for (let i = 0; i < toutes.length; i++) {
      const [typeIdx, graviteIdx, titre, detail, urlIdx] = toutes[i];
      const t = typesF[typeIdx];
      const g = fragment.gravites[graviteIdx] ?? "info";
      if (gravite !== undefined && g !== gravite) continue;
      if (type !== undefined && t?.code !== type) continue;
      vues.push({
        cle: `a-${i}`,
        type: t?.code ?? "",
        gravite: g,
        titre,
        detail,
        regle: t?.regle ?? null,
        base_legale: t?.base_legale ?? null,
        source_url: urlIdx >= 0 ? (fragment.urls[urlIdx] ?? null) : null,
      });
    }
    filtrees = vues;
    totalFiltre = vues.length;
  } else {
    filtrees = initiales.map((a) => ({
      cle: a.id,
      type: a.type,
      gravite: a.gravite,
      titre: a.titre,
      detail: a.detail,
      regle: a.regle,
      base_legale: a.base_legale,
      source_url: a.source_url,
    }));
    totalFiltre = total;
  }

  const pages = Math.max(Math.ceil(totalFiltre / ALERTES_PAR_PAGE), 1);
  // Tant que le fragment n'est pas là, seule la page 1 embarquée est
  // affichable : l'étiquette et la pagination disent la page RÉELLEMENT
  // affichée (jamais « page 2 » sur le contenu de la page 1).
  const pageBornee = depuisFragment ? Math.min(Math.max(page, 1), pages) : 1;
  const affichees = depuisFragment
    ? filtrees.slice((pageBornee - 1) * ALERTES_PAR_PAGE, pageBornee * ALERTES_PAR_PAGE)
    : filtrees;

  return (
    <>
      {/* Rangée de filtres (une seule, au-dessus de la liste — DATAVIZ §5) */}
      <div className="flex flex-col gap-2" aria-label="Filtres des alertes">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
            Gravité
          </span>
          <Pilule actif={gravite === undefined} surClic={() => appliquer({ gravite: undefined })}>
            Toutes ({formatNombre(total)})
          </Pilule>
          {parGravite.map((g) => (
            <Pilule
              key={g.gravite}
              actif={gravite === g.gravite}
              surClic={() =>
                appliquer({ gravite: estGravite(g.gravite) ? g.gravite : undefined })
              }
            >
              {estGravite(g.gravite) ? GRAVITE_UI[g.gravite].libelle : g.gravite} (
              {formatNombre(g.nb)})
            </Pilule>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
            Type
          </span>
          <Pilule actif={type === undefined} surClic={() => appliquer({ type: undefined })}>
            Tous
          </Pilule>
          {types.map((t) => (
            <Pilule
              key={t.type}
              actif={type === t.type}
              surClic={() => appliquer({ type: t.type })}
            >
              {libelleType(t.type)} ({formatNombre(t.nb)})
            </Pilule>
          ))}
        </div>
      </div>

      {/* Liste paginée */}
      <div className="flex flex-col gap-1.5">
        <p className="text-xs text-ink-muted" aria-live="polite">
          {totalFiltre === 0
            ? "Aucune alerte ne correspond à ces filtres."
            : `${formatNombre(totalFiltre)} alerte${totalFiltre > 1 ? "s" : ""} — page ${formatNombre(pageBornee)} sur ${formatNombre(pages)}`}
          {chargement ? " · chargement de la liste complète…" : ""}
        </p>
        {indisponible && besoinFragment && (
          <p className="text-xs text-ink-muted">
            Liste complète indisponible (fragment /data/alertes.json non chargé) — les{" "}
            {formatNombre(initiales.length)} premières alertes restent affichées.
          </p>
        )}
        <div className={chargement ? "flex flex-col gap-1.5 opacity-50" : "flex flex-col gap-1.5"}>
          {affichees.map((a) => {
            const ui = estGravite(a.gravite) ? GRAVITE_UI[a.gravite] : GRAVITE_UI.info;
            return (
              <AlertItem
                key={a.cle}
                gravite={ui.statut}
                graviteLibelle={ui.libelle}
                titre={a.titre}
                detail={a.detail ?? undefined}
                regle={a.regle ?? undefined}
                baseLegale={a.base_legale ?? undefined}
                source={sourceAlerte(a.type, a.source_url)}
              />
            );
          })}
        </div>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <nav aria-label="Pagination des alertes" className="flex items-center gap-3 text-sm">
          {pageBornee > 1 ? (
            <button
              type="button"
              onClick={() => appliquer({ page: pageBornee - 1 })}
              className="rounded-lg border border-card-border px-3 py-1.5 text-ink-secondary transition-colors hover:bg-hover hover:text-ink"
            >
              ‹ Page précédente
            </button>
          ) : (
            <span className="rounded-lg border border-card-border px-3 py-1.5 text-ink-muted opacity-50">
              ‹ Page précédente
            </span>
          )}
          <span className="text-xs text-ink-muted [font-variant-numeric:tabular-nums]">
            {formatNombre(pageBornee)} / {formatNombre(pages)}
          </span>
          {pageBornee < pages ? (
            <button
              type="button"
              onClick={() => appliquer({ page: pageBornee + 1 })}
              className="rounded-lg border border-card-border px-3 py-1.5 text-ink-secondary transition-colors hover:bg-hover hover:text-ink"
            >
              Page suivante ›
            </button>
          ) : (
            <span className="rounded-lg border border-card-border px-3 py-1.5 text-ink-muted opacity-50">
              Page suivante ›
            </span>
          )}
        </nav>
      )}
    </>
  );
}
