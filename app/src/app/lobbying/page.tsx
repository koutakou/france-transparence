import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AlertItem, type Gravite } from "@/components/ui/AlertItem";
import { BarChart } from "@/components/ui/BarChart";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { LineChart } from "@/components/ui/LineChart";
import { StatStrip } from "@/components/ui/StatStrip";
import { DefautsLobbying } from "@/components/client/DefautsLobbying";
import {
  TitulairesLobbyistes,
  type LigneTitulaireLobbyiste,
} from "@/components/client/TitulairesLobbyistes";
import { formatDateFr, formatEuros, formatNombre, formatPct } from "@/lib/format";
import {
  getCroisementLobbyingMarches,
  PLAFOND_ECRETAGE,
  type CroisementLobbyingMarches,
  type TitulaireLobbyiste,
} from "@/lib/queries/croisement-lobbying-marches";
import { metadonneesPage } from "@/lib/seo";
import {
  getDonneesLobbying,
  type FourchetteBudget,
  type InstitutionDetail,
  type MinistereVise,
  type TopEntite,
  type TrimestreActivites,
} from "@/lib/queries/lobbying";

// Rendu statique : la donnée ne change qu'à l'ingestion, le site est
// reconstruit après chaque ingestion (docs/deploiement/DECISION.md).

export const metadata: Metadata = metadonneesPage({
  chemin: "/lobbying/",
  titre: "Lobbying",
  description:
    "Le répertoire des représentants d'intérêts de la HATVP : activités déclarées, budgets, institutions visées, entités en défaut de déclaration, et les marchés publics dont ces représentants d'intérêts sont titulaires — constats officiels repris tels quels, datés et sourcés.",
});

/** Toggle « Vue tableau » — la jumelle WCAG de chaque graphique (DATAVIZ §7/§9). */
function VueTableau({ children }: { children: ReactNode }) {
  return (
    <details className="group mt-3">
      <summary className="cursor-pointer list-none text-xs text-ink-muted transition-colors hover:text-ink-secondary">
        <span
          aria-hidden="true"
          className="mr-1 inline-block transition-transform group-open:rotate-90"
        >
          ›
        </span>
        Vue tableau
      </summary>
      <div className="mt-2">{children}</div>
    </details>
  );
}

/** Gravité base (`haute`/`moyenne`/`info`) → gravité visuelle + libellé affiché. */
function graviteUi(g: string): { gravite: Gravite; libelle: string } {
  if (g === "haute") return { gravite: "serieux", libelle: "Gravité haute" };
  if (g === "moyenne") return { gravite: "attention", libelle: "Gravité moyenne" };
  return { gravite: "attention", libelle: "Info" };
}

/** Lien sortant vers une fiche HATVP (jamais de fetch serveur). */
function LienFiche({ url }: { url: string | null }) {
  if (!url) return <>—</>;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
    >
      Fiche HATVP
    </a>
  );
}

/** `10 000` → `10 k€`, `1 250 000` → `1,25 M€` (étiquettes d'axe compactes). */
function borneCompacte(v: number): string {
  if (v >= 1e6) {
    const m = v / 1e6;
    const dec = Number.isInteger(m) ? 0 : Number.isInteger(m * 10) ? 1 : 2;
    return `${formatNombre(m, dec)} M€`;
  }
  return `${formatNombre(v / 1e3)} k€`;
}

/**
 * Étiquette d'axe d'une fourchette native HATVP : sa borne basse compacte
 * (« < 10 k€ », « 25 k€ », « ≥ 10 M€ »). La fourchette complète reste
 * lisible dans l'infobulle et la vue tableau (libellés natifs).
 */
function libelleFourchetteCourt(f: FourchetteBudget): string {
  if (f.borne_min === null) return f.fourchette;
  if (f.borne_max === null) return `≥ ${borneCompacte(f.borne_min)}`;
  if (f.borne_min === 0) return `< ${borneCompacte(f.borne_max)}`;
  return borneCompacte(f.borne_min);
}

/** Part en % de `partie` dans `total` — `null` si le total est inconnu ou nul. */
function part(partie: number | null, total: number | null): number | null {
  if (partie === null || total === null || total === 0) return null;
  return (100 * partie) / total;
}

