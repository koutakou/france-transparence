import type { Metadata } from "next";
import type { ReactNode } from "react";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { JsonLd } from "@/components/JsonLd";
import { NoticeLecture } from "@/components/ui/NoticeLecture";
import { DataTable, type Colonne } from "@/components/ui/DataTable";
import { DeltaPct } from "@/components/ui/DeltaPct";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { LineChart } from "@/components/ui/LineChart";
import { StatStrip } from "@/components/ui/StatStrip";
import { ESPACE_FINE, formatDateFr, formatNombre } from "@/lib/format";
import {
  getKpisRecettes,
  getRecettesFiscalesDetail,
  getSerieRecettesNettes,
  getSeriesLonguesRecettes,
  getSourceRecettes,
  LIGNE_ID_TVA,
} from "@/lib/queries/recettes";
import { jsonLdPage, metadonneesPage } from "@/lib/seo";

// Rendu statique : la donnée ne change qu'à l'ingestion, le site est
// reconstruit après chaque ingestion (docs/deploiement/DECISION.md).

// Chemin, titre et description nommés UNE FOIS : les métadonnées et le
// balisage JSON-LD décrivent la même page, ils ne peuvent donc pas la
// décrire différemment le jour où l'un des deux est retouché.
const CHEMIN = "/recettes/";
const TITRE = "Recettes de l'État";
const DESCRIPTION =
  "Recettes nettes du budget général de l'État (DGFiP, situations mensuelles) : recettes fiscales par grand impôt, recettes non fiscales, fonds de concours — séries depuis 2013.";

export const metadata: Metadata = metadonneesPage({
  chemin: CHEMIN,
  titre: TITRE,
  description: DESCRIPTION,
});

const BALISAGE = jsonLdPage({
  chemin: CHEMIN,
  nom: TITRE,
  description: DESCRIPTION,
  ariane: [{ nom: "Accueil", chemin: "/" }, { nom: TITRE }],
});

const MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
const MOIS_LONGS = [
  "janvier", "février", "mars", "avril", "mai", "juin",
  "juillet", "août", "septembre", "octobre", "novembre", "décembre",
];

/** `184552567623.22` → `184,55 Md€` (précision maîtrisée pour les KPI). */
function enMd(v: number, decimales = 2): string {
  return `${formatNombre(v / 1e9, decimales)}${ESPACE_FINE}Md€`;
}

/** Montant en Md€ avec la valeur exacte en infobulle. */
function MontantMd({ valeur, decimales = 2 }: { valeur: number; decimales?: number }) {
  return <span title={`${formatNombre(valeur)}${ESPACE_FINE}€`}>{enMd(valeur, decimales)}</span>;
}

/** Variation en % vs N−1 — `null` (affiché « — ») si l'un des termes manque. */
function variationPct(v: number | null, n1: number | null): number | null {
  if (v === null || n1 === null || n1 === 0) return null;
  return ((v - n1) / Math.abs(n1)) * 100;
}

/** Vue tableau jumelle d'un graphique (DATAVIZ §9) — repli natif sans JS. */
function VueTableau({ children }: { children: ReactNode }) {
  return (
    <details className="mt-3">
      <summary className="w-fit cursor-pointer select-none text-xs text-ink-muted transition-colors hover:text-ink-secondary">
        Vue tableau
      </summary>
      <div className="mt-2">{children}</div>
    </details>
  );
}

/**
 * Recettes de l'État — pendant de /depenses, sur la MÊME source S13
 * (situations mensuelles budgétaires DGFiP) et elle seule. Server
 * Component : toutes les lectures viennent de `@/lib/queries/recettes`,
 * aucune donnée n'est fabriquée — une ligne absente s'affiche absente.
 */
