import type { Metadata } from "next";
import Link from "next/link";
import { BarChart } from "@/components/ui/BarChart";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { JsonLd } from "@/components/JsonLd";
import { NoticeLecture } from "@/components/ui/NoticeLecture";
import { DataTable, type Colonne } from "@/components/ui/DataTable";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { KpiTile } from "@/components/ui/KpiTile";
import { LineChart } from "@/components/ui/LineChart";
import { StatStrip } from "@/components/ui/StatStrip";
import { VueTableau } from "@/components/ui/VueTableau";
import { ESPACE_FINE, formatDateFr, formatEuros, formatNombre } from "@/lib/format";
import {
  getAgregatApu,
  perimetreAgregat,
} from "@/lib/queries/agregats-apu";
import {
  getCofogApu,
  perimetreCofog,
} from "@/lib/queries/cofog-apu";
import {
  getComptesApuInsee,
  perimetreCentrale,
} from "@/lib/queries/comptes-apu-insee";
import {
  getOdacInsee,
  perimetreOdac,
} from "@/lib/queries/odac-insee";
import {
  getBilanCge,
  perimetreCge,
} from "@/lib/queries/cge";
import {
  getProtectionSociale,
  perimetreRegimeGeneral,
  perimetreTotal,
} from "@/lib/queries/protection-sociale";
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
  perimetreSubventions,
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
  "Exécution budgétaire mensuelle de l'État (DGFiP), crédits du PLF 2026 par mission, crédits du PLF 2025 par ministère et subventions aux associations — données publiques réelles.";

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

/** Lien vers le développement déjà en ligne — la notice de page n'est pas recopiée dans chaque carte. */
function LienComprendre({ ancre }: { ancre: string }) {
  return (
    <p className="mt-3 text-[11px] text-ink-muted">
      Glossaire et méthode :{" "}
      <Link
        href={`/comprendre/#${ancre}`}
        className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
      >
        comprendre ces données
      </Link>
      .
    </p>
  );
}

