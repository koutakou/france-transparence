import type { Metadata } from "next";
import Link from "next/link";
import { AlertItem, type Gravite } from "@/components/ui/AlertItem";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { DataTable, type Colonne } from "@/components/ui/DataTable";
import { DeltaPct } from "@/components/ui/DeltaPct";
import { Donut } from "@/components/ui/Donut";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { KpiTile } from "@/components/ui/KpiTile";
import type { PointCarte } from "@/components/ui/MapFrance";
import { CarteDepartements } from "@/components/client/CarteDepartements";
import { JsonLd } from "@/components/JsonLd";
import { Money } from "@/components/ui/Money";
import { StatStrip } from "@/components/ui/StatStrip";
import type { MetaSource } from "@/lib/db";
import { ESPACE_FINE, formatDateFr, formatNombre } from "@/lib/format";
import {
  getDonneesAccueil,
  lireDepartementsGeojson,
  type AlerteAccueil,
} from "@/lib/queries/accueil";
import { jsonLdIdentiteSite, metadonneesPage } from "@/lib/seo";

// Rendu statique : la donnée ne change qu'à l'ingestion, le site est
// reconstruit après chaque ingestion (docs/deploiement/DECISION.md).

// Le title de l'accueil est le title par défaut du layout racine.
export const metadata: Metadata = metadonneesPage({
  chemin: "/",
  description:
    "Le tableau de bord de l'argent public : budget général de l'État, marchés publics, élus, lobbying, financement de la vie politique, finances locales, prestations de protection sociale et alertes d'intégrité — données publiques officielles, datées et sourcées.",
});

/* ------------------------------------------------------------------ */
/* Aides d'affichage (module accueil uniquement)                       */
/* ------------------------------------------------------------------ */

/** `240 537 726 398,7` € → `240,54 Md€` (héros et KPI, décimales choisies). */
function mdE(v: number, decimales = 1): string {
  return `${formatNombre(v / 1e9, decimales)}${ESPACE_FINE}Md€`;
}

/** ISO datetime UTC → `19/08 16:30` (heure de Paris). */
function formatDateHeureFr(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Paris",
  }).format(d);
}

/** Libellés courts des sources pour les badges (URL/date/fréquence réelles). */
const LIBELLES_SOURCES: Record<string, string> = {
  S13: "DGFiP · situations mensuelles",
  S20: "PLF 2026 · budget vert",
  S21: "PLF 2025 · destination",
  S1: "DECP consolidées",
  S2: "BOAMP",
  S3: "JO Lois et décrets",
  S17: "RNE",
  S16: "OFGL · comptes des collectivités",
  "S35-reforga-admin-etat": "DILA · RefOrga État",
};

function BadgeSource({ source, mention }: { source?: MetaSource; mention?: string }) {
  if (!source) return null;
  return (
    <FreshnessBadge
      dateDonnees={source.date_donnees}
      source={LIBELLES_SOURCES[source.source_id] ?? source.nom}
      frequence={source.frequence}
      url={source.url}
      mention={mention}
    />
  );
}

/**
 * Libellés courts des titres de dépense pour la légende du donut — les
 * libellés DGFiP complets (« Dépenses de personnel »…) débordent la colonne
 * gauche. Mapping d'AFFICHAGE uniquement : données et requêtes inchangées,
 * libellé inconnu → rendu tel quel.
 */
const LIBELLES_TITRES: Record<string, string> = {
  "Dépenses de personnel": "Personnel",
  "Dépenses d'intervention": "Intervention",
  "Dépenses de fonctionnement": "Fonctionnement",
  "Charges de la dette de l'Etat": "Charge de la dette",
  "Dépenses d'investissement": "Investissement",
  "Dotation des pouvoirs publics": "Pouvoirs publics",
  "Dépenses d'opérations financières": "Opérations financières",
};

/** Lien « Voir tout » vers le module concerné (convention footer du site). */
function LienModule({ href, libelle }: { href: string; libelle: string }) {
  return (
    <p className="mt-3">
      <Link
        href={href}
        className="text-xs text-ink-muted underline decoration-dotted underline-offset-2 transition-colors hover:text-ink-secondary"
      >
        {libelle} →
      </Link>
    </p>
  );
}

