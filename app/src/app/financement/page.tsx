import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AlertItem, type Gravite } from "@/components/ui/AlertItem";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { Donut } from "@/components/ui/Donut";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { LineChart } from "@/components/ui/LineChart";
import { StatStrip } from "@/components/ui/StatStrip";
import { formatNombre, formatPct } from "@/lib/format";
import {
  getDonneesFinancement,
  type AidePubliqueAnnee,
  type CampagneTopDepense,
  type DecisionDetail,
  type PartiTopProduits,
} from "@/lib/queries/financement";

// Rendu statique : la donnée ne change qu'à l'ingestion, le site est
// reconstruit après chaque ingestion (docs/deploiement/DECISION.md).

export const metadata: Metadata = {
  title: "Financement de la vie politique",
  description:
    "Comptes des partis politiques, dons et cotisations, aide publique et comptes de campagne (CNCCFP) : les flux d'argent de la vie politique, sourcés et datés.",
};

/** Toggle « Vue tableau » — la jumelle WCAG de chaque graphique (DATAVIZ §7/§9). */
function VueTableau({ children }: { children: ReactNode }) {
  return (
    <details className="group mt-3">
      <summary className="cursor-pointer list-none text-xs text-ink-muted transition-colors hover:text-ink-secondary">
        <span
          aria-hidden="true"
          className="mr-1 inline-block transition-transform group-open:rotate-90"
        >
          ›
        </span>
        Vue tableau
      </summary>
      <div className="mt-2">{children}</div>
    </details>
  );
}

/** Gravité base (`haute`/`moyenne`/`info`) → gravité visuelle + libellé affiché. */
function graviteUi(g: string): { gravite: Gravite; libelle: string } {
  if (g === "haute") return { gravite: "serieux", libelle: "Gravité haute" };
  if (g === "moyenne") return { gravite: "attention", libelle: "Gravité moyenne" };
  return { gravite: "attention", libelle: "Info" };
}

/** Montant en millions d'euros, décimales maîtrisées (`70,3 M€`, `64,26 M€`). */
function enMillions(v: number, decimales = 1): string {
  return `${formatNombre(v / 1e6, decimales)} M€`;
}

/** Libellés complets des familles de décision CNCCFP (codes natifs A/AR/R…). */
const LIBELLES_FAMILLES: Record<string, string> = {
  approuve: "Approuvé",
  approuve_apres_reformation: "Approuvé après réformation",
  rejete: "Rejeté",
  dispense_depot: "Dispensé de dépôt",
  absence_depot: "Absence de dépôt",
  hors_delai: "Déposé hors délai",
};

/** Ligne de la vue tableau jumelle du donut des ressources. */
type RessourceLigne = { type: string; montant: number };

/**
 * Financement de la vie politique — comptes des partis (CNCCFP, S25),
 * aide publique (S25 + décret 2026, S37) et comptes de campagne des
 * législatives 2024 (S29). Données 100 % réelles de data/france.db.
 */
