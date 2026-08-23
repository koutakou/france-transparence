import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { JsonLd } from "@/components/JsonLd";
import { NoticeLecture } from "@/components/ui/NoticeLecture";
import { DataTable, type Colonne } from "@/components/ui/DataTable";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { KpiTile } from "@/components/ui/KpiTile";
import { LineChart } from "@/components/ui/LineChart";
import { StatStrip } from "@/components/ui/StatStrip";
import { ESPACE_FINE, formatDateFr, formatEuros, formatNombre } from "@/lib/format";
import {
  getAgregatApu,
  perimetreAgregat,
} from "@/lib/queries/agregats-apu";
import {
  getBilanCge,
  perimetreCge,
} from "@/lib/queries/cge";
import {
  getDeficitMaastricht,
  perimetreDeficit,
} from "@/lib/queries/deficit-maastricht";
import {
  getDetteMaastricht,
  libelleTrimestre,
  perimetreDette,
} from "@/lib/queries/dette-maastricht";
import {
  getDepensesParTitre,
  getKpisBudgetMensuel,
  getMinisteresDestination2025,
  getMissionsPlf2026,
  getSerieDepensesNettes,
  getSourcesBudget,
  getSubventionsAssociations,
} from "@/lib/queries/depenses";
import { jsonLdPage, metadonneesPage } from "@/lib/seo";

// Rendu statique : la donnée ne change qu'à l'ingestion, le site est
// reconstruit après chaque ingestion (docs/deploiement/DECISION.md).

// Chemin, titre et description nommés UNE FOIS : les métadonnées et le
// balisage JSON-LD décrivent la même page, ils ne peuvent donc pas la
// décrire différemment le jour où l'un des deux est retouché.
const CHEMIN = "/depenses/";
const TITRE = "Dépenses de l'État";
const DESCRIPTION =
  "Exécution budgétaire mensuelle de l'État (DGFiP), budget voté par mission, dépenses par ministère et subventions aux associations — données publiques réelles.";

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

/** `240537726398.7` → `240,54 Md€` (précision maîtrisée pour les KPI). */
function enMd(v: number, decimales = 2): string {
  return `${formatNombre(v / 1e9, decimales)}${ESPACE_FINE}Md€`;
}

/** Montant en Md€ avec la valeur exacte en infobulle. */
function MontantMd({ valeur, decimales = 2 }: { valeur: number; decimales?: number }) {
  return <span title={`${formatNombre(valeur)}${ESPACE_FINE}€`}>{enMd(valeur, decimales)}</span>;
}

/** Variation en % vs N−1 (relative à |N−1| : garde son sens sur un solde négatif). */
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
 * Dépenses de l'État — exécution mensuelle (S13), budget par mission
 * (S20, PLF 2026), destination 2025 (S21), subventions aux associations
 * (S23), et blocs cloisonnés S41/S42/S44/S22. Server Component : les
 * lectures S13/S20/S21/S23 viennent de `@/lib/queries/depenses` ; S22
 * vient de `@/lib/queries/cge`. Aucune donnée n'est fabriquée.
 */
