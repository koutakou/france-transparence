import type { Metadata } from "next";
import { AlertesListe } from "@/components/client/AlertesListe";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { NoticeLecture } from "@/components/ui/NoticeLecture";
import { JsonLd } from "@/components/JsonLd";
import { StatStrip } from "@/components/ui/StatStrip";
import { formatDateFr, formatNombre } from "@/lib/format";
import {
  getAlertesDomaines,
  getAlertesPage,
  getAlertesStats,
  getAlertesTypes,
  getSourcesAlertes,
  PERIMETRE_ALERTES_TOTAL,
  PERIMETRE_GRAVITE_HAUTE,
  PERIMETRE_GRAVITE_INFO,
  PERIMETRE_GRAVITE_MOYENNE,
  SOURCES_ALERTES,
} from "@/lib/queries/alertes";
import { jsonLdPage, metadonneesPage } from "@/lib/seo";

/**
 * Page STATIQUE (site pré-rendu quotidiennement) : agrégats et première
 * page calculés au build ; filtres par type/gravité et pagination côté
 * client sur le fragment /data/alertes.json (docs/deploiement/DECISION.md).
 * Hors navigation principale (accès depuis l'accueil). Chaque AlertItem
 * déplie règle + base légale (docs/NOTES-FRONT.md §Alertes).
 */

// Chemin, titre et description nommés UNE FOIS : les métadonnées et le
// balisage JSON-LD décrivent la même page, ils ne peuvent donc pas la
// décrire différemment le jour où l'un des deux est retouché.
const CHEMIN = "/alertes/";
const TITRE = "Alertes transparence";
const DESCRIPTION =
  "Constats sourcés : déclarations HATVP non déposées, comptes de campagne rejetés, lobbying non déclaré — chaque alerte avec sa règle et sa base légale.";

export const metadata: Metadata = metadonneesPage({
  chemin: CHEMIN,
  titre: TITRE,
  description: DESCRIPTION,
});

// Fil d'Ariane à deux niveaux : la page est hors navigation principale, on
// n'invente donc pas de rubrique parente qui n'existe pas — elle s'atteint
// depuis l'accueil.
const BALISAGE = jsonLdPage({
  chemin: CHEMIN,
  nom: TITRE,
  description: DESCRIPTION,
  ariane: [{ nom: "Accueil", chemin: "/" }, { nom: TITRE }],
});

export default async function PageAlertes() {
  const stats = getAlertesStats();
  if (stats === null) {
    return (
      <section className="flex flex-col gap-4">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Alertes transparence
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          La base locale n’est pas encore construite — lancer{" "}
          <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code> pour
          ingérer les sources et calculer les alertes.
        </div>
      </section>
    );
  }

  const types = getAlertesTypes() ?? [];
  const domaines = getAlertesDomaines() ?? [];
  const sources = getSourcesAlertes() ?? {};
  // Première page (ordre canonique), rendue dans le HTML statique — la
  // suite et les filtres passent par le fragment côté client.
  const premierePage = getAlertesPage({ page: 1 })?.alertes ?? [];

  const nbParGravite = new Map(stats.parGravite.map((g) => [g.gravite, g.nb]));

  return (
    <section className="flex flex-col gap-6">
      <JsonLd donnees={BALISAGE} />
      {/* Bande 1 — une alerte au pli, pas le mur pédagogique. */}
      <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="max-w-2xl">
          <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
            Alertes transparence
          </h1>
          <p className="mt-2 text-sm text-ink-secondary">
            {formatNombre(stats.total)} alertes calculées à l’ingestion
            (dernier calcul&nbsp;:{" "}
            {stats.derniereDateCalcul ? formatDateFr(stats.derniereDateCalcul) : "—"}
            ).
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          {SOURCES_ALERTES.map((id) => {
            const source = sources[id];
            if (!source) return null;
            return (
              <FreshnessBadge
                key={id}
                dateDonnees={source.date_donnees}
                source={source.nom}
                frequence={source.frequence}
                url={source.url}
              />
            );
          })}
        </div>
      </header>

      {/* KPI par gravité */}
      <StatStrip
        stats={[
          {
            label: "Alertes au total",
            valeur: formatNombre(stats.total),
            perimetre: PERIMETRE_ALERTES_TOTAL,
          },
          {
            label: "Gravité haute",
            valeur: formatNombre(nbParGravite.get("haute") ?? 0),
            perimetre: PERIMETRE_GRAVITE_HAUTE,
          },
          {
            label: "Gravité moyenne",
            valeur: formatNombre(nbParGravite.get("moyenne") ?? 0),
            perimetre: PERIMETRE_GRAVITE_MOYENNE,
          },
          {
            label: "Information",
            valeur: formatNombre(nbParGravite.get("info") ?? 0),
            perimetre: PERIMETRE_GRAVITE_INFO,
          },
        ]}
      />

      {/* Filtres + liste + pagination (client, fragment /data/alertes.json) */}
      <AlertesListe
        types={types}
        parGravite={stats.parGravite}
        total={stats.total}
        initiales={premierePage}
      />

      <NoticeLecture
        ancre="alertes"
        commentLire={
          <p>
            Une alerte reprend un constat déjà formulé par une autorité, ou
            un signal d’attention tiré des sources, avec sa règle et sa
            base légale. Ce n’est pas un jugement du site. Les constats
            officiels de la HATVP, les décisions de la CNCCFP et les
            défauts AGORA portent un nom ; les retards HATVP
            «&nbsp;présumés&nbsp;» sont des agrégats, jamais un nom
            (réserve&nbsp;: répertoire des élus trimestriel).
          </p>
        }
        provenance={
          <p>
            Déclarations HATVP, répertoire des représentants d’intérêts,
            comptes de campagne publiés par la CNCCFP. Recalcul à chaque
            mise à jour des sources.
          </p>
        }
        limites={
          <p>
            Une alerte n’est pas une infraction constatée par ce site. Un
            homonyme non tranché ne donne lieu à aucune alerte nominative.
            Une donnée manquante en amont exclut le cas, plutôt que
            d’être estimée.
          </p>
        }
      />

      <Card
        titre="Répartition par domaine"
        sousTitre="Le préfixe du type d’alerte porte son domaine — valeurs exactes affichées"
      >
        <BarList
          items={domaines.map((d) => ({ libelle: d.domaine, valeur: d.nb }))}
          formatValeur={(v) => formatNombre(v)}
          largeurLibelle="42%"
        />
      </Card>
    </section>
  );
}