/**
 * Ligne du classement des titulaires, pour un périmètre donné : le montant
 * passe en MILLIONS d'euros parce que l'unité vit dans l'en-tête de colonne
 * (DATAVIZ §7) et n'est jamais répétée par cellule.
 */
function ligneTitulaire(
  t: TitulaireLobbyiste,
  perimetre: "horsAccordsCadres" | "tousMarches",
): LigneTitulaireLobbyiste {
  const horsAc = perimetre === "horsAccordsCadres";
  const montant = horsAc ? t.montant_hors_ac : t.montant_tous;
  return {
    siren: t.siren,
    denomination: t.denomination,
    categorie: t.categorie,
    url_fiche: t.url_fiche,
    defaut_declaration: t.defaut_declaration,
    activites_12m: t.activites_12m,
    nb_marches: horsAc ? t.nb_marches_hors_ac : t.nb_marches_tous,
    montant_meur: montant === null ? null : montant / 1e6,
  };
}

/** Ligne de la table « en défaut de déclaration ET titulaire de marchés ». */
type LigneDefautTitulaire = {
  siren: string;
  denomination: string;
  categorie: string | null;
  url_fiche: string | null;
  nb_marches_tous: number;
  montant_tous_meur: number | null;
  nb_marches_hors_ac: number;
  montant_hors_ac_meur: number | null;
};

/**
 * Croisement RÉPERTOIRE DES REPRÉSENTANTS D'INTÉRÊTS × MARCHÉS PUBLICS
 * (sources S4 × S1), joints sur le SIREN. Méthode complète, exclusions et
 * limites : docs/CROISEMENT-LOBBYING-MARCHES.md.
 *
 * Section extraite du corps de la page pour une raison de fond : elle ne
 * s'affiche QUE si les deux sources sont ingérées, et elle a besoin d'une
 * dizaine de valeurs dérivées (parts, conversions en M€) qu'il serait
 * illisible de calculer sous une garde `croisement && …` dans le JSX.
 *
 * `baseLegale` est reprise de l'alerte native du pipeline (table `alertes`)
 * plutôt que réécrite ici : le site n'a qu'UNE formulation du défaut de
 * déclaration, celle de la base.
 */
