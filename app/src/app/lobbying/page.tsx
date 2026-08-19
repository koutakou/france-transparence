import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AlertItem, type Gravite } from "@/components/ui/AlertItem";
import { BarChart } from "@/components/ui/BarChart";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { LineChart } from "@/components/ui/LineChart";
import { StatStrip } from "@/components/ui/StatStrip";
import { formatDateFr, formatNombre } from "@/lib/format";
import {
  getDonneesLobbying,
  type EntiteEnDefaut,
  type FourchetteBudget,
  type InstitutionDetail,
  type MinistereVise,
  type TopEntite,
  type TrimestreActivites,
} from "@/lib/queries/lobbying";

// La base locale évolue à chaque ingestion : jamais figer cet état au build.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Lobbying",
  description:
    "Le répertoire des représentants d'intérêts de la HATVP : activités déclarées, budgets, institutions visées et entités en défaut de déclaration — constats officiels repris tels quels, datés et sourcés.",
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

/** Lien sortant vers une fiche HATVP (jamais de fetch serveur). */
function LienFiche({ url }: { url: string | null }) {
  if (!url) return <>—</>;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
    >
      Fiche HATVP
    </a>
  );
}

/** `10 000` → `10 k€`, `1 250 000` → `1,25 M€` (étiquettes d'axe compactes). */
function borneCompacte(v: number): string {
  if (v >= 1e6) {
    const m = v / 1e6;
    const dec = Number.isInteger(m) ? 0 : Number.isInteger(m * 10) ? 1 : 2;
    return `${formatNombre(m, dec)} M€`;
  }
  return `${formatNombre(v / 1e3)} k€`;
}

/**
 * Étiquette d'axe d'une fourchette native HATVP : sa borne basse compacte
 * (« < 10 k€ », « 25 k€ », « ≥ 10 M€ »). La fourchette complète reste
 * lisible dans l'infobulle et la vue tableau (libellés natifs).
 */
function libelleFourchetteCourt(f: FourchetteBudget): string {
  if (f.borne_min === null) return f.fourchette;
  if (f.borne_max === null) return `≥ ${borneCompacte(f.borne_min)}`;
  if (f.borne_min === 0) return `< ${borneCompacte(f.borne_max)}`;
  return borneCompacte(f.borne_min);
}

/**
 * Lobbying — répertoire des représentants d'intérêts (HATVP, loi
 * « Sapin II »). Données 100 % réelles de data/france.db (source S4),
 * mises à jour quotidiennement par le pipeline.
 */
