import type { Metadata } from "next";
import Link from "next/link";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { DataTable, type Colonne } from "@/components/ui/DataTable";
import { Donut } from "@/components/ui/Donut";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { Sparkline } from "@/components/ui/Sparkline";
import { StatStrip } from "@/components/ui/StatStrip";
import { formatDateFr, formatNombre, formatPct } from "@/lib/format";
import {
  getFluxTextes,
  getJorfKpis,
  getMetaJorf,
  getNominationsParMinistere,
  getParutionsParJour,
  getRepartitionNatures,
  type JorfTexteLigne,
  type ParutionJour,
} from "@/lib/queries/documents";

// La base locale évolue à chaque ingestion : jamais figer cet état au build.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Documents — Journal officiel",
  description:
    "Les textes des 30 derniers Journaux officiels « Lois et décrets » : lois, décrets, arrêtés, nominations — flux filtrable, liens Légifrance.",
};

/* ------------------------------------------------------------------ */
/* Libellés des natures DILA (codes bruts en base : ARRETE, DECRET…)    */
/* ------------------------------------------------------------------ */

const LIBELLES_NATURE: Record<string, string> = {
  ARRETE: "Arrêté",
  DECRET: "Décret",
  AVIS: "Avis",
  DECISION: "Décision",
  INFORMATIONS_PARLEMENTAIRES: "Informations parlementaires",
  ANNONCES: "Annonces",
  LOI: "Loi",
  DELIBERATION: "Délibération",
  LISTE: "Liste",
  RAPPORT: "Rapport",
  ORDONNANCE: "Ordonnance",
  ARRET: "Arrêt",
  CITATION: "Citation",
  ACCORD: "Accord",
  ACCORD_FONCTION_PUBLIQUE: "Accord (fonction publique)",
  AVENANT: "Avenant",
  EXEQUATUR: "Exequatur",
  RECOMMANDATION: "Recommandation",
  TABLEAU: "Tableau",
};

/** Code DILA → libellé lisible ; nature absente (réel, 4 textes) → « — ». */
function libelleNature(code: string | null): string {
  if (!code) return "—";
  const connu = LIBELLES_NATURE[code];
  if (connu) return connu;
  const bas = code.toLowerCase().replace(/_/g, " ");
  return bas.charAt(0).toUpperCase() + bas.slice(1);
}

/** Pluriels pour le donut (seules les natures de tête y apparaissent). */
const PLURIELS_NATURE: Record<string, string> = {
  ARRETE: "Arrêtés",
  DECRET: "Décrets",
  AVIS: "Avis",
  DECISION: "Décisions",
  INFORMATIONS_PARLEMENTAIRES: "Informations parlementaires",
  LOI: "Lois",
};

function libelleNaturePluriel(code: string | null): string {
  if (!code) return "Nature non renseignée";
  return PLURIELS_NATURE[code] ?? libelleNature(code);
}

/* ------------------------------------------------------------------ */
/* Aides                                                                */
/* ------------------------------------------------------------------ */

/**
 * Série calendaire CONTINUE pour la sparkline : le JO ne paraît pas tous
 * les jours (trous réels) — un jour sans JO compte honnêtement 0 texte.
 * Itération en UTC pur : aucune dérive de fuseau.
 */
function serieCalendaire(parutions: ParutionJour[]): { date: string; nb: number }[] {
  if (parutions.length === 0) return [];
  const parDate = new Map(parutions.map((p) => [p.date_publi, p.nb]));
  const debut = Date.parse(parutions[0].date_publi + "T00:00:00Z");
  const fin = Date.parse(parutions[parutions.length - 1].date_publi + "T00:00:00Z");
  const jours: { date: string; nb: number }[] = [];
  for (let t = debut; t <= fin; t += 86_400_000) {
    const iso = new Date(t).toISOString().slice(0, 10);
    jours.push({ date: iso, nb: parDate.get(iso) ?? 0 });
  }
  return jours;
}

