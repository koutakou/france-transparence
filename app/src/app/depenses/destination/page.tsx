import type { Metadata } from "next";
import Link from "next/link";
import { BarList } from "@/components/ui/BarList";
import { JsonLd } from "@/components/JsonLd";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { NoticeLecture } from "@/components/ui/NoticeLecture";
import { ESPACE_FINE, formatEuros, formatNombre } from "@/lib/format";
import {
  getMissionsDestination2025Liste,
  getSourcesBudget,
  getTitresDestination2025,
  type MissionDestination2025,
} from "@/lib/queries/depenses";
import { jsonLdPage, metadonneesPage } from "@/lib/seo";

// Rendu statique : la donnée ne change qu'à l'ingestion, le site est
// reconstruit après chaque ingestion (docs/deploiement/DECISION.md).

// Titre, description et fil d'Ariane sont nommés une fois : les métadonnées
// et le balisage JSON-LD décrivent la même page, ils ne peuvent donc pas la
// décrire différemment.
const CHEMIN = "/depenses/destination/";
const TITRE = "Budget 2025 par destination";
const DESCRIPTION =
  "Les 46 missions du budget de l'État (PLF 2025) et leur ventilation par titre : chaque mission se déplie en programmes, actions et sous-actions — crédits de paiement et autorisations d'engagement.";

export const metadata: Metadata = metadonneesPage({
  chemin: CHEMIN,
  titre: TITRE,
  description: DESCRIPTION,
});

const BALISAGE = jsonLdPage({
  chemin: CHEMIN,
  nom: TITRE,
  description: DESCRIPTION,
  ariane: [
    { nom: "Accueil", chemin: "/" },
    { nom: "Dépenses de l'État", chemin: "/depenses/" },
    { nom: TITRE },
  ],
});

/** `823041234567` → `823,0 Md€` (précision maîtrisée). */
function enMd(v: number, decimales = 1): string {
  return `${formatNombre(v / 1e9, decimales)}${ESPACE_FINE}Md€`;
}

/**
 * Index de l'exploration par destination (S21) : ventilation par titre
 * LOLF, puis les 46 missions — chacune ouvrant sa page statique
 * programme → action → sous-action. Tout est pré-rendu au build, aucun
 * chargement dynamique.
 */
