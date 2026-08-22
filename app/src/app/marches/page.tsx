import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AlertItem, type Gravite } from "@/components/ui/AlertItem";
import { AppelsOffres } from "@/components/client/AppelsOffres";
import { BarChart } from "@/components/ui/BarChart";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { JsonLd } from "@/components/JsonLd";
import { NoticeLecture } from "@/components/ui/NoticeLecture";
import { CarteDepartements } from "@/components/client/CarteDepartements";
import { DataTable } from "@/components/ui/DataTable";
import { Donut, type DonutPart } from "@/components/ui/Donut";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { Money } from "@/components/ui/Money";
import { SerieMensuelleMarches } from "@/components/client/SerieMensuelleMarches";
import { Sparkline } from "@/components/ui/Sparkline";
import { StatStrip } from "@/components/ui/StatStrip";
import { TableTronquee } from "@/components/client/TableTronquee";
import {
  ESPACE_FINE,
  formatDateFr,
  formatEuros,
  formatNombre,
  formatPct,
} from "@/lib/format";
import { chargerDonneesMarches, type AlerteMarches } from "@/lib/queries/marches";
import { jsonLdPage, metadonneesPage } from "@/lib/seo";

/**
 * Page STATIQUE (site pré-rendu quotidiennement) : tout est calculé au
 * build sur la base du jour ; le filtre BOAMP par famille et la carte
 * vivent côté client sur fragments /data/* (docs/deploiement/DECISION.md).
 * L'instantané BOAMP est re-filtré (annulations, échéances passées) à
 * chaque construction du site — pas à chaque affichage.
 */

// Chemin, titre et description nommés UNE FOIS : les métadonnées et le
// balisage JSON-LD décrivent la même page, ils ne peuvent donc pas la
// décrire différemment le jour où l'un des deux est retouché.
const CHEMIN = "/marches/";
const TITRE = "Commande publique";
const DESCRIPTION =
  "Marchés publics notifiés et appels d’offres en cours : montants, attributaires, répartition par département — DECP consolidées et BOAMP, données datées.";

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

/* ------------------------------------------------------------------ */
/* Helpers d'affichage (purs, locaux à la page)                        */
/* ------------------------------------------------------------------ */

/** Tronque proprement un libellé long (le `title` porte le texte complet). */
function tronque(s: string | null, max: number): string {
  if (!s || s.trim() === "") return "—";
  return s.length > max ? `${s.slice(0, max - 1).trimEnd()}…` : s;
}

/**
 * Durée en jours, unité collée par une espace fine insécable (DATAVIZ §4).
 * `null` (quantile non calculable) ne devient jamais 0 : il s'affiche « — ».
 */
function formatJours(v: number | null): string {
  if (v === null) return "—";
  return `${formatNombre(v)}${ESPACE_FINE}${Math.abs(v) < 2 ? "jour" : "jours"}`;
}

/** La date de donnée est-elle celle du jour de construction du site ? */
function estJourDeConstruction(iso: string): boolean {
  return formatDateFr(iso) === formatDateFr(new Date().toISOString());
}

/** Gravités de la table `alertes` (haute/moyenne/info) → jeton AlertItem. */
function graviteAlerte(gravite: string): { gravite: Gravite; libelle: string } {
  if (gravite === "haute") return { gravite: "critique", libelle: "Haute" };
  if (gravite === "moyenne") return { gravite: "serieux", libelle: "Moyenne" };
  return { gravite: "attention", libelle: "Info" };
}

/* ------------------------------------------------------------------ */
/* Petits composants locaux (Server Components, zéro JS client)        */
/* ------------------------------------------------------------------ */

/** Vue tableau jumelle dépliable (toggle « Tableau », DATAVIZ §7/§9). */
function VueTableau({ children, resume = "Vue tableau" }: { children: ReactNode; resume?: string }) {
  return (
    <details className="group mt-3">
      <summary className="cursor-pointer list-none text-xs text-ink-muted transition-colors hover:text-ink-secondary">
        <span aria-hidden="true" className="mr-1 inline-block transition-transform group-open:rotate-90">
          ›
        </span>
        {resume}
      </summary>
      <div className="mt-2">{children}</div>
    </details>
  );
}

/** Un quantile du délai de publication : valeur au-dessus, libellé dessous. */
function Quantile({ libelle, valeur }: { libelle: string; valeur: number | null }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-lg font-semibold text-ink [font-variant-numeric:tabular-nums]">
        {formatJours(valeur)}
      </span>
      <span className="text-[11px] uppercase tracking-[0.06em] text-ink-muted">
        {libelle}
      </span>
    </div>
  );
}

/** Étiquette « suspect » : icône statut + libellé (jamais la couleur seule). */
function EtiquetteSuspect() {
  return (
    <span
      className="inline-flex items-center gap-1 text-[11px] text-ink-muted"
      title="Montant classé suspect : anomalie signalée à la source, ou montant supérieur à 100 M€ (écrêté dans les agrégats)."
    >
      <svg width="10" height="10" viewBox="0 0 14 14" aria-hidden="true" style={{ color: "var(--status-warning)" }}>
        <path d="M7 1.5L13 12H1z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M7 5.4v3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="7" cy="10.2" r="0.9" fill="currentColor" />
      </svg>
      suspect
    </span>
  );
}

