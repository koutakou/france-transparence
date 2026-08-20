import type { Metadata } from "next";
import { AlertesListe } from "@/components/client/AlertesListe";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { JsonLd } from "@/components/JsonLd";
import { StatStrip } from "@/components/ui/StatStrip";
import { formatDateFr, formatNombre } from "@/lib/format";
import {
  getAlertesDomaines,
  getAlertesPage,
  getAlertesStats,
  getAlertesTypes,
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
  // Première page (ordre canonique), rendue dans le HTML statique — la
  // suite et les filtres passent par le fragment côté client.
  const premierePage = getAlertesPage({ page: 1 })?.alertes ?? [];

  const nbParGravite = new Map(stats.parGravite.map((g) => [g.gravite, g.nb]));

  return (
    <section className="flex flex-col gap-6">
      <JsonLd donnees={BALISAGE} />
      {/* En-tête factuel */}
      <header className="flex flex-col gap-2">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Alertes transparence
        </h1>
        <p className="max-w-3xl text-sm text-ink-secondary">
          {formatNombre(stats.total)} alertes calculées à l’ingestion des données
          publiques (dernier calcul&nbsp;:{" "}
          {stats.derniereDateCalcul ? formatDateFr(stats.derniereDateCalcul) : "—"}).
          Chaque alerte cite sa règle de calcul et sa base légale (dépliables
          ci-dessous) — un constat officiel ou un signal d’attention tiré des
          sources, jamais un jugement. Recalcul à chaque mise à jour des sources
          (HATVP hebdomadaire, lobbying quotidien, financement annuel).
        </p>
        <p className="max-w-3xl text-xs text-ink-muted">
          Les retards HATVP «&nbsp;présumés&nbsp;» sont des agrégats non
          nominatifs (réserve&nbsp;: répertoire des élus trimestriel) — seuls
          les constats officiels de la HATVP sont nominatifs.
        </p>
      </header>

      {/* KPI par gravité */}
      <StatStrip
        stats={[
          { label: "Alertes au total", valeur: formatNombre(stats.total) },
          { label: "Gravité haute", valeur: formatNombre(nbParGravite.get("haute") ?? 0) },
          { label: "Gravité moyenne", valeur: formatNombre(nbParGravite.get("moyenne") ?? 0) },
          { label: "Information", valeur: formatNombre(nbParGravite.get("info") ?? 0) },
        ]}
      />

      {/* Répartition par domaine */}
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

      {/* Filtres + liste + pagination (client, fragment /data/alertes.json) */}
      <AlertesListe
        types={types}
        parGravite={stats.parGravite}
        total={stats.total}
        initiales={premierePage}
      />
    </section>
  );
}