export default async function PageDestination() {
  const sources = getSourcesBudget();
  const titres = getTitresDestination2025();
  const missions = getMissionsDestination2025Liste();

  if (!sources || !missions) {
    return (
      <section className="flex flex-col gap-4">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Budget 2025 par destination
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          La base locale n&apos;est pas encore construite — lancer{" "}
          <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code>{" "}
          pour ingérer les sources budgétaires.
        </div>
      </section>
    );
  }

  const badge = sources.S21 && (
    <FreshnessBadge
      dateDonnees={sources.S21.date_donnees}
      source="PLF 2025 — destination"
      frequence={sources.S21.frequence}
      url={sources.S21.url}
      mention="PLF 2025 — projet"
    />
  );

  // La mission « Remboursements et dégrèvements » explique l'essentiel de
  // l'écart entre ces CP bruts et les dépenses nettes de /depenses : on la
  // nomme avec son montant réellement en base plutôt qu'en dur.
  const remboursements = missions.missions.find((m) => m.mission === "RD");

  const colonnesMissions = [
    {
      cle: "libelle",
      entete: "Mission",
      rendu: (m: MissionDestination2025) => (
        <Link
          href={`/depenses/destination/${m.slug}/`}
          className="text-ink underline decoration-[var(--viz-grid)] underline-offset-2 transition-colors hover:decoration-current"
        >
          {m.libelle}
        </Link>
      ),
    },
    { cle: "typebudget", entete: "Budget", largeur: "5rem" },
    { cle: "nbProgrammes", entete: "Programmes", type: "nombre" as const },
    { cle: "cpMd", entete: "CP (Md€)", type: "montant" as const, decimales: 2 },
    { cle: "aeMd", entete: "AE (Md€)", type: "montant" as const, decimales: 2 },
  ];

  return (
    <div className="flex flex-col gap-6">
      <JsonLd donnees={BALISAGE} />
      {/* En-tête de module */}
      <section className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="max-w-2xl">
          <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
            Budget 2025 par destination
          </h1>
          <p className="mt-2 text-sm text-ink-secondary">
            Le budget de l&apos;État se lit en missions (les politiques
            publiques), découpées en programmes, actions et — quand la
            nomenclature en définit — sous-actions. Montants&nbsp;:{" "}
            {missions.etiquette}. Ce sont des crédits de paiement (CP) et
            autorisations d&apos;engagement (AE) BRUTS&nbsp;: ils ne sont pas
            comparables aux dépenses nettes de la page{" "}
            <Link href="/depenses" className="underline decoration-[var(--viz-grid)] underline-offset-2 hover:decoration-current">
              Dépenses
            </Link>
            .
          </p>
          <NoticeLecture
            ancre="depenses"
            commentLire={
              <p>
                Ces montants sont ceux du projet de loi de finances, pas de
                l’exécution mensuelle ni de la loi de finances votée. CP et
                AE sont bruts : ils ne se comparent pas aux dépenses nettes
                de la page Dépenses. Une mission n’est pas un ministère.
              </p>
            }
            provenance={
              <p>
                Projet de loi de finances 2025, répartition par destination
                (missions, programmes, actions). Une LFI 2025 par mission
                est publiée dans le budget vert ; ce n’est pas la
                granularité sous-action × nature.
              </p>
            }
            limites={
              <p>
                Ce n’est pas ce qui a été payé. Les paiements du système
                Chorus ne sont pas en open data. La mission
                «&nbsp;Pensions&nbsp;» est un compte d’affectation spéciale,
                pas une politique comparable aux autres.
              </p>
            }
          />
        </div>
        {badge}
      </section>

      {/* Ventilation par nature (titre LOLF) */}
      {titres && (
        <Card
          titre="Ventilation par titre (nature de la dépense)"
          sousTitre={`Tous budgets confondus — ${enMd(titres.totalCp)} de CP bruts, PLF 2025`}
          droite={badge}
        >
          <BarList
            items={titres.titres.map((t) => ({
              libelle: t.libelle ?? `Titre ${t.titre}`,
              valeur: t.cp,
            }))}
            formatValeur={(v) => formatEuros(v, "Md")}
          />
          <div className="mt-4">
            <DataTable
              colonnes={[
                { cle: "numero", entete: "Titre", largeur: "4rem" },
                { cle: "libelle", entete: "Nature" },
                { cle: "cpMd", entete: "CP (Md€)", type: "montant", decimales: 2 },
                { cle: "aeMd", entete: "AE (Md€)", type: "montant", decimales: 2 },
                { cle: "part", entete: "Part des CP", type: "pourcent", decimales: 1 },
              ]}
              lignes={titres.titres.map((t) => ({
                numero: t.titre,
                libelle: t.libelle ?? "—",
                cpMd: t.cp / 1e9,
                aeMd: t.ae / 1e9,
                part: titres.totalCp > 0 ? (t.cp / titres.totalCp) * 100 : null,
              }))}
              cleLigne={(l) => l.numero}
            />
          </div>
          <p className="mt-3 text-xs text-ink-muted">
            Le titre décrit la nature de la dépense (nomenclature LOLF,
            art. 5)&nbsp;; chaque titre se subdivise en catégories dans la
            source. Les AE engagent l&apos;État sur plusieurs années, les CP
            couvrent les paiements de l&apos;année&nbsp;: les deux colonnes ne
            s&apos;additionnent pas.
          </p>
        </Card>
      )}

      {/* Les 46 missions */}
      <Card
        titre="Les missions du budget de l'État"
        sousTitre={`${formatNombre(missions.missions.length)} missions — cliquer une mission pour la déplier en programmes, actions et sous-actions`}
        droite={badge}
      >
        <DataTable
          colonnes={colonnesMissions}
          lignes={missions.missions.map((m) => ({
            ...m,
            cpMd: m.cp / 1e9,
            aeMd: m.ae / 1e9,
          }))}
          cleLigne={(m) => m.mission}
          hauteurMax="34rem"
        />
        <p className="mt-3 text-xs text-ink-muted">
          Budget&nbsp;: BG&nbsp;= budget général, BA&nbsp;= budgets annexes,
          CAS&nbsp;= comptes d&apos;affectation spéciale, CCF&nbsp;= comptes de
          concours financiers. Total tous budgets&nbsp;:{" "}
          {enMd(missions.totalCp)} de CP bruts.
          {remboursements && (
            <>
              {" "}La mission «&nbsp;Remboursements et dégrèvements&nbsp;» (
              {enMd(remboursements.cp)}) retrace les sommes reversées aux
              contribuables&nbsp;: c&apos;est elle qui explique
              l&apos;essentiel de l&apos;écart entre ces montants bruts et les
              dépenses nettes publiées par la DGFiP.
            </>
          )}
        </p>
      </Card>

      {/* Encadré pédagogique obligatoire — CAS Pensions */}
      <Card titre="Ce que la mission « Pensions » couvre — et ne couvre pas">
        <div className="flex max-w-3xl flex-col gap-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            La mission «&nbsp;Pensions&nbsp;» est un compte d&apos;affectation
            spéciale (CAS). Elle couvre les pensions dont l&apos;État est
            l&apos;employeur&nbsp;: retraites des fonctionnaires civils de
            l&apos;État, retraites des militaires, pensions des ouvriers des
            établissements industriels de l&apos;État, et pensions militaires
            d&apos;invalidité et des victimes de guerre.
          </p>
          <p>
            Les retraites du régime général (CNAV), l&apos;assurance maladie
            et les prestations familiales (CAF) relèvent de la loi de
            financement de la sécurité sociale, hors budget de
            l&apos;État&nbsp;: elles ne figurent pas ici.
          </p>
        </div>
      </Card>
    </div>
  );
}
