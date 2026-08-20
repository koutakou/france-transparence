import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/db";
import { Card } from "@/components/ui/Card";
import { DataTable, type Colonne } from "@/components/ui/DataTable";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { StatStrip } from "@/components/ui/StatStrip";
import { formatDateFr, formatNombre, formatPct } from "@/lib/format";
import {
  getFicheElu,
  getSourcesElus,
  type DeclarationHatvp,
  type MandatJson,
  type VoteLigne,
} from "@/lib/queries/elus";
import type { MetaSource } from "@/lib/db";

/**
 * Fiches PRÉ-GÉNÉRÉES au build, limitées aux mandats nationaux et exécutifs
 * (docs/deploiement/DECISION.md) : députés, sénateurs, présidents de conseil
 * départemental et régional (≈ 1 053 fiches — les seules riches : votes
 * nominaux, groupes, HATVP). Les 35 000 autres élus du répertoire (maires,
 * présidents d'EPCI…) n'ont PAS de page dédiée : 404 assumé
 * (`dynamicParams = false`), expliqué sur /elus.
 */
export const dynamicParams = false;

/** Types de mandat (JSON `elus.mandats`) ouvrant droit à une fiche statique. */
const TYPES_FICHE_STATIQUE = [
  "depute",
  "senateur",
  "president_conseil_departemental",
  "president_conseil_regional",
] as const;

export function generateStaticParams(): { id: string }[] {
  const db = getDb();
  // Base absente (dev sans ingestion) : aucune fiche générée, pas de crash.
  if (!db) return [];
  const marques = TYPES_FICHE_STATIQUE.map(() => "?").join(", ");
  const lignes = db
    .prepare(
      `SELECT DISTINCT e.id
       FROM elus e, json_each(e.mandats) je
       WHERE json_extract(je.value, '$.type') IN (${marques})
       ORDER BY e.id`,
    )
    .all(...TYPES_FICHE_STATIQUE) as { id: string }[];
  return lignes.map((l) => ({ id: l.id }));
}

/** Title « Prénom Nom — Élus » + description factuelle (requête légère). */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  // Canonique de la FICHE (jamais celle de l'accueil) : chemin relatif, que
  // Next compose avec metadataBase — basePath compris. Slash final imposé
  // par `trailingSlash: true`.
  const alternates = { canonical: `/elus/${encodeURIComponent(decodeIdSur(id))}/` };
  const db = getDb();
  if (!db) return { alternates };
  const elu = db
    .prepare("SELECT nom, prenom, uid_an, matricule_senat FROM elus WHERE id = ?")
    .get(decodeIdSur(id)) as
    | { nom: string; prenom: string | null; uid_an: string | null; matricule_senat: string | null }
    | undefined;
  if (!elu) return { alternates };
  const nomComplet = `${elu.prenom ?? ""} ${elu.nom}`.trim();
  const description =
    elu.uid_an || elu.matricule_senat
      ? `Mandats, activité parlementaire et déclarations HATVP de ${nomComplet}, à partir des données publiques officielles (AN, Sénat, HATVP, RNE).`
      : `Mandats et déclarations HATVP de ${nomComplet}, à partir des données publiques officielles (RNE, HATVP).`;
  return { title: `${nomComplet} — Élus`, description, alternates };
}

/* ------------------------------------------------------------------ */
/* Libellés                                                            */
/* ------------------------------------------------------------------ */

const TYPES_MANDAT: Record<string, string> = {
  depute: "Député·e",
  senateur: "Sénateur·rice",
  maire: "Maire",
  president_epci: "Président·e d’intercommunalité (EPCI)",
  president_conseil_departemental: "Président·e de conseil départemental",
  president_conseil_regional: "Président·e de conseil régional",
};

const POSITIONS: Record<string, string> = {
  pour: "Pour",
  contre: "Contre",
  abstention: "Abstention",
  nonVotant: "Non-votant",
};

