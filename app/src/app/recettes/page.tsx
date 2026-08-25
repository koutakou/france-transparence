import type { Metadata } from "next";
import Link from "next/link";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { JsonLd } from "@/components/JsonLd";
import { NoticeLecture } from "@/components/ui/NoticeLecture";
import { DataTable, type Colonne } from "@/components/ui/DataTable";
import { DeltaPct } from "@/components/ui/DeltaPct";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { KpiTile } from "@/components/ui/KpiTile";
import { LineChart } from "@/components/ui/LineChart";
import { StatStrip } from "@/components/ui/StatStrip";
import { VueTableau } from "@/components/ui/VueTableau";
import { ESPACE_FINE, formatDateFr, formatNombre } from "@/lib/format";
import {
  getAgregatApu,
  perimetreAgregat,
} from "@/lib/queries/agregats-apu";
import {
  getKpisRecettes,
  getRecettesFiscalesDetail,
  getSerieRecettesNettes,
  getSeriesLonguesRecettes,
  getSourceRecettes,
  LIGNE_ID_TVA,
} from "@/lib/queries/recettes";
import {
  getRecettesPlfNonFiscales,
  perimetreNonFiscales,
  perimetreParticipations,
} from "@/lib/queries/recettes-plf";
import {
  getPrelevementsObligatoires,
  perimetrePo,
} from "@/lib/queries/comptes-apu-insee";
import {
  getIrcom,
  perimetreFoyersIrcom,
  perimetreIrcom,
} from "@/lib/queries/ircom";
import { jsonLdPage, metadonneesPage } from "@/lib/seo";

// Rendu statique : la donnée ne change qu'à l'ingestion, le site est
// reconstruit après chaque ingestion (docs/deploiement/DECISION.md).