export default async function LobbyingPage() {
  const donnees = getDonneesLobbying();

  if (!donnees) {
    return (
      <section className="flex flex-col gap-6">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Lobbying
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          <p>
            La base locale n&apos;est pas encore construite (ou la source HATVP
            n&apos;est pas ingérée) — lancer{" "}
            <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code>{" "}
            pour ingérer les sources.
          </p>
        </div>
      </section>
    );
  }

  const {
    meta,
    kpi,
    institutions,
    institutionsDetail,
    topEntites,
    budgets,
    budgetsCouverture,
    trimestres,
    ministeres,
    alerteDefauts,
    nbAlertesDefaut,
    entitesEnDefaut,
  } = donnees;

  const badge = (
    <FreshnessBadge
      dateDonnees={meta.date_donnees}
      source="HATVP — AGORA"
      frequence={meta.frequence}
      url={meta.url}
    />
  );

  const dernierTrimestre = trimestres[trimestres.length - 1];

  return (
    <section className="flex flex-col gap-6">
      {/* ── En-tête ─────────────────────────────────────────────────── */}
      <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="max-w-2xl">
          <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
            Lobbying — représentants d&apos;intérêts
          </h1>
          <p className="mt-2 text-sm text-ink-secondary">
            Répertoire des représentants d&apos;intérêts tenu par la Haute
            Autorité pour la transparence de la vie publique (HATVP), créé par
            la loi « Sapin II » du 9 décembre 2016. Les entités
            inscrites y déclarent leurs activités de représentation
            d&apos;intérêts et les moyens qui y sont consacrés ; le
            répertoire est mis à jour quotidiennement.
          </p>
        </div>
        {badge}
      </header>

      {/* ── KPI ─────────────────────────────────────────────────────── */}
      <StatStrip
        stats={[
          { label: "Entités inscrites au répertoire", valeur: formatNombre(kpi.entites) },
          { label: "Entités actives", valeur: formatNombre(kpi.actives) },
          {
            label: "Activités déclarées (historique)",
            valeur: formatNombre(kpi.activitesTotal),
          },
          {
            label: "Activités détaillées (24 derniers mois)",
            valeur: formatNombre(kpi.activites24m),
          },
        ]}
      />

      {/* ── Activités par institution visée ─────────────────────────── */}
      <Card
        titre="Activités par institution visée"
        sousTitre="Cumul historique des activités déclarées, par catégorie de responsables publics visés. La donnée source ne sépare pas l'Assemblée nationale du Sénat : ils forment la seule catégorie « Parlement (AN + Sénat) »."
        droite={badge}
      >
        <BarList
          items={institutions.map((i) => ({
            libelle: i.groupe,
            valeur: i.nb_activites_total,
          }))}
          formatValeur={(v) => formatNombre(v)}
          largeurLibelle="38%"
        />
        <VueTableau>
          <DataTable<InstitutionDetail>
            colonnes={[
              { cle: "institution", entete: "Catégorie de responsables publics (libellé natif)" },
              { cle: "groupe", entete: "Groupe", largeur: "12rem" },
              { cle: "nb_activites_total", entete: "Activités (hist.)", type: "nombre" },
              { cle: "nb_activites_12m", entete: "Activités (12 mois)", type: "nombre" },
              { cle: "nb_entites", entete: "Entités", type: "nombre" },
            ]}
            lignes={institutionsDetail}
            cleLigne={(l) => l.institution}
          />
        </VueTableau>
      </Card>

      {/* ── Top 20 des entités (12 mois) ─────────────────────────────── */}
      <Card
        titre="Entités les plus actives (12 derniers mois)"
        sousTitre="Top 20 par nombre d'activités publiées sur les 12 derniers mois."
        droite={badge}
      >
        <DataTable<TopEntite>
          colonnes={[
            { cle: "rang", entete: "Rang", type: "nombre", largeur: "3.5rem" },
            { cle: "denomination", entete: "Entité" },
            { cle: "categorie", entete: "Catégorie" },
            { cle: "nb_activites_12m", entete: "Activités (12 mois)", type: "nombre" },
            {
              cle: "url_fiche",
              entete: "Registre",
              rendu: (l) => <LienFiche url={l.url_fiche} />,
            },
          ]}
          lignes={topEntites}
          cleLigne={(l) => String(l.rang)}
        />
      </Card>

      {/* ── Répartition par fourchette de budget ─────────────────────── */}
      <Card
        titre="Répartition par fourchette de budget"
        sousTitre={`Entités par fourchette de budget annuel consacré à la représentation d'intérêts — fourchettes natives HATVP, telles que déclarées. ${formatNombre(budgetsCouverture.dansFourchettes)} entités ont déclaré une fourchette, sur ${formatNombre(budgetsCouverture.total)} inscrites.`}
        droite={badge}
      >
        <BarChart
          items={budgets.map((b) => ({
            libelle: libelleFourchetteCourt(b),
            valeur: b.nb_entites,
          }))}
          formatValeur={(v) => formatNombre(v)}
          largeur={1000}
          hauteur={260}
          ariaLabel="Nombre d'entités par fourchette de budget annuel déclaré"
        />
        <p className="mt-2 text-xs text-ink-muted">
          Colonnes étiquetées par la borne basse de leur fourchette. La
          fourchette la plus haute n&apos;a pas de borne supérieure publiée
          (« ≥ 10 000 000 € »).
        </p>
        <VueTableau>
          <DataTable<FourchetteBudget>
            colonnes={[
              { cle: "fourchette", entete: "Fourchette de budget (libellé natif)" },
              { cle: "nb_entites", entete: "Entités", type: "nombre" },
            ]}
            lignes={budgets}
            cleLigne={(l) => l.fourchette}
            hauteurMax="20rem"
          />
        </VueTableau>
      </Card>

      {/* ── Série trimestrielle ──────────────────────────────────────── */}
      <Card
        titre="Activités déclarées par trimestre"
        sousTitre={`Trimestre de publication des déclarations d'activités (${trimestres[0]?.trimestre} → ${dernierTrimestre?.trimestre}).`}
        droite={badge}
      >
        <LineChart
          labels={trimestres.map((t) => t.trimestre)}
          series={[
            {
              nom: "Activités publiées",
              valeurs: trimestres.map((t) => t.nb_activites),
            },
          ]}
          formatValeur={(v) => formatNombre(v)}
          largeur={880}
          hauteur={260}
          ariaLabel="Nombre d'activités de représentation d'intérêts publiées par trimestre"
        />
        <p className="mt-2 text-xs text-ink-muted">
          Les pics récurrents au premier trimestre correspondent au dépôt des
          déclarations annuelles d&apos;activités de l&apos;exercice précédent.
          Le trimestre {dernierTrimestre?.trimestre} est en cours :
          chiffres partiels au {formatDateFr(meta.date_donnees)}.
        </p>
        <VueTableau>
          <DataTable<TrimestreActivites>
            colonnes={[
              { cle: "trimestre", entete: "Trimestre" },
              { cle: "nb_activites", entete: "Activités publiées", type: "nombre" },
              { cle: "nb_entites", entete: "Entités déclarantes", type: "nombre" },
            ]}
            lignes={trimestres}
            cleLigne={(l) => l.trimestre}
            hauteurMax="20rem"
          />
        </VueTableau>
      </Card>

      {/* ── Ministères / institutions les plus visés ─────────────────── */}
      <Card
        titre="Ministères et institutions les plus visés"
        sousTitre="Top 12 par nombre d'activités déclarées (historique). Libellés tels que déclarés par les représentants d'intérêts : une même activité peut viser plusieurs libellés de portefeuille — les lignes ne se cumulent pas."
        droite={badge}
      >
        <DataTable<MinistereVise>
          colonnes={[
            { cle: "ministere", entete: "Ministère / institution (libellé déclaré)" },
            { cle: "nb_activites_total", entete: "Activités (hist.)", type: "nombre" },
            { cle: "nb_activites_12m", entete: "Activités (12 mois)", type: "nombre" },
            { cle: "nb_entites", entete: "Entités", type: "nombre" },
          ]}
          lignes={ministeres}
          cleLigne={(l) => l.ministere}
        />
      </Card>

      {/* ── Alertes : défauts de déclaration ─────────────────────────── */}
      <Card
        titre="Alertes — défauts de déclaration"
        sousTitre={`${formatNombre(nbAlertesDefaut)} entités inscrites sur la liste officielle HATVP des représentants d'intérêts en défaut de déclaration — flag public officiel, repris tel quel.`}
        droite={badge}
      >
        <div className="flex flex-col gap-3">
          {alerteDefauts && (
            <AlertItem
              gravite={graviteUi(alerteDefauts.gravite).gravite}
              graviteLibelle={graviteUi(alerteDefauts.gravite).libelle}
              titre={alerteDefauts.titre}
              detail={alerteDefauts.detail ?? undefined}
              regle={alerteDefauts.regle ?? undefined}
              baseLegale={alerteDefauts.base_legale ?? undefined}
              source={{
                libelle: "HATVP — AGORA",
                url: alerteDefauts.source_url ?? undefined,
              }}
            />
          )}
          <DataTable<EntiteEnDefaut>
            colonnes={[
              { cle: "denomination", entete: "Entité en défaut de déclaration" },
              { cle: "categorie", entete: "Catégorie" },
              { cle: "ville", entete: "Ville" },
              {
                cle: "url_fiche",
                entete: "Registre",
                rendu: (l) => <LienFiche url={l.url_fiche} />,
              },
            ]}
            lignes={entitesEnDefaut}
            cleLigne={(l) => l.id}
            hauteurMax="24rem"
          />
        </div>
      </Card>
    </section>
  );
}