function SectionCroisement({
  croisement,
  baseLegale,
}: {
  croisement: CroisementLobbyingMarches;
  baseLegale: string | null;
}) {
  const { metaS1, metaS4, couverture, agregats: ag, ensemble, titulaires } = croisement;

  const sansSiren = couverture.entites - couverture.entitesSiren;
  const partMontant = part(ag.montantHorsAc, ensemble.montantHorsAc);
  const partMarches = part(ag.marchesHorsAc, ensemble.marchesHorsAc);
  const partTitulaires = part(ag.sirensHorsAc, ensemble.sirensTitulaires);
  const partEcretee = part(ag.montantEcretesHorsAc, ag.montantHorsAc);
  const partSuspecte = part(ag.montantSuspectsHorsAc, ag.montantHorsAc);

  // Les DEUX classements sont calculés au build ; la bascule côté client ne
  // fait que choisir lequel afficher (aucun fetch, aucun recalcul).
  const topHorsAc = titulaires
    .slice(0, 20)
    .map((t) => ligneTitulaire(t, "horsAccordsCadres"));
  const topTous = [...titulaires]
    .sort((a, b) => (b.montant_tous ?? 0) - (a.montant_tous ?? 0))
    .slice(0, 20)
    .map((t) => ligneTitulaire(t, "tousMarches"));

  const enDefaut: LigneDefautTitulaire[] = titulaires
    .filter((t) => t.defaut_declaration === 1)
    .sort((a, b) => (b.montant_tous ?? 0) - (a.montant_tous ?? 0))
    .map((t) => ({
      siren: t.siren,
      denomination: t.denomination,
      categorie: t.categorie,
      url_fiche: t.url_fiche,
      nb_marches_tous: t.nb_marches_tous,
      montant_tous_meur: t.montant_tous === null ? null : t.montant_tous / 1e6,
      nb_marches_hors_ac: t.nb_marches_hors_ac,
      montant_hors_ac_meur:
        t.montant_hors_ac === null ? null : t.montant_hors_ac / 1e6,
    }));

  // Deux sources croisées = deux badges. Aucune fusion : chacune a sa date
  // et sa fréquence, et la DECP porte en plus sa latence légale.
  const badges = (
    <div className="flex flex-wrap items-center justify-end gap-1.5">
      <FreshnessBadge
        dateDonnees={metaS1.date_donnees}
        source="DECP consolidées"
        frequence={metaS1.frequence}
        url={metaS1.url}
        mention="latence légale ≤ 2 mois"
      />
      <FreshnessBadge
        dateDonnees={metaS4.date_donnees}
        source="HATVP — AGORA"
        frequence={metaS4.frequence}
        url={metaS4.url}
      />
    </div>
  );

  return (
    <>
      {/* ── Croisement : représentants d'intérêts titulaires de marchés ── */}
      <Card
        titre="Représentants d'intérêts titulaires de marchés publics"
        sousTitre={`Croisement de deux répertoires publics : le SIREN des entités inscrites au répertoire HATVP et le SIREN des titulaires de marchés publics (DECP consolidées). La jointure est exacte sur le SIREN — aucun rapprochement de noms, donc aucune homonymie. ${formatNombre(couverture.entitesSiren)} des ${formatNombre(couverture.entites)} entités inscrites portent un SIREN (${formatNombre(couverture.sirensDistincts)} SIREN distincts) ; les ${formatNombre(sansSiren)} autres sont identifiées par un numéro RNA d'association ou un identifiant interne HATVP et restent hors de portée de ce croisement.`}
        droite={badges}
      >
        <div className="flex flex-col gap-4">
          {/* Le cadrage éditorial passe AVANT le chiffre : sans lui, le
              tableau se lit comme une liste de suspects, ce qu'il n'est pas. */}
          <div className="rounded-xl border border-card-border bg-raised p-4">
            <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
              Ce que ce croisement ne dit pas
            </h3>
            <p className="text-xs leading-relaxed text-ink-secondary">
              Être inscrit au répertoire des représentants d&apos;intérêts et
              être titulaire d&apos;un marché public sont deux situations{" "}
              <strong className="font-medium text-ink">
                légales, distinctes et courantes
              </strong>
              . L&apos;inscription au répertoire est une obligation de
              transparence qui pèse sur qui exerce une activité de
              représentation d&apos;intérêts ; l&apos;attribution d&apos;un
              marché résulte d&apos;une procédure d&apos;achat public encadrée.
              Le cumul des deux n&apos;est ni interdit, ni irrégulier, ni
              suspect en soi : une entreprise, une association ou une chambre
              consulaire peut avoir des raisons parfaitement légitimes de
              figurer au répertoire. Aucune des entités listées ci-dessous
              n&apos;est en tort du seul fait d&apos;y figurer, et cette
              section ne formule aucun constat d&apos;irrégularité — à la seule
              exception du bloc suivant, qui reprend un constat officiel de la
              HATVP portant sur la déclaration, jamais sur le marché.
            </p>
          </div>

          <StatStrip
            stats={[
              {
                label: "Représentants d'intérêts titulaires (hors accords-cadres)",
                valeur: formatNombre(ag.sirensHorsAc),
              },
              {
                label: "Marchés notifiés (hors accords-cadres)",
                valeur: formatNombre(ag.marchesHorsAc),
              },
              {
                label: "Montant notifié (écrêté, hors accords-cadres)",
                valeur:
                  ag.montantHorsAc !== null ? formatEuros(ag.montantHorsAc) : "—",
                montantVedette: true,
              },
              {
                label: "Part du montant notifié hors accords-cadres",
                valeur: partMontant !== null ? formatPct(partMontant) : "—",
              },
            ]}
          />

          <p className="text-xs leading-relaxed text-ink-muted">
            Lecture : {formatNombre(ag.sirensHorsAc)} SIREN inscrits au
            répertoire — soit{" "}
            {partTitulaires !== null ? formatPct(partTitulaires, 2) : "—"} des{" "}
            {formatNombre(ensemble.sirensTitulaires)} SIREN titulaires
            d&apos;au moins un marché dans les DECP — sont titulaires de{" "}
            {partMarches !== null ? formatPct(partMarches) : "—"} des marchés
            notifiés hors accords-cadres, pour{" "}
            {partMontant !== null ? formatPct(partMontant) : "—"} du montant
            correspondant. Marchés notifiés = engagements contractuels, pas des
            paiements. Fenêtre couverte par la source DECP au{" "}
            {formatDateFr(metaS1.date_donnees)} : les 24 derniers mois environ,
            avec une latence légale de publication pouvant aller jusqu&apos;à
            deux mois.
          </p>

          {/* « Ce que vaut ce total » — même grille de lecture que /marches :
              un total DECP ne se publie pas sans ses parts écrêtée et
              suspecte, sinon le lecteur croit lire un montant homogène. */}
          <div className="rounded-xl border border-card-border bg-card p-4">
            <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
              Ce que vaut ce total
            </h3>
            <p className="text-xs leading-relaxed text-ink-secondary">
              Le total de{" "}
              <strong className="font-medium text-ink">
                {ag.montantHorsAc !== null ? formatEuros(ag.montantHorsAc) : "—"}
              </strong>{" "}
              porte sur {formatNombre(ag.marchesHorsAc)} marchés notifiés hors
              accords-cadres. Il n&apos;est pas homogène :
            </p>
            <ul className="mt-2 flex flex-col gap-1.5 text-xs leading-relaxed text-ink-secondary">
              <li>
                <strong className="font-medium text-ink">
                  {formatNombre(ag.ecretesHorsAc)} marchés
                </strong>{" "}
                dépassent le plafond de {formatEuros(PLAFOND_ECRETAGE)} et sont
                comptés à ce plafond. Ils apportent{" "}
                {ag.montantEcretesHorsAc !== null
                  ? formatEuros(ag.montantEcretesHorsAc)
                  : "—"}
                {partEcretee !== null && <>, soit {formatPct(partEcretee)} du total</>}{" "}
                : cette part est faite de valeurs de substitution, leur montant
                réel n&apos;est pas connu.
              </li>
              <li>
                <strong className="font-medium text-ink">
                  {formatNombre(ag.suspectsHorsAc)} marchés
                </strong>{" "}
                portent le drapeau « montant suspect » (anomalie signalée à la
                source, ou montant au-delà du plafond) et apportent{" "}
                {ag.montantSuspectsHorsAc !== null
                  ? formatEuros(ag.montantSuspectsHorsAc)
                  : "—"}
                {partSuspecte !== null && <>, soit {formatPct(partSuspecte)} du total</>}.
              </li>
              <li>
                En les écartant, il reste{" "}
                <strong className="font-medium text-ink">
                  {ag.montantHorsAcHorsSuspects !== null
                    ? formatEuros(ag.montantHorsAcHorsSuspects)
                    : "—"}
                </strong>{" "}
                pour {formatNombre(ag.marchesHorsAcHorsSuspects)} marchés et{" "}
                {formatNombre(ag.sirensHorsAcHorsSuspects)} représentants
                d&apos;intérêts. À lire comme une{" "}
                <strong className="font-medium text-ink">borne basse</strong>, et
                non comme le montant réel : le drapeau « suspect » n&apos;a pas
                été vérifié marché par marché, il écarte donc aussi des montants
                exacts.
              </li>
              <li>
                Sans aucun écrêtage, la somme brute atteindrait{" "}
                {ag.montantHorsAcBrut !== null
                  ? formatEuros(ag.montantHorsAcBrut)
                  : "—"}{" "}
                — ce que le plafond sert précisément à ne pas afficher.
              </li>
              <li>
                {formatNombre(ag.sansMontantHorsAc)} marchés sont notifiés sans
                montant renseigné : comptés dans le nombre de marchés, exclus de
                toutes les sommes.
              </li>
            </ul>
          </div>

          {/* Les accords-cadres ne sont pas passés sous silence : ils sont
              chiffrés, et dits pour ce qu'ils sont (un maximum, pas du
              dépensé). */}
          <div className="rounded-xl border border-card-border bg-card p-4">
            <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
              Les accords-cadres, comptés à part
            </h3>
            <p className="text-xs leading-relaxed text-ink-secondary">
              {formatNombre(ag.marchesAccordsCadres)} des{" "}
              {formatNombre(ag.marchesTous)} marchés du croisement sont des
              accords-cadres, pour un montant notifié de{" "}
              {ag.montantAccordsCadres !== null
                ? formatEuros(ag.montantAccordsCadres)
                : "—"}
              . Ce montant est un{" "}
              <strong className="font-medium text-ink">
                maximum contractuel, pas une dépense
              </strong>{" "}
              : l&apos;acheteur peut n&apos;en consommer qu&apos;une fraction, et
              la source ne publie pas ce qui a été réellement commandé. Les
              additionner au reste porterait le croisement à{" "}
              {ag.montantTous !== null ? formatEuros(ag.montantTous) : "—"} pour{" "}
              {formatNombre(ag.sirensTous)} représentants d&apos;intérêts et{" "}
              {formatNombre(ag.marchesTous)} marchés — un total qui mélange des
              plafonds et des engagements fermes. C&apos;est pourquoi le
              périmètre de référence de cette section les exclut ; la bascule
              du tableau ci-dessous permet néanmoins de les voir.
            </p>
          </div>

          <TitulairesLobbyistes horsAccordsCadres={topHorsAc} tousMarches={topTous} />

          <p className="text-xs leading-relaxed text-ink-muted">
            Classement des 20 premiers sur {formatNombre(titulaires.length)}{" "}
            représentants d&apos;intérêts titulaires d&apos;au moins un marché.
            La liste complète, les agrégats et la méthode sont exportés dans{" "}
            <code className="rounded bg-raised px-1 py-0.5">
              /api/lobbying-marches.json
            </code>
            . Un marché est rattaché à TOUS ses titulaires, co-titulaires
            compris (la donnée source ne désigne pas de mandataire) ; les
            activités déclarées sur 12 mois viennent du répertoire HATVP et
            n&apos;ont aucun lien de causalité avec les marchés listés.
            Consolidation DECP : decp-processing (Colin Maudry).
          </p>
        </div>
      </Card>

      {/* ── Sous-ensemble : titulaires en défaut de déclaration ────────── */}
      <Card
        titre="Titulaires de marchés en défaut de déclaration"
        sousTitre={`${formatNombre(ag.defautSirensTous)} des ${formatNombre(ag.sirensTous)} représentants d'intérêts titulaires d'un marché public figurent sur la liste officielle HATVP des représentants d'intérêts en défaut de déclaration — flag public officiel, repris tel quel.`}
        droite={badges}
      >
        <div className="flex flex-col gap-4">
          <div className="rounded-xl border border-card-border bg-raised p-4">
            <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
              Ce que « défaut de déclaration » veut dire ici
            </h3>
            <p className="text-xs leading-relaxed text-ink-secondary">
              Le défaut de déclaration est un{" "}
              <strong className="font-medium text-ink">
                constat officiel de la Haute Autorité pour la transparence de la
                vie publique
              </strong>
              , publié par elle dans son répertoire et repris ici tel quel : il
              désigne une entité inscrite sur la liste des représentants
              d&apos;intérêts n&apos;ayant pas communiqué à la Haute Autorité
              tout ou partie des informations exigibles par la loi, pour au
              moins un exercice. Ce n&apos;est ni un calcul, ni une
              interprétation, ni une accusation de France Transparence. Il porte
              sur la{" "}
              <strong className="font-medium text-ink">
                déclaration d&apos;activité de représentation d&apos;intérêts,
                jamais sur les marchés publics
              </strong>{" "}
              : rien n&apos;indique une irrégularité dans l&apos;attribution ou
              l&apos;exécution des marchés listés ci-dessous, et le croisement
              n&apos;en établit aucune. Il n&apos;est publié ici que parce que
              le manquement concerne des organisations qui sont aussi titulaires
              de la commande publique.
            </p>
            {baseLegale && (
              <p className="mt-2 text-[11px] leading-relaxed text-ink-muted">
                Base légale : {baseLegale}
              </p>
            )}
          </div>

          <p className="text-xs leading-relaxed text-ink-secondary">
            Ces {formatNombre(ag.defautSirensTous)} entités sont titulaires de{" "}
            {formatNombre(ag.defautMarchesTous)} marchés, tous types confondus,
            pour{" "}
            {ag.defautMontantTous !== null
              ? formatEuros(ag.defautMontantTous)
              : "—"}{" "}
            — dont{" "}
            {ag.defautMontantTousHorsSuspects !== null
              ? formatEuros(ag.defautMontantTousHorsSuspects)
              : "—"}{" "}
            sur {formatNombre(ag.defautMarchesTousHorsSuspects)} marchés une fois
            écartés les montants marqués suspects. Sur le périmètre de référence
            de cette page (accords-cadres exclus), il reste{" "}
            {formatNombre(ag.defautSirensHorsAc)} entités,{" "}
            {formatNombre(ag.defautMarchesHorsAc)} marchés et{" "}
            {ag.defautMontantHorsAc !== null
              ? formatEuros(ag.defautMontantHorsAc)
              : "—"}{" "}
            : l&apos;essentiel du montant de ce sous-ensemble tient à des
            accords-cadres, dont le montant est un maximum et non une dépense.
          </p>

          <DataTable<LigneDefautTitulaire>
            colonnes={[
              { cle: "denomination", entete: "Entité en défaut de déclaration" },
              { cle: "categorie", entete: "Catégorie (libellé natif HATVP)" },
              {
                cle: "nb_marches_tous",
                entete: "Marchés (tous)",
                type: "nombre",
                largeur: "6rem",
              },
              {
                cle: "montant_tous_meur",
                entete: "Montant (M€, tous)",
                type: "montant",
                decimales: 1,
                largeur: "7rem",
              },
              {
                cle: "nb_marches_hors_ac",
                entete: "Marchés (hors AC)",
                type: "nombre",
                largeur: "6rem",
              },
              {
                cle: "montant_hors_ac_meur",
                entete: "Montant (M€, hors AC)",
                type: "montant",
                decimales: 1,
                largeur: "7rem",
              },
              {
                cle: "url_fiche",
                entete: "Registre",
                rendu: (l) => <LienFiche url={l.url_fiche} />,
                largeur: "7rem",
              },
            ]}
            lignes={enDefaut}
            cleLigne={(l) => l.siren}
            vide="Aucun représentant d'intérêts en défaut de déclaration n'est titulaire d'un marché public dans les DECP."
            hauteurMax="24rem"
          />
          <p className="text-xs leading-relaxed text-ink-muted">
            « AC » = accord-cadre. Montants écrêtés à{" "}
            {formatEuros(PLAFOND_ECRETAGE)} par marché puis répartis entre
            co-titulaires ; ils comprennent ici les montants marqués suspects,
            le détail par entité étant trop fin pour qu&apos;une borne basse par
            ligne ait un sens. La liste officielle complète des représentants
            d&apos;intérêts en défaut de déclaration — marchés publics ou non —
            est celle du bloc précédent et reste consultable chez la HATVP.
          </p>
        </div>
      </Card>
    </>
  );
}

