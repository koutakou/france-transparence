import type { Metadata } from "next";
import { getDb } from "@/lib/db";
import { TableParlementaires } from "@/components/client/TableParlementaires";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { DataTable, type Colonne } from "@/components/ui/DataTable";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { StatStrip } from "@/components/ui/StatStrip";
import { VueTableau } from "@/components/ui/VueTableau";
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
  PERIMETRE_DEPUTES,
  PERIMETRE_ELUS_EN_BASE,
  PERIMETRE_MAIRES,
  PERIMETRE_SENATEURS,
  type ScrutinLigne,
} from "@/lib/queries/elus";
import type { MetaSource } from "@/lib/db";
import { JsonLd } from "@/components/JsonLd";
import { NoticeLecture } from "@/components/ui/NoticeLecture";
import { jsonLdPage, metadonneesPage } from "@/lib/seo";

/**
 * Page STATIQUE (site pré-rendu quotidiennement) : agrégats et premiers
 * écrans calculés au build ; les listes complètes de députés/sénateurs et
 * leurs filtres vivent côté client sur fragments /data/elus/*.json
 * (docs/deploiement/DECISION.md).
 */

// Chemin, titre et description nommés UNE FOIS : les métadonnées et le
// balisage JSON-LD décrivent la même page, ils ne peuvent donc pas la
// décrire différemment le jour où l'un des deux est retouché.
const CHEMIN = "/elus/";
const TITRE = "Élus & institutions";
const DESCRIPTION =
  "Députés, sénateurs, maires et présidents d’exécutifs locaux : mandats, groupes, votes nominaux et déclarations HATVP, à partir des données officielles datées.";

export const metadata: Metadata = metadonneesPage({
  chemin: CHEMIN,
  titre: TITRE,
  description: DESCRIPTION,
});

// `CollectionPage` et non `WebPage` : cette page est la PORTE D'ENTRÉE des
// 1 053 fiches individuelles /elus/[id], chacune balisée `ProfilePage` +
// `Person`. Le sous-type dit ce lien, que le fil d'Ariane des fiches affirme
// déjà dans l'autre sens (« Accueil › Élus & institutions › <personne> »).
//
// AUCUN `ItemList` en revanche : le HTML ne porte que le premier écran des
// tableaux (25 lignes), le reste se charge au geste depuis les fragments
// /data/elus/*.json. Baliser une liste de 25 noms, ce serait annoncer comme
// exhaustif un extrait ; la baliser en entier, ce serait baliser ce que la
// page n'affiche pas. Les personnes, elles, sont décrites là où elles sont
// vraiment décrites : sur leur fiche.
const BALISAGE = jsonLdPage({
  chemin: CHEMIN,
  nom: TITRE,
  description: DESCRIPTION,
  type: "CollectionPage",
  ariane: [{ nom: "Accueil", chemin: "/" }, { nom: TITRE }],
});

/** Premier écran des tableaux : le reste se charge au geste (fragments). */
const PREMIER_ECRAN = 25;

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