export default async function FinancementPage() {
  const donnees = getDonneesFinancement();

  if (!donnees) {
    return (
      <section className="flex flex-col gap-6">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Financement de la vie politique
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          <p>
            La base locale n&apos;est pas encore construite (ou les sources
            CNCCFP ne sont pas ingérées) — lancer{" "}
            <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code>{" "}
            pour ingérer les sources.
          </p>
        </div>
      </section>
    );
  }

  const {
    metaPartis,
    metaCampagnes,
    metaDecret,
    kpi,
    comptesHorsEuros,
    topProduits,
    ressources2024,
    aideEvolution,
    aide2026,
    campagnes,
    decisionsFamilles,
    decisionsDetail,
    topDepenses,
    nbReformationHausse,
    alertesRejets,
    alertesDependance,
    alerteDocumentaire,
  } = donnees;

  const badgePartis = (
    <FreshnessBadge
      dateDonnees={metaPartis.date_donnees}
      source="CNCCFP — comptes des partis"
      frequence={metaPartis.frequence}
      url={metaPartis.url}
      mention="exercice 2024 publié le 10/02/2026"
    />
  );
  const badgeCampagnes = (
    <FreshnessBadge
      dateDonnees={metaCampagnes.date_donnees}
      source="CNCCFP — législatives 2024"
      frequence={metaCampagnes.frequence}
      url={metaCampagnes.url}
      mention="décisions publiées le 29/07/2025"
    />
  );

  const aide2024 = aideEvolution.find((a) => a.exercice === 2024) ?? null;
  /** Comptes effectivement déposés = candidats − dispensés − absences (règle de la vue). */
  const comptesDeposes =
    campagnes.nb_candidats - campagnes.nb_dispenses_depot - campagnes.nb_absences_depot;
  const familleRejete = decisionsFamilles.find((f) => f.decision_famille === "rejete") ?? null;

  const ressourcesParts = ressources2024
    ? [
        { libelle: "Aide publique", valeur: ressources2024.aide_publique },
        {
          libelle: "Cotisations (adhérents + élus)",
          valeur: ressources2024.cotisations_adherents + ressources2024.cotisations_elus,
        },
        { libelle: "Autres produits", valeur: ressources2024.autres_produits },
        { libelle: "Dons", valeur: ressources2024.dons },
        { libelle: "Contributions reçues", valeur: ressources2024.contributions_recues },
      ].sort((a, b) => b.valeur - a.valeur)
    : [];

  const ressourcesLignes: RessourceLigne[] = ressources2024
    ? [
        { type: "Dons", montant: ressources2024.dons },
        { type: "Cotisations d'adhérents", montant: ressources2024.cotisations_adherents },
        { type: "Cotisations d'élus", montant: ressources2024.cotisations_elus },
        {
          type: "Aide publique (fractions 1 + 2 et autres aides publiques)",
          montant: ressources2024.aide_publique,
        },
        { type: "Contributions reçues", montant: ressources2024.contributions_recues },
        { type: "Autres produits", montant: ressources2024.autres_produits },
      ]
    : [];

  return (
    <section className="flex flex-col gap-6">
      {/* ── En-tête ─────────────────────────────────────────────────── */}
      <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="max-w-2xl">
          <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
            Financement de la vie politique
          </h1>
          <p className="mt-2 text-sm text-ink-secondary">
            Comptes des partis et groupements politiques certifiés par leurs
            commissaires aux comptes et déposés à la Commission nationale des
            comptes de campagne et des financements politiques (CNCCFP).
            Dernier exercice publié : 2024, paru le 10 février 2026.
          </p>
        </div>
        {badgePartis}
      </header>

      {/* ── KPI ─────────────────────────────────────────────────────── */}
      <StatStrip
        stats={[
          {
            label: "Produits totaux des partis (2024)",
            valeur: enMillions(kpi.produits2024),
            montantVedette: true,
          },
          {
            label: "Aide publique 2024 (fractions 1 + 2)",
            valeur: aide2024 ? enMillions(aide2024.aide_f1_f2) : "non publié",
          },
          {
            label: "Aide publique 2026 (décret n° 2026-149)",
            valeur: aide2026 ? enMillions(aide2026.montant_total_eur, 2) : "non publié",
          },
          {
            label: "Partis ayant déposé leurs comptes (2024)",
            valeur: formatNombre(kpi.depots2024),
          },
        ]}
      />
      {comptesHorsEuros.nb > 0 && (
        <p className="text-xs text-ink-muted">
          {comptesHorsEuros.nb} comptes de l&apos;exercice{" "}
          {comptesHorsEuros.exercice_min} déposés hors euros (francs pacifiques
          XPF ou unité absente) sont exclus des agrégats en euros.
        </p>
      )}

      {/* ── Top 10 des partis par produits ───────────────────────────── */}
      <Card
        titre="Partis par produits (exercice 2024)"
        sousTitre="Top 10 par produits totaux inscrits aux comptes déposés — comptes en euros."
        droite={badgePartis}
      >
        <BarList
          items={topProduits.map((p) => ({
            libelle: p.nom,
            valeur: p.produits_total ?? 0,
          }))}
          formatValeur={(v) => enMillions(v, 2)}
        />
        <VueTableau>
          <DataTable<PartiTopProduits>
            colonnes={[
              { cle: "nom", entete: "Parti (dénomination déposée)" },
              { cle: "produits_total", entete: "Produits (€)", type: "montant" },
              { cle: "aide_publique", entete: "Aide publique (€)", type: "montant" },
              { cle: "dons", entete: "Dons (€)", type: "montant" },
              { cle: "cotisations", entete: "Cotisations (€)", type: "montant" },
            ]}
            lignes={topProduits}
            cleLigne={(l) => l.parti_id}
          />
        </VueTableau>
      </Card>

      {/* ── Ressources par type ──────────────────────────────────────── */}
      <Card
        titre="Ressources des partis par type (2024)"
        sousTitre="Répartition des produits 2024 de l'ensemble des partis, par origine — comptes en euros."
        droite={badgePartis}
      >
        {ressources2024 ? (
          <>
            <Donut
              parts={ressourcesParts}
              formatValeur={(v) => enMillions(v)}
              libelleTotal="Produits 2024"
              totalMontant
              ariaLabel="Répartition des produits 2024 des partis par type de ressource"
            />
            <p className="mt-2 text-xs text-ink-muted">
              « Aide publique » agrège les deux fractions et les autres
              aides publiques
              {aide2024
                ? ` (${enMillions(aide2024.autres_aides_publiques, 2)} en 2024)`
                : ""}
              .
            </p>
            <VueTableau>
              <DataTable<RessourceLigne>
                colonnes={[
                  { cle: "type", entete: "Type de ressource" },
                  { cle: "montant", entete: "Montant (€)", type: "montant" },
                  {
                    cle: "part",
                    entete: "Part",
                    type: "pourcent",
                    rendu: (l) =>
                      formatPct((l.montant / ressources2024.produits_total) * 100),
                  },
                ]}
                lignes={ressourcesLignes}
                cleLigne={(l) => l.type}
              />
            </VueTableau>
          </>
        ) : (
          <p className="text-sm text-ink-muted">Exercice 2024 non publié.</p>
        )}
      </Card>

      {/* ── Évolution de l'aide publique ─────────────────────────────── */}
      <Card
        titre="Aide publique aux partis — évolution 2021-2024"
        sousTitre="Aide publique (1re + 2e fractions) telle qu'inscrite dans les comptes déposés, par exercice."
        droite={badgePartis}
      >
        <LineChart
          labels={aideEvolution.map((a) => String(a.exercice))}
          series={[
            {
              nom: "Aide publique (fractions 1 + 2)",
              valeurs: aideEvolution.map((a) => a.aide_f1_f2),
            },
          ]}
          formatValeur={(v) => enMillions(v)}
          largeur={720}
          hauteur={240}
          ariaLabel="Évolution de l'aide publique aux partis de 2021 à 2024"
        />
        <div className="mt-3">
          <DataTable<AidePubliqueAnnee>
            colonnes={[
              { cle: "exercice", entete: "Exercice" },
              { cle: "aide_f1", entete: "Fraction 1 (€)", type: "montant" },
              { cle: "aide_f2", entete: "Fraction 2 (€)", type: "montant" },
              { cle: "aide_f1_f2", entete: "Total fractions (€)", type: "montant" },
              { cle: "autres_aides_publiques", entete: "Autres aides (€)", type: "montant" },
              { cle: "nb_partis_aides", entete: "Partis aidés", type: "nombre" },
            ]}
            lignes={aideEvolution}
            cleLigne={(l) => String(l.exercice)}
          />
        </div>
      </Card>

      {/* ── Aide publique 2026 (décret) ──────────────────────────────── */}
      {aide2026 && metaDecret && (
        <Card
          titre="Aide publique 2026 — décret"
          sousTitre={aide2026.perimetre}
          droite={
            <FreshnessBadge
              dateDonnees={metaDecret.date_donnees}
              source="JORF — décret n° 2026-149"
              frequence={metaDecret.frequence}
              url={aide2026.source_url}
            />
          }
        >
          <p className="text-[26px] font-semibold leading-tight text-ink">
            {formatNombre(aide2026.montant_total_eur, 2)} €
          </p>
          <p className="mt-2 text-[13px] text-ink-secondary">
            {aide2026.reference}. Répartition par parti non publiée en données
            exploitables — l&apos;aide effectivement perçue par chaque parti
            figure dans ses comptes déposés (exercices 2021-2024 ci-dessus).
          </p>
        </Card>
      )}

      {/* ── Comptes de campagne — législatives 2024 ──────────────────── */}
      <header className="mt-2 flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="max-w-2xl">
          <h2 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
            Comptes de campagne — législatives 2024
          </h2>
          <p className="mt-2 text-sm text-ink-secondary">
            Scrutin des 30 juin et 7 juillet 2024 ; décisions de la CNCCFP
            publiées le 29 juillet 2025.
          </p>
        </div>
        {badgeCampagnes}
      </header>

      <StatStrip
        stats={[
          { label: "Candidats", valeur: formatNombre(campagnes.nb_candidats) },
          {
            label: "Taux de rejet (comptes déposés)",
            valeur: formatPct(campagnes.taux_rejet_comptes_deposes * 100, 2),
          },
          {
            label: "Dépenses retenues (total)",
            valeur: enMillions(campagnes.depenses_retenues),
          },
          {
            label: "Remboursement de l'État (total)",
            valeur: enMillions(campagnes.remboursement_etat),
          },
        ]}
      />

      <Card
        titre="Décisions de la CNCCFP"
        sousTitre={`Répartition des ${formatNombre(campagnes.nb_candidats)} candidats par famille de décision — libellés complets des codes natifs (A, AR, R…).`}
        droite={badgeCampagnes}
      >
        <Donut
          parts={decisionsFamilles.map((f) => ({
            libelle: LIBELLES_FAMILLES[f.decision_famille] ?? f.decision_famille,
            valeur: f.nb,
          }))}
          formatValeur={(v) => formatNombre(v)}
          libelleTotal="Candidats"
          ariaLabel="Répartition des candidats aux législatives 2024 par décision CNCCFP"
        />
        <p className="mt-2 text-xs text-ink-muted">
          Remboursement de l&apos;État :{" "}
          {formatNombre(campagnes.remboursement_etat)} € au total — dans
          les données, seuls les comptes approuvés (avec ou sans réformation)
          portent un remboursement.
        </p>
        <VueTableau>
          <DataTable<DecisionDetail>
            colonnes={[
              { cle: "decision", entete: "Code décision", largeur: "7rem" },
              {
                cle: "decision_famille",
                entete: "Famille",
                rendu: (l) => LIBELLES_FAMILLES[l.decision_famille] ?? l.decision_famille,
              },
              { cle: "nb", entete: "Comptes", type: "nombre" },
              { cle: "depenses_retenues", entete: "Dépenses retenues (€)", type: "montant" },
              { cle: "remboursement_etat", entete: "Remboursement État (€)", type: "montant" },
            ]}
            lignes={decisionsDetail}
            cleLigne={(l) => l.decision}
          />
        </VueTableau>
      </Card>

      <Card
        titre="Dépenses de campagne les plus élevées"
        sousTitre="Top 10 des candidats par dépenses retenues par la CNCCFP."
        droite={badgeCampagnes}
      >
        <DataTable<CampagneTopDepense>
          colonnes={[
            { cle: "nom", entete: "Candidat" },
            { cle: "circonscription", entete: "Circonscription" },
            { cle: "nuance", entete: "Nuance (telle que publiée)" },
            { cle: "depenses_declarees", entete: "Déclarées (€)", type: "montant" },
            { cle: "depenses_retenues", entete: "Retenues (€)", type: "montant" },
            { cle: "remboursement_etat", entete: "Remb. État (€)", type: "montant" },
            { cle: "decision", entete: "Décision", largeur: "6rem" },
          ]}
          lignes={topDepenses}
          cleLigne={(l) => l.candidat_id}
        />
      </Card>

      <Card
        titre="Réformation parfois à la hausse"
        sousTitre="La réformation par la CNCCFP ne joue pas toujours à la baisse."
        droite={badgeCampagnes}
      >
        <p className="text-sm text-ink-secondary">
          Sur {formatNombre(campagnes.nb_reformes)} comptes approuvés après
          réformation, {formatNombre(nbReformationHausse)} présentent des
          dépenses retenues supérieures aux dépenses déclarées : le montant
          retenu par la commission peut être révisé à la hausse comme à la
          baisse.
        </p>
      </Card>

      {/* ── Alertes financement ──────────────────────────────────────── */}
      <Card
        titre="Alertes financement"
        sousTitre="Constats calculés depuis les données publiées — règle et base légale dépliables sur chaque alerte."
        droite={
          <div className="flex flex-wrap justify-end gap-2">
            {badgePartis}
            {badgeCampagnes}
          </div>
        }
      >
        <div className="flex flex-col gap-3">
          <AlertItem
            gravite={graviteUi(alertesRejets.gravite).gravite}
            graviteLibelle={graviteUi(alertesRejets.gravite).libelle}
            titre={`${formatNombre(alertesRejets.nb)} comptes de campagne rejetés par la CNCCFP (législatives 2024)`}
            detail={`${formatNombre(alertesRejets.nb)} comptes rejetés sur ${formatNombre(comptesDeposes)} comptes déposés (${formatPct(campagnes.taux_rejet_comptes_deposes * 100, 2)}).${familleRejete ? ` Dépenses retenues de ces comptes : ${formatNombre(familleRejete.depenses_retenues)} € ; remboursement de l'État : ${formatNombre(familleRejete.remboursement_etat)} €.` : ""}`}
            regle={alertesRejets.regle ?? undefined}
            baseLegale={alertesRejets.base_legale ?? undefined}
            source={{
              libelle: "CNCCFP — data.gouv.fr",
              url: alertesRejets.source_url ?? undefined,
            }}
          />
          {alertesDependance.map((a) => (
            <AlertItem
              key={a.id}
              gravite={graviteUi(a.gravite).gravite}
              graviteLibelle={graviteUi(a.gravite).libelle}
              titre={a.titre}
              detail={a.detail ?? undefined}
              regle={a.regle ?? undefined}
              baseLegale={a.base_legale ?? undefined}
              source={{ libelle: "CNCCFP — data.gouv.fr", url: a.source_url ?? undefined }}
            />
          ))}
          {alerteDocumentaire && (
            <AlertItem
              gravite={graviteUi(alerteDocumentaire.gravite).gravite}
              graviteLibelle={graviteUi(alerteDocumentaire.gravite).libelle}
              titre={alerteDocumentaire.titre}
              detail={alerteDocumentaire.detail ?? undefined}
              regle={alerteDocumentaire.regle ?? undefined}
              baseLegale={alerteDocumentaire.base_legale ?? undefined}
              source={{
                libelle: "Journal officiel (PDF)",
                url: alerteDocumentaire.source_url ?? undefined,
              }}
            />
          )}
        </div>
      </Card>

      <p className="text-xs text-ink-muted">
        Municipales 2026 : comptes de campagne non publiés à ce jour —
        instruction CNCCFP en cours, publication attendue fin 2026/2027.
      </p>
    </section>
  );
}