export default async function PageDepenses() {
  const sources = getSourcesBudget();
  const kpis = getKpisBudgetMensuel();

  if (!sources || !kpis) {
    return (
      <section className="flex flex-col gap-4">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Dépenses de l&apos;État
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          La base locale n&apos;est pas encore construite — lancer{" "}
          <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code>{" "}
          pour ingérer les sources budgétaires.
        </div>
      </section>
    );
  }

  const serie = getSerieDepensesNettes(3);
  const parTitre = getDepensesParTitre();
  const dette = getDetteMaastricht();
  const deficit = getDeficitMaastricht();
  const depensesApu = getAgregatApu("TE");
  const bilanCge = getBilanCge();
  const missions = getMissionsPlf2026(10);
  const ministeres = getMinisteresDestination2025(10);
  const subventions = getSubventionsAssociations(10);

  const vsN1 = `même période ${kpis.annee - 1}`;
  const deltaDepenses = variationPct(kpis.depensesNettes, kpis.depensesNettesN1);
  const deltaRecettes = variationPct(kpis.recettesNettes, kpis.recettesNettesN1);
  const deltaSolde = variationPct(kpis.solde, kpis.soldeN1);

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

  // ---- Décomposition par titre : parts trop proches pour un anneau
  // (personnel 33,7 % vs intervention 30,4 % — DATAVIZ §2) → BarList.
  const totalTitres = (parTitre?.titres ?? []).reduce((somme, t) => somme + t.montantCumul, 0);

  return (
    <div className="flex flex-col gap-6">
      <JsonLd donnees={BALISAGE} />
      {/* En-tête de module */}
      <section className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="max-w-2xl">
          <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
            Dépenses de l&apos;État
          </h1>
          <p className="mt-2 text-sm text-ink-secondary">
            Exécution budgétaire publiée chaque mois par la DGFiP&nbsp;: les
            montants sont des cumuls depuis le 1er janvier, comparés à la même
            période de l&apos;année précédente. Ces situations paraissent avec
            cinq à sept semaines de latence — dernière publiée&nbsp;:{" "}
            {formatDateFr(kpis.dateFinMois)}.
          </p>
          <NoticeLecture
            ancre="depenses"
            commentLire={
              <p>
                Les montants sont des cumuls depuis le 1er janvier, pas un
                rythme quotidien. Les mois de l’année en cours sont
                provisoires jusqu’à la clôture. Un delta d’une année sur
                l’autre n’est ni une hausse «&nbsp;bonne&nbsp;» ni une baisse
                «&nbsp;mauvaise&nbsp;» : il est affiché neutre.
              </p>
            }
            provenance={
              <p>
                Situations mensuelles budgétaires de la DGFiP, projet de loi
                de finances (missions, budget vert), jaune budgétaire des
                subventions aux associations. Les paiements du système Chorus
                ne sont pas en open data.
              </p>
            }
            limites={
              <p>
                Le détail des paiements n’existe pas en donnée ouverte. La
                mission «&nbsp;Pensions&nbsp;» est un compte d’affectation
                spéciale, pas une politique comparable aux autres. Les
                administrations de sécurité sociale, la dépense propre des
                opérateurs et les entreprises publiques sont hors champ.
              </p>
            }
          />
        </div>
        {sources.S13 && (
          <FreshnessBadge
            dateDonnees={sources.S13.date_donnees}
            source="DGFiP — situations mensuelles"
            frequence={sources.S13.frequence}
            url={sources.S13.url}
          />
        )}
      </section>

      {/* KPI : dépenses nettes, recettes, solde (deltas neutres — §3.5) */}
      <StatStrip
        stats={[
          {
            label: `Dépenses nettes cumulées au ${formatDateFr(kpis.dateFinMois)}`,
            valeur: <MontantMd valeur={kpis.depensesNettes} />,
            montantVedette: true,
            perimetre: "budget général, cumul depuis le 1er janvier",
            delta: deltaDepenses === null ? undefined : { valeur: deltaDepenses, vs: vsN1 },
          },
          ...(kpis.recettesNettes === null
            ? []
            : [
                {
                  label: `Recettes nettes cumulées au ${formatDateFr(kpis.dateFinMois)}`,
                  valeur: <MontantMd valeur={kpis.recettesNettes} />,
                  perimetre: "budget général, cumul depuis le 1er janvier",
                  delta: deltaRecettes === null ? undefined : { valeur: deltaRecettes, vs: vsN1 },
                },
              ]),
          ...(kpis.solde === null
            ? []
            : [
                {
                  label: `Solde budgétaire au ${formatDateFr(kpis.dateFinMois)}`,
                  valeur: <MontantMd valeur={kpis.solde} />,
                  perimetre: "budget général, cumul depuis le 1er janvier",
                  delta: deltaSolde === null ? undefined : { valeur: deltaSolde, vs: vsN1 },
                },
              ]),
        ]}
      />

      {/* Série mensuelle des cumuls, 3 années */}
      {serie && serie.length > 0 && (
        <Card
          titre="Dépenses nettes cumulées par mois"
          sousTitre="Budget général — cumul depuis le 1er janvier, en Md€"
          droite={
            sources.S13 && (
              <FreshnessBadge
                dateDonnees={sources.S13.date_donnees}
                source="DGFiP — situations mensuelles"
                frequence={sources.S13.frequence}
                url={sources.S13.url}
              />
            )
          }
        >
          <LineChart
            labels={MOIS_COURTS}
            series={seriesCumul}
            formatValeur={(v) => `${formatNombre(v, 1)}${ESPACE_FINE}Md€`}
            ariaLabel={`Dépenses nettes cumulées du budget général par mois, ${(serie ?? [])
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

      {/* Décomposition par titre */}
      {parTitre && (
        <Card
          titre="Décomposition par titre"
          sousTitre={`Dépenses nettes du budget général au ${formatDateFr(parTitre.dateFinMois)} — cumul depuis le 1er janvier`}
          droite={
            sources.S13 && (
              <FreshnessBadge
                dateDonnees={sources.S13.date_donnees}
                source="DGFiP — situations mensuelles"
                frequence={sources.S13.frequence}
                url={sources.S13.url}
              />
            )
          }
        >
          <BarList
            items={parTitre.titres.map((t) => ({ libelle: t.ligne, valeur: t.montantCumul }))}
            formatValeur={(v) => formatEuros(v, "Md")}
          />
          <VueTableau>
            <DataTable
              colonnes={[
                { cle: "titre", entete: "Titre" },
                {
                  cle: "cumul",
                  entete: `Cumul au ${formatDateFr(parTitre.dateFinMois)} (Md€)`,
                  type: "montant",
                  decimales: 2,
                },
                { cle: "cumulN1", entete: "Même cumul N−1 (Md€)", type: "montant", decimales: 2 },
                { cle: "part", entete: "Part", type: "pourcent", decimales: 1 },
              ]}
              lignes={parTitre.titres.map((t) => ({
                titre: t.ligne,
                cumul: t.montantCumul / 1e9,
                cumulN1: t.montantCumulN1 === null ? null : t.montantCumulN1 / 1e9,
                part: totalTitres > 0 ? (t.montantCumul / totalTitres) * 100 : 0,
              }))}
              cleLigne={(l) => l.titre}
            />
          </VueTableau>
        </Card>
      )}

      {/* Encours Maastricht (S41) — stock APU, cloisonné des flux S13 */}
      {dette && (
        <>
          <div className="flex items-center gap-3" role="separator">
            <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
            <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
              Autre objet · stock des APU, pas un flux de l&apos;État
            </span>
            <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
          </div>

          <Card
            titre="Encours de dette des APU (Maastricht)"
            sousTitre="Stock consolidé brut à la valeur faciale, fin de trimestre — distinct des charges d'intérêts du budget général ci-dessus"
            droite={
              <FreshnessBadge
                dateDonnees={dette.meta.date_donnees}
                source="Eurostat — gov_10q_ggdebt"
                frequence={dette.meta.frequence}
                url={dette.meta.url}
              />
            }
          >
            <div className="mb-4 rounded-xl border border-card-border bg-raised p-4">
              <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
                Pourquoi ce bloc est séparé du reste de la page
              </h3>
              <p className="text-xs leading-relaxed text-ink-secondary">
                Tout ce qui précède décrit le{" "}
                <strong className="font-medium text-ink">budget de l&apos;État</strong>{" "}
                (source S13, DGFiP)&nbsp;: des flux, cumulés depuis le 1er
                janvier. Ce bloc est un{" "}
                <strong className="font-medium text-ink">stock</strong>
                &nbsp;: l&apos;encours de dette brute consolidée des
                administrations publiques (secteur ESA S13&nbsp;: État, Odac,
                APUL, ASSO), publié par Eurostat. Ce n&apos;est pas la dette
                de l&apos;État seul, et ce n&apos;est pas la ligne «&nbsp;charges
                de la dette de l&apos;État&nbsp;» du graphique ci-dessus.
              </p>
            </div>
            <KpiTile
              nu
              label="Encours de dette des APU (Maastricht)"
              valeur={`${formatNombre(dette.encoursMd, 1)}${ESPACE_FINE}Md€`}
              montantVedette
              perimetre={perimetreDette(dette.dernier)}
              delta={
                dette.deltaPct === null
                  ? undefined
                  : {
                      valeur: dette.deltaPct,
                      vs: dette.precedent
                        ? `trimestre ${libelleTrimestre(dette.precedent.trimestre)}`
                        : "trimestre précédent",
                    }
              }
            />
            <div className="mt-4">
            <NoticeLecture
              ancre="dette-maastricht"
              commentLire={
                <p>
                  C’est un stock en fin de trimestre, pas un flux. L’unité
                  affichée (Md€) est le million d’euros Eurostat divisé par
                  1&nbsp;000 — pas l’euro des situations DGFiP divisé par un
                  milliard.{" "}
                  {dette.dernier.statut === "p" ? (
                    <>
                      Le trimestre {libelleTrimestre(dette.dernier.trimestre)}{" "}
                      est flaggé provisoire (p).{" "}
                    </>
                  ) : null}
                  Un delta d’un trimestre sur l’autre n’est ni «&nbsp;bon&nbsp;»
                  ni «&nbsp;mauvais&nbsp;» : il est affiché neutre.
                </p>
              }
              provenance={
                <p>
                  Eurostat, datacode gov_10q_ggdebt (DOI{" "}
                  10.2908/GOV_10Q_GGDEBT), extrait geo=FR, sector=S13
                  (ESA&nbsp;: administrations publiques), na_item=GD, unit=MIO_EUR.
                  Réutilisation&nbsp;: décision 2011/833/UE.
                </p>
              }
              limites={
                <p>
                  Ce n’est pas la dette de l’État seul (sous-secteur S.1311).
                  Ce n’est pas la charge d’intérêts DGFiP déjà sur cette page
                  (flux, cumul depuis le 1er janvier, budget général). Ce n’est
                  pas le déficit (bloc suivant, flux annuel B9). Ce n’est pas
                  un montant par habitant, ni un pourcentage du PIB.
                </p>
              }
            />
            </div>
          </Card>
        </>
      )}

      {/* Déficit Maastricht (S42) — flux annuel APU, cloisonné du solde S13 et du stock S41 */}
      {deficit && (
        <>
          <div className="flex items-center gap-3" role="separator">
            <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
            <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
              Autre objet · flux annuel des APU, pas le solde de l&apos;État
            </span>
            <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
          </div>

          <Card
            titre="Déficit public des APU (Maastricht)"
            sousTitre="Capacité (+) / besoin (−) de financement annuel — distinct du solde du budget général et de l'encours ci-dessus"
            droite={
              <FreshnessBadge
                dateDonnees={deficit.meta.date_donnees}
                source="Eurostat — gov_10dd_edpt1"
                frequence={deficit.meta.frequence}
                url={deficit.meta.url}
              />
            }
          >
            <div className="mb-4 rounded-xl border border-card-border bg-raised p-4">
              <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
                Pourquoi ce bloc est séparé du reste de la page
              </h3>
              <p className="text-xs leading-relaxed text-ink-secondary">
                Le solde du budget général (source S13, DGFiP) est un flux
                de l&apos;État, cumulé depuis le 1er janvier. L&apos;encours
                ci-dessus (S41) est un stock. Ce bloc est un{" "}
                <strong className="font-medium text-ink">
                  flux annuel des administrations publiques
                </strong>{" "}
                (secteur ESA S13&nbsp;: État, Odac, APUL, ASSO), publié par
                Eurostat sous l&apos;indicateur B9. Les trois objets ne
                s&apos;additionnent pas.
              </p>
            </div>
            <KpiTile
              nu
              label={
                deficit.estDeficit
                  ? "Déficit public des APU (Maastricht)"
                  : "Capacité de financement des APU (Maastricht)"
              }
              valeur={`${formatNombre(
                deficit.estDeficit ? deficit.deficitMd : deficit.b9Md,
                1,
              )}${ESPACE_FINE}Md€`}
              montantVedette
              perimetre={perimetreDeficit(deficit.dernier)}
              delta={
                deficit.deltaPct === null
                  ? undefined
                  : {
                      valeur: deficit.deltaPct,
                      vs: deficit.precedent
                        ? `année ${deficit.precedent.annee}`
                        : "année précédente",
                    }
              }
            />
            <VueTableau>
              <DataTable
                colonnes={[
                  { cle: "annee", entete: "Année" },
                  {
                    cle: "b9md",
                    entete: "B9 (Md€)",
                    type: "montant",
                    decimales: 1,
                  },
                  {
                    cle: "pc",
                    entete: "% du PIB",
                    type: "nombre",
                    decimales: 1,
                  },
                ]}
                lignes={deficit.serie.slice(-12).map((o) => ({
                  annee: o.annee,
                  b9md: o.valeur_mio_eur / 1000,
                  pc: o.valeur_pc_gdp,
                }))}
                cleLigne={(l) => String(l.annee)}
              />
            </VueTableau>
            <div className="mt-4">
            <NoticeLecture
              ancre="deficit-maastricht"
              commentLire={
                <p>
                  C’est un flux d’année civile, pas un stock et pas un cumul
                  depuis le 1er janvier. B9 est signé&nbsp;: un nombre
                  négatif est un besoin de financement (déficit), un nombre
                  positif une capacité (excédent). La tuile affiche la
                  valeur absolue quand B9 est négatif, sous le libellé
                  «&nbsp;déficit&nbsp;». L’unité affichée (Md€) est le
                  million d’euros Eurostat divisé par 1&nbsp;000. Le
                  pourcentage du PIB est un fait de la même série, pas une
                  comparaison à un seuil. Un delta d’une année sur l’autre
                  n’est ni «&nbsp;bon&nbsp;» ni «&nbsp;mauvais&nbsp;» : il
                  est affiché neutre.
                </p>
              }
              provenance={
                <p>
                  Eurostat, datacode gov_10dd_edpt1 (DOI{" "}
                  10.2908/GOV_10DD_EDPT1), extraits geo=FR, sector=S13
                  (ESA&nbsp;: administrations publiques), na_item=B9,
                  unit=MIO_EUR et unit=PC_GDP. C’est la notification
                  d’avril (EDP), pas la date de diffusion. Réutilisation&nbsp;:
                  décision 2011/833/UE.
                </p>
              }
              limites={
                <p>
                  Ce n’est pas le solde du budget général (S13, État, cumul
                  depuis le 1er janvier). Ce n’est pas l’encours de dette
                  (S41, stock trimestriel). Ce n’est pas le déficit de
                  l’État seul (sous-secteur S.1311). Ce n’est pas un
                  montant par habitant. Le pourcentage du PIB n’est comparé
                  à aucun seuil.
                </p>
              }
            />
            </div>
          </Card>
        </>
      )}

      {/* Dépenses APU ESA (S44, TE) — flux annuel APU, cloisonné de l'exécution S13 et de Maastricht B9/GD */}
      {depensesApu && (
        <>
          <div className="flex items-center gap-3" role="separator">
            <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
            <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
              Autre objet · flux annuel des APU, pas l&apos;exécution de l&apos;État
            </span>
            <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
          </div>

          <Card
            titre="Dépenses des APU (ESA)"
            sousTitre="Total des dépenses des administrations publiques, flux d'année civile — distinct de l'exécution du budget général"
            droite={
              <FreshnessBadge
                dateDonnees={depensesApu.meta.date_donnees}
                source="Eurostat — gov_10a_main"
                frequence={depensesApu.meta.frequence}
                url={depensesApu.meta.url}
              />
            }
          >
            <div className="mb-4 rounded-xl border border-card-border bg-raised p-4">
              <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
                Pourquoi ce bloc est séparé du reste de la page
              </h3>
              <p className="text-xs leading-relaxed text-ink-secondary">
                Le budget général (source S13, DGFiP) est un flux de
                l&apos;État, cumulé depuis le 1er janvier. L&apos;encours
                (S41) et le déficit (S42) ci-dessus relèvent de Maastricht
                (GD, B9). Ce bloc est un{" "}
                <strong className="font-medium text-ink">
                  flux annuel des administrations publiques
                </strong>{" "}
                (secteur ESA S13&nbsp;: État, Odac, APUL, ASSO), publié par
                Eurostat sous l&apos;indicateur TE (total des dépenses). Ce
                n&apos;est pas Maastricht. Les objets ne s&apos;additionnent
                pas.
              </p>
            </div>
            <KpiTile
              nu
              label="Dépenses des APU (ESA)"
              valeur={`${formatNombre(depensesApu.montantMd, 1)}${ESPACE_FINE}Md€`}
              montantVedette
              perimetre={perimetreAgregat(depensesApu.dernier, "TE")}
              delta={
                depensesApu.deltaPct === null
                  ? undefined
                  : {
                      valeur: depensesApu.deltaPct,
                      vs: depensesApu.precedent
                        ? `année ${depensesApu.precedent.annee}`
                        : "année précédente",
                    }
              }
            />
            <VueTableau>
              <DataTable
                colonnes={[
                  { cle: "annee", entete: "Année" },
                  {
                    cle: "temd",
                    entete: "TE (Md€)",
                    type: "montant",
                    decimales: 1,
                  },
                  {
                    cle: "pc",
                    entete: "% du PIB",
                    type: "nombre",
                    decimales: 1,
                  },
                ]}
                lignes={depensesApu.serie.slice(-12).map((o) => ({
                  annee: o.annee,
                  temd: o.valeur_mio_eur / 1000,
                  pc: o.valeur_pc_gdp,
                }))}
                cleLigne={(l) => String(l.annee)}
              />
            </VueTableau>
            <div className="mt-4">
            <NoticeLecture
              ancre="depenses-apu-esa"
              commentLire={
                <p>
                  C’est un flux d’année civile, pas un stock et pas un cumul
                  depuis le 1er janvier. TE est le total des dépenses des
                  administrations publiques. L’unité affichée (Md€) est le
                  million d’euros Eurostat divisé par 1&nbsp;000. Le
                  pourcentage du PIB est un fait de la même série. Un delta
                  d’une année sur l’autre n’est ni «&nbsp;bon&nbsp;» ni
                  «&nbsp;mauvais&nbsp;» : il est affiché neutre.
                </p>
              }
              provenance={
                <p>
                  Eurostat, datacode gov_10a_main (DOI{" "}
                  10.2908/GOV_10A_MAIN), extraits geo=FR, sector=S13
                  (ESA&nbsp;: administrations publiques), na_item=TE,
                  unit=MIO_EUR et unit=PC_GDP. C’est la publication annuelle
                  des GFS (juillet), pas la date de diffusion.
                  Réutilisation&nbsp;: décision 2011/833/UE.
                </p>
              }
              limites={
                <p>
                  Ce n’est pas l’exécution du budget général (S13, État,
                  cumul depuis le 1er janvier). Ce n’est pas une ventilation
                  COFOG. Ce n’est pas la dépense de l’État seul (sous-secteur
                  S.1311). Ce n’est pas un montant par habitant. Ce n’est
                  pas le déficit (B9) ni l’encours (GD) au sens de
                  Maastricht.
                </p>
              }
            />
            </div>
          </Card>
        </>
      )}

      {/* Bilan CGE (S22) — stock patrimonial de l'État, cloisonné de S13 et de Maastricht */}
      {bilanCge && (
        <>
          <div className="flex items-center gap-3" role="separator">
            <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
            <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
              Autre objet · bilan patrimonial de l&apos;État, pas un flux ni Maastricht
            </span>
            <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
          </div>

          <Card
            titre="Situation nette de l'État (CGE)"
            sousTitre="Comptabilité générale — stock au 31 décembre, distinct du budget et des agrégats Maastricht des APU"
            droite={
              <FreshnessBadge
                dateDonnees={bilanCge.meta.date_donnees}
                source="DGFiP — compte général de l'État"
                frequence={bilanCge.meta.frequence}
                url={bilanCge.meta.url}
              />
            }
          >
            <div className="mb-4 rounded-xl border border-card-border bg-raised p-4">
              <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
                Pourquoi ce bloc est séparé du reste de la page
              </h3>
              <p className="text-xs leading-relaxed text-ink-secondary">
                Tout ce qui précède décrit soit le{" "}
                <strong className="font-medium text-ink">budget de l&apos;État</strong>{" "}
                (source S13, caisse, cumul depuis le 1er janvier), soit des
                agrégats{" "}
                <strong className="font-medium text-ink">Maastricht / ESA des APU</strong>{" "}
                (S41, S42, S44). Ce bloc est le{" "}
                <strong className="font-medium text-ink">
                  bilan patrimonial de l&apos;État
                </strong>
                , en comptabilité générale (droits constatés), arrêté au
                31 décembre. Situation nette = total actif (I) − total
                passif hors situation nette (II). Les objets ne
                s&apos;additionnent pas.
              </p>
            </div>
            <KpiTile
              nu
              label="Situation nette de l'État (CGE)"
              valeur={`${formatNombre(bilanCge.situationNetteMd, 1)}${ESPACE_FINE}Md€`}
              montantVedette
              perimetre={perimetreCge(bilanCge.dernier)}
              delta={
                bilanCge.deltaPct === null
                  ? undefined
                  : {
                      valeur: bilanCge.deltaPct,
                      vs: bilanCge.precedent
                        ? `année ${bilanCge.precedent.annee}`
                        : "année précédente",
                    }
              }
            />
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <KpiTile
                nu
                label="Total actif (I)"
                valeur={`${formatNombre(bilanCge.actifMd, 1)}${ESPACE_FINE}Md€`}
                perimetre={`31/12/${bilanCge.dernier.annee} · CGE · stock · Md€`}
              />
              <KpiTile
                nu
                label="Total passif hors situation nette (II)"
                valeur={`${formatNombre(bilanCge.passifHorsSnMd, 1)}${ESPACE_FINE}Md€`}
                perimetre={`31/12/${bilanCge.dernier.annee} · CGE · stock · Md€`}
              />
            </div>
            <VueTableau>
              <DataTable
                colonnes={[
                  { cle: "annee", entete: "Année" },
                  {
                    cle: "actif",
                    entete: "Actif I (Md€)",
                    type: "montant",
                    decimales: 1,
                  },
                  {
                    cle: "passif",
                    entete: "Passif II (Md€)",
                    type: "montant",
                    decimales: 1,
                  },
                  {
                    cle: "sn",
                    entete: "Situation nette (Md€)",
                    type: "montant",
                    decimales: 1,
                  },
                  {
                    cle: "solde",
                    entete: "Solde de l'exercice (Md€)",
                    type: "montant",
                    decimales: 1,
                  },
                ]}
                lignes={bilanCge.serie.slice(-12).map((o) => ({
                  annee: o.annee,
                  actif: o.actif / 1e9,
                  passif: o.passifHorsSn / 1e9,
                  sn: o.situationNette / 1e9,
                  solde: o.soldeExercice === null ? null : o.soldeExercice / 1e9,
                }))}
                cleLigne={(l) => String(l.annee)}
              />
            </VueTableau>
            <div className="mt-4">
            <NoticeLecture
              ancre="cge"
              commentLire={
                <p>
                  C’est un stock au 31 décembre, pas un flux et pas un cumul
                  depuis le 1er janvier. La situation nette est signée&nbsp;:
                  un nombre négatif veut dire que le passif hors situation
                  nette dépasse l’actif. L’unité affichée (Md€) est l’euro
                  (colonnes mixte euros / millions dans la pièce, converties)
                  divisé par un milliard — pas le million d’euros Eurostat
                  divisé par 1&nbsp;000. «&nbsp;Publié net&nbsp;» est
                  l’intitulé des colonnes de la pièce : le montant net
                  publié pour cet exercice, pas un retraitement de
                  l’exercice suivant. Un delta d’une année sur l’autre n’est
                  ni «&nbsp;bon&nbsp;» ni «&nbsp;mauvais&nbsp;» : il est
                  affiché neutre.
                </p>
              }
              provenance={
                <p>
                  DGFiP, compte général de l’État, pièce de synthèse jointe
                  au jeu « Données de comptabilité générale de l’État sur
                  dix ans » (data.economie.gouv.fr,{" "}
                  <code>balances_des_comptes_etat</code>). Totaux I, II et
                  III lus dans l’onglet Bilan, solde de l’exercice dans
                  l’onglet Compte de résultat. Licence Ouverte 2.0.
                  Le millésime est celui de la pièce, pas la date de
                  modification du catalogue.
                </p>
              }
              limites={
                <p>
                  Ce n’est pas l’exécution du budget général (S13, caisse,
                  cumul depuis le 1er janvier). Ce n’est pas l’encours
                  Maastricht des APU (S41) ni le déficit B9 (S42) ni les
                  agrégats ESA TE/TR (S44). Ce n’est pas « la dette de
                  l’État ». Les dettes financières CGE ne sont pas
                  l’encours Maastricht. Les balances compte × programme
                  ne sont pas sommées : un total 2025 n’est pas publié tant
                  que la pièce de synthèse ne le porte pas. Ce n’est pas
                  un montant par habitant.
                </p>
              }
            />
            </div>
          </Card>
        </>
      )}

      {/* Budget voté et exécuté par mission (PLF 2026) */}
      {missions && (
        <Card
          titre="Budget voté et exécuté par mission"
          sousTitre={`${missions.etiquette} · Crédits budgétaires seuls (hors dépenses fiscales), en crédits de paiement`}
          droite={
            sources.S20 && (
              <FreshnessBadge
                dateDonnees={sources.S20.date_donnees}
                source="Budget vert — PLF 2026"
                frequence={sources.S20.frequence}
                url={sources.S20.url}
                mention="PLF 2026 — la LFI 2026 n'est pas publiée en données"
              />
            )
          }
        >
          <p className="mb-4 text-sm text-ink-secondary">
            Total des crédits de paiement du PLF 2026&nbsp;:{" "}
            <span className="font-medium text-ink">
              <MontantMd valeur={missions.totalPlf2026Cp} decimales={1} />
            </span>
            . Top 10 des missions&nbsp;:
          </p>
          <BarList
            items={missions.missions.flatMap((m) =>
              m.plf2026Cp === null ? [] : [{ libelle: m.mission, valeur: m.plf2026Cp }],
            )}
            formatValeur={(v) => formatEuros(v, "Md")}
          />
          <h3 className="mb-2 mt-5 text-xs font-medium uppercase tracking-[0.08em] text-ink-muted">
            Exécution 2024 · LFI 2025 · PLF 2026 (top 10)
          </h3>
          <DataTable
            colonnes={[
              { cle: "mission", entete: "Mission" },
              { cle: "exec2024", entete: "Exécution 2024 (Md€)", type: "montant", decimales: 2 },
              { cle: "lfi2025", entete: "LFI 2025 (Md€)", type: "montant", decimales: 2 },
              { cle: "plf2026", entete: "PLF 2026 (Md€)", type: "montant", decimales: 2 },
            ]}
            lignes={missions.missions.map((m) => ({
              mission: m.mission,
              exec2024: m.exec2024Cp === null ? null : m.exec2024Cp / 1e9,
              lfi2025: m.lfi2025Cp === null ? null : m.lfi2025Cp / 1e9,
              plf2026: m.plf2026Cp === null ? null : m.plf2026Cp / 1e9,
            }))}
            cleLigne={(l) => l.mission}
          />
        </Card>
      )}

      {/* Dépenses 2025 par ministère (destination) */}
      {ministeres && (
        <Card
          titre="Dépenses 2025 par ministère (destination)"
          sousTitre={`${ministeres.etiquette} · Crédits de paiement bruts — non comparables aux dépenses nettes ci-dessus`}
          droite={
            sources.S21 && (
              <FreshnessBadge
                dateDonnees={sources.S21.date_donnees}
                source="PLF 2025 — destination"
                frequence={sources.S21.frequence}
                url={sources.S21.url}
                mention="PLF 2025 — projet"
              />
            )
          }
        >
          <DataTable
            colonnes={[
              { cle: "ministere", entete: "Ministère" },
              { cle: "cpBg", entete: "CP budget général (Md€)", type: "montant", decimales: 2 },
              {
                cle: "cpTotal",
                entete: "CP tous budgets (Md€)",
                type: "montant",
                decimales: 2,
              },
            ]}
            lignes={ministeres.ministeres.map((m) => ({
              ministere: m.ministere,
              cpBg: m.cpBudgetGeneral / 1e9,
              cpTotal: m.cpTotal / 1e9,
            }))}
            cleLigne={(l) => l.ministere}
          />
          <p className="mt-3 text-xs text-ink-muted">
            «&nbsp;Tous budgets&nbsp;» inclut budgets annexes et comptes
            spéciaux (pensions, avances…), d&apos;où des totaux supérieurs au
            seul budget général — total général&nbsp;:{" "}
            {enMd(ministeres.totalCp, 1)} de CP bruts.
          </p>
          <p className="mt-2 text-sm text-ink-secondary">
            La même source se déplie mission par mission&nbsp;:{" "}
            <Link
              href="/depenses/destination/"
              className="underline decoration-[var(--viz-grid)] underline-offset-2 transition-colors hover:decoration-current"
            >
              explorer le budget 2025 par destination
            </Link>{" "}
            — 46 missions, leurs programmes, actions et sous-actions, et la
            ventilation par titre (nature de la dépense).
          </p>
        </Card>
      )}

      {/* Subventions de l'État aux associations */}
      {subventions && (
        <Card
          titre={`Subventions de l'État aux associations (${subventions.annee})`}
          sousTitre={`Versements ${subventions.annee}, publiés dans l'annexe « jaune » du PLF ${subventions.annee + 2} — décalage structurel de deux ans`}
          droite={
            sources.S23 && (
              <FreshnessBadge
                dateDonnees={sources.S23.date_donnees}
                source="Jaune PLF 2025 — associations"
                frequence={sources.S23.frequence}
                url={sources.S23.url}
                mention={`versements ${subventions.annee}`}
              />
            )
          }
        >
          <div className="mb-4 grid gap-px overflow-hidden rounded-xl border border-card-border sm:grid-cols-2" style={{ background: "var(--border-card)" }}>
            <div className="bg-card">
              <KpiTile
                nu
                label={`Total versé en ${subventions.annee}`}
                valeur={<MontantMd valeur={subventions.total} />}
                montantVedette
              />
            </div>
            <div className="bg-card">
              <KpiTile
                nu
                label={`Nombre de versements en ${subventions.annee}`}
                valeur={formatNombre(subventions.nbVersements)}
              />
            </div>
          </div>
          <DataTable
            colonnes={[
              { cle: "siren", entete: "SIREN", largeur: "8rem" },
              { cle: "denomination", entete: "Bénéficiaire" },
              { cle: "montantM", entete: `Montant ${subventions.annee} (M€)`, type: "montant", decimales: 1 },
              { cle: "nb", entete: "Versements", type: "nombre" },
            ]}
            lignes={subventions.top.map((t) => ({
              siren: t.siren,
              denomination: t.denomination,
              montantM: t.montant / 1e6,
              nb: t.nbVersements,
            }))}
            cleLigne={(l, i) => `${l.siren ?? "sans-siren"}-${i}`}
          />
          <p className="mt-3 text-xs text-ink-muted">
            Le premier bénéficiaire, «&nbsp;ASS INTERNATIONALE DE
            DEVELOPPEMEN&nbsp;» (libellé tronqué dans la source), est
            l&apos;Association internationale de développement, le guichet du
            groupe Banque mondiale qui finance les pays à faible revenu&nbsp;:
            la ligne retrace la contribution française à cette institution,
            versée via le programme 110 («&nbsp;Aide économique et financière
            au développement&nbsp;», mission Aide publique au développement).
            SIREN absent («&nbsp;—&nbsp;»)&nbsp;: bénéficiaire sans SIREN dans
            la source (ex. organismes internationaux). Le champ
            «&nbsp;associations&nbsp;» s&apos;entend au sens large du jaune
            budgétaire.
          </p>
        </Card>
      )}

      {/* Encart pédagogique — faits constatés (docs/recherche/01-budget-etat.md) */}
      <Card titre={"Pourquoi pas de dépenses « en direct » ?"}>
        <div className="max-w-3xl text-sm leading-relaxed text-ink-secondary">
          <p>
            Le détail des paiements de l&apos;État (système Chorus) n&apos;est
            pas publié en open data&nbsp;: aucun jeu de données de paiements
            n&apos;existe sur data.economie.gouv.fr, et l&apos;outil Data-État
            est réservé aux agents autorisés. La donnée publique la plus
            fraîche est la situation mensuelle budgétaire de la DGFiP&nbsp;:
            des agrégats nationaux par grands postes, publiés avec environ six
            semaines de décalage (dernière disponible&nbsp;:{" "}
            {formatDateFr(kpis.dateFinMois)}). Le détail mensuel par mission et
            programme n&apos;existe qu&apos;en PDF, dont le téléchargement
            automatisé est bloqué par la protection anti-robots
            d&apos;economie.gouv.fr. Le niveau le plus fin — l&apos;action —
            n&apos;est publié qu&apos;une fois par an, via le budget vert
            annexé au PLF.
          </p>
        </div>
      </Card>
    </div>
  );
}
