import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import { AlertItem, type Gravite } from "@/components/ui/AlertItem";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { StatStrip } from "@/components/ui/StatStrip";
import { formatDateFr, formatNombre } from "@/lib/format";
import {
  estGraviteAlerte,
  getAlertesDomaines,
  getAlertesPage,
  getAlertesStats,
  getAlertesTypes,
  type Alerte,
  type GraviteAlerte,
} from "@/lib/queries/alertes";

// Les alertes sont recalculées à chaque ingestion : jamais figées au build.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Alertes transparence",
  description:
    "Alertes calculées à l'ingestion sur les données publiques : intégrité des élus (HATVP), lobbying, financement politique — chaque alerte cite sa règle et sa base légale.",
};

/**
 * Page /alertes — les alertes calculées à l'ingestion (1 590 au 19/08/2026).
 * Hors navigation principale (accès depuis l'accueil). Filtres par type et
 * gravité via searchParams (liens : aucun JS client), liste paginée à 50,
 * chaque AlertItem dépliant règle + base légale (docs/NOTES-FRONT.md §Alertes).
 */

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
function sourceAlerte(a: Alerte): { libelle: string; url?: string } {
  const url = a.source_url ?? undefined;
  if (a.type.startsWith("A1_")) return { libelle: "HATVP (liste.csv) × RNE", url };
  if (a.type.startsWith("lobbying_")) return { libelle: "HATVP — répertoire AGORA", url };
  if (a.type.startsWith("financement_campagne")) {
    return { libelle: "CNCCFP — comptes de campagne", url };
  }
  if (a.type.startsWith("financement_parti")) {
    return { libelle: "CNCCFP — comptes des partis", url };
  }
  return { libelle: "Source", url };
}

/** URL /alertes en conservant les filtres actifs (page omise si 1). */
function hrefAlertes(filtres: { type?: string; gravite?: GraviteAlerte; page?: number }): string {
  const params = new URLSearchParams();
  if (filtres.type) params.set("type", filtres.type);
  if (filtres.gravite) params.set("gravite", filtres.gravite);
  if (filtres.page && filtres.page > 1) params.set("page", String(filtres.page));
  const qs = params.toString();
  return qs ? `/alertes?${qs}` : "/alertes";
}

function premierParam(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

/** Pilule de filtre (lien serveur — la sélection porte une coche, DATAVIZ §5). */
function Pilule({ actif, href, children }: { actif: boolean; href: string; children: ReactNode }) {
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
    <Link
      href={href}
      className="inline-flex items-center rounded-full border border-card-border px-2.5 py-1 text-xs text-ink-secondary transition-colors hover:bg-hover hover:text-ink"
    >
      {children}
    </Link>
  );
}

