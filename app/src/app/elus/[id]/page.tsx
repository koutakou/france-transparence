import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/db";
import { Card } from "@/components/ui/Card";
import { JsonLd } from "@/components/JsonLd";
import { InteretsDeclares } from "@/components/client/InteretsDeclares";
import { DataTable, type Colonne } from "@/components/ui/DataTable";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { LienOfficiel } from "@/components/ui/LienOfficiel";
import { StatStrip } from "@/components/ui/StatStrip";
import { formatDateFr, formatNombre, formatPct } from "@/lib/format";
import {
  getFicheElu,
  getIdsFichesStatiques,
  getSourcesElus,
  PERIMETRE_PARTICIPATION_FT,
  PERIMETRE_PARTICIPATION_FT_SENAT,
  PERIMETRE_SCORE_DATAN,
  PERIMETRE_VOTES_12M,
  type DeclarationHatvp,
  type MandatJson,
  type VoteLigne,
} from "@/lib/queries/elus";
import {
  getInteretsElu,
  getSourceDeclarations,
  tronquerInterets,
} from "@/lib/queries/declarations";
import type { MetaSource } from "@/lib/db";
import {
  jsonLdFicheElu,
  metadonneesFicheProfil,
  metadonneesPage,
  type RoleElu,
} from "@/lib/seo";

/**
 * Fiches PRÉ-GÉNÉRÉES au build, limitées aux mandats nationaux et exécutifs
 * (docs/deploiement/DECISION.md) : députés, sénateurs en exercice (table
 * `senateurs`), présidents de conseil départemental et régional — les seules
 * riches : votes nominaux, groupes, HATVP. Les 35 000 autres élus du
 * répertoire (maires, présidents d'EPCI…) n'ont PAS de page dédiée : 404
 * assumé (`dynamicParams = false`), expliqué sur /elus.
 */
export const dynamicParams = false;

export function generateStaticParams(): { id: string }[] {
  // Sénateurs : table `senateurs` (ODSEN ACTIF), pas le JSON type=senateur.
  return getIdsFichesStatiques().map((id) => ({ id }));
}

/** Title « Prénom Nom — Élus » + description factuelle (requête légère). */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  // Chemin de la FICHE (jamais celui de l'accueil) : relatif, que Next
  // compose avec metadataBase — basePath compris. Slash final imposé par
  // `trailingSlash: true`. Ce seul chemin alimente la canonique ET l'og:url
  // de chaque fiche, via `metadonneesPage()`. Pas de volumétrie en dur ici :
  // le nombre de fiches rote à chaque ingestion (1 049 servies le 25/08/2026,
  // contre 1 053 écrites dans ce commentaire depuis sa rédaction).
  const chemin = `/elus/${encodeURIComponent(decodeIdSur(id))}/`;
  const db = getDb();
  // Base absente ou élu inconnu : la fiche garde son identité d'URL, mais on
  // n'invente ni titre ni description — Next retombe sur ceux du site.
  if (!db) return metadonneesPage({ chemin });
  const elu = db
    .prepare("SELECT nom, prenom, uid_an, matricule_senat FROM elus WHERE id = ?")
    .get(decodeIdSur(id)) as
    | { nom: string; prenom: string | null; uid_an: string | null; matricule_senat: string | null }
    | undefined;
  if (!elu) return metadonneesPage({ chemin });
  const nomComplet = `${elu.prenom ?? ""} ${elu.nom}`.trim();
  const description =
    elu.uid_an || elu.matricule_senat
      ? `Mandats, activité parlementaire et déclarations HATVP de ${nomComplet}, à partir des données publiques officielles (AN, Sénat, HATVP, RNE).`
      : `Mandats et déclarations HATVP de ${nomComplet}, à partir des données publiques officielles (RNE, HATVP).`;
  // `metadonneesFicheProfil` et non `metadonneesPage` : cette page décrit une
  // PERSONNE, son `og:type` vaut donc « profile » — ce que son JSON-LD dit
  // déjà (`ProfilePage` + `Person`), et que la carte de partage taisait.
  // `prenom` et `nom` sont pris TELS QU'EN BASE, jamais reconstitués en
  // découpant `nomComplet` : un prénom composé ou une particule y
  // produiraient une civilité fausse sur une personne réelle.
  return metadonneesFicheProfil({
    chemin,
    titre: `${nomComplet} — Élus`,
    description,
    prenom: elu.prenom,
    nom: elu.nom,
  });
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

