import type { Metadata } from "next";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { formatDateFr, formatNombre } from "@/lib/format";
import {
  getCatalogueSources,
  getDerniereIngestion,
  getLicences,
  type NiveauFraicheur,
  type SourceCataloguee,
} from "@/lib/queries/donnees";

// Le catalogue reflète la base locale à chaque ingestion : jamais figé au build.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Données & exports",
  description:
    "Le manifeste de méthode du site : catalogue des sources avec fraîcheur mesurée, périmètre et limites assumées, licences et crédits, exports JSON quotidiens, reproduction locale.",
};

/**
 * Page /donnees — « Données & exports », le manifeste de méthode du projet :
 * 1. le tableau de fraîcheur central (meta_sources + badge de fraîcheur
 *    relative, règle simple documentée) ;
 * 2. périmètre « argent public » et promesses marketing NON tenables avec la
 *    donnée réelle (docs/SOURCES.md §2 encart + §3) ;
 * 3. licences réellement présentes en base et crédits obligatoires ;
 * 4. les exports JSON quotidiens (site statique — plus une API interrogeable) ;
 * 5. reproduction (make ingest).
 */

/* ---------------------------------------------------------------- */
/* Badge de fraîcheur (pastille + libellé — jamais la couleur seule) */
/* ---------------------------------------------------------------- */

const NIVEAUX: Record<NiveauFraicheur, { jeton: string; libelle: string }> = {
  verte: { jeton: "var(--status-good)", libelle: "À jour" },
  orange: { jeton: "var(--status-warning)", libelle: "À surveiller" },
  rouge: { jeton: "var(--status-critical)", libelle: "En retard" },
  millesime: { jeton: "var(--viz-autre)", libelle: "Millésime" },
};

function BadgeFraicheur({ source }: { source: SourceCataloguee }) {
  const { niveau, ageJours, periodeJours } = source.fraicheur;
  const n = NIVEAUX[niveau];
  const detail =
    niveau === "millesime"
      ? `Âge de la donnée : ${ageJours} j — millésime, pas d'âge attendu pertinent (décalage structurel documenté)`
      : `Âge de la donnée : ${ageJours} j — période attendue : ${periodeJours} j`;
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap" title={detail}>
      <span
        aria-hidden="true"
        className="inline-block size-2 rounded-full"
        style={{ background: n.jeton }}
      />
      <span className="text-ink-secondary">{n.libelle}</span>
    </span>
  );
}

/** Fréquence courte (la précision complète reste en title). */
function FrequenceCourte({ frequence }: { frequence: string }) {
  const courte = frequence.split(" (")[0];
  return (
    <span title={frequence !== courte ? frequence : undefined} className="whitespace-nowrap">
      {courte}
    </span>
  );
}

/* ---------------------------------------------------------------- */
/* Promesses de la maquette intenables (condensé de docs/SOURCES.md) */
/* ---------------------------------------------------------------- */

