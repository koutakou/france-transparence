import type { Metadata } from "next";
import { Card } from "@/components/ui/Card";
import { CarteDepartements } from "@/components/client/CarteDepartements";
import { DataTable } from "@/components/ui/DataTable";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import type { KpiTileProps } from "@/components/ui/KpiTile";
import { LineChart } from "@/components/ui/LineChart";
import { Money } from "@/components/ui/Money";
import { ParticipationElectorale } from "@/components/client/ParticipationElectorale";
import { SeriesCollectivites } from "@/components/client/SeriesCollectivites";
import { SeriesCommunes } from "@/components/client/SeriesCommunes";
import { StatStrip } from "@/components/ui/StatStrip";
import { TableTronquee } from "@/components/client/TableTronquee";
import { formatEuros, formatNombre } from "@/lib/format";
import {
  getConseilsDepartementaux,
  getDepartementsDepenses,
  getDgfCommunesTopFlop,
  getDgfDepartements,
  getDgfNationale,
  getGrandesCommunes,
  getKpisCommunes,
  getMetaFinancesLocales,
  getNbRegionsReferentiel,
  getRegions,
} from "@/lib/queries/collectivites";
import {
  getDonneesElectionsInline,
  PERIMETRE_BLANCS_NULS,
  PERIMETRE_INSCRITS,
  PERIMETRE_PARTICIPATION,
  PERIMETRE_VOTANTS,
} from "@/lib/queries/elections";
import { JsonLd } from "@/components/JsonLd";
import { NoticeLecture } from "@/components/ui/NoticeLecture";
import { jsonLdPage, metadonneesPage } from "@/lib/seo";

/**
 * Page STATIQUE (site pré-rendu quotidiennement) : tous les agrégats sont
 * calculés au build ; les cartes (fond GeoJSON ~700 Ko) et les séries
 * pluriannuelles des collectivités sélectionnées vivent côté client sur
 * fragments /data/* (docs/deploiement/DECISION.md).
 */

// Chemin, titre et description nommés UNE FOIS : les métadonnées et le
// balisage JSON-LD décrivent la même page, ils ne peuvent donc pas la
// décrire différemment le jour où l'un des deux est retouché.
const CHEMIN = "/collectivites/";
const TITRE = "Finances locales";
const DESCRIPTION =
  "Comptes des communes, départements et régions : dépenses par habitant, dotations de l’État — données OFGL datées.";

export const metadata: Metadata = metadonneesPage({
  chemin: CHEMIN,
  titre: TITRE,
  description: DESCRIPTION,
});

// `WebPage` : un tableau de bord, comme /depenses ou /marches — le même
// moule, au mot près.
//
// PAS de `Dataset` : la page n'offre aucun téléchargement. Les fragments
// /data/collectivites/*.json qu'elle charge au geste ne sont pas des exports
// publiés mais la mécanique interne des graphiques — les annoncer en
// `DataDownload` désignerait comme jeu de données ce qui n'est qu'un détail
// d'implémentation, susceptible de changer de forme au prochain build.
//
// PAS de `spatialCoverage` non plus : la propriété existe bien sur une
// `CreativeWork`, mais « France » n'apprendrait rien qu'un consommateur ne
// lise déjà dans la langue, le nom du site et le contenu de la page.
const BALISAGE = jsonLdPage({
  chemin: CHEMIN,
  nom: TITRE,
  description: DESCRIPTION,
  ariane: [{ nom: "Accueil", chemin: "/" }, { nom: TITRE }],
});

/** Titre de sous-bloc (dans une Card). */
function SousTitreBloc({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
      {children}
    </h3>
  );
}

/** Vue tableau jumelle repliable d'un graphique (DATAVIZ §9). */
function VueTableau({ resume, children }: { resume: string; children: React.ReactNode }) {
  return (
    <details className="mt-2">
      <summary className="cursor-pointer text-xs text-ink-muted transition-colors hover:text-ink-secondary">
        {resume}
      </summary>
      <div className="mt-2">{children}</div>
    </details>
  );
}

