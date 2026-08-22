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
 * (S20, PLF 2026), destination 2025 (S21) et subventions aux associations
 * (S23). Server Component : toutes les lectures viennent de
 * `@/lib/queries/depenses`, aucune donnée n'est fabriquée.
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