const PROMESSES: { promesse: string; reel: string }[] = [
  {
    promesse: "Compteur « dépenses aujourd'hui », variation vs veille",
    reel:
      "Aucune donnée ouverte de paiement en temps réel n'existe (aucun dataset Chorus ; Data-État réservé aux agents). Meilleure fraîcheur réelle : mensuelle, ~5-7 semaines de décalage → compteur « depuis le 1er janvier » sur données DGFiP, variation vs même période N−1.",
  },
  {
    promesse: "Flux « dernières dépenses en direct » horodaté à la minute",
    reel:
      "Les flux quotidiens réels sont contractuels ou normatifs : derniers marchés notifiés (J−1, mention « en cours de consolidation », latence légale ≤ 2 mois) et derniers textes au Journal officiel (jour même, lot nocturne).",
  },
  {
    promesse: "Module « notes de frais » en flux",
    reel:
      "Aucune note de frais du pouvoir national n'est publiée ni communicable (ordonnance 58-1100, CE mars 2025, refus des deux chambres du 11/06/2026) → module « Frais & train de vie » : barèmes 2026, enveloppes, contrôles agrégés, et la « boîte noire » documentant ce qui est caché et pourquoi.",
  },
  {
    promesse: "Top ministères « aujourd'hui », évolution en continu",
    reel:
      "Le niveau mission/programme mensuel n'existe qu'en PDF anti-bot ; l'API mensuelle compte 26 lignes par grands titres → répartition mensuelle par nature de dépense + répartition annuelle par mission (PLF 2026 — la LFI 2026 n'a jamais été publiée en données).",
  },
  {
    promesse: "Carte de France des « dépenses en direct »",
    reel:
      "Les dépenses de l'État ne sont pas géolocalisées en open data → cartes réelles : marchés publics notifiés sur 30 jours (lat/lng natives) et finances locales en €/habitant, libellées comme telles.",
  },
  {
    promesse: "Bandeau « transactions »",
    reel:
      "Les DECP sont des engagements contractuels (montants maximums pour les accords-cadres), pas des paiements → libellé exact « marchés notifiés », montants rationalisés, jamais « dépensé ».",
  },
  {
    promesse: "Horodatage à la minute",
    reel:
      "Publication par lots (JO : 1 lot nocturne ; DECP : build quotidien ; HATVP : hebdomadaire) → horodatage au jour de publication de la source, latence connue affichée.",
  },
  {
    promesse: "Alertes « temps réel »",
    reel:
      "Les alertes sont recalculées à chaque mise à jour des sources (HATVP hebdomadaire ; lobbying et marchés quotidiens), chacune datée — voir la page Alertes.",
  },
];

/* ---------------------------------------------------------------- */
/* Exports JSON quotidiens (site statique — plus d'API paramétrique)  */
/* ---------------------------------------------------------------- */

const EXPORTS: { chemin: string; description: string }[] = [
  {
    chemin: "/api/meta.json",
    description:
      "Le catalogue meta_sources complet : chaque source tracée avec nom, URL amont, licence, fréquence, date des données, date d'ingestion, volumétrie et notes.",
  },
  {
    chemin: "/api/alertes.json",
    description:
      "Les alertes calculées à l'ingestion, chacune avec sa règle, sa base légale et son URL source.",
  },
  {
    chemin: "/api/elus.json",
    description:
      "Le répertoire des élus — champs publics uniquement, mandats détaillés en JSON.",
  },
  {
    chemin: "/api/budget-mensuel.json",
    description:
      "Situations mensuelles budgétaires de l'État (montants = cumuls depuis le 1er janvier).",
  },
  {
    chemin: "/api/marches-agregats.json",
    description:
      "Agrégats de marchés publics pré-calculés à l'ingestion : par département (12 mois, montants écrêtés à 100 M€/marché) et par mois (36 mois).",
  },
  {
    chemin: "/data/recherche-index.json",
    description:
      "L'index de la recherche du site — c'est ce fichier que la barre de recherche charge et interroge côté navigateur.",
  },
];

/* ---------------------------------------------------------------- */