/**
 * Lobbying — répertoire des représentants d'intérêts (HATVP, loi
 * « Sapin II »). Données 100 % réelles de data/france.db (source S4),
 * mises à jour quotidiennement par le pipeline.
 */
export default async function LobbyingPage() {
  const donnees = getDonneesLobbying();

  if (!donnees) {
    return (
      <section className="flex flex-col gap-6">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Lobbying
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          <p>
            La base locale n&apos;est pas encore construite (ou la source HATVP
            n&apos;est pas ingérée) — lancer{" "}
            <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code>{" "}
            pour ingérer les sources.
          </p>
        </div>
      </section>
    );
  }

  const {
    meta,
    kpi,
    institutions,
    institutionsDetail,
    topEntites,
    budgets,
    budgetsCouverture,
    trimestres,
    ministeres,
    alerteDefauts,
    nbAlertesDefaut,
    entitesEnDefaut,
  } = donnees;

  const badge = (
    <FreshnessBadge
      dateDonnees={meta.date_donnees}
      source="HATVP — AGORA"
      frequence={meta.frequence}
      url={meta.url}
    />
  );

  const dernierTrimestre = trimestres[trimestres.length - 1];

  // Croisement HATVP × DECP (S4 × S1). Facultatif par construction : si la
  // source marchés n'est pas ingérée, `null` — la section disparaît au lieu
  // d'afficher un croisement à une seule source, qui ne voudrait rien dire.
  const croisement = getCroisementLobbyingMarches();

  return (
    <section className="flex flex-col gap-6">
      {/* ── En-tête ─────────────────────────────────────────────────── */}
      <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="max-w-2xl">
          <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
            Lobbying — représentants d&apos;intérêts
          </h1>
          <p className="mt-2 text-sm text-ink-secondary">
            Répertoire des représentants d&apos;intérêts tenu par la Haute
            Autorité pour la transparence de la vie publique (HATVP), créé par
            la loi « Sapin II » du 9 décembre 2016. Les entités
            inscrites y déclarent leurs activités de représentation
            d&apos;intérêts et les moyens qui y sont consacrés ; le
            répertoire est mis à jour quotidiennement.
          </p>
        </div>
        {badge}
      </header>

      {/* ── KPI ─────────────────────────────────────────────────────── */}
      <StatStrip
        stats={[
          { label: "Entités inscrites au répertoire", valeur: formatNombre(kpi.entites) },
          { label: "Entités actives", valeur: formatNombre(kpi.actives) },
          {
            label: "Activités déclarées (historique)",
            valeur: formatNombre(kpi.activitesTotal),
          },
          {
            label: "Activités détaillées (24 derniers mois)",
            valeur: formatNombre(kpi.activites24m),
          },
        ]}
      />

      {/* ── Activités par institution visée ─────────────────────────── */}
      <Card
        titre="Activités par institution visée"
        sousTitre="Cumul historique des activités déclarées, par catégorie de responsables publics visés. La donnée source ne sépare pas l'Assemblée nationale du Sénat : ils forment la seule catégorie « Parlement (AN + Sénat) »."
        droite={badge}
      >
        <BarList
          items={institutions.map((i) => ({
            libelle: i.groupe,
            valeur: i.nb_activites_total,
          }))}
          formatValeur={(v) => formatNombre(v)}
          largeurLibelle="38%"
        />
        <VueTableau>
          <DataTable<InstitutionDetail>
            colonnes={[
              { cle: "institution", entete: "Catégorie de responsables publics (libellé natif)" },
              { cle: "groupe", entete: "Groupe", largeur: "12rem" },
              { cle: "nb_activites_total", entete: "Activités (hist.)", type: "nombre" },
              { cle: "nb_activites_12m", entete: "Activités (12 mois)", type: "nombre" },
              { cle: "nb_entites", entete: "Entités", type: "nombre" },
            ]}
            lignes={institutionsDetail}
            cleLigne={(l) => l.institution}
          />
        </VueTableau>
      </Card>

      {/* ── Top 20 des entités (12 mois) ─────────────────────────────── */}
      <Card
        titre="Entités les plus actives (12 derniers mois)"
        sousTitre="Top 20 par nombre d'activités publiées sur les 12 derniers mois."
        droite={badge}
      >
        <DataTable<TopEntite>
          colonnes={[
            { cle: "rang", entete: "Rang", type: "nombre", largeur: "3.5rem" },
            { cle: "denomination", entete: "Entité" },
            { cle: "categorie", entete: "Catégorie" },
            { cle: "nb_activites_12m", entete: "Activités (12 mois)", type: "nombre" },
            {
              cle: "url_fiche",
              entete: "Registre",
              rendu: (l) => <LienFiche url={l.url_fiche} />,
            },
          ]}
          lignes={topEntites}
          cleLigne={(l) => String(l.rang)}
        />
      </Card>

      {/* ── Répartition par fourchette de budget ─────────────────────── */}
      <Card
        titre="Répartition par fourchette de budget"
        sousTitre={`Entités par fourchette de budget annuel consacré à la représentation d'intérêts — fourchettes natives HATVP, telles que déclarées. ${formatNombre(budgetsCouverture.dansFourchettes)} entités ont déclaré une fourchette, sur ${formatNombre(budgetsCouverture.total)} inscrites.`}
        droite={badge}
      >
        <BarChart
          items={budgets.map((b) => ({
            libelle: libelleFourchetteCourt(b),
            valeur: b.nb_entites,
          }))}
          formatValeur={(v) => formatNombre(v)}
          largeur={1000}
          hauteur={260}
          ariaLabel="Nombre d'entités par fourchette de budget annuel déclaré"
        />
        <p className="mt-2 text-xs text-ink-muted">
          Colonnes étiquetées par la borne basse de leur fourchette. La
          fourchette la plus haute n&apos;a pas de borne supérieure publiée
          (« ≥ 10 000 000 € »).
        </p>
        <VueTableau>
          <DataTable<FourchetteBudget>
            colonnes={[
              { cle: "fourchette", entete: "Fourchette de budget (libellé natif)" },
              { cle: "nb_entites", entete: "Entités", type: "nombre" },
            ]}
            lignes={budgets}
            cleLigne={(l) => l.fourchette}
            hauteurMax="20rem"
          />
        </VueTableau>
      </Card>

      {/* ── Série trimestrielle ──────────────────────────────────────── */}
      <Card
        titre="Activités déclarées par trimestre"
        sousTitre={`Trimestre de publication des déclarations d'activités (${trimestres[0]?.trimestre} → ${dernierTrimestre?.trimestre}).`}
        droite={badge}
      >
        <LineChart
          labels={trimestres.map((t) => t.trimestre)}
          series={[
            {
              nom: "Activités publiées",
              valeurs: trimestres.map((t) => t.nb_activites),
            },
          ]}
          formatValeur={(v) => formatNombre(v)}
          largeur={880}
          hauteur={260}
          ariaLabel="Nombre d'activités de représentation d'intérêts publiées par trimestre"
        />
        <p className="mt-2 text-xs text-ink-muted">
          Les pics récurrents au premier trimestre correspondent au dépôt des
          déclarations annuelles d&apos;activités de l&apos;exercice précédent.
          Le trimestre {dernierTrimestre?.trimestre} est en cours :
          chiffres partiels au {formatDateFr(meta.date_donnees)}.
        </p>
        <VueTableau>
          <DataTable<TrimestreActivites>
            colonnes={[
              { cle: "trimestre", entete: "Trimestre" },
              { cle: "nb_activites", entete: "Activités publiées", type: "nombre" },
              { cle: "nb_entites", entete: "Entités déclarantes", type: "nombre" },
            ]}
            lignes={trimestres}
            cleLigne={(l) => l.trimestre}
            hauteurMax="20rem"
          />
        </VueTableau>
      </Card>

      {/* ── Ministères / institutions les plus visés ─────────────────── */}
      <Card
        titre="Ministères et institutions les plus visés"
        sousTitre="Top 12 par nombre d'activités déclarées (historique). Le champ « département ministériel » de la HATVP accepte plusieurs valeurs et son export CSV les sépare par une virgule, sans distinguer cette virgule de celle qui appartient au nom d'un ministère : « Environnement, énergie et mer » y figure en deux lignes. Les portefeuilles connus sont donc reconstitués à partir d'une liste de correspondances fermée, vérifiée sur les identifiants d'activité ; les autres libellés restent tels que déclarés. Une même activité pouvant viser plusieurs portefeuilles, les lignes ne se cumulent pas."
        droite={badge}
      >
        <DataTable<MinistereVise>
          colonnes={[
            {
              cle: "ministere",
              entete: "Ministère / institution (libellé reconstitué)",
            },
            { cle: "nb_activites_total", entete: "Activités (hist.)", type: "nombre" },
            { cle: "nb_activites_12m", entete: "Activités (12 mois)", type: "nombre" },
            { cle: "nb_entites", entete: "Entités", type: "nombre" },
          ]}
          lignes={ministeres}
          cleLigne={(l) => l.ministere}
        />
      </Card>

      {/* ── Alertes : défauts de déclaration ─────────────────────────── */}
      <Card
        titre="Alertes — défauts de déclaration"
        sousTitre={`${formatNombre(nbAlertesDefaut)} entités inscrites sur la liste officielle HATVP des représentants d'intérêts en défaut de déclaration — flag public officiel, repris tel quel.`}
        droite={badge}
      >
        <div className="flex flex-col gap-3">
          {alerteDefauts && (
            <AlertItem
              gravite={graviteUi(alerteDefauts.gravite).gravite}
              graviteLibelle={graviteUi(alerteDefauts.gravite).libelle}
              titre={alerteDefauts.titre}
              detail={alerteDefauts.detail ?? undefined}
              regle={alerteDefauts.regle ?? undefined}
              baseLegale={alerteDefauts.base_legale ?? undefined}
              source={{
                libelle: "HATVP — AGORA",
                url: alerteDefauts.source_url ?? undefined,
              }}
            />
          )}
          {/* 50 premières lignes dans le HTML, liste complète (316) chargée
              d'un clic depuis /data/lobbying/defauts.json — rendue côté
              serveur, la table complète dépassait le budget < 500 Ko. */}
          <DefautsLobbying
            premieres={entitesEnDefaut.slice(0, 50)}
            total={entitesEnDefaut.length}
          />
        </div>
      </Card>

      {/* ── Croisement lobbying × marchés publics (S4 × S1) ───────────── */}
      {croisement && (
        <SectionCroisement
          croisement={croisement}
          baseLegale={alerteDefauts?.base_legale ?? null}
        />
      )}
    </section>
  );
}