/** Premier élément d’un searchParam (string | string[] | undefined). */
function premier(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

/* ------------------------------------------------------------------ */
/* Page                                                                 */
/* ------------------------------------------------------------------ */

/**
 * Documents — Journal officiel. Fenêtre glissante des 30 derniers JO
 * « Lois et décrets » (dumps quotidiens DILA JORFSIMPLE, Licence Ouverte) :
 * cadrage chiffré, parutions par jour, nominations par ministère,
 * répartition par nature, puis flux filtrable et paginé (searchParams
 * côté serveur). Liens Légifrance sortants uniquement — jamais de fetch.
 */
export default async function DocumentsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;

  const meta = getMetaJorf();
  const kpis = getJorfKpis();
  const parutions = getParutionsParJour();
  const nominations = getNominationsParMinistere(10);
  const natures = getRepartitionNatures();

  // Base absente : message honnête (aucune donnée fictive).
  if (parutions === null || natures === null || nominations === null) {
    return (
      <section className="flex flex-col gap-6">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Documents — Journal officiel
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          <p>
            La base locale n’est pas encore construite — lancer{" "}
            <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code> pour ingérer
            les sources.
          </p>
        </div>
      </section>
    );
  }

  // Base présente mais table JORF vide : le dire tel quel.
  if (kpis === null) {
    return (
      <section className="flex flex-col gap-6">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Documents — Journal officiel
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          <p>
            Aucun texte du Journal officiel dans la base — l’ingestion de la source S3
            (DILA) n’a pas encore livré de données.
          </p>
        </div>
      </section>
    );
  }

  /* ---------------------------- Filtres (URL) ---------------------------- */
  const naturesFiltre = natures.flatMap((n) => (n.nature ? [{ code: n.nature, nb: n.nb }] : []));
  const natureBrute = premier(sp.nature);
  const natureActive = naturesFiltre.some((n) => n.code === natureBrute) ? natureBrute ?? null : null;
  const nominationsSeules = premier(sp.nominations) === "1";
  const pageDemandee = Number.parseInt(premier(sp.page) ?? "1", 10) || 1;

  const flux = getFluxTextes({
    nature: natureActive,
    nominationsSeules,
    page: pageDemandee,
  });

  /** URL du flux pour une page donnée, filtres préservés. */
  const hrefPage = (p: number): string => {
    const q = new URLSearchParams();
    if (natureActive) q.set("nature", natureActive);
    if (nominationsSeules) q.set("nominations", "1");
    if (p > 1) q.set("page", String(p));
    const s = q.toString();
    return s ? `/documents?${s}` : "/documents";
  };

  /* ------------------------------- Dérivés ------------------------------- */
  const serie = serieCalendaire(parutions);
  const joursSansJo = serie.length - parutions.length;
  const pic = parutions.reduce((a, b) => (b.nb > a.nb ? b : a), parutions[0]);
  const sansNature = natures.find((n) => n.nature === null)?.nb ?? 0;
  const resteNominations = nominations.total - nominations.top.reduce((s, n) => s + n.nb, 0);
  const resteMinisteres = nominations.nbMinisteres - nominations.top.length;
  const pctSansMinistere = (100 * kpis.sansMinistere) / kpis.textesFenetre;

  const colonnesParutions: Colonne<ParutionJour>[] = [
    { cle: "date_publi", entete: "JO du", type: "date" },
    { cle: "nb", entete: "Textes", type: "nombre" },
  ];

  const colonnesFlux: Colonne<JorfTexteLigne>[] = [
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

  return (
    <section className="flex flex-col gap-6">
      {/* ------------------------------- En-tête ------------------------------- */}
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="max-w-3xl">
          <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
            Documents — Journal officiel
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-secondary">
            Tous les textes du Journal officiel «&nbsp;Lois et décrets&nbsp;» — lois,
            décrets, arrêtés, avis, nominations — à partir des livraisons quotidiennes
            JORFSIMPLE de la DILA{meta ? <> ({meta.licence})</> : null}. Fenêtre
            courante&nbsp;: les {formatNombre(kpis.nbJours)}&nbsp;derniers JO parus, du{" "}
            {formatDateFr(kpis.premierJo)} au {formatDateFr(kpis.dernierJo)}. Chaque texte
            renvoie vers Légifrance.
          </p>
        </div>
        {meta && (
          <FreshnessBadge
            dateDonnees={meta.date_donnees}
            source={meta.nom}
            frequence={meta.frequence}
            url={meta.url}
          />
        )}
      </header>

      {/* ------------------------------- Cadrage ------------------------------- */}
      <StatStrip
        stats={[
          {
            label: `Textes publiés (${formatNombre(kpis.nbJours)} derniers JO)`,
            valeur: formatNombre(kpis.textesFenetre),
          },
          { label: "Dont nominations", valeur: formatNombre(kpis.nominationsFenetre) },
          {
            label: `Textes du JO du ${formatDateFr(kpis.dernierJo)}`,
            valeur: formatNombre(kpis.textesJour),
          },
          {
            label: `Nominations du JO du ${formatDateFr(kpis.dernierJo)}`,
            valeur: formatNombre(kpis.nominationsJour),
          },
        ]}
      />

      {/* --------------------- Parutions & répartition ------------------------- */}
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Card
          titre="Parutions par jour"
          sousTitre="Textes par JO paru — le JO ne paraît pas tous les jours : les jours sans parution comptent 0"
        >
          <div className="overflow-x-auto">
            <Sparkline
              valeurs={serie.map((s) => s.nb)}
              largeur={520}
              hauteur={72}
              ariaLabel={`Nombre de textes publiés par jour, du ${formatDateFr(
                kpis.premierJo,
              )} au ${formatDateFr(kpis.dernierJo)}`}
            />
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-ink-muted">
            Du {formatDateFr(kpis.premierJo)} au {formatDateFr(kpis.dernierJo)} · pic&nbsp;:{" "}
            {formatNombre(pic.nb)} textes le {formatDateFr(pic.date_publi)} ·{" "}
            {formatNombre(joursSansJo)} jours sans JO sur la période (trous réels).
          </p>
          <details className="mt-3">
            <summary className="cursor-pointer text-xs text-ink-muted transition-colors hover:text-ink-secondary">
              Vue tableau — textes par JO paru
            </summary>
            <DataTable
              className="mt-2"
              hauteurMax="16rem"
              colonnes={colonnesParutions}
              lignes={parutions}
              cleLigne={(l) => l.date_publi}
            />
          </details>
        </Card>

        <Card
          titre="Répartition par nature"
          sousTitre={`${formatNombre(
            kpis.textesFenetre,
          )} textes — natures en ordre de grandeur, les moins fréquentes repliées en « Autre »`}
        >
          <Donut
            parts={natures.map((n) => ({
              libelle: libelleNaturePluriel(n.nature),
              valeur: n.nb,
            }))}
            formatValeur={(v) => formatNombre(v)}
            libelleTotal="textes"
            ariaLabel={`Répartition des ${formatNombre(
              kpis.textesFenetre,
            )} textes des ${formatNombre(kpis.nbJours)} derniers JO par nature`}
          />
          <p className="mt-2 text-[11px] leading-relaxed text-ink-muted">
            {formatNombre(naturesFiltre.length)} natures distinctes sur la fenêtre
            {sansNature > 0 ? (
              <> · {formatNombre(sansNature)} textes sans nature renseignée (réel)</>
            ) : null}{" "}
            — détail par nature via le filtre du flux ci-dessous.
          </p>
        </Card>
      </div>

      {/* --------------------- Nominations par ministère ----------------------- */}
      <Card
        titre="Nominations par ministère"
        sousTitre={`Top ${formatNombre(nominations.top.length)} — fenêtre entière des ${formatNombre(
          kpis.nbJours,
        )} derniers JO, ${formatNombre(nominations.total)} nominations au total`}
      >
        <BarList
          items={nominations.top.map((n) => ({ libelle: n.ministere, valeur: n.nb }))}
          formatValeur={(v) => formatNombre(v)}
          largeurLibelle="46%"
        />
        {resteMinisteres > 0 && (
          <p className="mt-3 text-[11px] leading-relaxed text-ink-muted">
            {formatNombre(resteMinisteres)} autres ministères totalisent{" "}
            {formatNombre(resteNominations)} nominations sur la même fenêtre.
          </p>
        )}
      </Card>

      {/* ------------------------------- Flux ---------------------------------- */}
      <div className="flex flex-col gap-3">
        <form method="get" action="/documents" className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-[11px] font-medium uppercase tracking-[0.04em] text-ink-muted">
            Nature
            <select
              name="nature"
              defaultValue={natureActive ?? ""}
              className="h-8 rounded-lg border border-card-border bg-card px-2 text-[13px] text-ink"
            >
              <option value="">Toutes les natures</option>
              {naturesFiltre.map((n) => (
                <option key={n.code} value={n.code}>
                  {libelleNature(n.code)} — {formatNombre(n.nb)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex h-8 items-center gap-2 text-[13px] text-ink-secondary">
            <input
              type="checkbox"
              name="nominations"
              value="1"
              defaultChecked={nominationsSeules}
              className="size-4 accent-accent"
            />
            Nominations seulement
          </label>
          <button
            type="submit"
            className="h-8 rounded-lg border border-card-border bg-card px-3 text-[13px] text-ink transition-colors hover:bg-hover"
          >
            Filtrer
          </button>
          {(natureActive || nominationsSeules) && (
            <Link
              href="/documents"
              className="flex h-8 items-center text-xs text-ink-muted underline decoration-dotted underline-offset-2 transition-colors hover:text-ink-secondary"
            >
              Réinitialiser
            </Link>
          )}
        </form>

        <Card
          titre="Flux des textes"
          sousTitre={`Du plus récent au plus ancien — ministère absent sur ${formatPct(
            pctSansMinistere,
          )} des textes (lois, Conseil constitutionnel… — réel), affiché « — »`}
        >
          {flux && (
            <>
              <DataTable
                colonnes={colonnesFlux}
                lignes={flux.lignes}
                cleLigne={(l) => l.texte_id}
                vide="Aucun texte ne correspond à ces filtres."
              />
              <nav
                aria-label="Pagination du flux"
                className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs text-ink-muted"
              >
                <span>
                  Page {formatNombre(flux.page)} sur {formatNombre(flux.nbPages)} ·{" "}
                  {formatNombre(flux.total)} textes
                  {natureActive || nominationsSeules ? " (filtrés)" : ""} ·{" "}
                  {formatNombre(flux.parPage)} par page
                </span>
                <span className="flex gap-2">
                  {flux.page > 1 ? (
                    <Link
                      href={hrefPage(flux.page - 1)}
                      className="rounded-lg border border-card-border px-2.5 py-1 text-ink-secondary transition-colors hover:bg-hover hover:text-ink"
                    >
                      ← Page précédente
                    </Link>
                  ) : (
                    <span
                      aria-disabled="true"
                      className="rounded-lg border border-card-border px-2.5 py-1 opacity-40"
                    >
                      ← Page précédente
                    </span>
                  )}
                  {flux.page < flux.nbPages ? (
                    <Link
                      href={hrefPage(flux.page + 1)}
                      className="rounded-lg border border-card-border px-2.5 py-1 text-ink-secondary transition-colors hover:bg-hover hover:text-ink"
                    >
                      Page suivante →
                    </Link>
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
            </>
          )}
        </Card>
      </div>
    </section>
  );
}