/** Codes de documents HATVP (nomenclature officielle), code source affiché. */
const TYPES_DOCUMENT: Record<string, string> = {
  di: "Déclaration d’intérêts",
  dia: "Déclaration d’intérêts et d’activités",
  dim: "Déclaration d’intérêts modificative",
  diam: "Déclaration d’intérêts et d’activités modificative",
  dsp: "Déclaration de situation patrimoniale",
  dspm: "Déclaration de situation patrimoniale modificative",
  dspfm: "Déclaration de situation patrimoniale de fin de mandat",
};

function calculeAge(iso: string | null): number | null {
  if (!iso) return null;
  const naissance = new Date(iso);
  if (Number.isNaN(naissance.getTime())) return null;
  const present = new Date();
  let age = present.getFullYear() - naissance.getFullYear();
  const m = present.getMonth() - naissance.getMonth();
  if (m < 0 || (m === 0 && present.getDate() < naissance.getDate())) age -= 1;
  return age;
}

/** « 1 » → « 1re », « 5 » → « 5e » ; sinon la valeur telle quelle. */
function circonscriptionLisible(brut: string): string {
  if (/^\d+$/.test(brut)) {
    const n = Number(brut);
    return `${n === 1 ? "1re" : `${n}e`} circonscription`;
  }
  return brut;
}

function libelleSource(source: string | undefined): string {
  if (source === "AN-P9") return "AN";
  if (source === "SENAT-P9") return "Sénat";
  if (source === "RNE") return "RNE";
  return source ?? "—";
}

function lieuMandat(m: MandatJson): string | null {
  if (m.commune) return m.departement ? `${m.commune} (${m.departement})` : m.commune;
  if (m.epci) return m.departement ? `${m.epci} (${m.departement})` : m.epci;
  if (m.libelle) return m.libelle;
  if (m.region) return m.region;
  return m.departement ?? null;
}

function Badge({ source, mention }: { source: MetaSource | undefined; mention?: string }) {
  if (!source) return null;
  return (
    <FreshnessBadge
      dateDonnees={source.date_donnees}
      source={source.nom}
      frequence={source.frequence}
      url={source.url}
      mention={mention}
    />
  );
}

function LienExterne({ href, texte }: { href: string; texte: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 rounded-full border border-card-border bg-card px-2.5 py-1 text-[11px] leading-none text-ink-secondary transition-colors hover:border-raised-border hover:text-ink"
    >
      {texte}
      <span aria-hidden="true">↗</span>
    </a>
  );
}