// Chemin, titre et description nommés UNE FOIS : les métadonnées et le
// balisage JSON-LD décrivent la même page, ils ne peuvent donc pas la
// décrire différemment le jour où l'un des deux est retouché.
const CHEMIN = "/recettes/";
const TITRE = "Recettes de l'État";
const DESCRIPTION =
  "Recettes nettes du budget général de l'État (DGFiP, situations mensuelles) : recettes fiscales par grand impôt, recettes non fiscales, fonds de concours — séries depuis 2013. Le détail des non fiscales est celui du PLF, projet, pas l'exécution. L'impôt sur le revenu par territoire (IRCOM) est un autre objet : impôt net sur rôle, année des revenus.";

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
  const recettesApu = getAgregatApu("TR");
  const nonFiscalesPlf = getRecettesPlfNonFiscales();
  const ircom = getIrcom();
  const prelevements = getPrelevementsObligatoires();

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
            dégrèvements d&apos;impôts —, cumuls depuis le 1er janvier.
            Dernière situation DGFiP&nbsp;: {formatDateFr(kpis.dateFinMois)}{" "}
            (cinq à sept semaines de latence).
          </p>
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
            perimetre: "budget général, cumul depuis le 1er janvier",
            delta: deltaTotal === null ? undefined : { valeur: deltaTotal, vs: vsN1 },
          },
          ...(kpis.fiscalesNettes === null
            ? []
            : [
                {
                  label: "Recettes fiscales nettes",
                  valeur: <MontantMd valeur={kpis.fiscalesNettes} />,
                  perimetre: "budget général, cumul depuis le 1er janvier",
                  delta: deltaFiscales === null ? undefined : { valeur: deltaFiscales, vs: vsN1 },
                },
              ]),
          ...(kpis.nonFiscales === null
            ? []
            : [
                {
                  label: "Recettes non fiscales",
                  valeur: <MontantMd valeur={kpis.nonFiscales} />,
                  perimetre:
                    "exécution S13, un seul total — le détail du PLF (projet) est plus bas",
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
                  perimetre: "budget général, cumul depuis le 1er janvier",
                  delta: deltaFonds === null ? undefined : { valeur: deltaFonds, vs: vsN1 },
                },
              ]),
        ]}
      />
      <p className="text-xs leading-relaxed text-ink-muted">
        Les fonds de concours et attributions de produits sont une ligne
        propre, hors du total des recettes nettes — on ne les y additionne
        pas.
      </p>

      {/* Cumuls mensuels et décomposition par impôt, côte à côte dès xl */}
      {(serie && serie.length > 0) || detail ? (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2 xl:items-start">
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
                ) n&apos;ont, dans cette source, qu&apos;un total. Le détail
                ci-dessous est celui du PLF&nbsp;: un projet, pas cette
                exécution.
              </p>
            </Card>
          )}
        </div>
      ) : null}

      {nonFiscalesPlf && (
        <div id="recettes-plf" className="flex scroll-mt-32 flex-col gap-6">
          <div className="flex items-center gap-3" role="separator">
            <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
            <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
              Autre objet · PLF {nonFiscalesPlf.annee}, projet, pas l&apos;exécution
            </span>
            <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
          </div>

          <Card
            titre={`Recettes non fiscales prévues au PLF ${nonFiscalesPlf.annee}`}
            sousTitre="projet de loi, État A, recettes brutes — distinct du total d'exécution de la situation mensuelle"
            droite={
              <FreshnessBadge
                dateDonnees={nonFiscalesPlf.meta.date_donnees}
                source="Direction du Budget — État A du PLF"
                frequence={nonFiscalesPlf.meta.frequence}
                url={nonFiscalesPlf.meta.url}
                mention="PLF"
              />
            }
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <KpiTile
                nu
                label={`Non fiscales prévues (PLF ${nonFiscalesPlf.annee})`}
                valeur={`${formatNombre(nonFiscalesPlf.totalMd, 1)}${ESPACE_FINE}Md€`}
                perimetre={perimetreNonFiscales(nonFiscalesPlf.annee)}
              />
              <KpiTile
                nu
                label="dont participations et dividendes"
                valeur={`${formatNombre(nonFiscalesPlf.participations.totalMd, 1)}${ESPACE_FINE}Md€`}
                perimetre={perimetreParticipations(nonFiscalesPlf.annee)}
              />
            </div>
            <BarList
              className="mt-4"
              items={nonFiscalesPlf.lignes.slice(0, 8).map((l) => ({
                libelle: l.libelle,
                valeur: l.montantEuros / 1e9,
              }))}
              formatValeur={(v) => `${formatNombre(v, 2)}${ESPACE_FINE}Md€`}
            />
            <VueTableau>
              <DataTable
                colonnes={[
                  { cle: "code", entete: "Ligne" },
                  { cle: "libelle", entete: "Libellé" },
                  {
                    cle: "md",
                    entete: "PLF (Md€)",
                    type: "montant",
                    decimales: 3,
                  },
                ]}
                lignes={nonFiscalesPlf.lignes.map((l) => ({
                  code: String(l.code),
                  libelle: l.libelle,
                  md: l.montantEuros / 1e9,
                }))}
                cleLigne={(l) => l.code}
              />
            </VueTableau>
            <p className="mt-3 text-xs text-ink-muted">
              {nonFiscalesPlf.etiquette}. Un zéro publié est un zéro. Les
              recettes fiscales de ce même État A sont brutes&nbsp;: elles
              ne se comparent pas aux nettes de la situation mensuelle, et
              ne sont pas additionnées ici. Les prélèvements sur recettes
              (collectivités, Union européenne) sont un autre objet.
            </p>
            <LienComprendre ancre="recettes-plf" />
          </Card>
        </div>
      )}

      {ircom && (
        <div id="ircom" className="flex scroll-mt-32 flex-col gap-6">
          <div className="flex items-center gap-3" role="separator">
            <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
            <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
              Autre objet · IRCOM, revenus {ircom.annee}, pas la caisse
            </span>
            <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
          </div>

          <Card
            titre={`Impôt sur le revenu par territoire (IRCOM, revenus ${ircom.annee})`}
            sousTitre="impôt net sur rôle des foyers fiscaux, par commune de résidence — distinct de l'IR de caisse de la situation mensuelle"
            droite={
              <FreshnessBadge
                dateDonnees={ircom.meta.date_donnees}
                source="DGFiP — IRCOM"
                frequence={ircom.meta.frequence}
                url={ircom.meta.url}
              />
            }
          >
            <div className="grid gap-3 sm:grid-cols-3">
              <KpiTile
                nu
                label={`Impôt net publié (revenus ${ircom.annee})`}
                valeur={`${formatNombre(ircom.impotMd, 1)}${ESPACE_FINE}Md€`}
                perimetre={perimetreIrcom(ircom.annee)}
              />
              <KpiTile
                nu
                label="Foyers fiscaux"
                valeur={formatNombre(ircom.nFoyers, 0)}
                perimetre={perimetreFoyersIrcom(ircom.annee)}
              />
              <KpiTile
                nu
                label="Communes en n.c."
                valeur={formatNombre(ircom.nCommunesNc, 0)}
                perimetre="secret statistique DESF · hors de la somme d'impôt net"
              />
            </div>
            <BarList
              className="mt-4"
              items={ircom.departements.slice(0, 8).map((d) => ({
                libelle: d.nom,
                valeur: d.impotEuros / 1e9,
              }))}
              formatValeur={(v) => `${formatNombre(v, 2)}${ESPACE_FINE}Md€`}
            />
            <VueTableau>
              <DataTable
                colonnes={[
                  { cle: "dep", entete: "Dép." },
                  { cle: "nom", entete: "Département" },
                  {
                    cle: "md",
                    entete: "Impôt net (Md€)",
                    type: "montant",
                    decimales: 2,
                  },
                  {
                    cle: "foyers",
                    entete: "Foyers",
                    type: "nombre",
                    decimales: 0,
                  },
                  {
                    cle: "nc",
                    entete: "Communes n.c.",
                    type: "nombre",
                    decimales: 0,
                  },
                ]}
                lignes={ircom.departements.map((d) => ({
                  dep: d.dep,
                  nom: d.nom,
                  md: d.impotEuros / 1e9,
                  foyers: d.nFoyers,
                  nc: d.nCommunesNc,
                }))}
                cleLigne={(l) => l.dep}
              />
            </VueTableau>
            <p className="mt-3 text-xs text-ink-muted">
              {ircom.etiquette}. {formatNombre(ircom.nCommunes, 0)} communes
              Total, dont {formatNombre(ircom.nCommunesNc, 0)} dont l&apos;impôt
              net est n.c. (secret statistique). Un montant négatif, s&apos;il
              apparaît, est une restitution. Ce total n&apos;est pas
              l&apos;IR de la situation mensuelle, et n&apos;inclut pas le
              crédit d&apos;impôt relatif au PFU.
            </p>
            <LienComprendre ancre="ircom" />
          </Card>
        </div>
      )}

      <div className="flex flex-col gap-3">
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
              Ce n’est pas le détail des encaissements jour par jour. Les
              recettes de la sécurité sociale et des collectivités
              territoriales ne figurent pas ici. Les prestations de
              protection sociale (tous régimes) sont sur la page Dépenses.
              La LFSS, comme texte voté, n’est pas un module de recettes.
              Un impôt «&nbsp;net&nbsp;» n’est pas le montant mis à la
              charge du contribuable. Le détail des recettes non fiscales
              est celui du PLF (projet, recettes brutes), pas de
              l’exécution. L’IRCOM (impôt net sur rôle, par commune de
              résidence) est un autre objet, distinct de la ligne Impôt
              sur le revenu de cette situation mensuelle.
            </p>
          }
        />
      </div>

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

      {/* Recettes APU ESA (S44, TR) — flux annuel APU, cloisonné des recettes nettes S13 */}
      {recettesApu && (
        <div id="recettes-apu-esa" className="flex scroll-mt-32 flex-col gap-6">
          <div className="flex items-center gap-3" role="separator">
            <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
            <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
              Autre objet · flux annuel des APU, pas le budget général
            </span>
            <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
          </div>

          <Card
            titre="Recettes des APU (ESA)"
            sousTitre="Total des recettes des administrations publiques, flux d'année civile — distinct des recettes nettes du budget général"
            droite={
              <FreshnessBadge
                dateDonnees={recettesApu.meta.date_donnees}
                source="Eurostat — gov_10a_main"
                frequence={recettesApu.meta.frequence}
                url={recettesApu.meta.url}
              />
            }
          >
            <KpiTile
              nu
              label="Recettes des APU (ESA)"
              valeur={`${formatNombre(recettesApu.montantMd, 1)}${ESPACE_FINE}Md€`}
              perimetre={perimetreAgregat(recettesApu.dernier, "TR")}
              delta={
                recettesApu.deltaPct === null
                  ? undefined
                  : {
                      valeur: recettesApu.deltaPct,
                      vs: recettesApu.precedent
                        ? `année ${recettesApu.precedent.annee}`
                        : "année précédente",
                    }
              }
            />
            <VueTableau>
              <DataTable
                colonnes={[
                  { cle: "annee", entete: "Année" },
                  {
                    cle: "trmd",
                    entete: "TR (Md€)",
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
                lignes={recettesApu.serie.slice(-12).map((o) => ({
                  annee: o.annee,
                  trmd: o.valeur_mio_eur / 1000,
                  pc: o.valeur_pc_gdp,
                }))}
                cleLigne={(l) => String(l.annee)}
              />
            </VueTableau>
            <p className="mt-3 text-xs text-ink-muted">
              TR n&apos;est pas un montant «&nbsp;net DGFiP&nbsp;»&nbsp;: c&apos;est le
              flux annuel des recettes des administrations publiques, distinct
              du budget général — voir{" "}
              <Link
                href="/comprendre/#recettes-apu-esa"
                className="underline decoration-[var(--viz-grid)] underline-offset-2 transition-colors hover:decoration-current"
              >
                Comprendre
              </Link>
              .
            </p>
          </Card>
        </div>
      )}

      {/* S50 PO — tableau 3.216, pas taxag, pas TR. */}
      {prelevements && (
        <div id="prelevements-obligatoires" className="flex scroll-mt-32 flex-col gap-6">
          <div className="flex items-center gap-3" role="separator">
            <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
            <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
              Autre objet · prélèvements obligatoires, pas TR
            </span>
            <span className="h-px flex-1 bg-card-border" aria-hidden="true" />
          </div>

          <Card
            titre="Prélèvements obligatoires (INSEE)"
            sousTitre="Impôts et cotisations sociales des APU et des institutions de l'UE — distinct du total TR Eurostat et de taxag"
            droite={
              <FreshnessBadge
                dateDonnees={prelevements.meta.date_donnees}
                source="INSEE — comptes nationaux"
                frequence={prelevements.meta.frequence}
                url={prelevements.meta.url}
              />
            }
          >
            <KpiTile
              nu
              label="Prélèvements obligatoires"
              valeur={`${formatNombre(prelevements.total.valeurMd, 1)}${ESPACE_FINE}Md€`}
              perimetre={perimetrePo(prelevements.total)}
              delta={
                prelevements.deltaPct === null
                  ? undefined
                  : {
                      valeur: prelevements.deltaPct,
                      vs: prelevements.precedent
                        ? `année ${prelevements.precedent.annee}`
                        : "année précédente",
                    }
              }
            />
            <p className="mt-3 text-xs leading-relaxed text-ink-muted">
              Tableau 3.216 des comptes nationaux. Ce n&apos;est pas taxag,
              pas le total TR Eurostat (S44), pas l&apos;impôt sur le revenu
              de caisse du budget général. S1314 n&apos;est pas «&nbsp;la
              Sécu&nbsp;».
            </p>
            <BarList
              className="mt-4"
              items={prelevements.sousSecteurs.map((d) => ({
                libelle: d.libelle,
                valeur: d.valeurMd,
              }))}
              formatValeur={(v) => `${formatNombre(v, 1)}${ESPACE_FINE}Md€`}
            />
            <p className="mt-2 text-xs text-ink-muted">
              Ordre S1311, S1313, S1314, S212, année {prelevements.annee}.
              Ces quatre postes recomposent le total S13 et S212. Ce
              n&apos;est pas un classement, pas les consolidations de la
              présentation dépenses et recettes.
            </p>
            <LienComprendre ancre="prelevements-obligatoires" />
          </Card>
        </div>
      )}
    </div>
  );
}