export default async function PageDonnees() {
  const sources = getCatalogueSources();
  const licences = getLicences();
  const derniereIngestion = getDerniereIngestion();

  if (sources === null) {
    return (
      <section className="flex flex-col gap-4">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Données &amp; exports
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          La base locale n’est pas encore construite — lancer{" "}
          <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code> pour
          ingérer les sources. Cette page devient alors le catalogue de fraîcheur
          des données.
        </div>
      </section>
    );
  }

  const totalLignes = sources.reduce((s, x) => s + x.lignes, 0);

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Données &amp; exports
        </h1>
        <p className="max-w-3xl text-sm text-ink-secondary">
          Le manifeste de méthode du dashboard : données publiques réelles
          uniquement, fraîcheur mesurée et affichée, limites dites telles
          quelles. {formatNombre(sources.length)} sources tracées,{" "}
          {formatNombre(totalLignes)} lignes en base locale
          {derniereIngestion
            ? `, dernière ingestion le ${formatDateFr(derniereIngestion)}`
            : ""}
          .
        </p>
      </header>

      {/* 1. Le tableau de fraîcheur central */}
      <Card
        titre="Les sources de ce dashboard"
        sousTitre="meta_sources — chaque source porte sa date de données réelle, sa date d'ingestion, sa fréquence promise et sa licence"
      >
        <DataTable
          colonnes={[
            {
              cle: "nom",
              entete: "Source",
              rendu: (s: SourceCataloguee) => (
                <span className="block min-w-56 whitespace-normal leading-snug">
                  {s.nom}{" "}
                  <span className="text-[11px] text-ink-muted">({s.source_id})</span>
                </span>
              ),
            },
            { cle: "date_donnees", entete: "Données au", type: "date" },
            { cle: "date_ingestion", entete: "Ingérée le", type: "date" },
            {
              cle: "frequence",
              entete: "Fréquence",
              rendu: (s: SourceCataloguee) => <FrequenceCourte frequence={s.frequence} />,
            },
            { cle: "lignes", entete: "Lignes", type: "nombre" },
            {
              cle: "fraicheur",
              entete: "Fraîcheur",
              rendu: (s: SourceCataloguee) => <BadgeFraicheur source={s} />,
            },
            {
              cle: "licence",
              entete: "Licence",
              rendu: (s: SourceCataloguee) => (
                <span className="block min-w-36 whitespace-normal text-xs leading-snug text-ink-secondary">
                  {s.licence}
                </span>
              ),
            },
            {
              cle: "url",
              entete: "Lien",
              rendu: (s: SourceCataloguee) => (
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="whitespace-nowrap text-ink-secondary underline decoration-dotted underline-offset-2 hover:text-ink"
                >
                  source ↗
                </a>
              ),
            },
          ]}
          lignes={sources}
          cleLigne={(s) => s.source_id}
        />
        <div className="mt-3 flex flex-col gap-1.5 text-xs leading-relaxed text-ink-muted">
          <p>
            <span className="font-semibold text-ink-secondary">
              Règle du badge de fraîcheur
            </span>{" "}
            — âge de la donnée (aujourd’hui − date des données) comparé à la
            période P de la fréquence promise (quotidienne 1 j, hebdomadaire 7 j,
            mensuelle 30 j, trimestrielle 91 j)&nbsp;: «&nbsp;à jour&nbsp;» si
            âge ≤ 2×P + 2 j (marge de publication), «&nbsp;à surveiller&nbsp;»
            si âge ≤ 4×P + 7 j, «&nbsp;en retard&nbsp;» au-delà. Les sources à
            millésime (annuelle, par scrutin, statique, continue, à parution)
            n’ont pas d’âge attendu pertinent&nbsp;: leur décalage est
            structurel et documenté (ex. subventions aux associations&nbsp;:
            versements 2023, dernier millésime publié) — le pipeline vérifie à
            chaque ingestion qu’il tient le dernier millésime.
          </p>
          <p>
            Un badge «&nbsp;à surveiller&nbsp;» ou «&nbsp;en retard&nbsp;»
            signale un écart à la fréquence promise, pas forcément une
            panne&nbsp;: le flux amont peut être réellement en pause (ex.
            scrutins AN&nbsp;: dernier scrutin le 21/07/2026, vacances
            parlementaires).
          </p>
        </div>
      </Card>

      {/* 2. Périmètre et honnêteté */}
      <Card
        titre="Périmètre et honnêteté"
        sousTitre="Ce que couvre le dashboard, ce qu'il ne couvre pas, et ce que la maquette promettait à tort"
      >
        <div
          className="rounded-lg border border-card-border p-4 text-sm leading-relaxed text-ink-secondary"
          style={{ borderLeft: "2px solid var(--viz-serie-1)" }}
        >
          <h3 className="mb-1.5 text-[12px] font-semibold uppercase tracking-[0.1em] text-ink">
            Périmètre «&nbsp;argent public&nbsp;»
          </h3>
          <p>
            Le dashboard couvre le <strong className="text-ink">budget général de
            l’État</strong>, le <strong className="text-ink">Parlement et la vie
            politique</strong> (élus, lobbying, financement), la{" "}
            <strong className="text-ink">commande publique</strong> et les{" "}
            <strong className="text-ink">finances locales</strong>. Hors champ,
            et dit tel quel&nbsp;: les administrations de sécurité sociale
            (~600&nbsp;Md€, premier poste de la dépense publique), la dépense
            propre des opérateurs de l’État (seuls leurs crédits budgétaires
            apparaissent) et les entreprises publiques. Tout compteur global
            porte la mention «&nbsp;budget général de l’État&nbsp;» — jamais
            «&nbsp;la dépense publique&nbsp;».
          </p>
        </div>

        <h3 className="mb-2 mt-5 text-[12px] font-semibold uppercase tracking-[0.1em] text-ink">
          Promesses de la maquette non tenables avec la donnée réelle
        </h3>
        <p className="mb-3 max-w-3xl text-xs text-ink-muted">
          La maquette de référence était une fiction marketing sur plusieurs
          points. Chaque impossibilité est prouvée par les rapports de la
          Phase 0 (docs/SOURCES.md §3) ; voici la promesse et ce que le
          dashboard fait à la place.
        </p>
        <ul className="flex flex-col gap-3">
          {PROMESSES.map((p) => (
            <li
              key={p.promesse}
              className="border-l pl-3.5"
              style={{ borderColor: "var(--viz-grid)" }}
            >
              <p className="text-[13px] font-medium text-ink">
                <span className="mr-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted">
                  Promis
                </span>
                {p.promesse}
              </p>
              <p className="mt-0.5 text-[13px] leading-snug text-ink-secondary">
                <span className="mr-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted">
                  Réel
                </span>
                {p.reel}
              </p>
            </li>
          ))}
        </ul>
      </Card>

      {/* 3. Licences et crédits */}
      <Card
        titre="Licences et crédits"
        sousTitre="Licences telles qu'enregistrées en base (meta_sources.licence) — la réutilisation impose la mention de la source"
      >
        {licences && (
          <DataTable
            colonnes={[
              { cle: "licence", entete: "Licence" },
              { cle: "nb", entete: "Sources", type: "nombre" },
              {
                cle: "sources",
                entete: "Identifiants",
                rendu: (l) => (
                  <span className="block max-w-md whitespace-normal text-xs leading-snug text-ink-muted">
                    {l.sources}
                  </span>
                ),
              },
            ]}
            lignes={licences}
            cleLigne={(l) => l.licence}
          />
        )}
        <div className="mt-4 flex flex-col gap-1.5 text-[13px] leading-relaxed text-ink-secondary">
          <p>
            <strong className="text-ink">Crédits obligatoires</strong> — marchés
            publics&nbsp;: consolidation communautaire{" "}
            <a
              href="https://github.com/ColinMaudry/decp-processing"
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-dotted underline-offset-2 hover:text-ink"
            >
              decp-processing
            </a>{" "}
            (Colin Maudry) ; scores de participation et de loyauté des
            députés&nbsp;:{" "}
            <a
              href="https://datan.fr"
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-dotted underline-offset-2 hover:text-ink"
            >
              Datan
            </a>{" "}
            (méthode publiée par Datan, affichée à côté du taux calculé par
            France Transparence) ; Journal officiel, BOAMP, annuaire de
            l’administration et référentiel de l’organisation de l’État&nbsp;:
            DILA ; déclarations d’intérêts et répertoire des représentants
            d’intérêts&nbsp;: HATVP ; comptes des partis et comptes de
            campagne&nbsp;: CNCCFP ; répertoire national des élus&nbsp;:
            ministère de l’Intérieur ; données parlementaires&nbsp;: Assemblée
            nationale et Sénat ; finances locales&nbsp;: OFGL ; budget de
            l’État&nbsp;: DGFiP (data.economie.gouv.fr) ; populations de
            référence 2023&nbsp;: INSEE ; fond de carte&nbsp;: france-geojson
            (contours IGN/Etalab).
          </p>
          <p className="text-xs text-ink-muted">
            Les agrégats calculés par France Transparence (dont les exports
            JSON ci-dessous) sont ré-exploitables en Licence Ouverte 2.0, avec
            mention de la source amont de chaque donnée. Les constantes
            «&nbsp;train de vie&nbsp;» (S31) et le décret d’aide publique (S37)
            proviennent de publications officielles hors open data, citées avec
            leur URL.
          </p>
        </div>
      </Card>

      {/* 4. Exports JSON quotidiens */}
      <Card
        titre="Exports JSON (reconstruits chaque matin)"
        sousTitre="Fichiers statiques publiés avec le site à chaque ingestion — téléchargeables et ré-exploitables"
      >
        <p className="mb-4 max-w-3xl text-[13px] leading-relaxed text-ink-secondary">
          Chaque fichier est un <strong className="text-ink">instantané
          quotidien daté</strong> (champ{" "}
          <code className="rounded bg-raised px-1 py-0.5 text-xs">genere_le</code>{" "}
          de{" "}
          <code className="rounded bg-raised px-1 py-0.5 text-xs">meta.json</code>
          ), et non plus une API interrogeable&nbsp;; la recherche du site
          interroge l&apos;index côté navigateur.
        </p>
        <ul className="flex flex-col gap-4">
          {EXPORTS.map((e) => (
            <li key={e.chemin} className="border-l pl-3.5" style={{ borderColor: "var(--viz-grid)" }}>
              <p className="text-[13px]">
                <a
                  href={e.chemin}
                  className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
                >
                  <code className="rounded bg-raised px-1.5 py-0.5 text-xs text-ink">
                    {e.chemin}
                  </code>
                </a>
              </p>
              <p className="mt-1 text-[13px] leading-snug text-ink-secondary">{e.description}</p>
            </li>
          ))}
        </ul>
      </Card>

      {/* 5. Reproduire */}
      <Card
        titre="Reproduire"
        sousTitre="Tout le dashboard se reconstruit localement, sans clé d'API ni compte"
      >
        <div className="flex flex-col gap-3 text-[13px] leading-relaxed text-ink-secondary">
          <p>
            Les 13 pipelines Python (référentiels, budget, marchés, BOAMP,
            APProch, JO, Parlement, intégrité, lobbying, financement,
            collectivités, train de vie) téléchargent les sources ouvertes et
            construisent l’unique base{" "}
            <code className="rounded bg-raised px-1 py-0.5 text-xs">data/france.db</code>{" "}
            (SQLite) — l’application ne fait aucun appel externe au runtime,
            elle ne lit que cette base.
          </p>
          <pre className="overflow-x-auto rounded-lg bg-raised p-3 text-xs leading-relaxed text-ink">
            {`make ingest          # ingère les 13 pipelines → data/france.db
make ingest-jorf     # ré-ingère une seule source (ex. Journal officiel)
make test            # tests des pipelines
make dev             # lance l'application (port 3620)`}
          </pre>
          <p className="text-xs text-ink-muted">
            Mode d’emploi et catalogue complets dans le dépôt&nbsp;:{" "}
            <code className="rounded bg-raised px-1 py-0.5 text-[11px]">Makefile</code>{" "}
            (cibles d’ingestion),{" "}
            <code className="rounded bg-raised px-1 py-0.5 text-[11px]">docs/SOURCES.md</code>{" "}
            (référentiel des 39 sources évaluées, promesses écartées comprises) et{" "}
            <code className="rounded bg-raised px-1 py-0.5 text-[11px]">docs/SCHEMA-DB.md</code>{" "}
            (schéma exact de la base et volumétrie).
          </p>
        </div>
      </Card>
    </section>
  );
}
