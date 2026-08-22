import type { Metadata } from "next";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { JsonLd } from "@/components/JsonLd";
import { DataTable } from "@/components/ui/DataTable";
import { formatDateFr, formatNombre } from "@/lib/format";
import {
  getCatalogueSources,
  getCouvertureBudgetMensuel,
  getCouvertureMarchesAgregats,
  getDerniereIngestion,
  getDerniereIngestionParIds,
  getLicences,
  type Fraicheur,
  type NiveauFraicheur,
  type SourceCataloguee,
} from "@/lib/queries/donnees";
import {
  jsonLdCatalogueDonnees,
  type DescriptionDataset,
  metadonneesPage,
} from "@/lib/seo";

// Rendu statique : le catalogue est figé au build, qui suit chaque
// ingestion (docs/deploiement/DECISION.md) — il reste donc à jour.

export const metadata: Metadata = metadonneesPage({
  chemin: "/donnees/",
  titre: "Données & exports",
  description:
    "Le manifeste de méthode du site : catalogue des sources avec fraîcheur mesurée, périmètre et limites assumées, licences et crédits, exports JSON quotidiens, reproduction locale.",
});

/**
 * Page /donnees — « Données & exports », le manifeste de méthode du projet :
 * 1. le tableau de fraîcheur central (meta_sources + badge de fraîcheur,
 *    un seuil calibré par source, règle et provenance des seuils
 *    documentées sous le tableau) ;
 * 2. périmètre « argent public », et l'état de la donnée publique poste par
 *    poste — ce qu'elle contient, ce qui en est publié (docs/SOURCES.md
 *    §2 encart + §3) ;
 * 3. licences réellement présentes en base et crédits obligatoires ;
 * 4. les exports JSON quotidiens (site statique — plus une API interrogeable) ;
 * 5. reproduction (make ingest).
 */

/* ---------------------------------------------------------------- */
/* Badge de fraîcheur (pastille + libellé — jamais la couleur seule) */
/* ---------------------------------------------------------------- */

const NIVEAUX: Record<NiveauFraicheur, { jeton: string; libelle: string }> = {
  a_jour: { jeton: "var(--status-good)", libelle: "À jour" },
  a_surveiller: { jeton: "var(--status-warning)", libelle: "À surveiller" },
  en_retard: { jeton: "var(--status-serious)", libelle: "En retard" },
  attente_edition: {
    jeton: "var(--status-critical)",
    libelle: "En attente d’une édition",
  },
  non_calibre: { jeton: "var(--viz-autre)", libelle: "Seuil non calibré" },
};

/** « 678 jours », « 2 jours ouvrés » — l'unité est celle du seuil de la source. */
function libelleAge(f: Fraicheur): string {
  const pluriel = f.ageJours >= 2 ? "s" : "";
  const unite = f.unite === "jo" ? `jour${pluriel} ouvré${pluriel}` : `jour${pluriel}`;
  return `${formatNombre(f.ageJours)} ${unite}`;
}

/** Seuil affiché avec son unité (« 850 j », « 20 j ouvrés »). */
function libelleSeuil(f: Fraicheur, jours: number): string {
  return `${formatNombre(jours)} ${f.unite === "jo" ? "j ouvrés" : "j"}`;
}

/**
 * La phrase exacte derrière le badge — factuelle et datée.
 *
 * Pour une source en attente, elle ne dit RIEN de l'avenir ni de
 * l'intention de l'éditeur : seulement qu'aucune édition plus récente
 * n'était parue à la date du build. C'est le seul fait vérifiable.
 */
function phraseFraicheur(s: SourceCataloguee): string {
  const f = s.fraicheur;
  const donneesAu = `Données au ${formatDateFr(s.date_donnees)}`;
  if (f.niveau === "non_calibre") {
    return `${donneesAu}, soit ${libelleAge(f)}. Aucun seuil n’est calibré pour cette source : son état n’est pas évalué.`;
  }
  const seuils = `seuils calibrés pour cette source : ${libelleSeuil(f, f.seuilRetardJours ?? 0)} (à surveiller) / ${libelleSeuil(f, f.seuilAlerteJours ?? 0)} (alerte)`;
  if (f.niveau === "attente_edition") {
    return `${donneesAu}. Aucune édition plus récente n’a été publiée à ce jour — ${libelleAge(f)}, ${seuils}.`;
  }
  return `${donneesAu}, soit ${libelleAge(f)} — ${seuils}.`;
}