export default async function PageCollectivites() {
  const meta = getMetaFinancesLocales();

  // Base absente ou source non ingérée : message honnête, aucun chiffre.
  if (!meta) {
    return (
      <section className="flex flex-col gap-4">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Finances locales
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          La base locale n&apos;est pas construite ou la source S16 (OFGL) n&apos;y est pas
          encore ingérée — lancer{" "}
          <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code>. Aucune donnée
          fictive n&apos;est affichée.
        </div>
      </section>
    );
  }

  const departements = getDepartementsDepenses() ?? [];
  const kpis = getKpisCommunes();
  const dgfNationale = getDgfNationale() ?? [];
  const regions = getRegions() ?? [];
  const nbRegionsReferentiel = getNbRegionsReferentiel();
  const conseilsDep = getConseilsDepartementaux() ?? [];
  const grandesCommunes = getGrandesCommunes() ?? [];
  const dgfTopFlop = getDgfCommunesTopFlop();
  const dgfDepartements = getDgfDepartements() ?? [];

  // Badge de fraîcheur S16 (un par bloc) — fréquence réelle abrégée au 1er mot.
  const frequenceCourte = meta.frequence.split(" ")[0];
  const badge = (mention: string) => (
    <FreshnessBadge
      dateDonnees={meta.date_donnees}
      source="OFGL / DGFiP"
      frequence={frequenceCourte}
      url={meta.url}
      mention={mention}
    />
  );

  const exerciceComptes = kpis?.exercice ?? departements[0]?.exercice ?? 2025;
  const mentionComptes = `comptes ${exerciceComptes} provisoires`;

  // Carte €/hab : valeurs présentes + bornes réelles (min Orne / max Paris).
  const valeursCarte: Record<string, number> = {};
  for (const d of departements) {
    if (d.euros_par_hab !== null) valeursCarte[d.code] = d.euros_par_hab;
  }
  const avecValeur = departements.filter((d) => d.euros_par_hab !== null);
  const maxDep = avecValeur[0];
  const minDep = avecValeur[avecValeur.length - 1];
  const top10Dep = departements.slice(0, 10).map((d) => ({
    code: d.code,
    departement: `${d.nom} (${d.code})`,
    euros_par_hab: d.euros_par_hab,
    population: d.population,
  }));
  const flop10Dep = departements
    .slice(-10)
    .reverse()
    .map((d) => ({
      code: d.code,
      departement: `${d.nom} (${d.code})`,
      euros_par_hab: d.euros_par_hab,
      population: d.population,
    }));
  const colonnesTopFlopDep = [
    { cle: "departement", entete: "Département" },
    { cle: "euros_par_hab", entete: "Total (€/hab)", type: "montant" as const },
    { cle: "population", entete: "Population", type: "nombre" as const },
  ];

  // KPI : totaux communes + DGF nationale (évolution neutre — §3.5).
  const dgfDerniere = dgfNationale.at(-1) ?? null;
  const dgf2018 = dgfNationale.find((d) => d.exercice === 2018) ?? null;
  const deltaDgfDepuis2018 =
    dgfDerniere && dgf2018 && dgf2018.montant !== 0
      ? (dgfDerniere.montant / dgf2018.montant - 1) * 100
      : null;
  const tuiles: Omit<KpiTileProps, "nu">[] = [];
  if (kpis) {
    tuiles.push(
      {
        label: `Fonctionnement des communes (${kpis.exercice})`,
        valeur: <Money valeur={kpis.total_fonctionnement} />,
        montantVedette: true,
        perimetre:
          "budgets principaux, comptes provisoires — communes ayant rendu leurs comptes, via agrégats départementaux, hors budgets annexes",
      },
      {
        label: `Investissement des communes (${kpis.exercice})`,
        valeur: <Money valeur={kpis.total_investissement} />,
        perimetre:
          "budgets principaux, comptes provisoires — communes ayant rendu leurs comptes, via agrégats départementaux, hors budgets annexes",
      },
    );
  }
  if (dgfDerniere) {
    tuiles.push({
      label: `DGF nationale (${dgfDerniere.exercice})`,
      valeur: <Money valeur={dgfDerniere.montant} />,
      perimetre:
        "versée aux communes — les départements et les EPCI n’y sont pas",
      delta:
        deltaDgfDepuis2018 !== null
          ? { valeur: deltaDgfDepuis2018, vs: String(dgf2018?.exercice) }
          : undefined,
      tendance: dgfNationale.map((d) => d.montant),
    });
  }
  if (kpis) {
    tuiles.push({
      label: `Communes agrégées (comptes ${kpis.exercice})`,
      valeur: formatNombre(kpis.nb_communes),
      perimetre:
        "ayant rendu leurs comptes, via les agrégats départementaux — ce n’est pas le top 200 affiché plus bas",
    });
  }

  // Régions : lignes en M€ + total €/hab calculé (fonct + inv) / population.
  const ctu = regions.filter((r) => r.est_ctu === 1);
  const lignesRegions = regions.map((r) => ({
    code: r.code,
    nom: r.nom,
    siren: r.siren,
    est_ctu: r.est_ctu,
    population: r.population,
    fonctionnement_meur: r.fonctionnement === null ? null : r.fonctionnement / 1e6,
    investissement_meur: r.investissement === null ? null : r.investissement / 1e6,
    epargne_meur: r.epargne_brute === null ? null : r.epargne_brute / 1e6,
    total_euros_par_hab:
      r.fonctionnement !== null && r.investissement !== null && r.population
        ? (r.fonctionnement + r.investissement) / r.population
        : null,
  }));

  // Conseils départementaux : mêmes agrégats, 97 collectivités.
  const lignesConseilsDep = conseilsDep.map((d) => ({
    code: d.code,
    nom: `${d.nom} (${d.code})`,
    siren: d.siren,
    population: d.population,
    fonctionnement_meur: d.fonctionnement === null ? null : d.fonctionnement / 1e6,
    investissement_meur: d.investissement === null ? null : d.investissement / 1e6,
    epargne_meur: d.epargne_brute === null ? null : d.epargne_brute / 1e6,
    total_euros_par_hab:
      d.fonctionnement !== null && d.investissement !== null && d.population
        ? (d.fonctionnement + d.investissement) / d.population
        : null,
  }));

  // Grandes communes (top 200 par population — le tableau tronque
  // l'affichage à 20, pas la donnée : chaque commune est sélectionnable).
  const lignesGrandesCommunes = grandesCommunes.map((c) => ({
    code: c.code_insee,
    nom: c.nom,
    siren: c.siren,
    departement: c.dep_code ?? "—",
    population: c.population,
    fonctionnement_meur: c.fonctionnement === null ? null : c.fonctionnement / 1e6,
    fonct_euros_par_hab: c.fonct_euros_par_hab,
    investissement_meur: c.investissement === null ? null : c.investissement / 1e6,
    inv_euros_par_hab: c.inv_euros_par_hab,
  }));

  // DGF : évolution nationale (tableau jumeau en Md€), top/flop, carte.
  const lignesDgfNationale = dgfNationale.map((d) => ({
    exercice: String(d.exercice),
    montant_mdeur: d.montant / 1e9,
  }));
  const lignesDgfCommunes = (liste: NonNullable<typeof dgfTopFlop>["top"]) =>
    liste.map((c) => ({
      code: c.code,
      nom: c.nom,
      dgf_par_hab: c.dgf_par_hab,
      dgf_meur: c.dgf_montant / 1e6,
      population: c.population,
    }));
  const colonnesDgfCommunes = [
    { cle: "nom", entete: "Commune" },
    { cle: "dgf_par_hab", entete: "DGF (€/hab)", type: "montant" as const },
    { cle: "dgf_meur", entete: "DGF totale (M€)", type: "montant" as const, decimales: 1 },
    { cle: "population", entete: "Population", type: "nombre" as const },
  ];
  const parisEcrete = dgfTopFlop?.flop.some((c) => c.code === "75056" && c.dgf_montant === 0);
  const valeursDgfDep: Record<string, number> = {};
  for (const d of dgfDepartements) {
    if (d.dgf_par_hab !== null) valeursDgfDep[d.code] = d.dgf_par_hab;
  }
  const lignesDgfDep = dgfDepartements.map((d) => ({
    code: d.code,
    nom: `${d.nom} (${d.code})`,
    dgf_par_hab: d.dgf_par_hab,
    dgf_meur: d.dgf_montant / 1e6,
    population: d.population,
    nb_communes: d.nb_communes,
  }));
  const exerciceDgf = dgfDerniere?.exercice ?? dgfTopFlop?.exercice ?? null;
  const mentionDgf = exerciceDgf ? `dotations ${exerciceDgf}` : "dotations";

  return (
    <div className="flex flex-col gap-6">
      <JsonLd donnees={BALISAGE} />
      {/* Bande 1 — le chiffre au pli, pas le mur pédagogique. */}
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="max-w-2xl">
          <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
            Finances locales
          </h1>
          <p className="mt-2 text-sm text-ink-secondary">
            Comptes {exerciceComptes} des collectivités (OFGL / DGFiP), budgets
            principaux, montants provisoires jusqu&apos;en décembre 2026. DGF
            jusqu&apos;à l&apos;exercice {exerciceDgf ?? "—"}.
          </p>
        </div>
        {badge(mentionComptes)}
      </header>

      {/* ------------------------------------------------ KPI nationaux */}
      {tuiles.length > 0 && <StatStrip stats={tuiles} />}

      {/* Première bande de parcours — carte = outil (22 rem), pas un poster ;
          le tableau Grandes communes est l'objet à scanner, au plus près du pli. */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(16rem,22rem)_minmax(0,1fr)] xl:items-start">
      <section id="carte">
        <Card
          titre="Dépenses communales par habitant"
          sousTitre={`Fonctionnement + investissement des communes, agrégés par département — exercice ${exerciceComptes} (provisoire)`}
          droite={badge(mentionComptes)}
        >
          <div className="mx-auto w-full max-w-[22rem]">
            <CarteDepartements
              valeurs={valeursCarte}
              format="euros-par-hab"
              legendeTitre={`€ par habitant (${exerciceComptes})`}
              ariaLabel="Carte de France : dépenses communales par habitant et par département"
              messageAbsent="Fond de carte absent (data/geo/departements.geojson non trouvé) — les tableaux restent complets."
            />
          </div>
          {minDep && maxDep && (
            <p className="mt-2 text-xs text-ink-secondary">
              De {formatEuros(minDep.euros_par_hab ?? 0)} par habitant ({minDep.nom}) à{" "}
              {formatEuros(maxDep.euros_par_hab ?? 0)} ({maxDep.nom},{" "}
              {formatNombre(maxDep.nb_communes ?? 0)} commune
              {(maxDep.nb_communes ?? 0) > 1 ? "s" : ""}).
            </p>
          )}
          <p className="mt-1 text-[11px] text-ink-muted">
            Outre-mer hors rendu cartographique — présent dans les tableaux.
          </p>
        </Card>
      </section>

      <section id="communes" className="min-w-0">
        <Card
          titre="Grandes communes"
          sousTitre={
            grandesCommunes.length > 0
              ? `Les ${grandesCommunes.length} communes les plus peuplées — exercice ${grandesCommunes[0].exercice} (provisoire), séries 2018-2025 au clic`
              : undefined
          }
          droite={badge(mentionComptes)}
        >
          <SeriesCommunes lignes={lignesGrandesCommunes} hauteurMax="420px" />
          {/* Encadré méthode — cadre éditorial du module : aucune note,
              aucun classement, aucun jugement ; la seule comparaison est la
              médiane de strate, et une donnée absente reste absente. */}
          <div className="mt-3 rounded-lg border border-card-border bg-raised p-3 text-[11px] leading-relaxed text-ink-muted">
            <p className="mb-1 font-medium uppercase tracking-[0.04em]">Méthode</p>
            <p>
              Budget principal seul (les budgets annexes et les dépenses portées par
              l&apos;intercommunalité n&apos;y figurent pas). Exercice {exerciceComptes}{" "}
              provisoire : environ 97 communes manquent encore à la source — une commune
              absente s&apos;affiche « donnée non disponible », jamais 0. La comparaison
              proposée est la médiane des communes de la même strate démographique
              (calculée par l&apos;API OFGL sur l&apos;ensemble des communes de France) :
              un écart à la médiane de strate n&apos;est ni une faute ni un mérite —
              strate, compétences transférées à l&apos;intercommunalité et
              investissements ponctuels expliquent l&apos;essentiel des écarts.
              L&apos;intercommunalité de la commune est mentionnée quand la source la
              publie.
            </p>
          </div>
        </Card>
      </section>
      </div>

      <VueTableau resume="Top et flop 10 par habitant">
        <div className="flex flex-col gap-5 sm:flex-row sm:gap-8">
          <div className="min-w-0 flex-1">
            <SousTitreBloc>Top 10 — les plus dépensiers par habitant</SousTitreBloc>
            <DataTable
              colonnes={colonnesTopFlopDep}
              lignes={top10Dep}
              cleLigne={(l) => l.code}
            />
          </div>
          <div className="min-w-0 flex-1">
            <SousTitreBloc>Flop 10 — les plus faibles par habitant</SousTitreBloc>
            <DataTable
              colonnes={colonnesTopFlopDep}
              lignes={flop10Dep}
              cleLigne={(l) => l.code}
            />
          </div>
        </div>
      </VueTableau>

      {/* Bande 3 — notice APRÈS le chiffre et la 1re bande, pas un mur sur le pli. */}
      <NoticeLecture
        ancre="collectivites"
        commentLire={
          <p>
            Tous les montants portent sur le budget principal seul. Une
            commune absente d’un exercice provisoire n’a pas dépensé zéro :
            sa donnée n’est pas encore publiée. La colonne Population est la
            somme des seules communes ayant rendu leurs comptes : elle
            sous-estime les départements où il en manque, la Lozère de
            13&nbsp;% parce que Mende y figure parmi les manquantes. Un
            écart à la médiane de strate n’est ni une faute ni un mérite. La
            participation électorale porte sur les préfectures, les communes
            de plus de 50&nbsp;000&nbsp;habitants, et les 200 communes les
            plus peuplées — pas sur les 35&nbsp;000 communes de France.
          </p>
        }
        provenance={
          <p>
            Comptes des collectivités consolidés par l’OFGL à partir des
            données DGFiP. Participation : résultats agrégés du ministère
            de l’Intérieur. Dotation globale de fonctionnement : montants
            officiels de l’exercice affiché.
          </p>
        }
        limites={
          <p>
            Les budgets annexes et les dépenses portées par
            l’intercommunalité n’y sont pas. L’agrégat de participation
            s’appelle «&nbsp;ensemble des départements&nbsp;», jamais
            «&nbsp;la France&nbsp;» : les Français établis hors de France
            n’y figurent pas. Aucune nuance politique, aucun nom de
            candidat.
          </p>
        }
      />

      {/* ------------------------------------------------ régions */}
      <section id="regions">
        <Card
          titre="Régions"
          sousTitre={
            regions.length > 0
              ? `${regions.length}${
                  nbRegionsReferentiel ? ` des ${nbRegionsReferentiel}` : ""
                } collectivités régionales, exercice ${regions[0].exercice} — dont ${ctu.length} collectivités territoriales uniques (${ctu
                  .map((r) => r.nom)
                  .join(", ")}) exerçant aussi les compétences départementales`
              : undefined
          }
          droite={badge(mentionComptes)}
        >
          <SeriesCollectivites niveau="regions" lignes={lignesRegions} />
          {/* L'écart au référentiel s'explique, il ne se comble pas : rien
              n'est recopié depuis les comptes départementaux de Mayotte.
              La phrase disparaît d'elle-même si OFGL publie la 18e. */}
          {nbRegionsReferentiel !== null &&
            regions.length < nbRegionsReferentiel && (
              <p className="mt-2 text-[11px] text-ink-muted">
                {nbRegionsReferentiel - regions.length === 1
                  ? "Une collectivité régionale manque à ce tableau"
                  : `${nbRegionsReferentiel - regions.length} collectivités régionales manquent à ce tableau`}{" "}
                : le Département de Mayotte (976) est une collectivité unique
                qui exerce à la fois les compétences régionales et
                départementales, et la base OFGL ne le publie pas dans son jeu
                « régions ». Ses comptes figurent parmi les conseils
                départementaux ci-dessous. Ils n&apos;y sont pas recopiés :
                aucune ligne régionale n&apos;est fabriquée pour combler
                l&apos;écart.
              </p>
            )}
        </Card>
      </section>

      {/* ------------------------------------------------ conseils départementaux */}
      <section id="departements">
        <Card
          titre="Conseils départementaux"
          sousTitre={
            conseilsDep.length > 0
              ? `${conseilsDep.length} collectivités départementales, exercice ${conseilsDep[0].exercice}`
              : undefined
          }
          droite={badge(mentionComptes)}
        >
          <SeriesCollectivites
            niveau="departements"
            lignes={lignesConseilsDep}
            hauteurMax="420px"
          />
          <p className="mt-2 text-[11px] text-ink-muted">
            67A = Collectivité européenne d&apos;Alsace (Bas-Rhin + Haut-Rhin fusionnés) ·
            691 = Métropole de Lyon (compétences départementales sur son territoire) ·
            75 = Paris, collectivité à statut particulier (commune et département). L&apos;épargne
            brute peut être négative : donnée réelle, affichée signée.
          </p>
          <p className="mt-2 text-[11px] text-ink-muted">
            976 = Département de Mayotte, collectivité unique : il exerce aussi
            les compétences régionales, que les autres conseils départementaux
            n&apos;ont pas. Ses agrégats de fonctionnement ne sont donc pas
            comparables aux leurs. C&apos;est à ce titre qu&apos;il figure ici
            et non dans le tableau des régions ci-dessus, où la base OFGL ne le
            publie pas.
          </p>
        </Card>
      </section>

      {/* ------------------------------------------------ dotations DGF */}
      <section id="dgf" className="flex flex-col gap-6">
        <Card
          titre="Dotation globale de fonctionnement — évolution nationale"
          sousTitre={
            dgfNationale.length > 0
              ? `Dotation versée aux communes, ${dgfNationale[0].exercice}-${dgfNationale.at(-1)?.exercice} — hors départements et EPCI`
              : undefined
          }
          droite={badge(mentionDgf)}
        >
          {dgfNationale.length > 0 ? (
            <>
              <LineChart
                labels={dgfNationale.map((d) => String(d.exercice))}
                series={[{ nom: "DGF nationale", valeurs: dgfNationale.map((d) => d.montant) }]}
                formatValeur={(v) => formatEuros(v)}
                hauteur={220}
                ariaLabel="Évolution de la DGF nationale par exercice"
              />
              <VueTableau resume="Vue tableau">
                <DataTable
                  colonnes={[
                    { cle: "exercice", entete: "Exercice" },
                    { cle: "montant_mdeur", entete: "DGF (Md€)", type: "montant", decimales: 2 },
                  ]}
                  lignes={lignesDgfNationale}
                  cleLigne={(l) => l.exercice}
                />
              </VueTableau>
            </>
          ) : (
            <p className="text-sm text-ink-muted">Aucune donnée DGF nationale en base.</p>
          )}
        </Card>

        {/* grid-cols-1 explicite : piste minmax(0,1fr) — sans elle, la piste
            implicite « auto » s'élargit au min-content des tableaux (débord mobile). */}
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <Card
            titre="DGF par habitant — communes de 20 000 habitants ou plus"
            sousTitre={
              dgfTopFlop?.exercice
                ? `Extrêmes réels de l'exercice ${dgfTopFlop.exercice}, en euros par habitant`
                : undefined
            }
            droite={badge(mentionDgf)}
          >
            {dgfTopFlop && (dgfTopFlop.top.length > 0 || dgfTopFlop.flop.length > 0) ? (
              <div className="flex flex-col gap-5">
                <div>
                  <SousTitreBloc>Top 10 — DGF/hab les plus élevées</SousTitreBloc>
                  <DataTable
                    colonnes={colonnesDgfCommunes}
                    lignes={lignesDgfCommunes(dgfTopFlop.top)}
                    cleLigne={(l) => l.code}
                  />
                </div>
                <div>
                  <SousTitreBloc>Flop 10 — DGF/hab les plus faibles</SousTitreBloc>
                  <DataTable
                    colonnes={colonnesDgfCommunes}
                    lignes={lignesDgfCommunes(dgfTopFlop.flop)}
                    cleLigne={(l) => l.code}
                  />
                  <p className="mt-2 text-xs text-ink-secondary">
                    Une DGF à 0&nbsp;€ est une donnée réelle : la dotation de ces communes est
                    intégralement écrêtée — c&apos;est le cas de {dgfTopFlop.nb_zero} communes
                    de 20&nbsp;000 habitants ou plus en {dgfTopFlop.exercice}
                    {parisEcrete ? ", dont Paris" : ""}.
                  </p>
                </div>
              </div>
            ) : (
              <p className="text-sm text-ink-muted">Aucune donnée DGF communale en base.</p>
            )}
          </Card>

          <Card
            titre="DGF par habitant — par département"
            sousTitre={
              dgfDepartements.length > 0
                ? `DGF des communes agrégée par département, exercice ${dgfDepartements[0].exercice}`
                : undefined
            }
            droite={badge(mentionDgf)}
          >
            {dgfDepartements.length > 0 ? (
              <>
                <div className="max-w-md">
                  <CarteDepartements
                    valeurs={valeursDgfDep}
                    format="euros-par-hab"
                    legendeTitre={`DGF par habitant (${dgfDepartements[0].exercice})`}
                    ariaLabel="Carte de France : DGF par habitant et par département"
                    messageAbsent="Fond de carte absent — la vue tableau ci-dessous reste complète."
                  />
                </div>
                <p className="mt-1 text-[11px] text-ink-muted">
                  Outre-mer hors rendu cartographique — présent dans la vue tableau.
                </p>
                <VueTableau
                  resume={`Vue tableau (${dgfDepartements.length} départements et collectivités)`}
                >
                  <TableTronquee
                    colonnes={[
                      { cle: "nom", entete: "Département" },
                      { cle: "dgf_par_hab", entete: "DGF (€/hab)", type: "montant" },
                      { cle: "dgf_meur", entete: "DGF totale (M€)", type: "montant", decimales: 1 },
                      { cle: "population", entete: "Population", type: "nombre" },
                      { cle: "nb_communes", entete: "Communes", type: "nombre" },
                    ]}
                    lignes={lignesDgfDep}
                    cleChamp="code"
                    premierEcran={20}
                    libellePluriel="départements"
                    hauteurMax="320px"
                  />
                </VueTableau>
              </>
            ) : (
              <p className="text-sm text-ink-muted">Aucune donnée DGF départementale en base.</p>
            )}
          </Card>
        </div>
      </section>

      {/* ------------------------------------------------ participation électorale
          Source S26 (ministère de l'Intérieur), indépendante des comptes OFGL :
          le composant porte son propre badge de fraîcheur et ses propres
          réserves (participation seulement, aucune nuance politique, scrutins
          non comparables entre eux). Voir docs/ELECTIONS.md. */}
      <section id="participation">
        <ParticipationElectorale
          donnees={getDonneesElectionsInline()}
          perimetreInscrits={PERIMETRE_INSCRITS}
          perimetreVotants={PERIMETRE_VOTANTS}
          perimetreParticipation={PERIMETRE_PARTICIPATION}
          perimetreBlancsNuls={PERIMETRE_BLANCS_NULS}
        />
      </section>
    </div>
  );
}