/**
 * Institution d'exercice par type de mandat — pour le seul balisage
 * schema.org (`OrganizationRole.memberOf`). `lieu: true` = le nom de
 * l'organisme n'est pas identifiant sans sa collectivité (« Conseil
 * départemental — Nord ») ; l'Assemblée nationale et le Sénat, eux, sont
 * uniques : y accoler un département produirait un nom d'organisation faux.
 */
const ORGANISMES_MANDAT: Record<string, { nom: string; lieu: boolean }> = {
  depute: { nom: "Assemblée nationale", lieu: false },
  senateur: { nom: "Sénat", lieu: false },
  maire: { nom: "Commune", lieu: true },
  president_epci: {
    nom: "Établissement public de coopération intercommunale",
    lieu: true,
  },
  president_conseil_departemental: { nom: "Conseil départemental", lieu: true },
  president_conseil_regional: { nom: "Conseil régional", lieu: true },
};

/**
 * Intitulé de mandat pour le balisage, accordé comme il l'est à l'écran.
 * Le point médian de TYPES_MANDAT est un libellé d'interface : dans un
 * `roleName`/`jobTitle` lu par une machine, il dégrade la valeur — on
 * préfère la forme accordée quand le sexe est publié par la source.
 */
function titreMandatBalisage(type: string, sexe: string | null): string {
  const accords: Record<string, [string, string]> = {
    depute: ["Députée", "Député"],
    senateur: ["Sénatrice", "Sénateur"],
    maire: ["Maire", "Maire"],
    president_epci: [
      "Présidente d\u2019intercommunalité (EPCI)",
      "Président d\u2019intercommunalité (EPCI)",
    ],
    president_conseil_departemental: [
      "Présidente de conseil départemental",
      "Président de conseil départemental",
    ],
    president_conseil_regional: [
      "Présidente de conseil régional",
      "Président de conseil régional",
    ],
  };
  const accord = accords[type];
  if (!accord) return TYPES_MANDAT[type] ?? type;
  if (sexe === "F") return accord[0];
  if (sexe === "M") return accord[1];
  return TYPES_MANDAT[type] ?? accord[1];
}

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