export default async function PageElus() {
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

  const deputes = getDeputes() ?? [];
  const senateurs = getSenateurs() ?? [];
  const scrutins = getDerniersScrutins(10) ?? [];
  const legislature = groupesAn[0]?.legislature;

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
      <JsonLd donnees={BALISAGE} />
      {/* Bande 1 — table des noms au pli, pas le mur pédagogique. */}
      <section className="flex flex-col gap-2">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Élus &amp; institutions
        </h1>
        <p className="max-w-3xl text-sm text-ink-secondary">
          Composition réelle des assemblées (AN, Sénat) et répertoire national des élus
          (RNE)&nbsp;: les conseillers municipaux n’entrent dans aucun chiffre de cette
          page. Participation des députés aux scrutins publics, déclarations HATVP.
        </p>
      </section>

      {stats && (
        <>
          <StatStrip
            stats={[
              {
                label: "Députés",
                valeur: formatNombre(stats.deputes.nb),
                perimetre: PERIMETRE_DEPUTES,
              },
              {
                label: "Sénateurs",
                valeur: formatNombre(stats.senateurs.nb),
                perimetre: PERIMETRE_SENATEURS,
              },
              {
                label: "Maires (RNE)",
                valeur: formatNombre(stats.nb_maires),
                perimetre: PERIMETRE_MAIRES,
              },
              {
                label: "Élus en base",
                valeur: formatNombre(stats.nb_elus),
                perimetre: PERIMETRE_ELUS_EN_BASE,
              },
            ]}
          />
          <div className="-mt-3 flex flex-wrap gap-2">
            <Badge source={sources["S5-AMO10"]} />
            <Badge source={sources["S6-ODSEN"]} />
            <Badge source={sources["S17"]} />
          </div>
        </>
      )}

      <div id="deputes" className="scroll-mt-32">
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
          <TableParlementaires
            variante="deputes"
            initiaux={deputes.slice(0, PREMIER_ECRAN)}
            total={deputes.length}
            groupes={groupesAn.map((g) => ({ valeur: g.sigle, libelle: `${g.sigle} — ${g.nom}` }))}
            departements={departementsDeputes}
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

      <NoticeLecture
        ancre="elus"
        commentLire={
          <p>
            Une fiche nominative n’existe que pour les mandats nationaux et
            les exécutifs départementaux et régionaux. Les conseillers
            municipaux du RNE n’entrent dans aucun chiffre de cette page.
            Deux scores de participation cohabitent : l’un calculé ici, l’autre
            publié par Datan — deux méthodes, étiquetées.
          </p>
        }
        provenance={
          <p>
            Assemblée nationale et Sénat (composition, groupes, scrutins
            publics), répertoire national des élus (ministère de
            l’Intérieur), déclarations d’intérêts de la HATVP, scores Datan
            cités avec leur méthode.
          </p>
        }
        limites={
          <p>
            Cette page ne publie aucune nuance ou sensibilité politique. Un
            taux de participation aux scrutins n’est pas un jugement sur le
            travail d’un élu. Le contenu des déclarations de patrimoine
            consultables en préfecture n’y entre pas.
          </p>
        }
      />

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
        <VueTableau>
          <DataTable
            colonnes={[
              { cle: "nom", entete: "Groupe" },
              { cle: "sigle", entete: "Sigle" },
              { cle: "effectif", entete: "Sièges", type: "nombre" },
            ]}
            lignes={groupesAn}
            cleLigne={(g) => g.organe_ref}
          />
        </VueTableau>
        <p className="mt-2 text-[11px] text-ink-muted">
          Couleurs officielles des groupes (données AN) non reproduites : teinte unique du thème,
          validée pour le fond sombre — l’identité est portée par les libellés.
        </p>
      </Card>

      <div id="senateurs" className="scroll-mt-32">
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
          <div className="mb-4">
            <VueTableau>
              <DataTable
                colonnes={[
                  { cle: "groupe", entete: "Groupe" },
                  { cle: "effectif", entete: "Sièges", type: "nombre" },
                ]}
                lignes={groupesSenat}
                cleLigne={(g) => g.groupe}
              />
            </VueTableau>
          </div>
          <TableParlementaires
            variante="senateurs"
            initiaux={senateurs.slice(0, PREMIER_ECRAN)}
            total={senateurs.length}
            groupes={groupesSenat.map((g) => ({ valeur: g.groupe, libelle: g.groupe }))}
            departements={departementsSenat}
          />
          <p className="mt-3 text-[11px] leading-relaxed text-ink-muted">
            Les scrutins publics du Sénat ne sont pas ingérés à ce jour : aucun taux de
            participation n’est donc affiché pour les sénateurs (rien d’estimé, rien d’inventé).
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
          sousTitre="Appariement par URL de fiche nominative, pas par homonymie — ce n’est pas le stock total des déclarations HATVP. Le contenu des déclarations de patrimoine n’y entre pas."
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
