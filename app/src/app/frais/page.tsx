import type { Metadata } from "next";
import type { ReactNode } from "react";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { Money } from "@/components/ui/Money";
import { StatStrip } from "@/components/ui/StatStrip";
import { ESPACE_FINE, formatDateFr, formatNombre, formatPct } from "@/lib/format";
import {
  getFraisData,
  getVerrousCada,
  grouperParCategorie,
  SENS_REFUS,
  type TrainvieCategorie,
  type TrainvieFait,
  type VerrousCadaData,
} from "@/lib/queries/frais";
import { JsonLd } from "@/components/JsonLd";
import { jsonLdPage, metadonneesPage } from "@/lib/seo";

// Rendu statique : la donnée ne change qu'à l'ingestion, le site est
// reconstruit après chaque ingestion (docs/deploiement/DECISION.md).

// Chemin, titre et description nommés UNE FOIS : les métadonnées et le
// balisage JSON-LD décrivent la même page, ils ne peuvent donc pas la
// décrire différemment le jour où l'un des deux est retouché.
const CHEMIN = "/frais/";
const TITRE = "Frais & train de vie";
const DESCRIPTION =
  "Indemnités, frais de mandat et train de vie des responsables publics : les barèmes publics, les agrégats de contrôle — et ce que la loi ne publie pas.";

export const metadata: Metadata = metadonneesPage({
  chemin: CHEMIN,
  titre: TITRE,
  description: DESCRIPTION,
});

// `WebPage` : un tableau de bord, comme /depenses, /marches ou /financement —
// le même moule, au mot près.
//
// PAS de `Dataset` : la page n'offre aucun téléchargement (elle affiche des
// barèmes et des agrégats, chacun avec le lien vers SA source officielle),
// et les exports du site sont déjà décrits, au complet, par le `DataCatalog`
// de /donnees. PAS de `dateModified` non plus : les faits affichés viennent
// de sources aux rythmes différents (LFI annuelle, barèmes DGCL, rapports de
// la Cour des comptes), et leur fraîcheur est dite à l'écran, fait par fait.
const BALISAGE = jsonLdPage({
  chemin: CHEMIN,
  nom: TITRE,
  description: DESCRIPTION,
  ariane: [{ nom: "Accueil", chemin: "/" }, { nom: TITRE }],
});

/* ------------------------------------------------------------------ */
/* Formats propres au module (typographie française, espaces fines)    */
/* ------------------------------------------------------------------ */

/** `7637.39` → `7 637,39 €` ; `6600` → `6 600 €` (cents affichés si réels). */
function eurosExact(v: number): string {
  let s = formatNombre(v, Number.isInteger(v) ? 0 : 2);
  // formatNombre ne force pas les 2 décimales : `8239.1` → `8 239,1` → padder.
  if (/,\d$/.test(s)) s += "0";
  return s + ESPACE_FINE + "€";
}

const MOIS_LONGS = [
  "janvier",
  "février",
  "mars",
  "avril",
  "mai",
  "juin",
  "juillet",
  "août",
  "septembre",
  "octobre",
  "novembre",
  "décembre",
];

/** Dates sources à granularité variable : `2025` → `2025` ;
 *  `2026-01` → `janvier 2026` ; `2026-02-17` → `17/02/2026`.
 *  (formatDateFr inventerait un jour précis sur `2026-01`.) */
function formatDateSourceFr(d: string): string {
  if (/^\d{4}$/.test(d)) return d;
  const m = /^(\d{4})-(\d{2})$/.exec(d);
  if (m) return `${MOIS_LONGS[Number(m[2]) - 1]} ${m[1]}`;
  return formatDateFr(d);
}

/**
 * Assiette d’un montant (« brut » / « net »), accolée à la valeur.
 *
 * OBLIGATOIRE dès que la donnée la porte : cette page range dans la même
 * colonne des barèmes bruts (indemnités de fonction, plafonds DGCL) et des
 * montants nets (indemnité perçue par un parlementaire). Sans ce mot, la
 * comparaison visuelle est fausse — un questeur du Sénat paraîtrait moins
 * bien traité qu’un sénateur ordinaire, alors qu’on compare un brut à un net.
 */