/**
 * Dépenses de l'État — exécution mensuelle (S13), budget par mission
 * (S20, PLF 2026), destination 2025 (S21), subventions aux associations
 * (S23), et blocs cloisonnés S41/S42/S44/S49/S50/S51/S22/S45. Server Component : les
 * lectures S13/S20/S21/S23 viennent de `@/lib/queries/depenses` ; S22
 * vient de `@/lib/queries/cge` ; S45 de `@/lib/queries/protection-sociale` ;
 * S49 de `@/lib/queries/cofog-apu` ; S50 de `@/lib/queries/comptes-apu-insee` ;
 * S51 de `@/lib/queries/odac-insee`.
 * Aucune donnée n'est fabriquée.
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
  const cofogApu = getCofogApu();
  const comptesApuInsee = getComptesApuInsee();
  const odacInsee = getOdacInsee();
  const bilanCge = getBilanCge();
  const protectionSociale = getProtectionSociale();
  const missions = getMissionsPlf2026(10);
  const ministeres = getMinisteresDestination2025(10);
  const subventions = getSubventionsAssociations(10);

  const mentionProvisoire =
    kpis.dateFinMois.slice(5, 7) !== "12" ? "mois infra-annuels provisoires" : undefined;
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
      {/* Bande 1 — le chiffre au pli, pas le mur pédagogique. */}
      <section className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="max-w-2xl">
          <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
            Dépenses de l&apos;État
          </h1>
          <p className="mt-2 text-sm text-ink-secondary">
            Cumuls depuis le 1er janvier, budget général, comparés à la même
            période N−1 — dernière situation DGFiP&nbsp;:{" "}
            {formatDateFr(kpis.dateFinMois)} (cinq à sept semaines de latence).
          </p>
        </div>
        {sources.S13 && (
          <FreshnessBadge
            dateDonnees={sources.S13.date_donnees}
            source="DGFiP — situations mensuelles"
            frequence={sources.S13.frequence}
            url={sources.S13.url}
            mention={mentionProvisoire}
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
                  // Les deux tuiles voisines portaient la MÊME borne que celle-ci,
                  // ce qui invitait à les soustraire. La soustraction ne tombe pas
                  // juste : recettes moins dépenses = −55,99 Md€ quand le solde
                  // servi vaut −106,77 Md€, soit 50,79 Md€ d'écart. La cause est
                  // établie, et dans `budget_mensuel` que cette page lit déjà —
                  // décomposition rejouée sur la base du 25/08, résidu 3 centièmes
                  // de centime : (recettes BG − dépenses BG) − PSR 36,32 Md€
                  // + solde des comptes spéciaux −17,61 Md€ + budgets annexes 0
                  // + fonds de concours 3,14 Md€ = le solde servi. Le solde n'est
                  // donc pas borné au budget général : la borne le dit.
                  perimetre:
                    "solde budgétaire de l’État, cumul depuis le 1er janvier — au-delà du budget général : prélèvements sur recettes, solde des comptes spéciaux et fonds de concours compris",
                  delta: deltaSolde === null ? undefined : { valeur: deltaSolde, vs: vsN1 },
                },
              ]),
        ]}
      />

      {/* Bande 2 — le 240 Md€ se décompose tout de suite (G3d), pas un poster. */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2 xl:items-start">
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
                mention={mentionProvisoire}
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
                mention={mentionProvisoire}
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
      </div>

      {/* Bande 3 — notice 3 blocs APRÈS le chiffre, pas un mur sur le pli. */}
      <NoticeLecture
        ancre="depenses"
        commentLire={
          <p>
            Les montants du bandeau et des graphiques d’exécution sont des
            cumuls depuis le 1er janvier, pas un rythme quotidien. Les mois
            de l’année en cours sont provisoires jusqu’à la clôture. Les
            crédits par mission sont le PLF 2026, pas la LFI. La destination
            2025 est le PLF 2025 (projet, CP bruts, pas les dépenses nettes).
            Un delta n’est ni «&nbsp;bon&nbsp;» ni «&nbsp;mauvais&nbsp;» : il
            est affiché neutre.
          </p>
        }
        provenance={
          <p>
            Situations mensuelles budgétaires de la DGFiP, projet de loi de
            finances (missions, budget vert), jaune budgétaire des
            subventions aux associations. Les paiements Chorus ne sont pas
            en open data.
          </p>
        }
        limites={
          <p>
            Le détail des paiements n’existe pas en donnée ouverte. La
            mission «&nbsp;Pensions&nbsp;» est un compte d’affectation
            spéciale, pas une politique comparable aux autres. Ce bloc
            (budget général) ne couvre pas les prestations de protection
            sociale&nbsp;: elles figurent dans le{" "}
            <Link
              href="#protection-sociale"
              className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
            >
              bloc DREES
            </Link>
            . Hors champ&nbsp;: la loi de financement de la sécurité
            sociale en tant que texte voté, la dépense propre des
            opérateurs et les entreprises publiques.
          </p>
        }
      />

      {/* Crédits par mission (S20, PLF 2026) */}
      {missions && (
        <Card
          titre="Crédits par mission"
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
          <div className="mb-4">
            <KpiTile
              nu
              label="Crédits de paiement du PLF 2026"
              valeur={<MontantMd valeur={missions.totalPlf2026Cp} decimales={1} />}
              perimetre="PLF 2026 — projet, pas la LFI ; crédits budgétaires seuls, hors dépenses fiscales"
            />
          </div>
          <p className="mb-4 text-sm text-ink-secondary">
            Top 10 des missions, en crédits de paiement&nbsp;:
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

      {/* Crédits 2025 par ministère (S21, destination) */}
      {ministeres && (
        <Card
          titre="Crédits 2025 par ministère (destination)"
          sousTitre={`${ministeres.etiquette} · Crédits de paiement bruts — non comparables aux dépenses nettes du budget général (exécution DGFiP)`}
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
          <div className="mb-4">
            <KpiTile
              nu
              label="Crédits de paiement 2025 (bruts, tous budgets)"
              valeur={<MontantMd valeur={ministeres.totalCp} decimales={1} />}
              perimetre="PLF 2025 — projet, pas la LFI ni l’exécution ; CP bruts, non comparables aux dépenses nettes"
            />
          </div>
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
                  perimetre={perimetreSubventions(subventions.annee)}
              />
            </div>
            <div className="bg-card">
              <KpiTile
                nu
                label={`Nombre de versements en ${subventions.annee}`}
                valeur={formatNombre(subventions.nbVersements)}
                perimetre={perimetreSubventions(subventions.annee)}
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

      {/* Autres objets : galerie compacte, pas cinq héros. */}
      <div className="flex items-center gap-3" role="separator">
        <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
        <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
          Autres objets · ils ne s&apos;additionnent pas au budget général
        </span>
        <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2 xl:items-start">
      {/* S41 — stock APU, pas un flux S13. Pas de vedette : ce n'est pas le total de la page. */}
      {dette && (
        <div id="dette-maastricht" className="scroll-mt-32">
          <Card
            titre="Encours de dette des APU (Maastricht)"
            sousTitre="Stock consolidé brut à la valeur faciale, fin de trimestre — distinct des charges d'intérêts du budget général"
            droite={
              <FreshnessBadge
                dateDonnees={dette.meta.date_donnees}
                source="Eurostat — gov_10q_ggdebt"
                frequence={dette.meta.frequence}
                url={dette.meta.url}
              />
            }
          >
            <KpiTile
              nu
              label="Encours de dette des APU (Maastricht)"
              valeur={`${formatNombre(dette.encoursMd, 1)}${ESPACE_FINE}Md€`}
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
            <p className="mt-3 text-xs leading-relaxed text-ink-muted">
              Stock des administrations publiques, pas la dette de l&apos;État
              seul, pas la ligne «&nbsp;charges de la dette&nbsp;» du graphique
              d&apos;exécution.
              {dette.dernier.statut === "p" ? (
                <>
                  {" "}
                  Trimestre {libelleTrimestre(dette.dernier.trimestre)} flaggé
                  provisoire (p).
                </>
              ) : null}
            </p>
            <LienComprendre ancre="dette-maastricht" />
          </Card>
        </div>
      )}

      {/* S42 — flux annuel APU, pas le solde S13. */}
      {deficit && (
        <div id="deficit-maastricht" className="scroll-mt-32">
          <Card
            titre="Déficit public des APU (Maastricht)"
            sousTitre="Capacité (+) / besoin (−) de financement annuel — distinct du solde du budget général et de l'encours"
            droite={
              <FreshnessBadge
                dateDonnees={deficit.meta.date_donnees}
                source="Eurostat — gov_10dd_edpt1"
                frequence={deficit.meta.frequence}
                url={deficit.meta.url}
              />
            }
          >
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
            <p className="mt-3 text-xs leading-relaxed text-ink-muted">
              Flux d&apos;année civile des APU (B9), pas le solde du budget
              général, pas un stock. Le pourcentage du PIB n&apos;est comparé
              à aucun seuil.
            </p>
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
            <LienComprendre ancre="deficit-maastricht" />
          </Card>
        </div>
      )}

      {/* S44 TE — flux annuel APU, pas Maastricht, pas S13. */}
      {depensesApu && (
        <div id="depenses-apu-esa" className="scroll-mt-32">
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
            <KpiTile
              nu
              label="Dépenses des APU (ESA)"
              valeur={`${formatNombre(depensesApu.montantMd, 1)}${ESPACE_FINE}Md€`}
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
            <p className="mt-3 text-xs leading-relaxed text-ink-muted">
              Indicateur TE (ESA), pas Maastricht, pas l&apos;exécution du
              budget général, pas une ventilation COFOG.
            </p>
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
            <LienComprendre ancre="depenses-apu-esa" />
          </Card>
        </div>
      )}

      {/* S49 CFAP — ventilation par fonction, table distincte de S44. */}
      {cofogApu && (
        <div id="depenses-apu-cfap" className="scroll-mt-32">
          <Card
            titre="Dépenses des APU par fonction (CFAP)"
            sousTitre="Flux annuel des APU par fonction — table Eurostat distincte du total ESA (S44)"
            droite={
              <FreshnessBadge
                dateDonnees={cofogApu.meta.date_donnees}
                source="Eurostat — gov_10a_exp"
                frequence={cofogApu.meta.frequence}
                url={cofogApu.meta.url}
              />
            }
          >
            <KpiTile
              nu
              label="Dépenses des APU par fonction (CFAP)"
              valeur={`${formatNombre(cofogApu.montantMd, 1)}${ESPACE_FINE}Md€`}
              perimetre={perimetreCofog(cofogApu.dernier)}
              delta={
                cofogApu.deltaPct === null
                  ? undefined
                  : {
                      valeur: cofogApu.deltaPct,
                      vs: cofogApu.precedent
                        ? `année ${cofogApu.precedent.annee}`
                        : "année précédente",
                    }
              }
            />
            <p className="mt-3 text-xs leading-relaxed text-ink-muted">
              Classification des fonctions des administrations publiques
              (CFAP / COFOG-99), na_item=TE. Les dix fonctions, dans
              l&apos;ordre du producteur, recomposent ce total. Ce n&apos;est
              pas le total TE de la table gov_10a_main (S44), pas
              l&apos;exécution du budget général, pas les prestations DREES.
            </p>
            <BarList
              className="mt-4"
              items={cofogApu.divisions.map((d) => ({
                libelle: d.libelle,
                valeur: d.valeur_mio_eur / 1000,
              }))}
              formatValeur={(v) => `${formatNombre(v, 1)}${ESPACE_FINE}Md€`}
            />
            <p className="mt-2 text-xs text-ink-muted">
              Ordre CFAP GF01 à GF10, année {cofogApu.dernier.annee}. Ce
              n&apos;est pas un classement.
            </p>
            <VueTableau>
              <DataTable
                colonnes={[
                  { cle: "annee", entete: "Année" },
                  {
                    cle: "totalmd",
                    entete: "TOTAL (Md€)",
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
                lignes={cofogApu.serie.slice(-12).map((o) => ({
                  annee: o.annee,
                  totalmd: o.valeur_mio_eur / 1000,
                  pc: o.valeur_pc_gdp,
                }))}
                cleLigne={(l) => String(l.annee)}
              />
            </VueTableau>
            <LienComprendre ancre="depenses-apu-cfap" />
          </Card>
        </div>
      )}

      {/* S50 — comptes INSEE par sous-secteur, pas un second TE, pas B9. */}
      {comptesApuInsee && (
        <div id="comptes-apu-insee" className="scroll-mt-32">
          <Card
            titre="Dépenses des APU par sous-secteur (INSEE)"
            sousTitre="Comptes nationaux, présentation dépenses et recettes — distinct du total ESA (S44) et de la CFAP (S49)"
            droite={
              <FreshnessBadge
                dateDonnees={comptesApuInsee.meta.date_donnees}
                source="INSEE — comptes nationaux"
                frequence={comptesApuInsee.meta.frequence}
                url={comptesApuInsee.meta.url}
              />
            }
          >
            <KpiTile
              nu
              label="Administration publique centrale (S1311)"
              valeur={`${formatNombre(comptesApuInsee.centrale.depensesMd, 1)}${ESPACE_FINE}Md€`}
              perimetre={perimetreCentrale(comptesApuInsee.annee)}
              delta={
                comptesApuInsee.deltaCentralePct === null
                  ? undefined
                  : {
                      valeur: comptesApuInsee.deltaCentralePct,
                      vs: comptesApuInsee.precedentCentrale
                        ? `année ${comptesApuInsee.precedentCentrale.annee}`
                        : "année précédente",
                    }
              }
            />
            <p className="mt-3 text-xs leading-relaxed text-ink-muted">
              Présentation INSEE des dépenses et recettes (flux monétaires,
              imputés limités). Ce n&apos;est pas le budget général, pas le
              total TE Eurostat (S44), pas une ventilation CFAP, pas la
              dette de l&apos;État. Les trois sous-secteurs ne
              s&apos;additionnent pas&nbsp;: chaque bloc est consolidé en
              son sein. L&apos;État (S13111) est déjà dans S1311 ; il
              n&apos;est pas une ligne sœur.
            </p>
            <BarList
              className="mt-4"
              items={comptesApuInsee.sousSecteursDepenses.map((d) => ({
                libelle: d.libelle,
                valeur: d.depensesMd,
              }))}
              formatValeur={(v) => `${formatNombre(v, 1)}${ESPACE_FINE}Md€`}
            />
            <p className="mt-2 text-xs text-ink-muted">
              Ordre S1311, S1313, S1314, année {comptesApuInsee.annee}. Ce
              n&apos;est pas un classement. S1314 n&apos;est pas «&nbsp;la
              Sécu&nbsp;».
            </p>
            <VueTableau>
              <DataTable
                colonnes={[
                  { cle: "libelle", entete: "Sous-secteur" },
                  {
                    cle: "dep",
                    entete: "Dépenses (Md€)",
                    type: "montant",
                    decimales: 1,
                  },
                ]}
                lignes={comptesApuInsee.sousSecteursDepenses.map((l) => ({
                  libelle: l.libelle,
                  dep: l.depensesMd,
                }))}
                cleLigne={(l) => String(l.libelle)}
              />
            </VueTableau>
            <LienComprendre ancre="comptes-apu-insee" />
          </Card>
        </div>
      )}

      {/* S51 — ODAC INSEE S13112, déjà dans S1311, pas le jaune opérateurs. */}
      {odacInsee && (
        <div id="odac-insee" className="scroll-mt-32">
          <Card
            titre="Dépenses des ODAC (INSEE)"
            sousTitre="Organismes divers d'administration centrale, S13112 — déjà dans S1311, distinct du jaune opérateurs"
            droite={
              <FreshnessBadge
                dateDonnees={odacInsee.meta.date_donnees}
                source="INSEE — comptes nationaux"
                frequence={odacInsee.meta.frequence}
                url={odacInsee.meta.url}
              />
            }
          >
            <KpiTile
              nu
              label="Organismes divers d'administration centrale (S13112)"
              valeur={`${formatNombre(odacInsee.odac.depensesMd, 1)}${ESPACE_FINE}Md€`}
              perimetre={perimetreOdac(odacInsee.annee)}
              delta={
                odacInsee.deltaPct === null
                  ? undefined
                  : {
                      valeur: odacInsee.deltaPct,
                      vs: odacInsee.precedent
                        ? `année ${odacInsee.precedent.annee}`
                        : "année précédente",
                    }
              }
            />
            <p className="mt-3 text-xs leading-relaxed text-ink-muted">
              Ce n&apos;est pas le budget général, pas S1311, pas une ligne
              sœur de l&apos;État, pas les opérateurs du jaune PLF 2026
              (S39, liste sans €), pas un solde. On n&apos;additionne pas
              à S13111.
            </p>
            <VueTableau>
              <DataTable
                colonnes={[
                  { cle: "annee", entete: "Année" },
                  {
                    cle: "dep",
                    entete: "Dépenses (Md€)",
                    type: "montant",
                    decimales: 1,
                  },
                ]}
                lignes={[
                  ...(odacInsee.precedent
                    ? [
                        {
                          annee: odacInsee.precedent.annee,
                          dep: odacInsee.precedent.depensesMd,
                        },
                      ]
                    : []),
                  {
                    annee: odacInsee.odac.annee,
                    dep: odacInsee.odac.depensesMd,
                  },
                ]}
                cleLigne={(l) => String(l.annee)}
              />
            </VueTableau>
            <LienComprendre ancre="odac-insee" />
          </Card>
        </div>
      )}

      {/* S22 — bilan patrimonial, pas un flux, pas Maastricht. */}
      {bilanCge && (
        <div id="cge" className="scroll-mt-32">
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
            <KpiTile
              nu
              label="Situation nette de l'État (CGE)"
              valeur={`${formatNombre(bilanCge.situationNetteMd, 1)}${ESPACE_FINE}Md€`}
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
            <p className="mt-3 text-xs leading-relaxed text-ink-muted">
              Stock au 31 décembre (situation nette = actif − passif hors
              situation nette). Ce n&apos;est pas «&nbsp;la dette de
              l&apos;État&nbsp;», pas l&apos;encours Maastricht, pas
              l&apos;exécution de caisse.
            </p>
            <LienComprendre ancre="cge" />
          </Card>
        </div>
      )}
      </div>

      {/* S45 — prestations tous régimes, pas le budget, pas « la Sécu ». */}
      {protectionSociale && (
        <div id="protection-sociale" className="scroll-mt-32">
          <Card
            titre="Prestations de protection sociale"
            sousTitre="tous régimes, flux d'année civile — distinct du budget général et des agrégats ESA des APU"
            droite={
              <FreshnessBadge
                dateDonnees={protectionSociale.meta.date_donnees}
                source="DREES — comptes de la protection sociale"
                frequence={protectionSociale.meta.frequence}
                url={protectionSociale.meta.url}
              />
            }
          >
            <KpiTile
              nu
              label="Prestations de protection sociale"
              valeur={`${formatNombre(protectionSociale.montantMd, 1)}${ESPACE_FINE}Md€`}
              perimetre={perimetreTotal(protectionSociale.dernier)}
              delta={
                protectionSociale.deltaPct === null
                  ? undefined
                  : {
                      valeur: protectionSociale.deltaPct,
                      vs: protectionSociale.precedent
                        ? `année ${protectionSociale.precedent.annee}`
                        : "année précédente",
                      upIsGood: null,
                    }
              }
            />
            <div className="mt-4">
              <KpiTile
                nu
                label="dont régime général de la Sécurité sociale"
                valeur={`${formatNombre(protectionSociale.regimeGeneral.montantMd, 1)}${ESPACE_FINE}Md€`}
                perimetre={perimetreRegimeGeneral(protectionSociale.dernier.annee)}
              />
            </div>
            {protectionSociale.risques.length === 6 && (
              <>
                <BarChart
                  className="mt-4"
                  items={protectionSociale.risques.map((r) => ({
                    libelle: r.libelle,
                    valeur: r.val_mio_eur / 1000,
                  }))}
                  formatValeur={(v) => `${formatNombre(v, 1)}${ESPACE_FINE}Md€`}
                  maxEtiquettesX={6}
                  ariaLabel={`Prestations de protection sociale par risque, année ${protectionSociale.dernier.annee}, tous régimes, ordre des codes E11-1 à E11-6`}
                />
                <p className="mt-2 text-xs text-ink-muted">
                  Ordre des codes DREES (E11-1 à E11-6), année{" "}
                  {protectionSociale.dernier.annee}. Les six risques sont
                  exclusifs et recomposent le total — ce n&apos;est pas un
                  classement.
                </p>
              </>
            )}
            <VueTableau>
              <DataTable
                colonnes={[
                  { cle: "annee", entete: "Année" },
                  {
                    cle: "prestations",
                    entete: "Prestations Md€",
                    type: "montant",
                    decimales: 1,
                  },
                ]}
                lignes={protectionSociale.serie.slice(-12).map((o) => ({
                  annee: o.annee,
                  prestations: o.val_mio_eur / 1000,
                }))}
                cleLigne={(l) => String(l.annee)}
              />
              {protectionSociale.risques.length === 6 && (
                <div className="mt-3">
                  <DataTable
                    colonnes={[
                      { cle: "risque", entete: "Risque" },
                      {
                        cle: "montant",
                        entete: "Md€",
                        type: "montant",
                        decimales: 1,
                      },
                    ]}
                    lignes={protectionSociale.risques.map((r) => ({
                      risque: r.libelle,
                      montant: r.val_mio_eur / 1000,
                    }))}
                    cleLigne={(l) => l.risque}
                  />
                </div>
              )}
              {protectionSociale.regimes.length > 0 && (
                <div className="mt-3">
                  <DataTable
                    colonnes={[
                      { cle: "regime", entete: "Régime" },
                      {
                        cle: "montant",
                        entete: "Md€",
                        type: "montant",
                        decimales: 1,
                      },
                    ]}
                    lignes={protectionSociale.regimes.map((r) => ({
                      regime: r.libelle,
                      montant: r.val_mio_eur / 1000,
                    }))}
                    cleLigne={(l) => l.regime}
                  />
                </div>
              )}
            </VueTableau>
            <p className="mt-3 text-xs leading-relaxed text-ink-muted">
              Tous régimes, pas la LFSS, pas «&nbsp;la Sécu&nbsp;» : le régime
              général (S13141) est un régime parmi d&apos;autres. Ce n&apos;est
              pas l&apos;exécution du budget général.
            </p>
            <LienComprendre ancre="protection-sociale" />
          </Card>
        </div>
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
