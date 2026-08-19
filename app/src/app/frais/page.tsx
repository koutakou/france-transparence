import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Card } from "@/components/ui/Card";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { Money } from "@/components/ui/Money";
import { StatStrip } from "@/components/ui/StatStrip";
import { ESPACE_FINE, formatDateFr, formatNombre, formatPct } from "@/lib/format";
import {
  getFraisData,
  grouperParCategorie,
  type TrainvieCategorie,
  type TrainvieFait,
} from "@/lib/queries/frais";

// La base locale évolue à chaque ingestion : jamais figer cet état au build.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Frais & train de vie",
  description:
    "Indemnités, frais de mandat et train de vie des responsables publics : les barèmes publics, les agrégats de contrôle — et ce que la loi ne publie pas.",
};

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

/** Valeur d’un fait formatée selon son `unite` (jamais de montant nu). */
function ValeurFait({ fait }: { fait: TrainvieFait }) {
  switch (fait.unite) {
    case "euros":
      // ≥ 1 M€ : compaction Money (le title porte la valeur exacte).
      return fait.valeur >= 1e6 ? <Money valeur={fait.valeur} /> : <>{eurosExact(fait.valeur)}</>;
    case "euros_par_mois":
      return <>{eurosExact(fait.valeur)}/mois</>;
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

/** Titres et sous-titres des 7 catégories de faits. */
const CATEGORIES: { cle: TrainvieCategorie; titre: string; sousTitre: string }[] = [
  {
    cle: "indemnites_parlementaires",
    titre: "Indemnités parlementaires",
    sousTitre:
      "Barèmes publiés par les assemblées — indemnité de base identique pour les députés et les sénateurs",
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