function LienExterne({ href, texte, nom }: { href: string; texte: string; nom: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 rounded-full border border-card-border bg-card px-2.5 py-1 text-[11px] leading-none text-ink-secondary transition-colors hover:border-raised-border hover:text-ink"
    >
      {texte}
      <span className="sr-only">{` de ${nom} (nouvelle fenêtre)`}</span>
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
  // Contenu des déclarations d'INTÉRÊTS (S15). `null` = base absente ou
  // pipeline P15 jamais passé ; `apparie: false` = pipeline passé, mais
  // aucune déclaration rattachée à cette fiche. Les deux cas se disent
  // différemment à l'écran, et aucun des deux ne se dit « rien à déclarer ».
  const interets = getInteretsElu(decodeIdSur(id));
  const sourceDeclarations = getSourceDeclarations();
  const {
    elu,
    mandats,
    depute,
    senateur,
    votes,
    nb_scrutins_base,
    votes_senat,
    nb_scrutins_senat_base,
    declarations,
  } = fiche;

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
  function decomptesPositions(lignes: VoteLigne[] | null) {
    const d = { pour: 0, contre: 0, abstention: 0, nonVotant: 0, sans: 0 };
    if (!lignes) return d;
    for (const v of lignes) {
      if (v.position === "pour") d.pour += 1;
      else if (v.position === "contre") d.contre += 1;
      else if (v.position === "abstention") d.abstention += 1;
      else if (v.position === "nonVotant") d.nonVotant += 1;
      else d.sans += 1;
    }
    return d;
  }
  const decomptes = decomptesPositions(votes);
  const decomptesSenat = decomptesPositions(votes_senat);

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
        const texte = libelle ? `${libelle} (${l.type_document})` : l.type_document.toUpperCase();
        if (!l.url_fiche) return texte;
        return (
          <LienOfficiel href={l.url_fiche} source="HATVP">
            {texte}
          </LienOfficiel>
        );
      },
    },
    { cle: "type_mandat", entete: "Mandat" },
    { cle: "date_depot", entete: "Déposée le", type: "date" },
    { cle: "date_publication", entete: "Publiée le", type: "date" },
    { cle: "statut_publication", entete: "Statut (source HATVP)" },
  ];

  /* Données structurées — STRICTEMENT ce qui est déjà affiché sur la fiche,
     lui-même issu des open data officiels (AN, Sénat, RNE, HATVP). */
  const roles: RoleElu[] = [];
  const vus = new Set<string>();
  for (const m of mandats) {
    const type = m.type ?? "";
    const organisme = ORGANISMES_MANDAT[type];
    const lieu = lieuMandat(m);
    const organisation =
      organisme && !organisme.lieu
        ? organisme.nom
        : [organisme?.nom ?? "Institution publique", lieu].filter(Boolean).join(" — ");
    const roleName = m.fonction ?? titreMandatBalisage(type, elu.sexe);
    // Le même mandat est souvent décrit par DEUX sources (AN/Sénat et RNE) :
    // une seule entrée par (rôle, organisation), la plus ancienne date de
    // début faisant foi.
    const cle = `${roleName}|${organisation}`;
    const debut = m.date_debut ?? m.date_debut_mandat ?? m.date_debut_fonction ?? null;
    if (vus.has(cle)) {
      const existant = roles.find((r) => `${r.roleName}|${r.organisation}` === cle);
      if (existant && debut && (!existant.debut || debut < existant.debut)) existant.debut = debut;
      continue;
    }
    vus.add(cle);
    roles.push({ roleName, organisation, debut });
  }
  if (roles.length === 0 && depute) {
    roles.push({
      roleName: titreMandatBalisage("depute", elu.sexe),
      organisation: ORGANISMES_MANDAT.depute.nom,
      debut: depute.date_debut_mandat,
    });
  }
  if (roles.length === 0 && senateur) {
    roles.push({
      roleName: titreMandatBalisage("senateur", elu.sexe),
      organisation: ORGANISMES_MANDAT.senateur.nom,
      debut: senateur.date_debut_mandat,
    });
  }
  const balisage = jsonLdFicheElu({
    chemin: `/elus/${encodeURIComponent(elu.id)}/`,
    nomComplet,
    prenom: elu.prenom,
    nom: elu.nom,
    naissance: elu.date_naissance,
    fonction: depute
      ? titreMandatBalisage("depute", elu.sexe)
      : senateur
        ? titreMandatBalisage("senateur", elu.sexe)
        : (roles[0]?.roleName ?? null),
    roles,
    groupes: [depute?.groupe_nom, senateur?.groupe].filter(
      (g): g is string => typeof g === "string" && g.length > 0,
    ),
    sameAs: liens.map((l) => l.href),
    description: [nomComplet, mandatPrincipal].filter(Boolean).join(" — "),
  });

  return (
    <div className="flex flex-col gap-6">
      <JsonLd donnees={balisage} />
      <nav
        aria-label="Fil d’Ariane"
        className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted"
      >
        <Link href="/elus" className="transition-colors hover:text-ink-secondary">
          ← Élus &amp; institutions
        </Link>
        <Link
          href={depute ? "/elus#deputes" : senateur ? "/elus#senateurs" : "/elus"}
          className="transition-colors hover:text-ink-secondary"
        >
          Chercher un autre élu
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
              <LienExterne key={l.href} href={l.href} texte={l.texte} nom={nomComplet} />
            ))}
          </div>
        )}
        <p className="mt-2 max-w-3xl text-xs text-ink-muted">
          Une fiche nominative n&apos;existe que pour les mandats nationaux et
          les exécutifs. Le site ne publie aucune nuance politique. Comment
          lire ces pages&nbsp;:{" "}
          <Link
            href="/comprendre/#elus"
            className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
          >
            comprendre ces données
          </Link>
          .
        </p>
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
                perimetre: PERIMETRE_PARTICIPATION_FT,
              },
              {
                label: "Votes exprimés / scrutins du mandat (12 mois)",
                valeur:
                  depute.nb_votes_12m !== null && depute.nb_scrutins_12m !== null
                    ? `${formatNombre(depute.nb_votes_12m)} / ${formatNombre(depute.nb_scrutins_12m)}`
                    : "—",
                perimetre: PERIMETRE_VOTES_12M,
              },
              {
                label: "Participation (score Datan, 0–1)",
                valeur:
                  depute.datan_score_participation !== null
                    ? formatNombre(depute.datan_score_participation, 2)
                    : "—",
                perimetre: PERIMETRE_SCORE_DATAN,
              },
              {
                label: "Loyauté au groupe (score Datan, 0–1)",
                valeur:
                  depute.datan_score_loyaute !== null
                    ? formatNombre(depute.datan_score_loyaute, 2)
                    : "—",
                perimetre: PERIMETRE_SCORE_DATAN,
              },
              {
                label: "Proximité majorité (score Datan, 0–1)",
                valeur:
                  depute.datan_score_majorite !== null
                    ? formatNombre(depute.datan_score_majorite, 2)
                    : "—",
                perimetre: PERIMETRE_SCORE_DATAN,
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
        </Card>
      )}

      {senateur && (
        <Card
          titre="Participation aux scrutins publics du Sénat"
          sousTitre="Taux calculé ici sur les votes exprimés — ce n’est pas une présence en séance, pas un score Datan."
          droite={<Badge source={sources["S6-DOSLEG"]} />}
        >
          <StatStrip
            stats={[
              {
                label: "Participation 12 mois — calcul France Transparence",
                valeur:
                  senateur.taux_participation_12m !== null
                    ? formatPct(senateur.taux_participation_12m, 2)
                    : "—",
                perimetre: PERIMETRE_PARTICIPATION_FT_SENAT,
              },
              {
                label: "Votes exprimés / scrutins du mandat (12 mois)",
                valeur:
                  senateur.nb_votes_12m !== null && senateur.nb_scrutins_12m !== null
                    ? `${formatNombre(senateur.nb_votes_12m)} / ${formatNombre(senateur.nb_scrutins_12m)}`
                    : "—",
                perimetre: PERIMETRE_VOTES_12M,
              },
            ]}
          />
          <div className="mt-3 flex flex-col gap-1 text-[11px] leading-relaxed text-ink-muted">
            {senateur.participation_source && (
              <p>
                Méthode du taux : {senateur.participation_source}
                {senateur.participation_maj
                  ? ` — mis à jour le ${formatDateFr(senateur.participation_maj)}.`
                  : "."}
              </p>
            )}
          </div>

          {votes_senat && votes_senat.length > 0 && (
            <div className="mt-5">
              <h3 className="text-xs font-semibold uppercase tracking-[0.08em] text-ink-secondary">
                Positions sur les {formatNombre(votes_senat.length)} derniers scrutins
              </h3>
              <p className="mt-1 mb-2 text-xs text-ink-muted">
                {nb_scrutins_senat_base !== null && nb_scrutins_senat_base > votes_senat.length
                  ? `Affichage des ${formatNombre(votes_senat.length)} derniers scrutins sur ${formatNombre(nb_scrutins_senat_base)} présents en base. `
                  : ""}
                Sur ces scrutins&nbsp;: Pour {formatNombre(decomptesSenat.pour)} · Contre{" "}
                {formatNombre(decomptesSenat.contre)} · Abstention{" "}
                {formatNombre(decomptesSenat.abstention)} · Non-votant{" "}
                {formatNombre(decomptesSenat.nonVotant)} · Sans position enregistrée{" "}
                {formatNombre(decomptesSenat.sans)}
              </p>
              <DataTable
                colonnes={colonnesVotes}
                lignes={votes_senat}
                cleLigne={(l) => l.scrutin_uid}
                hauteurMax="24rem"
              />
              <p className="mt-2 text-[11px] leading-relaxed text-ink-muted">
                « — » : aucune position enregistrée au scrutin public (donnée Sénat telle quelle) ;
                « non-votant » est un statut officiel distinct (présidence de séance, etc.). Une
                délégation de vote n’est pas une présence physique.
              </p>
            </div>
          )}
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
        sousTitre="Déclarations publiées par la HATVP, appariées par URL de fiche nominative — statut affiché tel que publié. Le contenu des déclarations de patrimoine n’est pas affiché ; il se consulte en préfecture."
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
            Aucune déclaration HATVP appariée à cette fiche dans la base.{" "}
            <strong className="text-ink-secondary">Dans ce bloc</strong>, l’appariement se fait
            uniquement par URL de fiche nominative HATVP, jamais par homonymie ; le bloc
            « Intérêts déclarés » ci-dessous procède autrement, et l’absence d’appariement ici ne
            signifie pas l’absence de déclaration.
          </p>
        )}
      </Card>

      <Card
        titre="Intérêts déclarés"
        sousTitre="Contenu des déclarations d’intérêts publiées par la HATVP, reproduit mot pour mot et daté."
        droite={<Badge source={sourceDeclarations ?? undefined} />}
      >
        {interets === null ? (
          <p className="text-sm text-ink-muted">
            Le contenu des déclarations n’est pas ingéré dans cette base.
          </p>
        ) : interets.apparie ? (
          <>
            <p className="mb-4 text-[11px] leading-relaxed text-ink-muted">
              Ce qui suit est une <strong className="text-ink-secondary">déclaration</strong> :
              son contenu a été renseigné par la personne elle-même et publié tel quel par la
              HATVP. France Transparence ne l’a pas vérifié et n’en garantit pas l’exactitude ;
              rien n’y est recalculé, additionné ni classé — les libellés de la source ne sont
              pas normalisés et ne le supporteraient pas. Chaque montant est celui d’une année
              précise, tel qu’il a été saisi.
              {urlHatvp ? (
                <>
                  {" "}
                  Les documents d’origine sont consultables sur la{" "}
                  <a
                    href={urlHatvp}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
                  >
                    fiche HATVP
                  </a>
                  .
                </>
              ) : null}
            </p>
            {/* Payload réduit à ce que l'écran affiche (8 lignes par
                rubrique, première déclaration seule) : la queue vit dans le
                fragment /data/elus/interets/<id>.json, qui n'existe que pour
                les élus appariés — d'où fragmentDisponible, qui autorise le
                chargement au clic. */}
            <InteretsDeclares
              declarations={tronquerInterets(interets).declarations}
              eluId={elu.id}
              fragmentDisponible={interets.apparie}
            />
          </>
        ) : (
          <p className="text-sm leading-relaxed text-ink-muted">
            Aucune déclaration d’intérêts n’a pu être rattachée à cette fiche dans notre base.
            <strong className="text-ink-secondary">
              {" "}
              Cela ne veut pas dire que cette personne n’a rien déclaré.
            </strong>{" "}
            <strong className="text-ink-secondary">Dans ce bloc</strong>, l’appariement se fait sur
            le nom, le prénom et la date de naissance — pas par URL comme au bloc précédent : une déclaration
            déposée mais non publiée, une publication faite en préfecture, ou une identité
            orthographiée autrement dans le fichier amont suffisent à l’empêcher. Le
            bloc « Déclarations HATVP » ci-dessus indique, le cas échéant, le statut publié par
            la HATVP{urlHatvp ? ", et la fiche HATVP donne l’état officiel" : ""}.
          </p>
        )}
      </Card>
    </div>
  );
}