function Assiette({ fait }: { fait: TrainvieFait }) {
  if (!fait.assiette) return null;
  return (
    <span className="ml-1 font-normal text-ink-muted">
      {fait.assiette === "brut" ? "brut" : "net"}
    </span>
  );
}

/** Valeur d’un fait formatée selon son `unite` (jamais de montant nu). */
function ValeurFait({ fait }: { fait: TrainvieFait }) {
  switch (fait.unite) {
    case "euros":
      // ≥ 1 M€ : compaction Money (le title porte la valeur exacte).
      return fait.valeur >= 1e6 ? (
        <Money valeur={fait.valeur} />
      ) : (
        <>
          {eurosExact(fait.valeur)}
          <Assiette fait={fait} />
        </>
      );
    case "euros_par_mois":
      return (
        <>
          {eurosExact(fait.valeur)}/mois
          <Assiette fait={fait} />
        </>
      );
    case "pourcent":
      return <>{formatPct(fait.valeur, Number.isInteger(fait.valeur) ? 0 : 1)}</>;
    case "personnes":
      return <>{formatNombre(fait.valeur) + ESPACE_FINE + "personnes"}</>;
    case "justificatifs":
      return <>{formatNombre(fait.valeur) + ESPACE_FINE + "justificatifs"}</>;
    case "deplacements":
      return <>{formatNombre(fait.valeur) + ESPACE_FINE + "déplacements"}</>;
    default:
      return <>{formatNombre(fait.valeur)}</>;
  }
}

/* ------------------------------------------------------------------ */
/* Blocs d’affichage                                                    */
/* ------------------------------------------------------------------ */