/** Décodage défensif : un id malformé (`%zz`) doit finir en 404, pas en 500. */
function decodeIdSur(brut: string): string {
  try {
    return decodeURIComponent(brut);
  } catch {
    return brut;
  }
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default async function PageFicheElu({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  if (!getDb()) {
    return (
      <section className="flex flex-col gap-6">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Fiche élu
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          <p>
            La base locale n’est pas encore construite — lancer{" "}
            <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code> pour ingérer les
            sources.
          </p>
        </div>
      </section>
    );
  }

  const fiche = getFicheElu(decodeIdSur(id));
  if (!fiche) notFound();

  const sources = getSourcesElus() ?? {};
  const { elu, mandats, depute, senateur, votes, nb_scrutins_base, declarations } = fiche;

  const nomComplet = `${elu.prenom ?? ""} ${elu.nom}`.trim();
  const age = calculeAge(elu.date_naissance);
  const neLe = elu.sexe === "F" ? "Née le" : elu.sexe === "M" ? "Né le" : "Né·e le";

  // Ligne de mandat principale (factuelle, depuis les tables officielles).
  let mandatPrincipal: string | null = null;
  if (depute) {
    const morceaux: string[] = [];
    if (depute.groupe_nom) morceaux.push(`${depute.groupe_nom} (${depute.groupe_sigle ?? "—"})`);
    if (depute.departement) {
      morceaux.push(
        depute.num_circo
          ? `${depute.departement}, ${circonscriptionLisible(depute.num_circo)}`
          : depute.departement,
      );
    }
    mandatPrincipal = `${elu.sexe === "F" ? "Députée" : elu.sexe === "M" ? "Député" : "Député·e"}${
      morceaux.length > 0 ? ` — ${morceaux.join(" · ")}` : ""
    }`;
  } else if (senateur) {
    const morceaux: string[] = [];
    if (senateur.groupe) {
      morceaux.push(
        senateur.groupe_appartenance
          ? `${senateur.groupe} (${senateur.groupe_appartenance})`
          : senateur.groupe,
      );
    }
    if (senateur.circonscription) morceaux.push(senateur.circonscription);
    mandatPrincipal = `${
      elu.sexe === "F" ? "Sénatrice" : elu.sexe === "M" ? "Sénateur" : "Sénateur·rice"
    }${morceaux.length > 0 ? ` — ${morceaux.join(" · ")}` : ""}`;
  } else {
    const premier = mandats[0];
    if (premier) {
      const titre = premier.fonction ?? TYPES_MANDAT[premier.type ?? ""] ?? premier.type ?? null;
      const lieu = lieuMandat(premier);
      mandatPrincipal = [titre, lieu].filter(Boolean).join(" — ") || null;
    }
  }

  const liens: { href: string; texte: string }[] = [];
  if (depute?.url_fiche_an) liens.push({ href: depute.url_fiche_an, texte: "Fiche Assemblée nationale" });
  if (senateur?.url_fiche_senat) liens.push({ href: senateur.url_fiche_senat, texte: "Fiche Sénat" });
  const urlHatvp = elu.hatvp_url ?? depute?.url_hatvp ?? null;
  if (urlHatvp) liens.push({ href: urlHatvp, texte: "Fiche HATVP" });

  // Décompte des positions sur les scrutins AFFICHÉS (les N derniers).
  const decomptes = { pour: 0, contre: 0, abstention: 0, nonVotant: 0, sans: 0 };
  if (votes) {
    for (const v of votes) {
      if (v.position === "pour") decomptes.pour += 1;
      else if (v.position === "contre") decomptes.contre += 1;
      else if (v.position === "abstention") decomptes.abstention += 1;
      else if (v.position === "nonVotant") decomptes.nonVotant += 1;
      else decomptes.sans += 1;
    }
  }

  const colonnesVotes: Colonne<VoteLigne>[] = [
    { cle: "date_scrutin", entete: "Date", type: "date" },
    { cle: "numero", entete: "N°", type: "nombre" },
    {
      cle: "titre",
      entete: "Scrutin",
      // Pas d'attribut title : il doublerait le titre complet dans le HTML
      // ET le payload RSC (~13 Ko/fiche) — le texte intégral reste dans le
      // nœud texte, seul l'affichage est tronqué (ellipse CSS).
      rendu: (l) =>
        l.titre ? <span className="block max-w-[34rem] truncate">{l.titre}</span> : "—",
    },
    {
      cle: "position",
      entete: "Position",
      rendu: (l) => {
        if (!l.position) return <span className="text-ink-muted">—</span>;
        const libelle = POSITIONS[l.position] ?? l.position;
        return (
          <span>
            {libelle}
            {l.par_delegation ? " (par délégation)" : ""}
          </span>
        );
      },
    },
    {
      cle: "sort",
      entete: "Résultat",
      rendu: (l) => (l.sort ? l.sort.charAt(0).toUpperCase() + l.sort.slice(1) : "—"),
    },
  ];

  const colonnesDeclarations: Colonne<DeclarationHatvp>[] = [
    {
      cle: "type_document",
      entete: "Document",
      rendu: (l) => {
        if (!l.type_document) return "—";
        const libelle = TYPES_DOCUMENT[l.type_document];
        return libelle ? `${libelle} (${l.type_document})` : l.type_document.toUpperCase();
      },
    },
    { cle: "type_mandat", entete: "Mandat" },
    { cle: "date_depot", entete: "Déposée le", type: "date" },
    { cle: "date_publication", entete: "Publiée le", type: "date" },
    { cle: "statut_publication", entete: "Statut (source HATVP)" },
  ];

  return (
    <div className="flex flex-col gap-6">
      <nav aria-label="Fil d’Ariane">
        <Link
          href="/elus"
          className="text-xs text-ink-muted transition-colors hover:text-ink-secondary"
        >
          ← Élus &amp; institutions
        </Link>
      </nav>

      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold leading-tight text-ink">{nomComplet}</h1>
        {mandatPrincipal && <p className="text-sm text-ink-secondary">{mandatPrincipal}</p>}
        <p className="text-xs text-ink-muted">
          {elu.date_naissance
            ? `${neLe} ${formatDateFr(elu.date_naissance)}${age !== null ? ` (${formatNombre(age)} ans)` : ""}`
            : "Date de naissance non publiée"}
          {elu.profession ? ` · ${elu.profession}` : ""}
        </p>
        {liens.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-2">
            {liens.map((l) => (
              <LienExterne key={l.href} href={l.href} texte={l.texte} />
            ))}
          </div>
        )}
      </header>

      {depute && (
        <Card
          titre="Participation aux scrutins publics"
          sousTitre="Deux mesures distinctes, chacune étiquetée avec sa méthode : le calcul France Transparence et les scores publiés par Datan."
          droite={
            <div className="flex flex-wrap justify-end gap-2">
              <Badge source={sources["S5-SCRUTINS"]} />
              <Badge source={sources["S7-DATAN"]} mention="scores Datan crédités" />
            </div>
          }
        >
          <StatStrip
            stats={[
              {
                label: "Participation 12 mois — calcul France Transparence",
                valeur:
                  depute.taux_participation_12m !== null
                    ? formatPct(depute.taux_participation_12m, 2)
                    : "—",
              },
              {
                label: "Votes exprimés / scrutins du mandat (12 mois)",
                valeur:
                  depute.nb_votes_12m !== null && depute.nb_scrutins_12m !== null
                    ? `${formatNombre(depute.nb_votes_12m)} / ${formatNombre(depute.nb_scrutins_12m)}`
                    : "—",
              },
              {
                label: "Participation (score Datan, 0–1)",
                valeur:
                  depute.datan_score_participation !== null
                    ? formatNombre(depute.datan_score_participation, 2)
                    : "—",
              },
              {
                label: "Loyauté au groupe (score Datan, 0–1)",
                valeur:
                  depute.datan_score_loyaute !== null
                    ? formatNombre(depute.datan_score_loyaute, 2)
                    : "—",
              },
              {
                label: "Proximité majorité (score Datan, 0–1)",
                valeur:
                  depute.datan_score_majorite !== null
                    ? formatNombre(depute.datan_score_majorite, 2)
                    : "—",
              },
            ]}
          />
          <div className="mt-3 flex flex-col gap-1 text-[11px] leading-relaxed text-ink-muted">
            {depute.participation_source && (
              <p>
                Méthode du taux : {depute.participation_source}
                {depute.participation_maj
                  ? ` — mis à jour le ${formatDateFr(depute.participation_maj)}.`
                  : "."}
              </p>
            )}
            {depute.datan_source && (
              <p>
                Méthode des scores : {depute.datan_source}
                {depute.datan_date ? ` — données du ${formatDateFr(depute.datan_date)}.` : "."}
              </p>
            )}
          </div>

          {votes && votes.length > 0 && (
            <div className="mt-5">
              <h3 className="text-xs font-semibold uppercase tracking-[0.08em] text-ink-secondary">
                Positions sur les {formatNombre(votes.length)} derniers scrutins
              </h3>
              <p className="mt-1 mb-2 text-xs text-ink-muted">
                {nb_scrutins_base !== null && nb_scrutins_base > votes.length
                  ? `Affichage des ${formatNombre(votes.length)} derniers scrutins sur ${formatNombre(nb_scrutins_base)} présents en base. `
                  : ""}
                Sur ces scrutins&nbsp;: Pour {formatNombre(decomptes.pour)} · Contre{" "}
                {formatNombre(decomptes.contre)} · Abstention{" "}
                {formatNombre(decomptes.abstention)} · Non-votant{" "}
                {formatNombre(decomptes.nonVotant)} · Sans position enregistrée{" "}
                {formatNombre(decomptes.sans)}
              </p>
              <DataTable
                colonnes={colonnesVotes}
                lignes={votes}
                cleLigne={(l) => l.scrutin_uid}
                hauteurMax="24rem"
              />
              <p className="mt-2 text-[11px] leading-relaxed text-ink-muted">
                « — » : aucune position enregistrée au scrutin public (donnée AN telle quelle) ;
                « non-votant » est un statut officiel distinct (présidence de séance, etc.).
              </p>
            </div>
          )}
        </Card>
      )}

      {senateur && (
        <Card
          titre="Mandat au Sénat"
          sousTitre="Renouvellement du Sénat le 27/09/2026."
          droite={<Badge source={sources["S6-ODSEN"]} />}
        >
          <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs text-ink-muted">Groupe</dt>
              <dd className="mt-0.5 text-ink">
                {senateur.groupe ?? "—"}
                {senateur.groupe_appartenance ? ` (${senateur.groupe_appartenance})` : ""}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Circonscription</dt>
              <dd className="mt-0.5 text-ink">{senateur.circonscription ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Commission</dt>
              <dd className="mt-0.5 text-ink">{senateur.commission ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Mandat en cours depuis</dt>
              <dd className="mt-0.5 text-ink">
                {senateur.date_debut_mandat ? formatDateFr(senateur.date_debut_mandat) : "—"}
              </dd>
            </div>
          </dl>
          <p className="mt-3 text-[11px] leading-relaxed text-ink-muted">
            Les scrutins publics du Sénat ne sont pas encore ingérés : aucun taux de participation
            n’est affiché pour les sénateurs.
          </p>
        </Card>
      )}

      <Card
        titre="Mandats"
        sousTitre="Tels que publiés par l’AN, le Sénat et le répertoire national des élus — un même mandat peut apparaître dans deux sources."
        droite={<Badge source={sources["S17"]} />}
      >
        {mandats.length === 0 ? (
          <p className="text-sm text-ink-muted">Aucun mandat détaillé en base pour cette fiche.</p>
        ) : (
          <ul className="flex flex-col">
            {mandats.map((m, i) => {
              const titre = m.fonction ?? TYPES_MANDAT[m.type ?? ""] ?? m.type ?? "Mandat";
              const lieu = lieuMandat(m);
              const debut = m.date_debut ?? m.date_debut_mandat ?? null;
              return (
                <li
                  key={i}
                  className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 py-2.5"
                  style={{ borderBottom: "1px solid var(--viz-grid)" }}
                >
                  <span className="text-sm font-semibold text-ink">{titre}</span>
                  {lieu && <span className="text-[13px] text-ink-secondary">{lieu}</span>}
                  {m.circonscription && (
                    <span className="text-[13px] text-ink-secondary">
                      {circonscriptionLisible(m.circonscription)}
                    </span>
                  )}
                  {m.groupe && <span className="text-[13px] text-ink-secondary">groupe {m.groupe}</span>}
                  {m.legislature !== undefined && (
                    <span className="text-xs text-ink-muted">{m.legislature}ᵉ législature</span>
                  )}
                  {debut && (
                    <span className="text-xs text-ink-muted">
                      depuis le {formatDateFr(debut)}
                      {m.date_fin ? ` — fin le ${formatDateFr(m.date_fin)}` : ""}
                    </span>
                  )}
                  <span className="ml-auto rounded-full border border-card-border px-1.5 py-0.5 text-[10px] uppercase tracking-[0.08em] text-ink-muted">
                    {libelleSource(m.source)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <Card
        titre="Déclarations HATVP"
        sousTitre="Déclarations publiées par la HATVP, appariées à cette fiche par URL de fiche nominative — statut affiché tel que publié."
        droite={<Badge source={sources["S14"]} />}
      >
        {declarations.length > 0 ? (
          <DataTable
            colonnes={colonnesDeclarations}
            lignes={declarations}
            cleLigne={(l) => String(l.id)}
          />
        ) : (
          <p className="text-sm text-ink-muted">
            Aucune déclaration HATVP appariée à cette fiche dans la base. L’appariement se fait
            uniquement par URL de fiche nominative HATVP (jamais par homonymie) : l’absence
            d’appariement ne signifie pas l’absence de déclaration.
          </p>
        )}
      </Card>
    </div>
  );
}
