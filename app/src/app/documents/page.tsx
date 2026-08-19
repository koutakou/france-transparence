import type { Metadata } from "next";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { DataTable, type Colonne } from "@/components/ui/DataTable";
import { Donut } from "@/components/ui/Donut";
import { FluxTextes } from "@/components/client/FluxTextes";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { Sparkline } from "@/components/ui/Sparkline";
import { StatStrip } from "@/components/ui/StatStrip";
import { formatDateFr, formatNombre } from "@/lib/format";
import { libelleNaturePluriel } from "@/lib/jorf-libelles";
import {
  getFluxTextes,
  getJorfKpis,
  getMetaJorf,
  getNominationsParMinistere,
  getParutionsParJour,
  getRepartitionNatures,
  type ParutionJour,
} from "@/lib/queries/documents";

/**
 * Documents — Journal officiel. Page STATIQUE (site pré-rendu
 * quotidiennement) : fenêtre glissante des 30 derniers JO « Lois et
 * décrets » (dumps quotidiens DILA JORFSIMPLE, Licence Ouverte) — cadrage
 * chiffré, parutions par jour, nominations par ministère, répartition par
 * nature calculés au build ; flux filtrable et paginé CÔTÉ CLIENT sur le
 * fragment /data/documents/textes.json. Liens Légifrance sortants
 * uniquement — jamais de fetch de contenu externe.
 */

export const metadata: Metadata = {
  title: "Journal officiel",
  description:
    "Lois, décrets et nominations du Journal officiel, à parution — source DILA.",
};

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

/* ------------------------------------------------------------------ */
/* Page                                                                 */
/* ------------------------------------------------------------------ */

export default async function DocumentsPage() {
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

  const naturesFiltre = natures.flatMap((n) => (n.nature ? [{ code: n.nature, nb: n.nb }] : []));

  // Première page du flux complet, rendue dans le HTML statique — filtres
  // et pagination passent ensuite par le fragment côté client.
  const flux = getFluxTextes({ nature: null, nominationsSeules: false, page: 1 });

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
      <FluxTextes
        natures={naturesFiltre}
        initiales={flux?.lignes ?? []}
        total={flux?.total ?? kpis.textesFenetre}
        pctSansMinistere={pctSansMinistere}
      />
    </section>
  );
}
