import type { Metadata } from "next";
import Link from "next/link";
import { getDb } from "@/lib/db";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { DataTable, type Colonne } from "@/components/ui/DataTable";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { StatStrip } from "@/components/ui/StatStrip";
import { formatNombre, formatPct } from "@/lib/format";
import {
  getDepartementsDeputes,
  getDepartementsSenat,
  getDeputes,
  getDerniersScrutins,
  getGroupesAn,
  getGroupesSenat,
  getSenateurs,
  getSourcesElus,
  getStatsElus,
  type DeputeLigne,
  type ScrutinLigne,
  type SenateurLigne,
} from "@/lib/queries/elus";
import type { MetaSource } from "@/lib/db";

// La base locale évolue à chaque ingestion : jamais figer cette page au build.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Élus & institutions — France Transparence",
  description:
    "Députés, sénateurs et élus locaux : composition réelle des assemblées, participation aux scrutins, scrutins récents, croisements HATVP.",
};

/** searchParams (Next 16 : Promise) — filtres server-side des deux tables. */
type ParamsRecherche = Promise<{ [cle: string]: string | string[] | undefined }>;

function premier(v: string | string[] | undefined): string | undefined {
  const brut = Array.isArray(v) ? v[0] : v;
  const propre = brut?.trim();
  return propre ? propre : undefined;
}

function hrefElus(params: Record<string, string | undefined>): string {
  const usp = new URLSearchParams();
  for (const [cle, valeur] of Object.entries(params)) {
    if (valeur) usp.set(cle, valeur);
  }
  const qs = usp.toString();
  return qs ? `/elus?${qs}` : "/elus";
}

