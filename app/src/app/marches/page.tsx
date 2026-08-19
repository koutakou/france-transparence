import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AlertItem, type Gravite } from "@/components/ui/AlertItem";
import { AppelsOffres } from "@/components/client/AppelsOffres";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { CarteDepartements } from "@/components/client/CarteDepartements";
import { DataTable } from "@/components/ui/DataTable";
import { Donut, type DonutPart } from "@/components/ui/Donut";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { Money } from "@/components/ui/Money";
import { SerieMensuelleMarches } from "@/components/client/SerieMensuelleMarches";
import { Sparkline } from "@/components/ui/Sparkline";
import { StatStrip } from "@/components/ui/StatStrip";
import { TableTronquee } from "@/components/client/TableTronquee";
import { formatDateFr, formatEuros, formatNombre, formatPct } from "@/lib/format";
import { chargerDonneesMarches, type AlerteMarches } from "@/lib/queries/marches";

/**
 * Page STATIQUE (site pré-rendu quotidiennement) : tout est calculé au
 * build sur la base du jour ; le filtre BOAMP par famille et la carte
 * vivent côté client sur fragments /data/* (docs/deploiement/DECISION.md).
 * L'instantané BOAMP est re-filtré (annulations, échéances passées) à
 * chaque construction du site — pas à chaque affichage.
 */

export const metadata: Metadata = {
  title: "Commande publique",
  description:
    "Marchés publics notifiés et appels d’offres en cours : montants, attributaires, répartition par département — DECP consolidées et BOAMP, données datées.",
};

/* ------------------------------------------------------------------ */
/* Helpers d'affichage (purs, locaux à la page)                        */
/* ------------------------------------------------------------------ */

/** Tronque proprement un libellé long (le `title` porte le texte complet). */
function tronque(s: string | null, max: number): string {
  if (!s || s.trim() === "") return "—";
  return s.length > max ? `${s.slice(0, max - 1).trimEnd()}…` : s;
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

  const { meta, kpis, serieMensuelle, familles, alertes } = donnees;

  /* ---- KPI : tendances 12 derniers mois de la série mensuelle ---- */
  const douzeDerniers = serieMensuelle.slice(-12);
  const tendanceNb = douzeDerniers.map((m) => m.nb_marches);
  const montantsDouze = douzeDerniers.map((m) => m.montant_total);
  const tendanceMontant = montantsDouze.every((v): v is number => v !== null)
    ? montantsDouze
    : undefined;

  /* ---- Carte : montants par département (NULL écarté, jamais 0).
     Codes à 2 caractères = métropole + Corse, le périmètre réellement
     rendu par la carte (v1) : l'échelle de la légende ne doit décrire
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
          dépensé.
        </p>
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
          neutraliser les saisies aberrantes ({formatNombre(kpis.nbEcretes12m)}{" "}
          marchés au-delà du plafond sur 12&nbsp;mois, acheteurs à département
          connu) ; les montants non renseignés restent exclus des sommes —
          aucune valeur n’est inventée.
        </p>
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
              (jamais confondu avec 0&nbsp;€). Outre-mer hors rendu carte en
              v1 — les valeurs figurent dans le tableau. Montants écrêtés à
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
        sousTitre="36 derniers mois civils — les 2 derniers mois sont incomplets (latence légale de publication ≤ 2 mois)"
        droite={badgeS1}
      >
        <SerieMensuelleMarches serie={serieMensuelle} />
      </Card>

      {/* ---------------------------------------------------------- */}
      {/* Top acheteurs / top titulaires                              */}
      {/* ---------------------------------------------------------- */}
      <Card
        titre="Principaux acheteurs et titulaires"
        sousTitre="12 derniers mois, classement par montant notifié écrêté"
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
                libelle: a.nom ?? a.siret ?? "—",
                valeur: a.montant_total ?? 0,
              }))}
              formatValeur={(v) => formatEuros(v)}
              largeurLibelle="45%"
            />
            <VueTableau resume="Vue tableau — top acheteurs">
              <DataTable
                colonnes={[
                  { cle: "rang", entete: "Rang", type: "nombre", largeur: "3.5rem" },
                  {
                    cle: "nom",
                    entete: "Acheteur",
                    rendu: (a) => <span title={a.nom ?? undefined}>{tronque(a.nom, 60)}</span>,
                  },
                  { cle: "siret", entete: "SIRET", rendu: (a) => a.siret ?? "—" },
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
                libelle: t.nom ?? t.siret ?? "—",
                valeur: t.montant_total ?? 0,
              }))}
              formatValeur={(v) => formatEuros(v)}
              largeurLibelle="45%"
            />
            <p className="mt-2 text-xs text-ink-muted">
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
                  { cle: "categorie", entete: "Catégorie", rendu: (t) => t.categorie ?? "—" },
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
                  <span className="text-ink-secondary" title="SIREN absent du référentiel entités">
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
          le SIREN de l’acheteur — le nom est affiché quand ce SIREN figure au
          référentiel des entités. Les montants sont des tranches indicatives
          en texte, non sommables.
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