export default async function PageRecettes() {
  const source = getSourceRecettes();
  const kpis = getKpisRecettes();

  if (!source || !kpis) {
    return (
      <section className="flex flex-col gap-4">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Recettes de l&apos;État
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          La base locale n&apos;est pas encore construite — lancer{" "}
          <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code>{" "}
          pour ingérer les sources budgétaires.
        </div>
      </section>
    );
  }

  const serie = getSerieRecettesNettes(3);
  const detail = getRecettesFiscalesDetail();
  const longues = getSeriesLonguesRecettes();

  // Les mois infra-annuels de la DGFiP sont provisoires : la mention
  // accompagne chaque badge tant que l'année en cours est incomplète.
  const mentionProvisoire = kpis.mois < 12 ? "mois infra-annuels provisoires" : undefined;
  const badge = (
    <FreshnessBadge
      dateDonnees={source.date_donnees}
      source="DGFiP — situations mensuelles"
      frequence={source.frequence}
      url={source.url}
      mention={mentionProvisoire}
    />
  );

  const vsN1 = `même période ${kpis.annee - 1}`;
  const deltaTotal = variationPct(kpis.totalNettes, kpis.totalNettesN1);
  const deltaFiscales = variationPct(kpis.fiscalesNettes, kpis.fiscalesNettesN1);
  const deltaNonFiscales = variationPct(kpis.nonFiscales, kpis.nonFiscalesN1);
  const deltaFonds = variationPct(kpis.fondsConcours, kpis.fondsConcoursN1);

  // ---- LineChart : cumuls mensuels (Md€) + lignes de la vue tableau jumelle
  const seriesCumul = (serie ?? []).map((s) => ({
    nom: String(s.annee),
    valeurs: s.valeurs.map((v) => (v === null ? null : v / 1e9)),
  }));
  const colonnesMois: Colonne<Record<string, string | number | null>>[] = [
    { cle: "mois", entete: "Mois" },
    ...(serie ?? []).map((s) => ({
      cle: `a${s.annee}`,
      entete: `Cumul ${s.annee} (Md€)`,
      type: "montant" as const,
      decimales: 2,
    })),
  ];
  const lignesMois: Record<string, string | number | null>[] = MOIS_LONGS.map((mois, i) => {
    const ligne: Record<string, string | number | null> = { mois };
    for (const s of serie ?? []) {
      const v = s.valeurs[i];
      ligne[`a${s.annee}`] = v === null ? null : v / 1e9;
    }
    return ligne;
  });

  // ---- Séries longues : années complètes uniquement (l'année en cours,
  // incomplète, est dite à part — jamais tracée comme une année pleine).
  const anneesCompletes = longues?.annees ?? [];
  const labelsAnnees = anneesCompletes.map((a) => String(a.annee));

  return (
    <div className="flex flex-col gap-6">
      <JsonLd donnees={BALISAGE} />
      {/* En-tête de module */}
      <section className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="max-w-2xl">
          <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
            Recettes de l&apos;État
          </h1>
          <p className="mt-2 text-sm text-ink-secondary">
            Recettes nettes du budget général — nettes des remboursements et
            dégrèvements d&apos;impôts — publiées chaque mois par la
            DGFiP&nbsp;: les montants sont des cumuls depuis le 1er janvier,
            comparés à la même période de l&apos;année précédente. Les mois de
            l&apos;année en cours sont provisoires jusqu&apos;à la clôture de
            l&apos;exercice. Dernière situation publiée&nbsp;:{" "}
            {formatDateFr(kpis.dateFinMois)}.
          </p>
          <NoticeLecture
            ancre="recettes"
            commentLire={
              <p>
                Les montants sont des cumuls depuis le 1er janvier, nets des
                remboursements et dégrèvements. Les mois de l’année en cours
                sont provisoires jusqu’à la clôture. Un tiret «&nbsp;—&nbsp;»
                n’est pas un zéro.
              </p>
            }
            provenance={
              <p>
                Situations mensuelles budgétaires de la DGFiP, même source
                que les dépenses d’exécution. Fraîcheur et licence sur la
                page Données.
              </p>
            }
            limites={
              <p>
                Ce n’est pas le détail des encaissements jour par jour, ni
                la fiscalité locale, ni les recettes de la sécurité sociale.
                Un impôt «&nbsp;net&nbsp;» n’est pas le montant mis à la
                charge du contribuable.
              </p>
            }
          />
        </div>
        {badge}
      </section>

      {/* KPI : les quatre agrégats publiés (deltas neutres — DATAVIZ §3.5) */}
      <StatStrip
        stats={[
          {
            label: `Recettes nettes cumulées au ${formatDateFr(kpis.dateFinMois)}`,
            valeur: <MontantMd valeur={kpis.totalNettes} />,
            montantVedette: true,
            delta: deltaTotal === null ? undefined : { valeur: deltaTotal, vs: vsN1 },
          },
          ...(kpis.fiscalesNettes === null
            ? []
            : [
                {
                  label: "Recettes fiscales nettes",
                  valeur: <MontantMd valeur={kpis.fiscalesNettes} />,
                  delta: deltaFiscales === null ? undefined : { valeur: deltaFiscales, vs: vsN1 },
                },
              ]),
          ...(kpis.nonFiscales === null
            ? []
            : [
                {
                  label: "Recettes non fiscales",
                  valeur: <MontantMd valeur={kpis.nonFiscales} />,
                  delta:
                    deltaNonFiscales === null ? undefined : { valeur: deltaNonFiscales, vs: vsN1 },
                },
              ]),
          ...(kpis.fondsConcours === null
            ? []
            : [
                {
                  label: "Fonds de concours et attributions de produits",
                  valeur: <MontantMd valeur={kpis.fondsConcours} />,
                  delta: deltaFonds === null ? undefined : { valeur: deltaFonds, vs: vsN1 },
                },
              ]),
        ]}
      />

      {/* Série mensuelle des cumuls, 3 années */}
      {serie && serie.length > 0 && (
        <Card
          titre="Recettes nettes cumulées par mois"
          sousTitre="Budget général, nettes des remboursements et dégrèvements — cumul depuis le 1er janvier, en Md€"
          droite={badge}
        >
          <LineChart
            labels={MOIS_COURTS}
            series={seriesCumul}
            formatValeur={(v) => `${formatNombre(v, 1)}${ESPACE_FINE}Md€`}
            ariaLabel={`Recettes nettes cumulées du budget général par mois, ${(serie ?? [])
              .map((s) => s.annee)
              .join(" contre ")}`}
          />
          <VueTableau>
            <DataTable
              colonnes={colonnesMois}
              lignes={lignesMois}
              cleLigne={(l) => String(l.mois)}
            />
          </VueTableau>
        </Card>
      )}

      {/* Décomposition des recettes fiscales nettes par grand impôt */}
      {detail && (
        <Card
          titre="Recettes fiscales nettes par grand impôt"
          sousTitre={`Cumul au ${formatDateFr(detail.dateFinMois)} depuis le 1er janvier — les cinq lignes publiées par la DGFiP`}
          droite={badge}
        >
          {detail.totalFiscales !== null && (
            <p className="mb-4 text-sm text-ink-secondary">
              Total des recettes fiscales nettes&nbsp;:{" "}
              <span className="font-medium text-ink">
                <MontantMd valeur={detail.totalFiscales} />
              </span>
              .
            </p>
          )}
          <BarList
            items={detail.impots.map((i) => ({
              libelle: i.ligneId === LIGNE_ID_TVA ? `${i.ligne} (part État)` : i.ligne,
              valeur: i.montantCumul,
            }))}
            formatValeur={(v) => enMd(v)}
          />
          <VueTableau>
            <DataTable
              colonnes={[
                { cle: "impot", entete: "Impôt" },
                {
                  cle: "cumul",
                  entete: `Cumul au ${formatDateFr(detail.dateFinMois)} (Md€)`,
                  type: "montant",
                  decimales: 2,
                },
                { cle: "cumulN1", entete: "Même cumul N−1 (Md€)", type: "montant", decimales: 2 },
                {
                  cle: "variation",
                  entete: "Variation",
                  rendu: (l: {
                    impot: string;
                    cumul: number;
                    cumulN1: number | null;
                    variation: number | null;
                  }) => (l.variation === null ? "—" : <DeltaPct valeur={l.variation} />),
                },
              ]}
              lignes={detail.impots.map((i) => ({
                impot: i.ligneId === LIGNE_ID_TVA ? `${i.ligne} (part État)` : i.ligne,
                cumul: i.montantCumul / 1e9,
                cumulN1: i.montantCumulN1 === null ? null : i.montantCumulN1 / 1e9,
                variation: variationPct(i.montantCumul, i.montantCumulN1),
              }))}
              cleLigne={(l) => l.impot}
            />
          </VueTableau>
          <p className="mt-3 text-xs text-ink-muted">
            La ligne TVA ne couvre que la part revenant au budget général de
            l&apos;État&nbsp;: les fractions de TVA affectées à d&apos;autres
            administrations (sécurité sociale, collectivités territoriales)
            n&apos;y figurent pas. Les recettes non fiscales (
            {kpis.nonFiscales === null ? "montant non publié ce mois-ci" : enMd(kpis.nonFiscales)}
            ) ne sont pas détaillées dans cette source&nbsp;: la situation
            mensuelle n&apos;en publie que le total.
          </p>
        </Card>
      )}

      {/* Séries longues — années complètes depuis 2013 */}
      {longues && anneesCompletes.length > 0 && (
        <Card
          titre="Recettes nettes par année depuis 2013"
          sousTitre="Cumul au 31 décembre de chaque année complète, en Md€ — recettes nettes des remboursements et dégrèvements"
          droite={badge}
        >
          <LineChart
            labels={labelsAnnees}
            series={[
              {
                nom: "Recettes nettes du budget général",
                valeurs: anneesCompletes.map((a) =>
                  a.totalNettes === null ? null : a.totalNettes / 1e9,
                ),
              },
              {
                nom: "dont recettes fiscales nettes",
                valeurs: anneesCompletes.map((a) =>
                  a.fiscalesNettes === null ? null : a.fiscalesNettes / 1e9,
                ),
                couleur: "var(--viz-autre)",
              },
            ]}
            formatValeur={(v) => `${formatNombre(v, 0)}${ESPACE_FINE}Md€`}
            ariaLabel={`Recettes nettes annuelles du budget général, ${labelsAnnees[0]}–${labelsAnnees[labelsAnnees.length - 1]}`}
          />
          <VueTableau>
            <DataTable
              colonnes={[
                { cle: "annee", entete: "Année" },
                { cle: "total", entete: "Recettes nettes (Md€)", type: "montant", decimales: 2 },
                {
                  cle: "fiscales",
                  entete: "dont fiscales nettes (Md€)",
                  type: "montant",
                  decimales: 2,
                },
              ]}
              lignes={anneesCompletes.map((a) => ({
                annee: String(a.annee),
                total: a.totalNettes === null ? null : a.totalNettes / 1e9,
                fiscales: a.fiscalesNettes === null ? null : a.fiscalesNettes / 1e9,
              }))}
              cleLigne={(l) => l.annee}
            />
          </VueTableau>
          {longues.enCours && longues.enCours.totalNettes !== null && (
            <p className="mt-3 text-xs text-ink-muted">
              {longues.enCours.annee} est en cours et n&apos;est pas tracée
              avec les années pleines&nbsp;: cumul provisoire de{" "}
              {enMd(longues.enCours.totalNettes)} au{" "}
              {formatDateFr(longues.enCours.dateFinMois)}.
            </p>
          )}
        </Card>
      )}

      {/* Encart pédagogique — périmètre exact de ce qui est affiché */}
      <Card titre={"Que couvrent ces montants ?"}>
        <div className="flex max-w-3xl flex-col gap-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            «&nbsp;Nettes&nbsp;» signifie nettes des remboursements et
            dégrèvements d&apos;impôts&nbsp;: la DGFiP déduit des recettes
            brutes les sommes reversées aux contribuables (crédits
            d&apos;impôt, restitutions, corrections). Tous les totaux de cette
            page suivent cette convention.
          </p>
          <p>
            Le périmètre est le seul budget général de l&apos;État. Les
            recettes de la sécurité sociale et des collectivités territoriales
            relèvent d&apos;autres comptes et d&apos;autres textes&nbsp;: elles
            ne figurent pas ici, et les montants de cette page ne peuvent pas
            leur être comparés ni s&apos;y additionner. Les fonds de concours
            et attributions de produits — versements de tiers que l&apos;État
            emploie à une dépense déterminée — sont publiés sur une ligne
            propre, hors du total des recettes nettes.
          </p>
          <p>
            La situation mensuelle est provisoire tant que l&apos;exercice
            n&apos;est pas clos&nbsp;: les cumuls de l&apos;année en cours
            peuvent être révisés d&apos;une publication à l&apos;autre, et la
            dernière situation paraît avec cinq à sept semaines de latence
            (dernière disponible&nbsp;: {formatDateFr(kpis.dateFinMois)}).
            Le détail des recettes non fiscales et le produit par impôt au-delà
            des cinq lignes ci-dessus ne sont pas publiés dans cette source —
            cette page ne les invente pas.
          </p>
        </div>
      </Card>
    </div>
  );
}