/** Lien vers une fiche élu (id = `elus.id`). */
function LienFiche({ id, texte }: { id: string; texte: string }) {
  return (
    <Link
      href={`/elus/${encodeURIComponent(id)}`}
      className="text-ink underline decoration-dotted underline-offset-2 transition-colors hover:text-accent"
    >
      {texte}
    </Link>
  );
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

const STYLE_SELECT =
  "rounded-lg border border-card-border bg-page px-3 py-1.5 text-[13px] text-ink focus:border-raised-border";
const STYLE_BOUTON =
  "rounded-lg border border-card-border bg-raised px-3 py-1.5 text-[13px] text-ink transition-colors hover:bg-hover";

export default async function PageElus({ searchParams }: { searchParams: ParamsRecherche }) {
  const sp = await searchParams;

  if (!getDb()) {
    return (
      <section className="flex flex-col gap-6">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Élus &amp; institutions
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          <p>
            La base locale n’est pas encore construite — lancer{" "}
            <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code> pour ingérer les
            sources (AN, Sénat, RNE, HATVP, Datan).
          </p>
        </div>
      </section>
    );
  }

  const sources = getSourcesElus() ?? {};
  const stats = getStatsElus();
  const groupesAn = getGroupesAn() ?? [];
  const groupesSenat = getGroupesSenat() ?? [];
  const departementsDeputes = getDepartementsDeputes() ?? [];
  const departementsSenat = getDepartementsSenat() ?? [];

  // Filtres validés contre les valeurs réelles (sinon ignorés).
  const gdBrut = premier(sp.gd);
  const ddBrut = premier(sp.dd);
  const gsBrut = premier(sp.gs);
  const dsBrut = premier(sp.ds);
  const gd = groupesAn.some((g) => g.sigle === gdBrut) ? gdBrut : undefined;
  const dd = departementsDeputes.includes(ddBrut ?? "") ? ddBrut : undefined;
  const gs = groupesSenat.some((g) => g.groupe === gsBrut) ? gsBrut : undefined;
  const ds = departementsSenat.includes(dsBrut ?? "") ? dsBrut : undefined;

  const deputes = getDeputes({ groupe: gd, departement: dd }) ?? [];
  const senateurs = getSenateurs({ groupe: gs, departement: ds }) ?? [];
  const scrutins = getDerniersScrutins(10) ?? [];
  const legislature = groupesAn[0]?.legislature;

  const colonnesDeputes: Colonne<DeputeLigne>[] = [
    {
      cle: "nom",
      entete: "Député·e",
      rendu: (l) => <LienFiche id={l.elu_id} texte={`${l.prenom ?? ""} ${l.nom}`.trim()} />,
    },
    {
      cle: "groupe_sigle",
      entete: "Groupe",
      rendu: (l) =>
        l.groupe_sigle ? <span title={l.groupe_nom ?? undefined}>{l.groupe_sigle}</span> : "—",
    },
    { cle: "departement", entete: "Département" },
    {
      cle: "taux_participation_12m",
      entete: "Participation 12 mois ¹",
      type: "pourcent",
      decimales: 1,
    },
    {
      cle: "datan_score_participation",
      entete: "Score Datan (0–1) ²",
      type: "nombre",
      decimales: 2,
    },
  ];

  const colonnesSenateurs: Colonne<SenateurLigne>[] = [
    {
      cle: "nom",
      entete: "Sénateur·rice",
      rendu: (l) => <LienFiche id={l.elu_id} texte={`${l.prenom ?? ""} ${l.nom}`.trim()} />,
    },
    {
      cle: "groupe",
      entete: "Groupe",
      rendu: (l) =>
        l.groupe ? <span title={l.groupe_appartenance || undefined}>{l.groupe}</span> : "—",
    },
    { cle: "circonscription", entete: "Département" },
    {
      cle: "commission",
      entete: "Commission",
      rendu: (l) =>
        l.commission ? (
          <span className="block max-w-[18rem] truncate" title={l.commission}>
            {l.commission}
          </span>
        ) : (
          "—"
        ),
    },
  ];

  const colonnesScrutins: Colonne<ScrutinLigne>[] = [
    { cle: "date_scrutin", entete: "Date", type: "date" },
    { cle: "numero", entete: "N°", type: "nombre" },
    {
      cle: "titre",
      entete: "Scrutin",
      rendu: (l) =>
        l.titre ? (
          <span className="block max-w-[38rem] truncate" title={l.titre}>
            {l.titre}
          </span>
        ) : (
          "—"
        ),
    },
    { cle: "pour", entete: "Pour", type: "nombre" },
    { cle: "contre", entete: "Contre", type: "nombre" },
    {
      cle: "sort",
      entete: "Résultat",
      rendu: (l) => {
        const libelle = l.sort ?? (l.adopte === 1 ? "adopté" : "rejeté");
        return libelle.charAt(0).toUpperCase() + libelle.slice(1);
      },
    },
  ];

  const partFemmesAn =
    stats && stats.deputes.nb > 0 ? (stats.deputes.nb_femmes / stats.deputes.nb) * 100 : null;
  const partFemmesSenat =
    stats && stats.senateurs.nb > 0
      ? (stats.senateurs.nb_femmes / stats.senateurs.nb) * 100
      : null;

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-3">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Élus &amp; institutions
        </h1>
        <p className="max-w-3xl text-sm text-ink-secondary">
          Composition réelle des assemblées, participation des députés aux scrutins publics et
          répertoire national des élus — données officielles AN, Sénat, ministère de l’Intérieur
          (RNE), croisées avec les déclarations HATVP.
        </p>
      </section>

      {stats && (
        <>
          <StatStrip
            stats={[
              { label: "Députés", valeur: formatNombre(stats.deputes.nb) },
              { label: "Sénateurs", valeur: formatNombre(stats.senateurs.nb) },
              { label: "Maires (RNE)", valeur: formatNombre(stats.nb_maires) },
              { label: "Élus recensés (RNE)", valeur: formatNombre(stats.nb_elus) },
            ]}
          />
          <div className="-mt-3 flex flex-wrap gap-2">
            <Badge source={sources["S17"]} />
          </div>
        </>
      )}

      <Card
        titre="Assemblée nationale — groupes politiques"
        sousTitre={
          legislature
            ? `${formatNombre(groupesAn.reduce((s, g) => s + g.effectif, 0))} sièges · ${legislature}ᵉ législature · effectifs par groupe (préséance AN)`
            : "Effectifs par groupe (préséance AN)"
        }
        droite={<Badge source={sources["S5-AMO10"]} />}
      >
        <BarList
          items={groupesAn.map((g) => ({
            libelle: `${g.nom} (${g.sigle})`,
            valeur: g.effectif,
            couleur: g.sigle === "NI" ? "var(--viz-autre)" : undefined,
          }))}
        />
        {stats && (
          <p className="mt-3 text-xs text-ink-secondary">
            Parité : {formatNombre(stats.deputes.nb_femmes)} femmes sur{" "}
            {formatNombre(stats.deputes.nb)}
            {partFemmesAn !== null ? ` (${formatPct(partFemmesAn)})` : ""} · âge moyen{" "}
            {stats.deputes.age_moyen !== null ? `${formatNombre(stats.deputes.age_moyen, 1)} ans` : "—"}{" "}
            — calculés depuis l’état civil du répertoire des élus.
          </p>
        )}
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-ink-muted transition-colors hover:text-ink-secondary">
            Vue tableau
          </summary>
          <DataTable
            className="mt-2"
            colonnes={[
              { cle: "nom", entete: "Groupe" },
              { cle: "sigle", entete: "Sigle" },
              { cle: "effectif", entete: "Sièges", type: "nombre" },
            ]}
            lignes={groupesAn}
            cleLigne={(g) => g.organe_ref}
          />
        </details>
        <p className="mt-2 text-[11px] text-ink-muted">
          Couleurs officielles des groupes (données AN) non reproduites : teinte unique du thème,
          validée pour le fond sombre — l’identité est portée par les libellés.
        </p>
      </Card>

      <div id="deputes" className="scroll-mt-20">
        <Card
          titre="Députés — participation aux scrutins"
          sousTitre="Taux calculé par France Transparence et score Datan, côte à côte : deux méthodes distinctes, étiquetées."
          droite={
            <div className="flex flex-wrap justify-end gap-2">
              <Badge source={sources["S5-AMO10"]} />
              <Badge source={sources["S7-DATAN"]} mention="scores Datan crédités" />
            </div>
          }
        >
          <form method="get" action="/elus" className="mb-4 flex flex-wrap items-end gap-3">
            {gs && <input type="hidden" name="gs" value={gs} />}
            {ds && <input type="hidden" name="ds" value={ds} />}
            <label className="flex flex-col gap-1 text-[11px] uppercase tracking-[0.04em] text-ink-muted">
              Groupe
              <select name="gd" defaultValue={gd ?? ""} className={STYLE_SELECT}>
                <option value="">Tous les groupes</option>
                {groupesAn.map((g) => (
                  <option key={g.organe_ref} value={g.sigle}>
                    {g.sigle} — {g.nom}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-[11px] uppercase tracking-[0.04em] text-ink-muted">
              Département
              <select name="dd" defaultValue={dd ?? ""} className={STYLE_SELECT}>
                <option value="">Tous les départements</option>
                {departementsDeputes.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" className={STYLE_BOUTON}>
              Filtrer
            </button>
            {(gd || dd) && (
              <Link
                href={hrefElus({ gs, ds })}
                className="text-xs text-ink-muted underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
              >
                Réinitialiser
              </Link>
            )}
          </form>
          <p className="mb-2 text-xs text-ink-muted">
            {formatNombre(deputes.length)} député·e{deputes.length > 1 ? "s" : ""} affiché·e
            {deputes.length > 1 ? "s" : ""}
            {gd ? ` · groupe ${gd}` : ""}
            {dd ? ` · ${dd}` : ""}
          </p>
          <DataTable
            colonnes={colonnesDeputes}
            lignes={deputes}
            cleLigne={(l) => l.uid_an}
            hauteurMax="30rem"
            vide="Aucun député pour ces filtres"
          />
          <div className="mt-3 flex flex-col gap-1 text-[11px] leading-relaxed text-ink-muted">
            <p>
              ¹ Calcul France Transparence : votes exprimés / scrutins publics de l’AN des 365
              derniers jours depuis l’entrée en mandat (source AN, scrutins nominaux). Le 0,63 %
              de la présidente de l’Assemblée est normal : elle préside et ne prend pas part aux
              votes.
            </p>
            <p>
              ² Score de participation publié par{" "}
              <a
                href="https://datan.fr"
                target="_blank"
                rel="noopener noreferrer"
                className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
              >
                Datan (datan.fr)
              </a>
              , échelle 0 à 1, méthodologie Datan — calculé par Datan, non recalculé par France
              Transparence.
            </p>
          </div>
        </Card>
      </div>

      <div id="senateurs" className="scroll-mt-20">
        <Card
          titre="Sénat"
          sousTitre="348 sièges · renouvellement du Sénat le 27/09/2026"
          droite={<Badge source={sources["S6-ODSEN"]} />}
        >
          <BarList
            items={groupesSenat.map((g) => ({
              libelle: g.groupe,
              valeur: g.effectif,
              couleur: g.groupe === "NI" ? "var(--viz-autre)" : undefined,
            }))}
          />
          {stats && (
            <p className="mt-3 text-xs text-ink-secondary">
              Parité : {formatNombre(stats.senateurs.nb_femmes)} femmes sur{" "}
              {formatNombre(stats.senateurs.nb)}
              {partFemmesSenat !== null ? ` (${formatPct(partFemmesSenat)})` : ""} · âge moyen{" "}
              {stats.senateurs.age_moyen !== null
                ? `${formatNombre(stats.senateurs.age_moyen, 1)} ans`
                : "—"}{" "}
              — calculés depuis les données open data du Sénat.
            </p>
          )}
          <details className="mt-2 mb-4">
            <summary className="cursor-pointer text-xs text-ink-muted transition-colors hover:text-ink-secondary">
              Vue tableau
            </summary>
            <DataTable
              className="mt-2"
              colonnes={[
                { cle: "groupe", entete: "Groupe" },
                { cle: "effectif", entete: "Sièges", type: "nombre" },
              ]}
              lignes={groupesSenat}
              cleLigne={(g) => g.groupe}
            />
          </details>
          <form method="get" action="/elus" className="mb-4 flex flex-wrap items-end gap-3">
            {gd && <input type="hidden" name="gd" value={gd} />}
            {dd && <input type="hidden" name="dd" value={dd} />}
            <label className="flex flex-col gap-1 text-[11px] uppercase tracking-[0.04em] text-ink-muted">
              Groupe
              <select name="gs" defaultValue={gs ?? ""} className={STYLE_SELECT}>
                <option value="">Tous les groupes</option>
                {groupesSenat.map((g) => (
                  <option key={g.groupe} value={g.groupe}>
                    {g.groupe}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-[11px] uppercase tracking-[0.04em] text-ink-muted">
              Département
              <select name="ds" defaultValue={ds ?? ""} className={STYLE_SELECT}>
                <option value="">Tous les départements</option>
                {departementsSenat.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" className={STYLE_BOUTON}>
              Filtrer
            </button>
            {(gs || ds) && (
              <Link
                href={hrefElus({ gd, dd })}
                className="text-xs text-ink-muted underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
              >
                Réinitialiser
              </Link>
            )}
          </form>
          <p className="mb-2 text-xs text-ink-muted">
            {formatNombre(senateurs.length)} sénateur·rice{senateurs.length > 1 ? "s" : ""} affiché·e
            {senateurs.length > 1 ? "s" : ""}
            {gs ? ` · groupe ${gs}` : ""}
            {ds ? ` · ${ds}` : ""}
          </p>
          <DataTable
            colonnes={colonnesSenateurs}
            lignes={senateurs}
            cleLigne={(l) => l.matricule}
            hauteurMax="30rem"
            vide="Aucun sénateur pour ces filtres"
          />
          <p className="mt-3 text-[11px] leading-relaxed text-ink-muted">
            Les scrutins publics du Sénat ne sont pas encore ingérés : aucun taux de participation
            n’est donc affiché pour les sénateurs (rien d’estimé, rien d’inventé).
          </p>
        </Card>
      </div>

      <Card
        titre="Scrutins récents à l’Assemblée nationale"
        sousTitre="Les 10 derniers scrutins publics présents en base — résultat officiel pour/contre."
        droite={<Badge source={sources["S5-SCRUTINS"]} />}
      >
        <DataTable colonnes={colonnesScrutins} lignes={scrutins} cleLigne={(l) => l.uid} />
      </Card>

      {stats && (
        <Card
          titre="Intégrité — déclarations HATVP"
          sousTitre="Croisement factuel : fiches nominatives HATVP appariées aux élus du répertoire."
          droite={<Badge source={sources["S14"]} />}
        >
          <div className="flex flex-wrap gap-x-8 gap-y-2 text-sm text-ink-secondary">
            <p>
              <span className="font-semibold text-ink">
                {formatNombre(stats.nb_declarations_hatvp)}
              </span>{" "}
              déclarations publiées référencées
            </p>
            <p>
              <span className="font-semibold text-ink">{formatNombre(stats.nb_elus_hatvp)}</span>{" "}
              élus avec fiche HATVP appariée
            </p>
          </div>
          <p className="mt-3 text-[11px] leading-relaxed text-ink-muted">
            L’appariement se fait par URL de fiche nominative HATVP (jamais par simple homonymie).
            Les déclarations d’un élu et leur statut, tels que publiés par la HATVP, sont visibles
            sur sa fiche.
          </p>
        </Card>
      )}
    </div>
  );
}