/** Une ligne « fait » : libellé, valeur selon unité, période, source, notes. */
function FaitRow({ fait, dernier }: { fait: TrainvieFait; dernier: boolean }) {
  return (
    <li
      className="flex items-start justify-between gap-4 py-2.5"
      style={dernier ? undefined : { borderBottom: "1px solid var(--viz-grid)" }}
    >
      <div className="min-w-0">
        <p className="text-[13px] leading-snug text-ink-secondary">{fait.libelle}</p>
        {fait.notes && (
          <p className="mt-1 text-[11px] leading-snug text-ink-muted">{fait.notes}</p>
        )}
        <p className="mt-1 text-[11px] leading-snug text-ink-muted">
          Source&nbsp;:{" "}
          <a
            href={fait.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
          >
            {fait.source_nom}
          </a>{" "}
          · {formatDateSourceFr(fait.date_source)}
        </p>
      </div>
      <div className="max-w-[11rem] shrink-0 text-right">
        <div className="text-[15px] font-semibold leading-tight text-ink">
          <ValeurFait fait={fait} />
        </div>
        <div className="mt-0.5 text-[11px] leading-snug text-ink-muted">
          {fait.periode} · {fait.institution}
        </div>
      </div>
    </li>
  );
}

/** Colonne de l’encart récapitulatif final (public / non public). */
function ResumeCol({
  etat,
  nonPublic = false,
  titre,
  children,
}: {
  etat: string;
  nonPublic?: boolean;
  titre: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-card-border p-4">
      <span
        className={`self-start rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.12em] ${
          nonPublic
            ? "border-dashed border-raised-border text-ink"
            : "border-card-border text-ink-secondary"
        }`}
      >
        {etat}
      </span>
      <h3 className="text-sm font-semibold text-ink">{titre}</h3>
      <p className="text-xs leading-relaxed text-ink-secondary">{children}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Carte des verrous (S38 — avis de la CADA)                           */
/* ------------------------------------------------------------------ */

/** Libellés des catégories d'administration produites par le pipeline. */
const CATEGORIES_CADA: Record<string, string> = {
  ministere: "Ministères et Premier ministre",
  prefecture: "Préfectures",
  commune: "Communes et intercommunalités",
  departement_region: "Départements et régions",
  sante: "Hôpitaux et santé",
  enseignement: "Enseignement et recherche",
  securite_sociale: "Organismes de sécurité sociale",
  finances: "Finances publiques et douanes",
  justice_police: "Justice, police, pénitentiaire",
  autorite_independante: "Autorités indépendantes",
  autre: "Autres organismes (non classés)",
};

/** Écart en mois entre deux dates ISO, arrondi — jamais figé dans le code. */
function moisEntre(debutIso: string, finIso: string): number {
  const debut = new Date(debutIso);
  const fin = new Date(finIso);
  return Math.round((fin.getTime() - debut.getTime()) / (1000 * 60 * 60 * 24 * 30.44));
}

/**
 * La carte des verrous : qui refuse de communiquer, sur quel fondement, et
 * dans quel sens la CADA tranche.
 *
 * Rendue intégralement côté serveur — le site doit rester utilisable sans
 * JavaScript — et tenue à des agrégats : le corpus compte des dizaines de
 * milliers de décisions, la page n'en porte que les dénombrements. Chaque
 * bloc a été pesé : cette carte ajoute une quinzaine de kilo-octets au HTML
 * de /frais, sur une page qui en fait déjà plus de deux cents.
 */
function CarteDesVerrous({ data }: { data: VerrousCadaData }) {
  const { meta, avis, conseils, premiereAnnee, derniereAnnee, administrations } = data;
  const retardMois = moisEntre(meta.date_donnees, meta.date_ingestion);
  const defavorable = data.sens.find((s) => s.sens === "Défavorable")?.dossiers ?? 0;
  const favorable = data.sens.find((s) => s.sens === "Favorable")?.dossiers ?? 0;
  const pct = (v: number) => formatPct((100 * v) / avis, 0);

  return (
    <Card
      titre="La carte des verrous"
      sousTitre="Ce que l’administration refuse de communiquer, et ce que la CADA en dit"
      droite={
        <FreshnessBadge
          dateDonnees={meta.date_donnees}
          source="Avis de la CADA"
          frequence={meta.frequence}
          url={meta.url}
          mention={`retard de versement : ${retardMois} mois`}
        />
      }
    >
      <div className="flex flex-col gap-5">
        <p className="max-w-3xl text-[13px] leading-relaxed text-ink-secondary">
          Quand une administration refuse de communiquer un document, le demandeur peut
          saisir la Commission d’accès aux documents administratifs, qui rend un avis.
          Ces avis sont publiés : ils dessinent, décision après décision, la carte des
          refus. {formatNombre(avis)} avis et {formatNombre(conseils)} conseils sont ici
          dépouillés, de {premiereAnnee} à {derniereAnnee}, visant{" "}
          {formatNombre(administrations)} libellés d’administration distincts. Seuls des
          dénombrements sont conservés : le texte des décisions, qui nomme des
          responsables publics, n’est pas repris.
        </p>

        {/* Le piège éditorial, en clair et jamais masqué. */}
        <p className="max-w-3xl rounded-lg border border-dashed border-raised-border p-3 text-[13px] leading-relaxed text-ink-secondary">
          <span className="font-semibold text-ink">
            {retardMois}&nbsp;mois de retard de versement.
          </span>{" "}
          La CADA publie par lots : le jeu de données porte une date de mise à jour
          récente, mais la dernière séance qu’il contient est celle du{" "}
          {formatDateFr(meta.date_donnees)}. Les millésimes {derniereAnnee - 1} et{" "}
          {derniereAnnee} sont donc incomplets par construction, et l’écart s’aggrave :
          les derniers lots couvrent moins de mois de séance qu’il ne s’écoule de mois
          entre deux versements. Ces chiffres décrivent un corpus arrêté, pas l’activité
          de la commission aujourd’hui.
        </p>

        <div className="grid items-start gap-5 lg:grid-cols-2">
          <div className="flex flex-col gap-2">
            <h3 className="text-xs font-semibold uppercase tracking-[0.1em] text-ink">
              Dans quel sens la CADA tranche
            </h3>
            <p className="text-[11px] leading-snug text-ink-muted">
              Avis seulement, sur {formatNombre(avis)} dossiers. Une décision peut porter
              plusieurs sens (favorable sur une pièce, défavorable sur une autre) : le
              total dépasse donc 100 %.
            </p>
            <BarList
              items={data.sens.map((s) => ({
                libelle: s.sens,
                valeur: s.dossiers,
                // Emphase sur les trois sens de refus ; les deux autres en
                // couleur de contexte (BarList §3.2 : une série nominale, une
                // couleur, la seconde ne sert qu’à la dé-emphase).
                couleur: (SENS_REFUS as readonly string[]).includes(s.sens)
                  ? undefined
                  : "var(--viz-autre)",
              }))}
              largeurLibelle="34%"
              formatValeur={(v) => `${formatNombre(v)} (${pct(v)})`}
            />
          </div>

          <div className="flex flex-col gap-2">
            <h3 className="text-xs font-semibold uppercase tracking-[0.1em] text-ink">
              Sur quel fondement l’accès est refusé
            </h3>
            <p className="text-[11px] leading-snug text-ink-muted">
              Les motivations de refus les plus fréquentes, telles que la CADA les
              qualifie — un avis défavorable donne raison à l’administration, une
              incompétence renvoie ailleurs, une irrecevabilité écarte la saisine sans
              juger du fond.
            </p>
            <ul className="flex flex-col text-[13px]">
              {data.motifs.map((m) => (
                <li
                  key={`${m.sens}-${m.motivation ?? ""}`}
                  className="flex items-baseline justify-between gap-3 border-b border-card-border py-1.5 last:border-0"
                >
                  <span className="min-w-0 truncate text-ink-secondary">
                    {m.sens}
                    {m.motivation ? ` · ${m.motivation}` : ""}
                  </span>
                  <span className="shrink-0 [font-variant-numeric:tabular-nums]">
                    {formatNombre(m.dossiers)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <h3 className="text-xs font-semibold uppercase tracking-[0.1em] text-ink">
            Qui est mis en cause
          </h3>
          <p className="max-w-3xl text-[11px] leading-snug text-ink-muted">
            Le champ « administration » de la CADA est du texte libre, sans identifiant :
            ces catégories sont une typologie grossière, déduite du seul libellé publié,
            et ce qui n’entre dans aucune règle reste explicitement non classé. La part
            de refus est donnée sur les seuls avis défavorables, jamais sur la somme des
            refus, qui compterait deux fois les décisions composites.
          </p>
          <ul className="mt-1 flex flex-col text-[13px]">
            {data.categories.map((c) => (
              <li
                key={c.categorie}
                className="flex items-baseline justify-between gap-4 border-b border-card-border py-1.5 last:border-0"
              >
                <span className="min-w-0 truncate text-ink-secondary">
                  {CATEGORIES_CADA[c.categorie] ?? c.categorie}
                </span>
                <span className="shrink-0 text-[12px] text-ink-muted [font-variant-numeric:tabular-nums]">
                  <span className="font-semibold text-ink">{formatNombre(c.dossiers)}</span>{" "}
                  avis · {formatNombre(c.defavorable)} défavorables
                </span>
              </li>
            ))}
          </ul>
        </div>

        <p className="text-[11px] leading-relaxed text-ink-muted">
          Lecture : la CADA donne raison au demandeur, au moins en partie, dans{" "}
          {pct(favorable)} des avis, et à l’administration dans {pct(defavorable)}. Un
          avis n’a pas force exécutoire : l’administration reste libre de maintenir son
          refus, le demandeur devant alors saisir le juge administratif. Le corpus ne dit
          donc pas ce qui a été communiqué, seulement ce que la commission a estimé
          communicable.
        </p>
      </div>
    </Card>
  );
}

/** Titres et sous-titres des 7 catégories de faits. */
const CATEGORIES: { cle: TrainvieCategorie; titre: string; sousTitre: string }[] = [
  {
    cle: "indemnites_parlementaires",
    titre: "Indemnités parlementaires",
    sousTitre:
      "Barèmes publiés par les assemblées. Bruts et nets y coexistent tels qu’ils sont publiés : chaque montant porte son assiette, ne les comparez pas entre eux.",
  },
  {
    cle: "frais_mandat",
    titre: "Frais de mandat — les enveloppes",
    sousTitre:
      "Avances et dotations forfaitaires : les barèmes sont publics, pas le détail des dépenses",
  },
  {
    cle: "controles",
    titre: "Contrôles des frais de mandat",
    sousTitre:
      "Agrégats anonymisés publiés par le déontologue de l’Assemblée nationale et le comité de déontologie du Sénat",
  },
  {
    cle: "elysee",
    titre: "Élysée",
    sousTitre:
      "Comptes de la présidence de la République audités par la Cour des comptes — un rapport par an",
  },
  {
    cle: "institutions",
    titre: "Institutions — dotations 2026",
    sousTitre: "Mission « Pouvoirs publics » de la loi de finances initiale pour 2026",
  },
  {
    cle: "cabinets",
    titre: "Cabinets ministériels",
    sousTitre: "Jaune budgétaire annexé au PLF 2026 — situation au 01/07/2025",
  },
  {
    cle: "elus_locaux",
    titre: "Élus locaux — barèmes",
    sousTitre:
      "Indemnités maximales publiées par la DGCL au 01/01/2026 — les montants réellement versés ne sont pas centralisés",
  },
];

/* ------------------------------------------------------------------ */
/* Page                                                                 */
/* ------------------------------------------------------------------ */

/**
 * Frais & train de vie — LE module pédagogique du projet. La maquette
 * promettait des « notes de frais en direct » : c’est matériellement
 * impossible (aucun justificatif parlementaire n’est publié ni
 * communicable) — cette page montre ce qui est réellement public
 * (barèmes, agrégats de contrôle) et documente, source à l’appui,
 * ce que la loi ne publie pas.
 */
export default async function FraisPage() {
  const data = getFraisData();
  const verrous = getVerrousCada();

  if (!data) {
    return (
      <section className="flex flex-col gap-6">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Frais &amp; train de vie
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          <p>
            La base locale n’est pas encore construite — lancer{" "}
            <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code> pour ingérer
            les sources.
          </p>
        </div>
      </section>
    );
  }

  const { meta, faits, opacites } = data;
  const groupes = grouperParCategorie(faits);
  const parId = new Map(faits.map((f) => [f.id, f]));

  // Chiffres clés (mise en avant) — uniquement des faits réellement en base.
  const tuiles: { fait: TrainvieFait; label: string; vedette?: boolean }[] = [];
  const pousser = (id: string, label: (f: TrainvieFait) => string, vedette = false) => {
    const f = parId.get(id);
    if (f) tuiles.push({ fait: f, label: label(f), vedette });
  };
  pousser("ip-total-brut", () => "Indemnité parlementaire mensuelle brute", true);
  pousser("dfp-metropole", () => "Dotation de fonctionnement d’un député (créée au 01/01/2026)");
  pousser("ctrl-an-total-reversements", () => {
    const demandes = parId.get("ctrl-an-demandes-reversement");
    return demandes
      ? `Reversements demandés à ${formatNombre(demandes.valeur)} députés (2024)`
      : "Reversements demandés aux députés (2024)";
  });
  pousser("elysee-charges-2024", () => "Charges de la présidence de la République (2024)");
  pousser("lfi2026-an", () => "Dotation de l’Assemblée nationale (LFI 2026)");
  pousser("lfi2026-senat", () => "Dotation du Sénat (LFI 2026)");
  const sourcesTuiles = [...new Map(tuiles.map((t) => [t.fait.source_url, t.fait])).values()];

  return (
    <section className="flex flex-col gap-6">
      <JsonLd donnees={BALISAGE} />
      {/* ------------------------------- En-tête ------------------------------- */}
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="max-w-3xl">
          <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
            Frais &amp; train de vie
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-secondary">
            Les montants alloués aux responsables publics sont publics&nbsp;: indemnités,
            dotations et avances font l’objet de barèmes publiés par les assemblées et
            l’administration, et les comptes de l’Élysée sont audités chaque année par la
            Cour des comptes. En revanche, les justificatifs de frais des parlementaires ne
            sont ni publiés ni communicables (ordonnance n°&nbsp;58-1100 du 17&nbsp;novembre
            1958&nbsp;; refus écrits de l’Assemblée nationale et du Sénat du
            11&nbsp;juin&nbsp;2026). Des «&nbsp;notes de frais en direct&nbsp;» sont donc
            matériellement impossibles&nbsp;: cette page montre ce qui est réellement publié
            — et documente ce qui ne l’est pas.
          </p>
        </div>
        {meta && (
          <FreshnessBadge
            dateDonnees={meta.date_donnees}
            source={meta.nom}
            frequence={meta.frequence}
            url={meta.url}
          />
        )}
      </header>

      {/* --------------------------- Chiffres clés ---------------------------- */}
      {tuiles.length > 0 && (
        <div className="flex flex-col gap-2">
          <StatStrip
            stats={tuiles.map((t) => ({
              label: t.label,
              valeur: <ValeurFait fait={t.fait} />,
              montantVedette: t.vedette,
            }))}
          />
          <p className="text-[11px] leading-relaxed text-ink-muted">
            Sources des chiffres clés&nbsp;:{" "}
            {sourcesTuiles.map((f, i) => (
              <span key={f.source_url}>
                {i > 0 && " · "}
                <a
                  href={f.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
                >
                  {f.source_nom}
                </a>
              </span>
            ))}{" "}
            — détail et notes dans les cartes ci-dessous.
          </p>
        </div>
      )}

      {/* -------------------------- Ce qui est public -------------------------- */}
      <div className="flex flex-col gap-1">
        <h2 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Ce qui est public
        </h2>
        <p className="text-xs text-ink-secondary">
          {formatNombre(faits.length)} faits sourcés — chaque montant renvoie à sa
          publication officielle, datée.
        </p>
      </div>
      <div className="grid items-start gap-4 lg:grid-cols-2">
        {groupes.map((groupe) => {
          const infos = CATEGORIES.find((c) => c.cle === groupe.categorie);
          return (
            <Card
              key={groupe.categorie}
              titre={infos?.titre ?? groupe.categorie}
              sousTitre={infos?.sousTitre}
            >
              <ul className="flex flex-col">
                {groupe.faits.map((fait, i) => (
                  <FaitRow key={fait.id} fait={fait} dernier={i === groupe.faits.length - 1} />
                ))}
              </ul>
            </Card>
          );
        })}
      </div>

      {/* ----------------------------- Boîte noire ----------------------------- */}
      <div className="mt-2 flex flex-col gap-1">
        <h2 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          La boîte noire — ce que la loi ne publie pas
        </h2>
        <p className="max-w-3xl text-xs leading-relaxed text-ink-secondary">
          {formatNombre(opacites.length)} points documentés où la donnée n’est ni publiée ni
          accessible — avec, à chaque fois, ce qui manque, la base du refus et la source
          datée.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {opacites.map((o) => (
          <Card key={o.id} className="flex flex-col gap-2">
            <h3 className="text-sm font-semibold leading-snug text-ink">{o.sujet}</h3>
            <p className="text-[13px] leading-relaxed text-ink-secondary">{o.ce_qui_manque}</p>
            <p className="text-xs leading-relaxed text-ink-muted">
              <span className="font-medium uppercase tracking-[0.08em] text-[10px]">
                Base du refus&nbsp;
              </span>
              — {o.base_du_refus}
            </p>
            <p className="mt-auto pt-1 text-[11px] leading-snug text-ink-muted">
              Source&nbsp;:{" "}
              <a
                href={o.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
              >
                {o.source_nom}
              </a>{" "}
              · {formatDateSourceFr(o.date)}
            </p>
          </Card>
        ))}
      </div>

      {/* --------------------------- Carte des verrous -------------------------- */}
      {verrous && <CarteDesVerrous data={verrous} />}

      {/* ------------------------------ En résumé ------------------------------ */}
      <Card titre="En résumé" sousTitre="Ce que la loi publie — et ce qu’elle ne publie pas">
        <div className="grid gap-3 sm:grid-cols-3">
          <ResumeCol etat="Publics" titre="Les barèmes">
            Indemnités parlementaires, dotations de frais de mandat, indemnités maximales
            des élus locaux, dotations des pouvoirs publics&nbsp;: les grilles et enveloppes
            sont publiées par les assemblées, la DGCL et les documents budgétaires.
          </ResumeCol>
          <ResumeCol etat="Publics" titre="Les agrégats de contrôle">
            Les contrôles sont restitués en totaux anonymisés&nbsp;: rapports du déontologue
            de l’Assemblée nationale et du comité de déontologie du Sénat, rapports annuels
            de la Cour des comptes sur les comptes de l’Élysée.
          </ResumeCol>
          <ResumeCol etat="Non publics" titre="Les justificatifs" nonPublic>
            Les justificatifs et notes de frais des parlementaires ne sont ni publiés ni
            communicables (ordonnance n°&nbsp;58-1100&nbsp;; refus écrits de l’Assemblée
            nationale et du Sénat du 11&nbsp;juin&nbsp;2026). À l’inverse, les notes de
            frais des élus locaux sont communicables sur demande depuis la décision du
            Conseil d’État du 8&nbsp;février&nbsp;2023 — le Parlement est l’exception.
          </ResumeCol>
        </div>
      </Card>
    </section>
  );
}