function BadgeFraicheur({ source }: { source: SourceCataloguee }) {
  const f = source.fraicheur;
  const n = NIVEAUX[f.niveau];
  const detaille = f.niveau === "en_retard" || f.niveau === "attente_edition";
  return (
    <span className="inline-flex flex-col gap-0.5" title={phraseFraicheur(source)}>
      <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
        <span
          aria-hidden="true"
          className="inline-block size-2 shrink-0 rounded-full"
          style={{ background: n.jeton }}
        />
        <span className="text-ink-secondary">{n.libelle}</span>
      </span>
      {detaille && (
        <span className="whitespace-nowrap pl-3.5 text-[11px] text-ink-muted">
          {libelleAge(f)}
        </span>
      )}
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

/* ------------------------------------------------------------------ */
/* État de la donnée publique, poste par poste                         */
/* (condensé de docs/SOURCES.md § 3)                                   */
/*                                                                     */
/* Chaque entrée énonce ce que les sources publiques françaises        */
/* contiennent sur un poste, puis ce que le site publie à partir de    */
/* là. Rien d'autre : ni objectif, ni échéance, ni comparaison à un    */
/* état souhaité. Une absence de donnée est un fait constaté au        */
/* présent, et c'est à ce titre qu'elle figure ici.                    */
/* ------------------------------------------------------------------ */

const POSTES: { poste: string; donnee: string; publie: string }[] = [
  {
    poste: "Dépenses de l'État",
    donnee:
      "Aucune donnée ouverte de paiement en temps réel n'existe : aucun dataset Chorus, et Data-État est réservé aux agents. La maille la plus fraîche est mensuelle, avec ~5-7 semaines de décalage.",
    publie:
      "Un compteur « depuis le 1er janvier » sur données DGFiP, et sa variation par rapport à la même période N−1.",
  },
  {
    poste: "Flux quotidiens",
    donnee:
      "Les seuls flux réellement quotidiens sont contractuels ou normatifs : les marchés notifiés et les textes du Journal officiel.",
    publie:
      "Les derniers marchés notifiés (J−1, mention « en cours de consolidation », latence légale ≤ 2 mois) et les derniers textes au Journal officiel (jour même, lot nocturne).",
  },
  {
    poste: "Notes de frais",
    donnee:
      "Aucune note de frais du pouvoir national n'est publiée, ni communicable (ordonnance 58-1100, CE mars 2025, refus des deux chambres du 11/06/2026).",
    publie:
      "La page « Frais & train de vie » : barèmes 2026, enveloppes, contrôles agrégés, et la « boîte noire » qui documente ce qui est caché et sur quel fondement.",
  },
  {
    poste: "Ventilation par ministère",
    donnee:
      "Le niveau mission/programme mensuel n'existe qu'en PDF anti-bot ; l'API mensuelle compte 26 lignes, par grands titres. La LFI 2026 n'a jamais été publiée en données.",
    publie:
      "Une répartition mensuelle par nature de dépense, et une répartition annuelle par mission issue du PLF 2026.",
  },
  {
    poste: "Cartographie",
    donnee:
      "Les dépenses de l'État ne sont pas géolocalisées en open data.",
    publie:
      "Deux cartes libellées pour ce qu'elles sont : les marchés publics notifiés sur 12 mois, agrégés par département et signalés au chef-lieu, et les finances locales en €/habitant.",
  },
  {
    poste: "Montants des marchés",
    donnee:
      "Les DECP sont des engagements contractuels — pour un accord-cadre, un montant maximum — et non des paiements.",
    publie:
      "Le libellé exact « marchés notifiés », avec les montants rationalisés. Jamais le mot « dépensé ».",
  },
  {
    poste: "Horodatage",
    donnee:
      "Les sources publient par lots : un lot nocturne au Journal officiel, un build quotidien pour les DECP, une mise à jour hebdomadaire à la HATVP.",
    publie:
      "L'horodatage au jour de publication de la source, avec sa latence affichée.",
  },
  {
    poste: "Alertes",
    donnee:
      "Les sources dont dérivent les alertes se mettent à jour à leur propre cadence : HATVP hebdomadaire, lobbying et marchés quotidiens.",
    publie:
      "Des alertes recalculées à chaque mise à jour de source, chacune datée — voir la page Alertes.",
  },
];

/* ---------------------------------------------------------------- */
/* Exports JSON quotidiens (site statique — plus d'API paramétrique)  */
/* ---------------------------------------------------------------- */

/**
 * Les exports JSON publiés avec le site.
 *
 * En plus de ce qui est affiché (`chemin`, `description`), chaque entrée
 * porte ce qu'exige le balisage `Dataset` de schema.org — celui que Google
 * Dataset Search indexe, et la cible réelle de ce site (journalistes de
 * données, chercheurs) :
 * - `nom` : titre du jeu de données (l'URL ne suffit pas comme nom) ;
 * - `sources` : identifiants `meta_sources` amont, d'où est tirée la date de
 *   dernière modification RÉELLE (jamais la date du build) ; ils reprennent
 *   exactement ceux déclarés par la route de l'export ;
 * - `motsCles` : vocabulaire de recherche, factuel.
 */
type ExportJson = {
  cle: string;
  nom: string;
  chemin: string;
  description: string;
  sources: string[];
  motsCles: string[];
};

const EXPORTS: ExportJson[] = [
  {
    cle: "meta",
    nom: "Catalogue des sources de France Transparence (meta_sources)",
    sources: [],
    motsCles: ["open data", "catalogue de sources", "fraîcheur des données", "France"],
    chemin: "/api/meta.json",
    description:
      "Le catalogue meta_sources complet : chaque source tracée avec nom, URL amont, licence, fréquence, date des données, date d'ingestion, volumétrie et notes — plus genere_le, la date du build (témoin de fraîcheur du déploiement).",
  },
  {
    cle: "alertes",
    nom: "Alertes d'intégrité de la vie publique (France Transparence)",
    sources: ["S14", "S17", "S4", "S25", "S29"],
    motsCles: ["intégrité publique", "HATVP", "lobbying", "financement politique", "France"],
    chemin: "/api/alertes.json",
    description:
      "Toutes les alertes calculées à l'ingestion (dump complet), chacune avec sa règle, sa base légale et son URL source.",
  },
  {
    cle: "elus",
    nom: "Répertoire des élus français — champs publics compacts",
    sources: ["S17", "S5-AMO10", "S6-ODSEN", "S14"],
    motsCles: ["élus", "députés", "sénateurs", "mandats", "répertoire national des élus", "France"],
    chemin: "/api/elus.json",
    description:
      "Le répertoire des élus, en champs publics compacts : identité, identifiants AN/Sénat, lien HATVP, types de mandats (le détail des mandats reste sur les fiches et dans le RNE amont).",
  },
  {
    cle: "budget-mensuel",
    nom: "Situations mensuelles budgétaires de l'État français",
    sources: ["S13"],
    motsCles: ["budget de l'État", "dépenses publiques", "DGFiP", "série mensuelle", "France"],
    chemin: "/api/budget-mensuel.json",
    description:
      "Situations mensuelles budgétaires de l'État, série complète 2013 → dernier mois publié (26 lignes par mois, montants = cumuls depuis le 1er janvier).",
  },
  {
    cle: "marches-agregats",
    nom: "Agrégats de marchés publics français (DECP consolidées)",
    sources: ["S1"],
    motsCles: ["marchés publics", "commande publique", "DECP", "acheteurs publics", "France"],
    chemin: "/api/marches-agregats.json",
    description:
      "Agrégats de marchés publics pré-calculés à l'ingestion : par département (12 mois, montants écrêtés à 100 M€/marché) et par mois (36 mois). Chaque marché est compté à la date de sa notification initiale, un avenant ne le redate pas.",
  },
  {
    cle: "lobbying-marches",
    nom: "Croisement lobbying × marchés publics (HATVP × DECP)",
    sources: ["S4", "S1"],
    motsCles: [
      "lobbying",
      "représentants d’intérêts",
      "marchés publics",
      "HATVP",
      "DECP",
      "France",
    ],
    chemin: "/api/lobbying-marches.json",
    description:
      "Les représentants d'intérêts inscrits au répertoire HATVP qui sont titulaires de marchés publics, joints sur le SIREN : agrégats par périmètre (hors accords-cadres, montants écrêtés à 100 M€/marché puis répartis entre co-titulaires) et les titulaires détaillés. Être inscrit au répertoire et titulaire d'un marché est légal et courant : le fichier ne constate aucune irrégularité, hormis le constat officiel de défaut de déclaration de la HATVP, repris tel quel.",
  },
  {
    cle: "recherche-index",
    nom: "Index de recherche du site (élus et entités publiques)",
    sources: ["S17", "S5-AMO10", "S6-ODSEN"],
    motsCles: ["index de recherche", "élus", "institutions", "France"],
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

  /* Synthèse de fraîcheur, en tête du tableau : combien de sources sont à
     jour au regard de LEUR seuil, et lesquelles attendent une édition plus
     récente. Ce que l'open data ne contient pas se documente ; ça se dit
     sobrement, daté, avec l'ancienneté — sans rien affirmer de l'avenir. */
  const compte = (n: NiveauFraicheur) =>
    sources.filter((s) => s.fraicheur.niveau === n).length;
  const nbAJour = compte("a_jour");
  const nbASurveiller = compte("a_surveiller");
  const nbEnRetard = compte("en_retard");
  const nbNonCalibre = compte("non_calibre");
  const enAttente = sources.filter((s) => s.fraicheur.niveau === "attente_edition");

  /* Balisage `DataCatalog` + `Dataset` : dates de modification et couvertures
     temporelles LUES EN BASE — un balisage qui affirmerait une fraîcheur que
     la donnée n'a pas serait pire que pas de balisage du tout. */
  const couvertures: Record<string, string | null> = {
    "budget-mensuel": getCouvertureBudgetMensuel(),
    "marches-agregats": getCouvertureMarchesAgregats(),
  };
  const datasets: DescriptionDataset[] = EXPORTS.map((e) => ({
    cle: e.cle,
    nom: e.nom,
    description: e.description,
    chemin: e.chemin,
    motsCles: e.motsCles,
    dateModified:
      (e.sources.length > 0 ? getDerniereIngestionParIds(e.sources) : null) ??
      derniereIngestion,
    temporalCoverage: couvertures[e.cle] ?? null,
  }));

  return (
    <section className="flex flex-col gap-6">
      <JsonLd donnees={jsonLdCatalogueDonnees(datasets, derniereIngestion)} />
      <header className="flex flex-col gap-2">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Données &amp; exports
        </h1>
        <p className="max-w-3xl text-sm text-ink-secondary">
          Le manifeste de méthode du dashboard : données publiques réelles
          uniquement, fraîcheur mesurée et affichée, limites dites telles
          quelles. Comment lire un chiffre, d’où il vient et ce qu’il ne dit
          pas : page{" "}
          <Link
            href="/comprendre"
            className="underline decoration-dotted underline-offset-2 hover:text-ink"
          >
            Comprendre les données
          </Link>
          . {formatNombre(sources.length)} sources tracées,{" "}
          {formatNombre(totalLignes)} lignes ingérées
          {derniereIngestion
            ? `, dernière ingestion le ${formatDateFr(derniereIngestion)}`
            : ""}
          .
        </p>
      </header>

      {/* 1. Le tableau de fraîcheur central */}
      <Card
        titre="Les sources de ce dashboard"
        sousTitre="meta_sources — chaque source porte sa date de données réelle, sa date d'ingestion, sa fréquence déclarée et sa licence"
      >
        <div className="mb-4 flex flex-col gap-2 text-[13px] leading-relaxed text-ink-secondary">
          <p>
            <strong className="text-ink">
              {formatNombre(nbAJour)} source{nbAJour > 1 ? "s" : ""} sur{" "}
              {formatNombre(sources.length)}
            </strong>{" "}
            {nbAJour > 1 ? "sont à jour" : "est à jour"} au regard du seuil calibré
            pour chacune
            {nbASurveiller > 0 ? `, ${nbASurveiller} à surveiller` : ""}
            {nbEnRetard > 0 ? `, ${nbEnRetard} en retard` : ""}
            {nbNonCalibre > 0 ? `, ${nbNonCalibre} sans seuil calibré` : ""}
            {enAttente.length > 0
              ? `, ${enAttente.length} en attente d’une édition plus récente`
              : ""}
            .
          </p>
          {enAttente.length > 0 && (
            <ul className="flex flex-col gap-1.5">
              {enAttente.map((s) => (
                <li
                  key={s.source_id}
                  className="border-l pl-3"
                  style={{ borderColor: "var(--viz-grid)" }}
                >
                  <span className="text-ink">{s.nom}</span>{" "}
                  <span className="text-[11px] text-ink-muted">({s.source_id})</span>{" "}
                  — données au {formatDateFr(s.date_donnees)} ; aucune édition plus
                  récente n’a été publiée à ce jour ({libelleAge(s.fraicheur)}).
                </li>
              ))}
            </ul>
          )}
        </div>
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
            — l’âge de la donnée (aujourd’hui − date des données) est comparé
            à <strong className="text-ink-secondary">deux seuils calibrés pour
            cette source-là</strong>, et non à sa fréquence déclarée&nbsp;:
            «&nbsp;à jour&nbsp;» sous le premier seuil, «&nbsp;à
            surveiller&nbsp;» entre les deux, «&nbsp;en retard&nbsp;» au-delà
            du second, «&nbsp;en attente d’une édition&nbsp;» quand le
            dépassement excède à son tour la largeur de la bande de
            surveillance. Une règle générique tirée du mot
            «&nbsp;quotidienne&nbsp;» ou «&nbsp;annuelle&nbsp;» ne peut pas
            marcher&nbsp;: l’Assemblée nationale ne vote pas pendant la trêve
            estivale (un mois sans scrutin n’est pas un retard), et les
            subventions aux associations sont publiées 12 à 13 mois après la
            clôture de l’exercice (un âge de deux ans y est normal). Cinq
            sources publiées les jours ouvrés (Journal officiel, BOAMP,
            marchés publics, lobbying HATVP, APProch) ont leur âge compté en
            jours ouvrés.
          </p>
          <p>
            <span className="font-semibold text-ink-secondary">
              D’où viennent ces seuils
            </span>{" "}
            — du même référentiel que la supervision du serveur
            (<code className="rounded bg-raised px-1 py-0.5">fraicheur.conf</code>,
            une ligne par source, calibrée sur l’historique de publication
            réellement observé et sur les décalages documentés par les
            pipelines). Ce fichier n’étant lisible ni par le processus qui
            construit le site, ni dans un dépôt fraîchement cloné,
            l’application en embarque une copie&nbsp;:{" "}
            <code className="rounded bg-raised px-1 py-0.5">
              app/src/lib/queries/donnees.ts
            </code>
            , où le point de synchronisation des deux est documenté. Les deux
            se modifient ensemble.
          </p>
          <p>
            <span className="font-semibold text-ink-secondary">
              «&nbsp;En attente d’une édition&nbsp;» décrit la source, pas le
              site
            </span>{" "}
            — à cette date, aucune édition plus récente n’a été publiée en
            amont. Ce n’est ni une panne du dashboard, ni un pronostic&nbsp;:
            l’édition suivante peut paraître à tout moment, et la première
            ingestion qui la trouve la publiera.
          </p>
        </div>
      </Card>

      {/* 2. Périmètre et honnêteté */}
      <Card
        titre="Périmètre et honnêteté"
        sousTitre="Ce que couvre le dashboard, ce qu'il ne couvre pas, et l'état de la donnée disponible poste par poste"
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
          État de la donnée publique, poste par poste
        </h3>
        <p className="mb-3 max-w-3xl text-xs text-ink-muted">
          Aucune source publique française ne diffuse la dépense de l’État en
          continu. Pour chaque poste, voici ce que la donnée contient — chaque
          limite étant établie source à l’appui (docs/SOURCES.md §3) — et ce que
          le dashboard publie à partir de là.
        </p>
        <ul className="flex flex-col gap-3">
          {POSTES.map((p) => (
            <li
              key={p.poste}
              className="border-l pl-3.5"
              style={{ borderColor: "var(--viz-grid)" }}
            >
              <p className="text-[13px] font-medium text-ink">{p.poste}</p>
              <p className="mt-1 text-[13px] leading-snug text-ink-secondary">
                <span className="mr-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted">
                  Donnée
                </span>
                {p.donnee}
              </p>
              <p className="mt-0.5 text-[13px] leading-snug text-ink-secondary">
                <span className="mr-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted">
                  Publié
                </span>
                {p.publie}
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
        sousTitre="Fichiers statiques publiés avec le site à chaque ingestion — des instantanés datés téléchargeables, pas une API paramétrable"
      >
        <p className="mb-4 max-w-3xl text-[13px] leading-relaxed text-ink-secondary">
          Chaque fichier est un <strong className="text-ink">instantané
          quotidien daté</strong> (champ{" "}
          <code className="rounded bg-raised px-1 py-0.5 text-xs">genere_le</code>{" "}
          de{" "}
          <code className="rounded bg-raised px-1 py-0.5 text-xs">meta.json</code>
          ), et non plus une API interrogeable. Les exports{" "}
          <code className="rounded bg-raised px-1 py-0.5 text-xs">/api/*.json</code>{" "}
          portent un bloc <code className="rounded bg-raised px-1 py-0.5 text-xs">meta</code>{" "}
          (source(s) amont, date des données, licence) et un bloc{" "}
          <code className="rounded bg-raised px-1 py-0.5 text-xs">donnees</code> — un
          dump complet, sans paramètre de filtrage&nbsp;: le tri et le filtrage
          se font chez le réutilisateur. La recherche du site interroge son
          index côté navigateur.
        </p>
        <ul className="flex flex-col gap-4">
          {EXPORTS.map((e) => (
            <li key={e.chemin} className="border-l pl-3.5" style={{ borderColor: "var(--viz-grid)" }}>
              <p className="text-[13px]">
                <a
                  href={`${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}${e.chemin}`}
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
            Les pipelines Python (référentiels, budget, marchés, BOAMP,
            APProch, JO, Parlement, intégrité, déclarations HATVP, lobbying,
            financement, collectivités, élections, train de vie) téléchargent
            les sources ouvertes et
            construisent l’unique base{" "}
            <code className="rounded bg-raised px-1 py-0.5 text-xs">data/france.db</code>{" "}
            (SQLite) — l’application ne fait aucun appel externe au runtime,
            elle ne lit que cette base.
          </p>
          <pre className="overflow-x-auto rounded-lg bg-raised p-3 text-xs leading-relaxed text-ink">
            {`make ingest          # ingère tous les pipelines → data/france.db
make ingest-jorf     # ré-ingère une seule source (ex. Journal officiel)
make test            # tests des pipelines
make dev             # lance l'application (port 3620)`}
          </pre>
          <p className="text-xs text-ink-muted">
            Mode d’emploi et catalogue complets dans le dépôt&nbsp;:{" "}
            <code className="rounded bg-raised px-1 py-0.5 text-[11px]">Makefile</code>{" "}
            (cibles d’ingestion),{" "}
            <code className="rounded bg-raised px-1 py-0.5 text-[11px]">docs/SOURCES.md</code>{" "}
            (référentiel des 39 sources évaluées, sources écartées comprises) et{" "}
            <code className="rounded bg-raised px-1 py-0.5 text-[11px]">docs/SCHEMA-DB.md</code>{" "}
            (schéma exact de la base et volumétrie).
          </p>
        </div>
      </Card>
    </section>
  );
}