export default async function PageAlertes({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const graviteBrute = premierParam(sp.gravite);
  const gravite = graviteBrute && estGraviteAlerte(graviteBrute) ? graviteBrute : undefined;
  const pageBrute = Number.parseInt(premierParam(sp.page) ?? "1", 10);
  const pageDemandee = Number.isFinite(pageBrute) && pageBrute > 0 ? pageBrute : 1;

  const stats = getAlertesStats();
  if (stats === null) {
    return (
      <section className="flex flex-col gap-4">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Alertes transparence
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          La base locale n’est pas encore construite — lancer{" "}
          <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code> pour
          ingérer les sources et calculer les alertes.
        </div>
      </section>
    );
  }

  const types = getAlertesTypes() ?? [];
  const domaines = getAlertesDomaines() ?? [];
  // Un type inconnu de la base (URL modifiée à la main) = pas de filtre.
  const typeBrut = premierParam(sp.type);
  const type = typeBrut && types.some((t) => t.type === typeBrut) ? typeBrut : undefined;

  const resultat = getAlertesPage({ type, gravite, page: pageDemandee });
  const { alertes, total, page, pages } = resultat ?? {
    alertes: [],
    total: 0,
    page: 1,
    pages: 1,
  };

  const nbParGravite = new Map(stats.parGravite.map((g) => [g.gravite, g.nb]));

  return (
    <section className="flex flex-col gap-6">
      {/* En-tête factuel */}
      <header className="flex flex-col gap-2">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Alertes transparence
        </h1>
        <p className="max-w-3xl text-sm text-ink-secondary">
          {formatNombre(stats.total)} alertes calculées à l’ingestion des données
          publiques (dernier calcul&nbsp;:{" "}
          {stats.derniereDateCalcul ? formatDateFr(stats.derniereDateCalcul) : "—"}).
          Chaque alerte cite sa règle de calcul et sa base légale (dépliables
          ci-dessous) — un constat officiel ou un signal d’attention tiré des
          sources, jamais un jugement. Recalcul à chaque mise à jour des sources
          (HATVP hebdomadaire, lobbying quotidien, financement annuel).
        </p>
        <p className="max-w-3xl text-xs text-ink-muted">
          Les retards HATVP «&nbsp;présumés&nbsp;» sont des agrégats non
          nominatifs (réserve&nbsp;: répertoire des élus trimestriel) — seuls
          les constats officiels de la HATVP sont nominatifs.
        </p>
      </header>

      {/* KPI par gravité */}
      <StatStrip
        stats={[
          { label: "Alertes au total", valeur: formatNombre(stats.total) },
          { label: "Gravité haute", valeur: formatNombre(nbParGravite.get("haute") ?? 0) },
          { label: "Gravité moyenne", valeur: formatNombre(nbParGravite.get("moyenne") ?? 0) },
          { label: "Information", valeur: formatNombre(nbParGravite.get("info") ?? 0) },
        ]}
      />

      {/* Répartition par domaine */}
      <Card
        titre="Répartition par domaine"
        sousTitre="Le préfixe du type d’alerte porte son domaine — valeurs exactes affichées"
      >
        <BarList
          items={domaines.map((d) => ({ libelle: d.domaine, valeur: d.nb }))}
          formatValeur={(v) => formatNombre(v)}
          largeurLibelle="42%"
        />
      </Card>

      {/* Rangée de filtres (une seule, au-dessus de la liste — DATAVIZ §5) */}
      <div className="flex flex-col gap-2" aria-label="Filtres des alertes">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
            Gravité
          </span>
          <Pilule actif={gravite === undefined} href={hrefAlertes({ type })}>
            Toutes ({formatNombre(stats.total)})
          </Pilule>
          {stats.parGravite.map((g) => (
            <Pilule
              key={g.gravite}
              actif={gravite === g.gravite}
              href={hrefAlertes({
                type,
                gravite: estGraviteAlerte(g.gravite) ? g.gravite : undefined,
              })}
            >
              {estGraviteAlerte(g.gravite) ? GRAVITE_UI[g.gravite].libelle : g.gravite} (
              {formatNombre(g.nb)})
            </Pilule>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
            Type
          </span>
          <Pilule actif={type === undefined} href={hrefAlertes({ gravite })}>
            Tous
          </Pilule>
          {types.map((t) => (
            <Pilule
              key={t.type}
              actif={type === t.type}
              href={hrefAlertes({ type: t.type, gravite })}
            >
              {libelleType(t.type)} ({formatNombre(t.nb)})
            </Pilule>
          ))}
        </div>
      </div>

      {/* Liste paginée */}
      <div className="flex flex-col gap-2.5">
        <p className="text-xs text-ink-muted">
          {total === 0
            ? "Aucune alerte ne correspond à ces filtres."
            : `${formatNombre(total)} alerte${total > 1 ? "s" : ""} — page ${formatNombre(page)} sur ${formatNombre(pages)}`}
        </p>
        {alertes.map((a) => {
          const ui = estGraviteAlerte(a.gravite) ? GRAVITE_UI[a.gravite] : GRAVITE_UI.info;
          return (
            <AlertItem
              key={a.id}
              gravite={ui.statut}
              graviteLibelle={ui.libelle}
              titre={a.titre}
              detail={a.detail ?? undefined}
              regle={a.regle ?? undefined}
              baseLegale={a.base_legale ?? undefined}
              source={sourceAlerte(a)}
            />
          );
        })}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <nav aria-label="Pagination des alertes" className="flex items-center gap-3 text-sm">
          {page > 1 ? (
            <Link
              href={hrefAlertes({ type, gravite, page: page - 1 })}
              className="rounded-lg border border-card-border px-3 py-1.5 text-ink-secondary transition-colors hover:bg-hover hover:text-ink"
            >
              ‹ Page précédente
            </Link>
          ) : (
            <span className="rounded-lg border border-card-border px-3 py-1.5 text-ink-muted opacity-50">
              ‹ Page précédente
            </span>
          )}
          <span className="text-xs text-ink-muted [font-variant-numeric:tabular-nums]">
            {formatNombre(page)} / {formatNombre(pages)}
          </span>
          {page < pages ? (
            <Link
              href={hrefAlertes({ type, gravite, page: page + 1 })}
              className="rounded-lg border border-card-border px-3 py-1.5 text-ink-secondary transition-colors hover:bg-hover hover:text-ink"
            >
              Page suivante ›
            </Link>
          ) : (
            <span className="rounded-lg border border-card-border px-3 py-1.5 text-ink-muted opacity-50">
              Page suivante ›
            </span>
          )}
        </nav>
      )}
    </section>
  );
}