/**
 * Gravités de la table `alertes` (haute/moyenne/info) → les trois statuts
 * distincts et croissants d'AlertItem ; le libellé affiché reste la gravité
 * RÉELLE de la donnée (jamais la couleur seule, DATAVIZ §3.4).
 */
const GRAVITES_UI: Record<string, { gravite: Gravite; libelle: string }> = {
  haute: { gravite: "critique", libelle: "Gravité haute" },
  moyenne: { gravite: "serieux", libelle: "Gravité moyenne" },
  info: { gravite: "attention", libelle: "Info" },
};

/** Source amont d'une alerte, déduite du préfixe de type (domaine). */
function sourceAlerte(a: AlerteAccueil): { libelle: string; url?: string } {
  const libelle = a.type.startsWith("financement_")
    ? "CNCCFP"
    : a.type.startsWith("lobbying_")
      ? "HATVP · AGORA"
      : a.type.startsWith("A1_")
        ? "HATVP"
        : "source officielle";
  return { libelle, url: a.sourceUrl ?? undefined };
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

/**
 * Accueil — entrée citoyenne. Un chiffre héros (exécution S13 YTD),
 * trois tuiles d'activité bornées, puis le reste du tableau de bord.
 * Même ordre de scan au bureau (max-w-7xl) et au téléphone : le DOM
 * s'empile, il n'y a pas d'arbre mobile distinct. Server Component :
 * données depuis data/france.db en lecture seule. Pas de temps réel :
 * les fréquences affichées sont celles des sources.
 */
export default async function Accueil() {
  const donnees = getDonneesAccueil();

  if (donnees === null) {
    return (
      <section className="flex flex-col gap-6">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Vue d&apos;ensemble
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          <p>
            La base locale n&apos;est pas encore construite — lancer{" "}
            <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code>{" "}
            pour ingérer les sources.
          </p>
        </div>
      </section>
    );
  }

  const {
    execution,
    partsTitres,
    missionsPlf2026,
    etiquettePlf2026,
    totalCpPlf2026,
    departementsCarte,
    prefectures,
    kpis,
    suivi,
    ministeres2025,
    totalCp2025,
    derniersMarches,
    textesJo,
    aoCloture,
    alertes,
    sources,
  } = donnees;

  /* --- Carte : valeurs par département limitées au fond métropole
         (l'outre-mer est hors du rendu — codes 97x/98x écartés).
         Le GeoJSON n'est lu ici QUE pour filtrer les codes : le fond est
         chargé côté client depuis /data/carte-departements.json
         (CarteDepartements), où les contours sont déjà projetés au build,
         pour ne pas peser dans le HTML statique. --- */
  const geojson = lireDepartementsGeojson();
  const codesCarte = new Set(
    (geojson?.features ?? [])
      .map((f) => f.properties?.code)
      .filter((c): c is string => typeof c === "string" && !c.startsWith("97")),
  );
  const valeursCarte: Record<string, number> = {};
  const nomsDepartements = new Map<string, string | null>();
  for (const d of departementsCarte) {
    nomsDepartements.set(d.code, d.nom);
    // NULL = aucun montant connu → laissé « donnée manquante », jamais 0.
    // Arrondi à l'euro : ces montants sont sérialisés tels quels dans le
    // payload RSC de l'accueil, où SQLite les livre en flottants à 7 décimales
    // (« 902703865.3733331 »). Ils sont affichés au million près par la carte
    // et son échelle : les décimales sont du bruit qui ne sert qu'à gonfler le
    // payload (406 flottants à ≥ 3 décimales sur la seule page d'accueil).
    if (d.montant !== null && codesCarte.has(d.code))
      valeursCarte[d.code] = Math.round(d.montant);
  }
  // Préfectures (chefs-lieux) : poids = montant 12 mois de LEUR département,
  // même unité que l'aplat → un seul format, tooltips honnêtes.
  const pointsPrefectures: PointCarte[] = prefectures
    .filter((p) => valeursCarte[p.departement] !== undefined)
    .map((p) => ({
      lat: p.lat,
      lon: p.lon,
      label: `${p.nom} · ${nomsDepartements.get(p.departement) ?? p.departement}`,
      poids: valeursCarte[p.departement],
    }));

  /* --- Compteur : delta neutre (une dépense qui monte n'est pas « mauvaise ») --- */
  const anneeExecution = execution ? Number(execution.dateFinMois.slice(0, 4)) : null;
  const dateN1 =
    execution && anneeExecution
      ? `${anneeExecution - 1}${execution.dateFinMois.slice(4)}`
      : null;

  // Même raison : ces deux valeurs partent dans le payload RSC et sont
  // affichées à 2 et 1 décimale (colonnes ci-dessous). On les arrondit à
  // 2 décimales, soit la précision réellement rendue — pas une de plus.
  const arrondi2 = (v: number) => Math.round(v * 100) / 100;
  const lignesMinisteres = ministeres2025.map((m) => ({
    ministere: m.ministere,
    cpMd: arrondi2(m.cp / 1e9),
    partPct: arrondi2(m.partPct),
  }));
  const colonnesMinisteres: Colonne<(typeof lignesMinisteres)[number]>[] = [
    { cle: "ministere", entete: "Ministère" },
    { cle: "cpMd", entete: "CP (Md€)", type: "montant", decimales: 2 },
    { cle: "partPct", entete: "Part", type: "pourcent", decimales: 1 },
  ];

  const dernierCalculAlertes = alertes.reduce(
    (max, a) => (a.dateCalcul > max ? a.dateCalcul : max),
    alertes[0]?.dateCalcul ?? "",
  );

  return (
    <div className="flex flex-col gap-4">
      {/* Identité du site (WebSite + Project) — portée par la seule page
          d'accueil : la répéter sur chaque page n'apporte rien. */}
      <JsonLd donnees={jsonLdIdentiteSite()} />
      {/* Identité + hors-champ F1 au-dessus du chiffre : une restriction
          dite plus bas ne compte pas. Le héros suit, pleine largeur. */}
      <header className="flex flex-col gap-3">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Vue d&apos;ensemble
        </h1>
        <p className="rounded-lg border border-card-border bg-card px-4 py-2.5 text-xs leading-relaxed text-ink-secondary">
          Ce tableau de bord couvre le budget général de l&apos;État, la
          commande publique, le Journal officiel, le Parlement et les élus, le
          lobbying, le financement de la vie politique, les finances locales et
          les prestations de protection sociale (tous régimes), uniquement à
          partir de données publiques officielles — chaque bloc affiche la date
          et la fréquence réelle de sa source. Hors champ&nbsp;: la loi de
          financement de la sécurité sociale en tant que texte voté, la
          dépense propre des opérateurs de l&apos;État et les entreprises
          publiques. Comment les lire sur{" "}
          <Link
            href="/comprendre"
            className="underline decoration-dotted underline-offset-2 hover:text-ink"
          >
            Comprendre les données
          </Link>
          ; périmètre exact et licences sur{" "}
          <Link
            href="/donnees"
            className="underline decoration-dotted underline-offset-2 hover:text-ink"
          >
            Données&nbsp;&amp;&nbsp;API
          </Link>
          .
        </p>
      </header>

      {/* Entrée bureau : héros 2/3 + trois tuiles 1/3 (le justify-between
          pleine largeur laissait un vide). Même ordre empilé au téléphone. */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3 xl:items-stretch">
        <div className="min-w-0 xl:col-span-2">
          <Card
            titre="Dépenses de l'État"
            sousTitre={
              execution
                ? `Exécution au ${formatDateFr(execution.dateFinMois)} — cumul depuis le 1er janvier, dépenses nettes du budget général`
                : "Exécution mensuelle — dépenses nettes du budget général"
            }
            droite={<BadgeSource source={sources.S13} />}
            className="h-full"
          >
            {execution ? (
              <>
                <p
                  className="text-5xl font-semibold leading-none tracking-tight"
                  style={{ color: "var(--montant)" }}
                  title={`${formatNombre(execution.cumul)}${ESPACE_FINE}€`}
                >
                  {mdE(execution.cumul, 2)}
                </p>
                <div className="mt-3">
                  {execution.deltaPct !== null && dateN1 ? (
                    <DeltaPct
                      valeur={execution.deltaPct}
                      vs={formatDateFr(dateN1)}
                      decimales={2}
                    />
                  ) : (
                    <span className="text-xs text-ink-muted">
                      comparaison N−1 non publiée
                    </span>
                  )}
                </div>
                <p className="mt-3 text-xs leading-relaxed text-ink-muted">
                  Situation mensuelle DGFiP — pas de temps réel : dernier mois
                  publié au {formatDateFr(execution.dateFinMois)}.
                </p>
                <LienModule href="/depenses" libelle="Voir les dépenses" />
              </>
            ) : (
              <>
                <p className="text-sm text-ink-muted">
                  Situation mensuelle non publiée dans la base.
                </p>
                <LienModule href="/depenses" libelle="Voir les dépenses" />
              </>
            )}
          </Card>
        </div>

        {/* Trois tuiles bornées (contrat F1) — rangée dès sm, colonne à xl. */}
        <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-3 xl:grid-cols-1">
          <KpiTile
            label="Marchés notifiés (30 j)"
            valeur={formatNombre(kpis.marches30j)}
            perimetre="notification initiale, 30 derniers jours — ce n’est pas le stock total"
          />
          <KpiTile
            label="Appels d'offres en cours (BOAMP)"
            valeur={formatNombre(kpis.aoEnCours)}
            perimetre="annonces BOAMP non annulées, date limite encore ouverte — stock du jour, pas un flux 30 j"
          />
          <KpiTile
            label="Textes au JO (30 j)"
            valeur={formatNombre(kpis.textesJo30j)}
            perimetre="JORF Lois et décrets, 30 derniers jours"
          />
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <BadgeSource source={sources.S1} mention="J-1" />
        <BadgeSource source={sources.S2} />
        <BadgeSource source={sources.S3} />
      </div>

      <StatStrip
        stats={[
          {
            label: "Marchés publics suivis",
            valeur: formatNombre(suivi.marchesSuivis),
            perimetre: "notifiés sur les 24 derniers mois — ce n’est pas le stock total",
          },
          {
            label: "Entités publiques référencées",
            valeur: formatNombre(suivi.entitesPubliques),
            perimetre:
              "ministères, institutions, régions, départements et les 200 plus grandes communes",
          },
          {
            label: "Élus suivis nominativement",
            valeur: formatNombre(suivi.elusSuivis),
            perimetre:
              "maires, présidences d’exécutifs et parlementaires — hors conseillers municipaux",
          },
        ]}
      />
      <div className="flex flex-wrap gap-1.5">
        <BadgeSource source={sources.S1} mention="J-1" />
        <BadgeSource source={sources.S16} />
        <BadgeSource source={sources.S17} />
        <BadgeSource source={sources["S35-reforga-admin-etat"]} />
      </div>

      {/* Carte pleine largeur : collée à deux listes empilées, elle
          s'arrêtait à mi-colonne et laissait un vide sous le fond
          (viewport 1280, sous le pli). */}
      <Card
        titre="Marchés publics par département"
        sousTitre="Marchés notifiés, 12 derniers mois — montants écrêtés (plafond 100 M€ par marché), acheteurs à département connu · points : préfectures · outre-mer hors carte"
        droite={<BadgeSource source={sources.S1} mention="J-1" />}
      >
        <CarteDepartements
          valeurs={valeursCarte}
          points={pointsPrefectures}
          format="euros"
          legendeTitre="Montant notifié (12 mois)"
          ariaLabel="Carte de France des montants de marchés publics notifiés par département sur 12 mois"
          messageAbsent="Fond de carte non disponible (data/geo/departements.geojson manquant)."
        />
        <p className="mt-2 text-[11px] leading-relaxed text-ink-muted">
          Consolidation DECP&nbsp;: decp-processing (C.&nbsp;Maudry) —
          latence légale de publication ≤&nbsp;2&nbsp;mois. Marchés datés
          de leur notification initiale, un avenant ne les redate pas.
        </p>
        <LienModule href="/marches" libelle="Voir les marchés publics" />
      </Card>

      {/* Deux listes de même nature, côte à côte — items-start : une
          carte ne s'étire pas en océan vide pour égaler l'autre. */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2 xl:items-start">
        <div className="min-w-0">
          <Card
            titre="Derniers marchés notifiés"
            droite={<BadgeSource source={sources.S1} mention="J-1" />}
          >
            <ul className="flex flex-col">
              {derniersMarches.map((m) => (
                <li
                  key={m.rang}
                  className="flex items-start justify-between gap-3 py-2"
                  style={{ borderBottom: "1px solid var(--viz-grid)" }}
                >
                  <div className="min-w-0">
                    <div className="flex items-baseline gap-2 text-[11px]">
                      <span className="shrink-0 text-ink-muted [font-variant-numeric:tabular-nums]">
                        {formatDateFr(m.date)}
                      </span>
                      <span className="min-w-0 break-words text-ink-secondary">
                        {m.acheteur?.trim() ? m.acheteur : "acheteur non renseigné"}
                      </span>
                    </div>
                    <p
                      className="line-clamp-2 break-words text-[13px] text-ink"
                      title={m.objet ?? undefined}
                    >
                      {m.objet?.trim() ? m.objet : "objet non publié"}
                    </p>
                  </div>
                  <span className="shrink-0 pt-3 text-[13px] [font-variant-numeric:tabular-nums]">
                    {m.montant !== null ? (
                      <Money valeur={m.montant} />
                    ) : (
                      <span className="text-ink-muted">non publié</span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-[11px] text-ink-muted">
              Montants d&apos;accords-cadres = maximums.
            </p>
            <LienModule href="/marches" libelle="Voir les marchés publics" />
          </Card>
        </div>

        <div className="min-w-0">
          <Card
            titre="Derniers textes au JO"
            sousTitre="Le JO ne paraît pas tous les jours — liens vers Légifrance"
            droite={<BadgeSource source={sources.S3} />}
          >
            <ul className="flex flex-col">
              {textesJo.map((t) => (
                <li
                  key={t.id}
                  className="py-2"
                  style={{ borderBottom: "1px solid var(--viz-grid)" }}
                >
                  <div className="flex items-baseline gap-2 text-[11px]">
                    <span className="shrink-0 text-ink-muted [font-variant-numeric:tabular-nums]">
                      {formatDateFr(t.date)}
                    </span>
                    {t.nature && (
                      <span className="shrink-0 rounded bg-raised px-1.5 py-0.5 text-[10px] uppercase tracking-[0.04em] text-ink-secondary">
                        {t.nature}
                      </span>
                    )}
                  </div>
                  <a
                    href={t.lien}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={t.titre}
                    className="mt-0.5 block line-clamp-2 break-words text-[13px] text-ink underline-offset-2 hover:underline"
                  >
                    {t.titre}
                    <span aria-hidden="true" className="ml-1 text-ink-muted">
                      ↗
                    </span>
                  </a>
                </li>
              ))}
            </ul>
            <LienModule href="/documents" libelle="Voir les documents" />
          </Card>
        </div>
      </div>

      {/* Composition : deux viz côte à côte, tableau ministères en
          pleine largeur (en 1/3 il rognait « CP (Md€) »). */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2 xl:items-start">
        <Card
          titre="Décomposition par titre"
          sousTitre={
            execution
              ? `Dépenses nettes du budget général, cumul au ${formatDateFr(execution.dateFinMois)}`
              : "Dépenses nettes du budget général"
          }
          droite={<BadgeSource source={sources.S13} />}
        >
          {partsTitres.length > 0 ? (
            <Donut
              parts={partsTitres.map((p) => ({
                libelle: LIBELLES_TITRES[p.ligne] ?? p.ligne,
                valeur: p.montant,
              }))}
              formatValeur={(v) => mdE(v, 1)}
              libelleTotal={
                execution
                  ? `Cumul au ${formatDateFr(execution.dateFinMois)}`
                  : "Cumul"
              }
              taille={180}
              ariaLabel="Décomposition des dépenses nettes de l'État par titre"
            />
          ) : (
            <p className="text-sm text-ink-muted">Décomposition non publiée.</p>
          )}
          <LienModule href="/depenses" libelle="Voir les dépenses" />
        </Card>

        <Card
          titre="Top 5 missions (PLF 2026)"
          sousTitre={etiquettePlf2026 ?? "Crédits de paiement du PLF 2026"}
          droite={<BadgeSource source={sources.S20} mention="PLF" />}
        >
          <BarList
            items={missionsPlf2026.map((m) => ({ libelle: m.mission, valeur: m.cp }))}
            formatValeur={(v) => mdE(v, 1)}
            largeurLibelle="45%"
          />
          {totalCpPlf2026 !== null && (
            <p className="mt-3 text-xs text-ink-muted">
              Crédits de paiement (crédits budgétaires) — total toutes
              missions&nbsp;: {mdE(totalCpPlf2026, 1)}.
            </p>
          )}
          <LienModule href="/depenses" libelle="Voir les dépenses" />
        </Card>
      </div>

      <Card
        titre="Budget par ministère (destination 2025)"
        sousTitre="Crédits de paiement BRUTS du PLF 2025 — non comparables aux dépenses nettes du budget général"
        droite={<BadgeSource source={sources.S21} mention="PLF" />}
      >
        <DataTable
          colonnes={colonnesMinisteres}
          lignes={lignesMinisteres}
          cleLigne={(l) => l.ministere}
          vide="Aucune donnée"
        />
        <p className="mt-2 text-[11px] text-ink-muted">
          Top 8 sur {totalCp2025 !== null ? mdE(totalCp2025, 1) : "—"} de CP
          au total. Pas de colonne d&apos;évolution&nbsp;: la donnée est un
          instantané PLF, sans exercice N−1 comparable.
        </p>
        <LienModule href="/depenses" libelle="Voir les dépenses" />
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2 xl:items-start">
        <Card
          titre="Appels d'offres proches de la clôture"
          sousTitre="Date limite de réponse (heure de Paris) — annonces BOAMP non annulées"
          droite={<BadgeSource source={sources.S2} />}
        >
          <ul className="flex flex-col">
            {aoCloture.map((ao) => (
              <li
                key={ao.id}
                className="py-2"
                style={{ borderBottom: "1px solid var(--viz-grid)" }}
              >
                <div className="flex items-baseline justify-between gap-3 text-[11px]">
                  <span className="shrink-0 font-medium text-ink-secondary [font-variant-numeric:tabular-nums]">
                    Clôture le {formatDateHeureFr(ao.dateLimite)}
                  </span>
                  <span className="min-w-0 break-words text-right text-ink-muted">
                    {ao.acheteur?.trim() ? ao.acheteur : "acheteur non renseigné"}
                  </span>
                </div>
                <p
                  className="line-clamp-2 break-words text-[13px] text-ink"
                  title={ao.objet ?? undefined}
                >
                  {ao.url ? (
                    <a
                      href={ao.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline-offset-2 hover:underline"
                    >
                      {ao.objet?.trim() ? ao.objet : "objet non publié"}
                    </a>
                  ) : ao.objet?.trim() ? (
                    ao.objet
                  ) : (
                    "objet non publié"
                  )}
                </p>
                <p className="text-[11px] text-ink-muted">
                  Montant estimé&nbsp;:{" "}
                  {ao.montantEstime !== null ? (
                    <Money valeur={ao.montantEstime} className="text-ink-secondary" />
                  ) : (
                    "non publié"
                  )}
                </p>
              </li>
            ))}
          </ul>
          <LienModule href="/marches" libelle="Voir les marchés publics" />
        </Card>

        <Card
          titre="Alertes transparence"
          sousTitre={
            dernierCalculAlertes
              ? `Les plus récentes de chaque gravité — dernier calcul le ${formatDateFr(dernierCalculAlertes)}`
              : "Les plus récentes de chaque gravité"
          }
        >
          <div className="flex flex-col gap-2">
            {alertes.map((a) => {
              const ui = GRAVITES_UI[a.gravite] ?? {
                gravite: "attention" as Gravite,
                libelle: a.gravite,
              };
              return (
                <AlertItem
                  key={a.id}
                  gravite={ui.gravite}
                  graviteLibelle={ui.libelle}
                  titre={a.titre}
                  detail={a.detail ?? undefined}
                  regle={a.regle ?? undefined}
                  baseLegale={a.baseLegale ?? undefined}
                  source={sourceAlerte(a)}
                />
              );
            })}
          </div>
          <LienModule href="/alertes" libelle="Toutes les alertes" />
        </Card>
      </div>
    </div>
  );
}