/** Lien sortant discret (annonce BOAMP, consultation APProch). */
function LienSortant({ href, libelle }: { href: string | null; libelle: string }) {
  if (!href) return <>—</>;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-ink-secondary underline decoration-dotted underline-offset-2 hover:text-ink"
    >
      {libelle}
    </a>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default async function PageMarches() {
  const donnees = chargerDonneesMarches(null);

  if (donnees === null) {
    return (
      <section className="flex flex-col gap-6">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Marchés publics
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          La base locale n’est pas encore construite — lancer{" "}
          <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code>{" "}
          pour ingérer les sources (DECP, BOAMP, APProch).
        </div>
      </section>
    );
  }

  const {
    meta,
    kpis,
    serieMensuelle,
    familles,
    alertes,
    qualiteMontants,
    decompositionSuspects,
    qualitePublication,
    qualiteTitulaires,
    qualiteAcheteurs,
    formesIdentifiantsEcartes,
  } = donnees;

  /* ---- « Ce que vaut ce total » : parts écrêtée et suspecte du KPI héros.
     Le chiffre affiché n'est PAS modifié — on lui ajoute son contexte.
     Les parts se lisent sur le total écrêté lui-même (montant_total de
     decp_qualite_montants = valeur du KPI). `null` tant que le pipeline
     n'a pas produit la table : le paragraphe disparaît, aucun chiffre
     n'est deviné. */
  const qm = qualiteMontants;
  const totalQm = qm?.montant_total ?? null;
  const partEcretee =
    qm && totalQm && qm.montant_ecretes !== null
      ? (100 * qm.montant_ecretes) / totalQm
      : null;
  const partSuspecte =
    qm && totalQm && qm.montant_suspects !== null
      ? (100 * qm.montant_suspects) / totalQm
      : null;

  /* ---- Ce que le drapeau « suspect » recouvre. Un compteur unique met dans
     le même sac ce que la source a DÉJÀ corrigé et ce qu'elle signale sans
     rien corriger : deux choses de valeur très différente. On les compte
     séparément, chacune avec sa propre somme mesurée — aucun ratio n'est
     reconstitué à partir de l'autre. `null` (fenêtre non reconstituée) →
     le compteur unique reste affiché seul, comme avant. */
  const ds = decompositionSuspects;
  const partAberrants =
    ds && totalQm && ds.montantAberrants !== null
      ? (100 * ds.montantAberrants) / totalQm
      : null;

  /* ---- Qualité de publication : délai notification -> 1re publication.
     Rien n'est recalculé ici — quantiles, dénominateurs et taux viennent de
     la base tels quels. Les seules opérations faites côté page sont des
     mises en forme et deux rapports entre entiers déjà publiés :
     - la part des marchés sans catégorie d'acheteur, rapportée aux marchés
       des cohortes CLOSES, c'est-à-dire ceux que la ventilation couvre
       (somme des lignes affichées) plus ceux qu'elle ne couvre pas ;
     - la part des marchés à publication antérieure à la notification, sur
       les marchés de la source.
     `null` tant que les tables ne sont pas en base : la section entière
     disparaît, aucun chiffre n'est deviné. */
  const qp = qualitePublication;
  const anneesChiffrees = (qp?.annees ?? []).filter((a) => a.taux_dans_delai !== null);
  const anneesProvisoires = (qp?.annees ?? []).filter((a) => a.cohorte_close === 0);
  const acheteursChiffres = (qp?.acheteurs ?? []).filter((a) => a.taux_dans_delai !== null);
  const nbAcheteursCouverts = (qp?.acheteurs ?? []).reduce((s, a) => s + a.nb_marches, 0);
  const nbCohortesCloses = qp ? nbAcheteursCouverts + qp.synthese.nb_sans_categorie : 0;
  const partSansCategorie =
    qp && nbCohortesCloses > 0
      ? (100 * qp.synthese.nb_sans_categorie) / nbCohortesCloses
      : null;
  const partPublicationAnterieure =
    qp && qp.synthese.nb_marches_source > 0
      ? (100 * qp.synthese.nb_publication_anterieure) / qp.synthese.nb_marches_source
      : null;

  /* ---- Ce que le classement des titulaires couvre. Le classement porte sur
     l'ENTREPRISE (SIREN) : les établissements d'une même personne morale y
     comptent pour une seule ligne. Les lignes dont l'identifiant de
     titulaire n'est pas exploitable ne se rattachent à aucune entreprise :
     elles sont écartées du classement, et leur nombre comme leur montant se
     lisent en base — jamais une formule vague. La part écartée est le seul
     calcul fait ici, entre deux montants déjà publiés par la table.
     `null` tant que la table n'est pas produite : le paragraphe disparaît. */
  const qt = qualiteTitulaires;
  const totalTitulaires =
    qt && qt.montant_identifiable !== null && qt.montant_ecarte !== null
      ? qt.montant_identifiable + qt.montant_ecarte
      : null;
  const partEcartee =
    qt && totalTitulaires && qt.montant_ecarte !== null
      ? (100 * qt.montant_ecarte) / totalTitulaires
      : null;

  /* ---- Le même filtre de conformité vaut côté acheteurs : ce qu'il écarte
     est donc dit là aussi, au même endroit que le classement concerné.
     L'unité est le MARCHÉ (un marché n'a qu'un acheteur), et l'ampleur est
     sans commune mesure avec celle des titulaires — la mention tient en une
     phrase, mais elle existe : un identifiant écarté sans compteur serait
     une disparition silencieuse. Aucun ratio n'est calculé ici, les deux
     compteurs affichés sont lus en base. */
  const qa = qualiteAcheteurs;

  /* ---- KPI : tendances 12 derniers mois de la série mensuelle ---- */
  const douzeDerniers = serieMensuelle.slice(-12);
  const tendanceNb = douzeDerniers.map((m) => m.nb_marches);
  const montantsDouze = douzeDerniers.map((m) => m.montant_total);
  const tendanceMontant = montantsDouze.every((v): v is number => v !== null)
    ? montantsDouze
    : undefined;

  /* ---- Carte : montants par département (NULL écarté, jamais 0).
     Codes à 2 caractères = métropole + Corse, le périmètre réellement
     rendu par la carte : l'échelle de la légende ne doit décrire
     que ce qui est affiché — l'outre-mer reste lisible dans le tableau. */
  const valeursCarte: Record<string, number> = {};
  for (const d of donnees.departements) {
    if (d.montant_total !== null && d.departement_code.length === 2) {
      valeursCarte[d.departement_code] = d.montant_total;
    }
  }

  /* ---- Donut procédures : ≤ 6 segments, « Non renseigné » explicite ---- */
  const procedures = donnees.repartitionProcedure;
  const nommees = procedures.filter((r) => r.valeur !== null);
  const nbNonRenseigne = procedures
    .filter((r) => r.valeur === null)
    .reduce((s, r) => s + r.nb_marches, 0);
  const tete = nommees.slice(0, 4);
  const nbAutres = nommees.slice(4).reduce((s, r) => s + r.nb_marches, 0);
  const partsDonut: DonutPart[] = [
    ...tete.map((r, i) => ({
      libelle: r.valeur as string,
      valeur: r.nb_marches,
      couleur: `var(--viz-serie-${i + 1})`,
    })),
    { libelle: "Autres procédures", valeur: nbAutres, couleur: "var(--viz-autre)" },
    { libelle: "Non renseigné", valeur: nbNonRenseigne, couleur: "var(--viz-serie-5)" },
  ]
    .filter((p) => p.valeur > 0)
    .sort((a, b) => b.valeur - a.valeur);
  const totalProcedures = procedures.reduce((s, r) => s + r.nb_marches, 0);

  /* ---- BOAMP : compteurs du bloc annonces ---- */
  const totalAnnonces31j = donnees.annoncesParJour.reduce((s, j) => s + j.nb, 0);

  const badgeS1 = meta.s1 && (
    <FreshnessBadge
      dateDonnees={meta.s1.date_donnees}
      source="DECP consolidées"
      frequence={meta.s1.frequence}
      url={meta.s1.url}
    />
  );

  return (
    <div className="flex flex-col gap-6">
      <JsonLd donnees={BALISAGE} />
      {/* ---------------------------------------------------------- */}
      {/* En-tête honnête                                            */}
      {/* ---------------------------------------------------------- */}
      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
            Marchés publics
          </h1>
          {badgeS1}
        </div>
        <p className="max-w-3xl text-sm text-ink-secondary">
          Marchés notifiés d’après les données essentielles de la commande
          publique (DECP), consolidées par le projet communautaire{" "}
          <a
            href="https://www.data.gouv.fr/datasets/donnees-essentielles-de-la-commande-publique-consolidees-format-tabulaire"
            target="_blank"
            rel="noopener noreferrer"
            className="underline decoration-dotted underline-offset-2 hover:text-ink"
          >
            decp-processing
          </a>{" "}
          (Colin Maudry) — complétés des appels d’offres en cours (BOAMP) et
          des achats annoncés (APProch). La publication des marchés connaît
          une latence légale jusqu’à 2&nbsp;mois : les fenêtres récentes sont
          structurellement incomplètes. Les montants d’accords-cadres sont des
          <strong className="font-medium text-ink"> maximums</strong>, pas du
          dépensé. Un marché est daté de sa{" "}
          <strong className="font-medium text-ink">
            notification initiale
          </strong>{" "}
          — un avenant ne le redate pas — et toutes les fenêtres de cette page
          (30&nbsp;jours, 12&nbsp;mois, 36&nbsp;mois) portent sur cette date ;
          les montants et les titulaires affichés sont, eux, ceux de la
          version courante du marché.
        </p>
        <NoticeLecture
          ancre="marches"
          commentLire={
            <p>
              Un marché est daté de sa notification initiale, pas de son
              dernier avenant. Les totaux «&nbsp;12 mois&nbsp;» et
              «&nbsp;30 jours&nbsp;» portent sur cette date. Les montants
              agrégés sont écrêtés à 100&nbsp;M€ par marché avant sommation ;
              un accord-cadre y entre pour son maximum, pas pour le dépensé.
              Un tiret «&nbsp;—&nbsp;» n’est pas un zéro.
            </p>
          }
          provenance={
            <p>
              Données essentielles de la commande publique (DECP),
              consolidées par le projet communautaire decp-processing ;
              appels d’offres en cours du BOAMP ; achats annoncés d’APProch.
              La publication légale peut prendre jusqu’à deux mois : les
              fenêtres récentes sont incomplètes.
            </p>
          }
          limites={
            <p>
              Cette page ne dit pas si un marché a été exécuté, ni s’il a été
              payé, ni s’il était le mieux-disant. Un identifiant qui n’est
              pas un SIRET de 14 chiffres est écarté des classements et
              compté à part — il n’est pas complété d’un zéro de tête. Le
              classement s’arrête à l’entreprise : il ne remonte pas au
              groupe.
            </p>
          }
        />
      </section>

      {/* ---------------------------------------------------------- */}
      {/* KPI                                                        */}
      {/* ---------------------------------------------------------- */}
      <section className="flex flex-col gap-2">
        <StatStrip
          stats={[
            {
              label: "Marchés notifiés (12 mois)",
              valeur: formatNombre(kpis.nbMarches12m),
              tendance: tendanceNb,
            },
            {
              label: "Montant notifié (12 mois, écrêté)",
              valeur: kpis.montant12m !== null ? <Money valeur={kpis.montant12m} /> : "—",
              montantVedette: true,
              tendance: tendanceMontant,
            },
            {
              label: "Marchés notifiés (30 derniers jours)",
              valeur: formatNombre(kpis.nbMarches30j),
            },
            {
              label: "Appels d’offres en cours (BOAMP)",
              valeur: formatNombre(kpis.aoEnCours),
            },
            {
              label: "Achats annoncés (APProch)",
              valeur: formatNombre(kpis.marchesAVenir),
            },
          ]}
        />
        <p className="text-xs leading-relaxed text-ink-muted">
          Méthode : montants agrégés écrêtés à 100&nbsp;M€ par marché pour
          neutraliser les saisies aberrantes ; les montants non renseignés
          restent exclus des sommes — aucune valeur n’est inventée.
        </p>
        {qm && totalQm !== null && (
          <div className="max-w-3xl rounded-xl border border-card-border bg-card p-4">
            <h2 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
              Ce que vaut ce total
            </h2>
            <p className="text-xs leading-relaxed text-ink-secondary">
              Le total de{" "}
              <strong className="font-medium text-ink">
                {formatEuros(totalQm)}
              </strong>{" "}
              porte sur {formatNombre(qm.nb_marches)} marchés notifiés sur
              12&nbsp;mois. Il n’est pas homogène :
            </p>
            <ul className="mt-2 flex flex-col gap-1.5 text-xs leading-relaxed text-ink-secondary">
              <li>
                <strong className="font-medium text-ink">
                  {formatNombre(qm.nb_ecretes)} marchés
                </strong>{" "}
                dépassent le plafond de {formatEuros(qm.plafond)} et sont
                comptés à ce plafond. Ils apportent{" "}
                {qm.montant_ecretes !== null ? formatEuros(qm.montant_ecretes) : "—"}
                {partEcretee !== null && <>, soit {formatPct(partEcretee)} du total</>} :
                cette part est faite de valeurs de substitution, leur montant
                réel n’est pas connu.
              </li>
              <li>
                <strong className="font-medium text-ink">
                  {formatNombre(qm.nb_suspects)} marchés
                </strong>{" "}
                portent le drapeau « montant suspect » (anomalie signalée à la
                source, ou montant au-delà du plafond) et apportent{" "}
                {qm.montant_suspects !== null ? formatEuros(qm.montant_suspects) : "—"}
                {partSuspecte !== null && <>, soit {formatPct(partSuspecte)} du total</>}.
                {ds !== null && (
                  <>
                    {" "}
                    Ce drapeau unique recouvre trois situations qui ne se valent
                    pas :
                    <ul className="mt-1.5 flex flex-col gap-1.5 border-l border-card-border pl-3">
                      <li>
                        <strong className="font-medium text-ink">
                          {formatNombre(ds.nbSuspectsSource)} marchés
                        </strong>{" "}
                        sont signalés par la source{" "}
                        <strong className="font-medium text-ink">
                          sans être corrigés
                        </strong>{" "}
                        : le montant déclaré est conservé tel quel et compte
                        pour{" "}
                        {ds.montantSuspectsSource !== null
                          ? formatEuros(ds.montantSuspectsSource)
                          : "—"}
                        . C’est là, et seulement là, que porte l’incertitude
                        sur le total.
                      </li>
                      <li>
                        <strong className="font-medium text-ink">
                          {formatNombre(ds.nbAberrants)} marchés
                        </strong>{" "}
                        ont été classés aberrants{" "}
                        <strong className="font-medium text-ink">
                          et déjà redressés par la source
                        </strong>{" "}
                        : c’est le montant corrigé qui est compté, pour{" "}
                        {ds.montantAberrants !== null
                          ? formatEuros(ds.montantAberrants)
                          : "—"}
                        {partAberrants !== null && (
                          <>, soit {formatPct(partAberrants, 2)} du total</>
                        )}
                        . Le drapeau garde la trace de la correction ; il ne dit
                        pas que le chiffre affiché serait faux.
                      </li>
                      <li>
                        <strong className="font-medium text-ink">
                          {formatNombre(ds.nbHorsPlafond)} marchés
                        </strong>{" "}
                        ne sont signalés par aucune anomalie : leur drapeau
                        vient de notre seul écrêtage, leur montant dépassant le
                        plafond. Ils sont comptés au plafond, pour{" "}
                        {ds.montantHorsPlafond !== null
                          ? formatEuros(ds.montantHorsPlafond)
                          : "—"}
                        .
                      </li>
                    </ul>
                  </>
                )}
              </li>
              <li>
                En les écartant tous, il reste{" "}
                {qm.montant_hors_suspects !== null
                  ? formatEuros(qm.montant_hors_suspects)
                  : "—"}
                . À lire comme une{" "}
                <strong className="font-medium text-ink">borne basse</strong>, et
                non comme le montant réel : le drapeau « suspect » n’a pas été
                vérifié marché par marché, il écarte donc aussi des montants
                exacts
                {ds !== null && (
                  <> — à commencer par les {formatNombre(ds.nbAberrants)} déjà
                  redressés à la source</>
                )}
                .
              </li>
              <li>
                Sans aucun écrêtage, la somme brute des montants déclarés
                atteindrait{" "}
                {qm.montant_brut !== null ? formatEuros(qm.montant_brut) : "—"} —
                ce que le plafond sert précisément à ne pas afficher.
              </li>
              <li>
                {formatNombre(qm.nb_sans_montant)} marchés sont notifiés sans
                montant renseigné : comptés dans le nombre de marchés, exclus
                de toutes les sommes.
              </li>
            </ul>
          </div>
        )}
      </section>

      {/* ---------------------------------------------------------- */}
      {/* Carte des montants par département                          */}
      {/* ---------------------------------------------------------- */}
      <Card
        titre="Montants par département"
        sousTitre="Marchés notifiés sur 12 mois — montants écrêtés, acheteurs à département connu"
        droite={badgeS1}
      >
        {/* grid-cols-1 explicite : piste minmax(0,1fr) — sans elle, la piste
            implicite « auto » s'élargit au min-content du tableau (débord mobile). */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div>
            <CarteDepartements
              valeurs={valeursCarte}
              format="euros"
              legendeTitre="Montant notifié (12 mois)"
              ariaLabel="Carte de France des montants de marchés publics notifiés par département sur 12 mois"
              messageAbsent="Fond de carte indisponible (data/geo/departements.geojson manquant) — les valeurs restent lisibles dans le tableau ci-contre."
            />
            <p className="mt-2 text-xs leading-relaxed text-ink-muted">
              « Donnée manquante » = aucun montant connu pour le département
              (jamais confondu avec 0&nbsp;€). Outre-mer hors rendu carte&nbsp;:
              les valeurs figurent dans le tableau. Montants écrêtés à
              100&nbsp;M€ par marché.
            </p>
          </div>
          <TableTronquee
            colonnes={[
              { cle: "departement_code", entete: "Code", largeur: "4rem" },
              { cle: "departement_nom", entete: "Département" },
              { cle: "nb_marches", entete: "Marchés", type: "nombre" },
              {
                cle: "montant_total",
                entete: "Montant",
                type: "money",
                titreSiNull: "Aucun montant connu",
              },
              { cle: "nb_marches_ecretes", entete: "Écrêtés", type: "nombre" },
            ]}
            lignes={donnees.departements}
            cleChamp="departement_code"
            premierEcran={20}
            libellePluriel="départements"
            hauteurMax="460px"
            vide="Aucun agrégat départemental"
          />
        </div>
      </Card>

      {/* ---------------------------------------------------------- */}
      {/* Série mensuelle 36 mois                                     */}
      {/* ---------------------------------------------------------- */}
      <Card
        titre="Série mensuelle"
        sousTitre="36 derniers mois civils, chaque marché rangé au mois de sa notification initiale (un avenant ne le redate pas) — les 2 derniers mois sont incomplets (latence légale de publication ≤ 2 mois)"
        droite={badgeS1}
      >
        <SerieMensuelleMarches serie={serieMensuelle} />
      </Card>

      {/* ---------------------------------------------------------- */}
      {/* Qualité de publication : délai notification -> publication  */}
      {/* ---------------------------------------------------------- */}
      {qp && (
        <Card
          titre="Qualité de publication"
          sousTitre="Délai entre la notification d’un marché et la première publication de ses données"
          droite={badgeS1}
        >
          <p className="max-w-3xl text-sm leading-relaxed text-ink-secondary">
            Les données d’un marché notifié doivent être publiées dans un
            délai légal de {formatNombre(qp.synthese.delai_legal_mois)}&nbsp;mois. Ce délai
            se mesure sur{" "}
            <strong className="font-medium text-ink">
              {formatNombre(qp.synthese.nb_retenus)} marchés
            </strong>{" "}
            — ceux dont la notification et la première publication sont l’une
            et l’autre connues et cohérentes — sur les{" "}
            {formatNombre(qp.synthese.nb_marches_source)} marchés que compte la
            source.
            {qp.synthese.date_observation_max !== null && (
              <>
                {" "}
                La publication la plus récente prise en compte date du{" "}
                {formatDateFr(qp.synthese.date_observation_max)}.
              </>
            )}{" "}
            Un marché jamais publié n’a, lui, aucun délai : il ne figure dans
            aucun des taux qui suivent, alors qu’il y serait hors délai. Ces
            taux sont donc à lire comme une{" "}
            <strong className="font-medium text-ink">borne haute</strong> du
            respect du délai, et non comme le respect réel : prendre ces
            marchés en compte ne pourrait que faire baisser ces taux.
          </p>

          {/* ---- Distribution du délai : quartiles + 9e décile ---- */}
          <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Quantile libelle="1er quartile" valeur={qp.synthese.delai_q1} />
            <Quantile libelle="Médiane" valeur={qp.synthese.delai_median} />
            <Quantile libelle="3e quartile" valeur={qp.synthese.delai_q3} />
            <Quantile libelle="9e décile" valeur={qp.synthese.delai_d9} />
          </div>
          <p className="mt-3 max-w-3xl text-xs leading-relaxed text-ink-muted">
            Un quart des marchés retenus sont publiés en{" "}
            {formatJours(qp.synthese.delai_q1)} ou moins et la moitié en{" "}
            {formatJours(qp.synthese.delai_median)} ou moins ; un quart dépasse{" "}
            {formatJours(qp.synthese.delai_q3)} et un dixième dépasse{" "}
            {formatJours(qp.synthese.delai_d9)}. C’est cette queue longue qui
            commande la fenêtre de la ventilation par acheteur ci-dessous : une
            année de notification récente compte encore des marchés dont les
            données ne sont pas publiées, et son taux repose donc sur un
            dénominateur incomplet.
          </p>

          {/* grid-cols-1 explicite : piste minmax(0,1fr) — sans elle, la piste
              implicite « auto » s'élargit au min-content des libellés (débord mobile). */}
          <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-2">
            {/* ---- Série par année de notification ---- */}
            <div>
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-ink-secondary">
                Publication dans le délai légal, par année de notification
              </h3>
              <BarChart
                items={anneesChiffrees.map((a) => ({
                  libelle:
                    a.cohorte_close === 1
                      ? String(a.annee)
                      : `${a.annee}${ESPACE_FINE}*`,
                  // Dé-emphase des cohortes provisoires : leur dénominateur
                  // est incomplet, elles ne se comparent pas aux autres.
                  couleur: a.cohorte_close === 1 ? undefined : "var(--viz-autre)",
                  valeur: a.taux_dans_delai ?? 0,
                }))}
                formatValeur={(v) => formatPct(v, 0)}
                // Chaque abscisse est une ANNÉE : elle porte l'information et
                // ne se devine pas d'après ses voisines. On étiquette donc
                // toutes les colonnes plutôt que d'en laisser éclaircir une
                // sur deux par le réglage par défaut.
                maxEtiquettesX={anneesChiffrees.length}
                ariaLabel={`Part des marchés publiés dans le délai légal de ${qp.synthese.delai_legal_mois} mois, par année de notification`}
              />
              <p className="mt-2 text-xs leading-relaxed text-ink-muted">
                Part des marchés d’une année de notification dont les données
                ont été publiées dans le délai légal.
                {anneesProvisoires.length > 0 && (
                  <>
                    {" "}
                    Les colonnes grises suivies d’un astérisque —{" "}
                    {anneesProvisoires.map((a) => a.annee).join(", ")} — sont{" "}
                    <strong className="font-medium text-ink">provisoires</strong>{" "}
                    : leur dénominateur est incomplet, car les marchés notifiés
                    ces années-là et restés non publiés à ce jour n’y figurent
                    pas. Leur taux est optimiste par construction et ne se
                    compare pas aux années closes, qui vont jusqu’à{" "}
                    {qp.synthese.cohorte_max}.
                  </>
                )}
              </p>
              <VueTableau resume="Vue tableau — par année de notification">
                <DataTable
                  colonnes={[
                    {
                      cle: "annee",
                      entete: "Année",
                      largeur: "4.5rem",
                      rendu: (a) => String(a.annee),
                    },
                    { cle: "nb_marches", entete: "Marchés", type: "nombre" },
                    { cle: "nb_dans_delai", entete: "Dans le délai", type: "nombre" },
                    { cle: "taux_dans_delai", entete: "Part", type: "pourcent" },
                    {
                      cle: "delai_median",
                      entete: "Délai médian (j)",
                      type: "nombre",
                    },
                    { cle: "nb_plus_un_an", entete: "Plus d’un an", type: "nombre" },
                    {
                      cle: "cohorte_close",
                      entete: "Cohorte",
                      rendu: (a) =>
                        a.cohorte_close === 1 ? "Close" : "Provisoire",
                    },
                  ]}
                  lignes={qp.annees}
                  cleLigne={(a) => String(a.annee)}
                  vide="Aucune année mesurée"
                />
              </VueTableau>
            </div>

            {/* ---- Ventilation par catégorie d'acheteur ---- */}
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-[0.08em] text-ink-secondary">
                Écart entre catégories d’acheteurs
              </h3>
              <p className="mb-3 text-xs text-ink-muted">
                Marchés notifiés de {qp.synthese.cohorte_min} à{" "}
                {qp.synthese.cohorte_max} — cohortes closes seules.
              </p>
              <BarList
                items={acheteursChiffres.map((a) => ({
                  libelle: a.categorie,
                  valeur: a.taux_dans_delai ?? 0,
                }))}
                formatValeur={(v) => formatPct(v)}
                largeurLibelle="45%"
              />
              <p className="mt-2 text-xs leading-relaxed text-ink-muted">
                Part des marchés publiés dans le délai légal, par catégorie
                d’acheteur ; barres proportionnelles au taux le plus élevé de
                la liste. L’écart d’une catégorie à l’autre décrit une pratique
                de publication : il ne dit rien des raisons du retard, et cette
                donnée seule ne qualifie aucun manquement.
              </p>
              <VueTableau resume="Vue tableau — par catégorie d’acheteur">
                <DataTable
                  colonnes={[
                    { cle: "categorie", entete: "Catégorie d’acheteur" },
                    { cle: "nb_marches", entete: "Marchés", type: "nombre" },
                    { cle: "nb_dans_delai", entete: "Dans le délai", type: "nombre" },
                    { cle: "taux_dans_delai", entete: "Part", type: "pourcent" },
                    {
                      cle: "delai_median",
                      entete: "Délai médian (j)",
                      type: "nombre",
                    },
                    { cle: "nb_plus_un_an", entete: "Plus d’un an", type: "nombre" },
                    {
                      cle: "taux_plus_un_an",
                      entete: "Part plus d’un an",
                      type: "pourcent",
                    },
                  ]}
                  lignes={qp.acheteurs}
                  cleLigne={(a) => a.categorie}
                  vide="Aucune catégorie d’acheteur renseignée"
                />
              </VueTableau>
            </div>
          </div>

          {/* ---- Les limites, sur la page et non en note de bas de page ---- */}
          <div className="mt-6 max-w-3xl rounded-xl border border-card-border bg-raised p-4">
            <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
              Ce que cette mesure ne couvre pas
            </h3>
            <ul className="flex flex-col gap-1.5 text-xs leading-relaxed text-ink-secondary">
              <li>
                Seuls les marchés{" "}
                <strong className="font-medium text-ink">publiés</strong> ont un
                délai mesurable :{" "}
                <strong className="font-medium text-ink">
                  {formatNombre(qp.synthese.nb_sans_publication)} marchés
                </strong>{" "}
                de la source n’ont aucune date de première publication. Ils
                manquent au numérateur comme au dénominateur de chaque taux, et
                y seraient hors délai — c’est ce qui fait de tous les taux de
                cette section des bornes hautes.
              </li>
              <li>
                La ventilation par catégorie d’acheteur ne couvre pas tout :
                elle porte sur {formatNombre(nbAcheteursCouverts)} marchés des
                cohortes closes, et{" "}
                <strong className="font-medium text-ink">
                  {formatNombre(qp.synthese.nb_sans_categorie)} marchés
                </strong>{" "}
                de ces mêmes cohortes n’ont aucune catégorie d’acheteur
                renseignée
                {partSansCategorie !== null && (
                  <>, soit {formatPct(partSansCategorie)} d’entre eux</>
                )}
                . Ils ne figurent dans aucune barre et ne forment pas une
                catégorie de plus.
              </li>
              <li>
                <strong className="font-medium text-ink">
                  {formatNombre(qp.synthese.nb_publication_anterieure)} marchés
                </strong>{" "}
                portent une première publication antérieure à leur notification
                {partPublicationAnterieure !== null && (
                  <>, soit {formatPct(partPublicationAnterieure)} de la source</>
                )}
                . Ils sont écartés du calcul du délai et comptés à part : un
                délai négatif n’est pas ramené à zéro.
              </li>
              <li>
                {formatNombre(qp.synthese.nb_sans_notification)} marchés n’ont
                pas de date de notification et{" "}
                {formatNombre(qp.synthese.nb_dates_hors_bornes)} portent des
                dates hors des bornes plausibles (dates sentinelles). Eux aussi
                restent hors du calcul, plutôt que comptés au hasard.
              </li>
              <li>
                La ventilation par acheteur porte sur les seules années de
                notification{" "}
                <strong className="font-medium text-ink">
                  {qp.synthese.cohorte_min} à {qp.synthese.cohorte_max}
                </strong>
                , celles dont le dénominateur est complet
                {anneesProvisoires.length > 0 && (
                  <>
                    {" "}
                    ; les cohortes{" "}
                    {anneesProvisoires.map((a) => a.annee).join(", ")} restent
                    provisoires et n’y entrent pas
                  </>
                )}
                .
              </li>
            </ul>
          </div>
        </Card>
      )}

      {/* ---------------------------------------------------------- */}
      {/* Top acheteurs / top titulaires                              */}
      {/* ---------------------------------------------------------- */}
      <Card
        titre="Principaux acheteurs et titulaires"
        sousTitre="12 derniers mois, par entreprise (SIREN) — classement par montant notifié écrêté"
        droite={badgeS1}
      >
        {/* grid-cols-1 explicite : piste minmax(0,1fr) — sans elle, la piste
            implicite « auto » s'élargit au min-content des libellés (débord mobile). */}
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
          <div>
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-ink-secondary">
              Top acheteurs
            </h3>
            <BarList
              items={donnees.topAcheteurs.map((a) => ({
                libelle: a.nom ?? a.siren ?? "—",
                valeur: a.montant_total ?? 0,
              }))}
              formatValeur={(v) => formatEuros(v)}
              largeurLibelle="45%"
            />
            {qa && (
              <p className="mt-2 text-xs leading-relaxed text-ink-muted">
                Les identifiants d’acheteur qui ne sont pas un SIRET (14
                chiffres, rien d’autre) sont écartés de ce classement et
                comptés à part :{" "}
                {formatNombre(qa.nb_marches_ecartes)} marchés sur{" "}
                {formatNombre(qa.nb_marches_avec_acheteur)}, portant{" "}
                {qa.montant_ecarte !== null ? formatEuros(qa.montant_ecarte) : "—"},
                sous {formatNombre(qa.nb_identifiants_ecartes)} valeurs
                d’identifiant distinctes
                {formesIdentifiantsEcartes && formesIdentifiantsEcartes.length > 0 ? (
                  <>
                    {" "}
                    — {formesIdentifiantsEcartes.map((f, i) => (
                      <span key={f.classe}>
                        {i > 0 ? (i === formesIdentifiantsEcartes.length - 1 ? " et " : ", ") : ""}
                        {f.libelle} ({formatNombre(f.nb_identifiants)},{" "}
                        {formatNombre(f.nb_marches)}{" "}
                        {f.nb_marches < 2 ? "marché" : "marchés"})
                      </span>
                    ))}
                  </>
                ) : null}
                . Un numéro à 13 chiffres n’est pas complété d’un zéro de
                tête.
              </p>
            )}
            <VueTableau resume="Vue tableau — top acheteurs">
              <DataTable
                colonnes={[
                  { cle: "rang", entete: "Rang", type: "nombre", largeur: "3.5rem" },
                  {
                    cle: "nom",
                    entete: "Acheteur",
                    rendu: (a) => <span title={a.nom ?? undefined}>{tronque(a.nom, 60)}</span>,
                  },
                  { cle: "siren", entete: "SIREN", rendu: (a) => a.siren ?? "—" },
                  {
                    cle: "nb_etablissements",
                    entete: "Établissements",
                    type: "nombre",
                  },
                  { cle: "nb_marches", entete: "Marchés", type: "nombre" },
                  {
                    cle: "montant_total",
                    entete: "Montant",
                    type: "montant",
                    rendu: (a) =>
                      a.montant_total === null ? "—" : <Money valeur={a.montant_total} />,
                  },
                ]}
                lignes={donnees.topAcheteurs}
                cleLigne={(a) => String(a.rang)}
              />
            </VueTableau>
          </div>
          <div>
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-ink-secondary">
              Top titulaires
            </h3>
            <BarList
              items={donnees.topTitulaires.map((t) => ({
                libelle: t.nom ?? t.siren ?? "—",
                valeur: t.montant_total ?? 0,
              }))}
              formatValeur={(v) => formatEuros(v)}
              largeurLibelle="45%"
            />
            <p className="mt-2 text-xs leading-relaxed text-ink-muted">
              Montant d’un marché multi-titulaires réparti à parts égales
              entre co-titulaires.
            </p>
            <VueTableau resume="Vue tableau — top titulaires">
              <DataTable
                colonnes={[
                  { cle: "rang", entete: "Rang", type: "nombre", largeur: "3.5rem" },
                  {
                    cle: "nom",
                    entete: "Titulaire",
                    rendu: (t) => <span title={t.nom ?? undefined}>{tronque(t.nom, 60)}</span>,
                  },
                  { cle: "siren", entete: "SIREN", rendu: (t) => t.siren ?? "—" },
                  { cle: "categorie", entete: "Catégorie", rendu: (t) => t.categorie ?? "—" },
                  {
                    cle: "nb_etablissements",
                    entete: "Établissements",
                    type: "nombre",
                  },
                  { cle: "nb_marches", entete: "Marchés", type: "nombre" },
                  {
                    cle: "montant_total",
                    entete: "Montant",
                    type: "montant",
                    rendu: (t) =>
                      t.montant_total === null ? "—" : <Money valeur={t.montant_total} />,
                  },
                ]}
                lignes={donnees.topTitulaires}
                cleLigne={(t) => String(t.rang)}
              />
            </VueTableau>
          </div>
        </div>
        {/* ---- La règle de regroupement et sa limite, sur la page ---- */}
        <div className="mt-6 max-w-3xl rounded-xl border border-card-border bg-raised p-4">
          <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
            Ce que compte une ligne
          </h3>
          <p className="text-xs leading-relaxed text-ink-secondary">
            Une ligne est une{" "}
            <strong className="font-medium text-ink">entreprise</strong> — une
            personne morale, identifiée par son{" "}
            <strong className="font-medium text-ink">SIREN</strong>. Les marchés
            de tous ses établissements sont regroupés sur cette ligne unique, et
            la colonne «&nbsp;Établissements&nbsp;» dit combien d’établissements
            distincts de cette entreprise figurent dans les marchés de la
            période — et non combien elle en compte. Le nom affiché est la
            dénomination du répertoire Sirene quand le SIREN y figure, sinon le
            nom déclaré dans les données de marché.
          </p>
          <p className="mt-2 text-xs leading-relaxed text-ink-secondary">
            Le regroupement s’arrête à l’entreprise : il ne remonte pas au
            groupe. POMONA et POMONA EPISAVEURS sont deux SIREN, donc deux
            entreprises distinctes, dont les montants ne sont jamais
            additionnés. Le site n’exploite aucun référentiel de liens
            capitalistiques : un classement «&nbsp;par groupe&nbsp;» serait une
            reconstitution, pas une mesure.
          </p>
          {qt && (
            <p className="mt-2 text-xs leading-relaxed text-ink-secondary">
              Un identifiant de titulaire dont on ne peut extraire aucun SIREN
              ne se rattache à aucune entreprise : sa ligne est écartée du
              classement et comptée à part. Sur les 12&nbsp;mois,{" "}
              <strong className="font-medium text-ink">
                {formatNombre(qt.nb_lignes_ecartees)} lignes
              </strong>{" "}
              sur {formatNombre(qt.nb_lignes)} sont dans ce cas, réparties sur{" "}
              {formatNombre(qt.nb_identifiants_ecartes)} valeurs d’identifiant
              distinctes, et portent{" "}
              <strong className="font-medium text-ink">
                {qt.montant_ecarte !== null ? formatEuros(qt.montant_ecarte) : "—"}
              </strong>
              {partEcartee !== null && (
                <>, soit {formatPct(partEcartee)} du montant des titulaires</>
              )}{" "}
              — un montant que ce classement n’attribue à aucune entreprise.
            </p>
          )}
          {qt && (
            <p className="mt-2 text-xs leading-relaxed text-ink-muted">
              Le classement retient{" "}
              {formatNombre(qt.nb_lignes_identifiables)} lignes, soit{" "}
              {formatNombre(qt.nb_sirets)} établissements ramenés à{" "}
              {formatNombre(qt.nb_sirens)} entreprises, dont{" "}
              {formatNombre(qt.nb_sirens_multi_etab)} présentes par plus d’un
              établissement. Une ligne est un couple marché × titulaire :{" "}
              {formatNombre(qt.nb_marches_avec_titulaire)} des{" "}
              {formatNombre(qt.nb_marches)} marchés de la fenêtre déclarent au
              moins un titulaire, et un marché à plusieurs co-titulaires produit
              autant de lignes.
            </p>
          )}
        </div>
      </Card>

      {/* ---------------------------------------------------------- */}
      {/* Répartition par procédure                                   */}
      {/* ---------------------------------------------------------- */}
      <Card
        titre="Répartition par procédure"
        sousTitre="Marchés notifiés sur 12 mois, par procédure de passation"
        droite={badgeS1}
      >
        <Donut
          parts={partsDonut}
          formatValeur={(v) => formatNombre(v)}
          libelleTotal="marchés · 12 mois"
          ariaLabel="Répartition des marchés notifiés sur 12 mois par procédure de passation"
        />
        <p className="mt-3 text-xs leading-relaxed text-ink-muted">
          « Non renseigné » = procédure absente de la déclaration source ;
          «&nbsp;Autres procédures&nbsp;» regroupe les{" "}
          {formatNombre(Math.max(nommees.length - 4, 0))} procédures les moins
          fréquentes — détail complet dans la vue tableau.
        </p>
        <VueTableau resume="Vue tableau — toutes les procédures">
          <DataTable
            colonnes={[
              {
                cle: "valeur",
                entete: "Procédure",
                rendu: (r) => r.valeur ?? "Non renseigné",
              },
              { cle: "nb_marches", entete: "Marchés", type: "nombre" },
              {
                cle: "part",
                entete: "Part",
                type: "pourcent",
                rendu: (r) =>
                  totalProcedures > 0
                    ? formatPct((100 * r.nb_marches) / totalProcedures)
                    : "—",
              },
              {
                cle: "montant_total",
                entete: "Montant (écrêté)",
                type: "montant",
                rendu: (r) =>
                  r.montant_total === null ? "—" : <Money valeur={r.montant_total} />,
              },
            ]}
            lignes={procedures}
            cleLigne={(r) => r.valeur ?? "(non renseigné)"}
          />
        </VueTableau>
      </Card>

      {/* ---------------------------------------------------------- */}
      {/* Derniers marchés notifiés                                   */}
      {/* ---------------------------------------------------------- */}
      <Card
        titre="Derniers marchés notifiés"
        sousTitre="Les 20 notifications les plus récentes du flux consolidé (J-1)"
        droite={badgeS1}
      >
        <DataTable
          colonnes={[
            { cle: "date_notification", entete: "Notifié le", type: "date", largeur: "6.5rem" },
            {
              cle: "acheteur_nom",
              entete: "Acheteur",
              rendu: (m) => (
                <span title={m.acheteur_nom ?? undefined}>{tronque(m.acheteur_nom, 48)}</span>
              ),
            },
            {
              cle: "objet",
              entete: "Objet",
              rendu: (m) => <span title={m.objet ?? undefined}>{tronque(m.objet, 80)}</span>,
            },
            {
              cle: "titulaire_nom",
              entete: "Titulaire",
              rendu: (m) => (
                <span title={m.titulaire_nom ?? undefined}>
                  {tronque(m.titulaire_nom, 36)}
                  {m.nb_titulaires > 1 && (
                    <span className="text-ink-muted"> +{m.nb_titulaires - 1} co-tit.</span>
                  )}
                </span>
              ),
            },
            {
              cle: "montant_retenu",
              entete: "Montant",
              type: "montant",
              rendu: (m) =>
                m.montant_retenu === null ? (
                  <span title="Montant non renseigné à la source">—</span>
                ) : (
                  <span className="inline-flex items-baseline gap-1.5">
                    <Money valeur={m.montant_retenu} />
                    {(m.techniques ?? "").includes("Accord-cadre") && (
                      <span
                        className="text-[11px] text-ink-muted"
                        title="Accord-cadre : le montant notifié est un maximum, pas du dépensé."
                      >
                        max
                      </span>
                    )}
                    {m.montant_suspect === 1 && <EtiquetteSuspect />}
                  </span>
                ),
            },
          ]}
          lignes={donnees.derniersMarches}
          cleLigne={(m) => m.uid}
          vide="Aucun marché dans le flux"
        />
        <p className="mt-3 text-xs leading-relaxed text-ink-muted">
          Montants retenus tels que déclarés (non écrêtés dans ce détail) ;
          « max » signale un accord-cadre (montant = maximum) ; « suspect » =
          anomalie signalée à la source ou montant &gt; 100&nbsp;M€, écrêté
          des agrégats.
        </p>
      </Card>

      {/* ---------------------------------------------------------- */}
      {/* Appels d’offres en cours (BOAMP, S2)                        */}
      {/* ---------------------------------------------------------- */}
      <div id="appels-offres" className="scroll-mt-4">
        <Card
          titre="Appels d’offres en cours"
          sousTitre="BOAMP — instantané quotidien, re-filtré à chaque construction du site (annonces annulées et échéances passées écartées)"
          droite={
            meta.s2 && (
              <FreshnessBadge
                dateDonnees={meta.s2.date_donnees}
                source="BOAMP"
                frequence={meta.s2.frequence}
                url={meta.s2.url}
                mention={estJourDeConstruction(meta.s2.date_donnees) ? "jour même" : undefined}
              />
            )
          }
        >
          {/* rythme de publication : sparkline 31 jours + vue tableau */}
          <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2">
            <Sparkline
              valeurs={donnees.annoncesParJour.map((j) => j.nb)}
              largeur={240}
              hauteur={40}
              ariaLabel={`Annonces publiées par jour au BOAMP sur 31 jours, ${formatNombre(totalAnnonces31j)} au total`}
            />
            <p className="text-xs text-ink-secondary">
              {formatNombre(totalAnnonces31j)} annonces publiées en 31 jours
              (toutes natures : appels d’offres, attributions, rectificatifs)
              {donnees.annoncesParJour.length > 0 && (
                <span className="text-ink-muted">
                  {" "}
                  — du {formatDateFr(donnees.annoncesParJour[0].jour)} au{" "}
                  {formatDateFr(donnees.annoncesParJour[donnees.annoncesParJour.length - 1].jour)}
                </span>
              )}
            </p>
          </div>
          <VueTableau resume="Vue tableau — annonces par jour (31 j)">
            <DataTable
              hauteurMax="280px"
              colonnes={[
                { cle: "jour", entete: "Jour", type: "date" },
                { cle: "nb", entete: "Annonces", type: "nombre" },
                { cle: "nb_appels_offre", entete: "Appels d’offres", type: "nombre" },
                { cle: "nb_attributions", entete: "Attributions", type: "nombre" },
              ]}
              lignes={donnees.annoncesParJour}
              cleLigne={(j) => j.jour}
            />
          </VueTableau>

          {/* filtre par famille — côté client, fragments /data/marches/ao.json */}
          <AppelsOffres
            familles={familles}
            vueToutes={{
              total: donnees.aoTotalFiltre,
              sansMontant: donnees.aoSansMontantFiltre,
              lignes: donnees.ao,
            }}
            aoEnCours={kpis.aoEnCours}
          />
        </Card>
      </div>

      {/* ---------------------------------------------------------- */}
      {/* Achats publics annoncés (APProch, S9)                       */}
      {/* ---------------------------------------------------------- */}
      <Card
        titre="Achats publics annoncés"
        sousTitre="APProch (DAE/AIFE) — projets d’achats de l’État à publication prévue"
        droite={
          meta.s9 && (
            <FreshnessBadge
              dateDonnees={meta.s9.date_donnees}
              source="APProch"
              frequence={meta.s9.frequence}
              url={meta.s9.url}
            />
          )
        }
      >
        <DataTable
          colonnes={[
            {
              cle: "date_prev_publication",
              entete: "Publication prévue",
              type: "date",
              largeur: "8rem",
            },
            {
              cle: "intitule",
              entete: "Intitulé",
              rendu: (m) => <span title={m.intitule ?? undefined}>{tronque(m.intitule, 70)}</span>,
            },
            {
              cle: "acheteur_nom",
              entete: "Acheteur",
              rendu: (m) =>
                m.acheteur_nom ? (
                  <span title={`SIREN ${m.acheteur_siren ?? "inconnu"}`}>{m.acheteur_nom}</span>
                ) : m.acheteur_siren ? (
                  <span
                    className="text-ink-secondary"
                    title="SIREN nommé par aucun référentiel"
                  >
                    SIREN {m.acheteur_siren}
                  </span>
                ) : (
                  "—"
                ),
            },
            {
              cle: "categorie_achat",
              entete: "Catégorie",
              rendu: (m) => m.categorie_achat ?? "—",
            },
            {
              cle: "montant_estime_tranche",
              entete: "Tranche de montant",
              rendu: (m) =>
                m.montant_estime_tranche ?? (
                  <span className="text-ink-muted">non publié</span>
                ),
            },
            {
              cle: "lien_consultation",
              entete: "Consultation",
              rendu: (m) => <LienSortant href={m.lien_consultation} libelle="Fiche" />,
            },
          ]}
          lignes={donnees.marchesAVenir}
          cleLigne={(m) => m.code}
          vide="Aucun achat annoncé"
        />
        <p className="mt-3 text-xs leading-relaxed text-ink-muted">
          {formatNombre(donnees.marchesAVenir.length)} publications prévues
          les plus proches affichées sur{" "}
          {formatNombre(kpis.marchesAVenir)} projets. La source ne fournit que
          le SIREN de l’acheteur : le nom affiché est celui du référentiel des
          entités, ou à défaut la dénomination légale du répertoire Sirene.
          Quand aucun des deux ne nomme le SIREN, c’est le SIREN qui est
          affiché — aucun nom n’est reconstitué. Les montants sont des
          tranches indicatives en texte, non sommables.
        </p>
      </Card>

      {/* ---------------------------------------------------------- */}
      {/* Alertes du domaine (rendues seulement si présentes)         */}
      {/* ---------------------------------------------------------- */}
      {alertes.length > 0 && (
        <Card
          titre="Alertes marchés publics"
          sousTitre="Signaux calculés sur les données de la commande publique"
        >
          <div className="flex flex-col gap-3">
            {alertes.map((a: AlerteMarches) => {
              const g = graviteAlerte(a.gravite);
              return (
                <AlertItem
                  key={a.id}
                  gravite={g.gravite}
                  graviteLibelle={g.libelle}
                  titre={a.titre}
                  detail={a.detail ?? undefined}
                  regle={a.regle ?? undefined}
                  baseLegale={a.base_legale ?? undefined}
                  source={
                    a.source_url
                      ? { libelle: "Source amont", url: a.source_url }
                      : undefined
                  }
                />
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}
