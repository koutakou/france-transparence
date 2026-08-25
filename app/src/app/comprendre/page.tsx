import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { JsonLd } from "@/components/JsonLd";
import { jsonLdPage, metadonneesPage } from "@/lib/seo";
import { CONTACT_ISSUES_URL } from "@/lib/site";

/**
 * Page /comprendre — appareil pédagogique du site.
 *
 * Elle décrit la méthode actuellement pratiquée : republication de données
 * officielles, fonctionnement de chaque publication, lecture, provenance,
 * limites, et un journal daté des lectures. Elle ne porte aucun chiffre
 * qui dérive (les valeurs vivantes restent sur les pages de données),
 * aucune projection, et ne présente pas l'éditeur comme une personne
 * morale — l'association porteuse n'a pas encore la capacité juridique.
 *
 * Vocabulaire : les mots de la loi du 19 juillet 1977 n'apparaissent nulle part.
 */

const CHEMIN = "/comprendre/";
const TITRE = "Comprendre les données";
const DESCRIPTION =
  "Comment fonctionnent les données publiques de ce site : glossaire, provenance, ce qu’elles disent et ce qu’elles ne disent pas.";

export const metadata: Metadata = metadonneesPage({
  chemin: CHEMIN,
  titre: TITRE,
  description: DESCRIPTION,
});

const BALISAGE = jsonLdPage({
  chemin: CHEMIN,
  nom: TITRE,
  description: DESCRIPTION,
  ariane: [{ nom: "Accueil", chemin: "/" }, { nom: TITRE }],
});

const LIEN =
  "underline decoration-dotted underline-offset-2 hover:text-ink-secondary";

function LienPage({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className={LIEN}>
      {children}
    </Link>
  );
}

type EntreeGlossaire = { terme: string; id: string; def: ReactNode };

const GLOSSAIRE: EntreeGlossaire[] = [
  {
    terme: "SIREN",
    id: "siren",
    def: (
      <>
        Identifiant de 9 chiffres d’une entreprise ou d’une personne morale,
        attribué par l’Insee au répertoire Sirene. C’est l’unité que ce site
        emploie pour classer un acheteur ou un titulaire de marché : une
        entreprise, pas un établissement.
      </>
    ),
  },
  {
    terme: "SIRET",
    id: "siret",
    def: (
      <>
        Identifiant de 14 chiffres d’un établissement : le SIREN de
        l’entreprise, suivi de 5 chiffres propres au lieu (le NIC). La source
        des marchés publics n’identifie acheteurs et titulaires que par SIRET.
        Un identifiant qui n’est pas 14 chiffres, et rien d’autre, est écarté
        des classements et compté à part.
      </>
    ),
  },
  {
    terme: "DECP",
    id: "decp",
    def: (
      <>
        Données essentielles de la commande publique. Chaque acheteur public
        déclare les marchés qu’il notifie. Ce site lit une consolidation
        communautaire de ces déclarations (projet{" "}
        <a
          href="https://www.data.gouv.fr/datasets/donnees-essentielles-de-la-commande-publique-consolidees-format-tabulaire"
          target="_blank"
          rel="noopener noreferrer"
          className={LIEN}
        >
          decp-processing
        </a>
        ), pas un fichier unique produit par l’État.
      </>
    ),
  },
  {
    terme: "BOAMP",
    id: "boamp",
    def: (
      <>
        Bulletin officiel des annonces de marchés publics. Il publie les
        appels d’offres encore ouverts, pas les marchés déjà notifiés. Sur
        ce site, c’est une publication distincte des DECP.
      </>
    ),
  },
  {
    terme: "APProch",
    id: "approch",
    def: (
      <>
        Plateforme où un acheteur annonce un achat avant de le lancer. Un
        achat annoncé n’est pas un appel d’offres, et n’est pas un marché
        notifié. Ce site tient les trois listes séparées.
      </>
    ),
  },
  {
    terme: "Notification",
    id: "notification",
    def: (
      <>
        Acte par lequel l’acheteur informe le titulaire que le marché lui est
        attribué. Sur ce site, un marché est daté de sa notification{" "}
        <strong className="font-medium text-ink">initiale</strong>. Un avenant
        ultérieur change le montant ou les titulaires affichés, pas la date.
      </>
    ),
  },
  {
    terme: "Avenant",
    id: "avenant",
    def: (
      <>
        Modification d’un marché déjà notifié. À la source, la ligne d’un
        avenant porte comme date de notification la date de l’avenant. Ce site
        ne s’en sert pas pour dater le marché.
      </>
    ),
  },
  {
    terme: "Écrêtement",
    id: "ecretement",
    def: (
      <>
        Dans les totaux, chaque marché est plafonné à 100&nbsp;millions
        d’euros avant sommation. Un montant saisi à 12&nbsp;milliards ne pèse
        que 100&nbsp;M€ dans un agrégat. Le détail d’un marché conserve le
        montant non écrêté, avec un drapeau «&nbsp;suspect&nbsp;».
      </>
    ),
  },
  {
    terme: "Acheteur / titulaire",
    id: "acheteur-titulaire",
    def: (
      <>
        L’acheteur est la personne morale qui passe le marché (État,
        collectivité, établissement public…). Le titulaire est celle qui
        l’exécute. Un marché a un seul acheteur et peut avoir plusieurs
        co-titulaires ; le montant est alors réparti à parts égales, la source
        ne le ventilant pas.
      </>
    ),
  },
  {
    terme: "HATVP",
    id: "hatvp",
    def: (
      <>
        Haute Autorité pour la transparence de la vie publique. Elle tient le
        répertoire des représentants d’intérêts et publie les déclarations
        d’intérêts et d’activités des responsables publics. Ce site n’utilise
        que ses flux open data : le contenu des déclarations de patrimoine
        consultables en préfecture n’y entre pas.
      </>
    ),
  },
  {
    terme: "Représentant d’intérêts",
    id: "representant-interets",
    def: (
      <>
        Personne morale inscrite au répertoire HATVP qui déclare des
        activités destinées à influer sur la décision publique. L’inscription
        et le contenu des déclarations sont le fait de l’entité, sous le
        contrôle de la Haute Autorité. Un «&nbsp;défaut de déclaration&nbsp;»
        affiché ici reprend un constat de la HATVP, ce n’est pas un jugement
        du site.
      </>
    ),
  },
  {
    terme: "RNE",
    id: "rne",
    def: (
      <>
        Répertoire national des élus, tenu par le ministère de l’Intérieur.
        Il recense les mandats, y compris les conseillers municipaux. Ce
        site n’ingère pas ces conseillers nom par nom : ils n’entrent dans
        aucun chiffre d’élus affiché, et n’ont pas de fiche.
      </>
    ),
  },
  {
    terme: "Datan",
    id: "datan",
    def: (
      <>
        Projet indépendant qui publie des scores de participation des
        députés, calculés selon sa propre méthode. Sur les fiches de ce
        site, ce score cohabite avec un taux calculé ici sur les scrutins
        publics de l’Assemblée : deux méthodes, étiquetées comme telles.
      </>
    ),
  },
  {
    terme: "EPCI",
    id: "epci",
    def: (
      <>
        Établissement public de coopération intercommunale : un groupement
        de communes (métropole, communauté d’agglomération, communauté de
        communes…). Les dépenses qu’il porte n’entrent pas dans les comptes
        du budget principal d’une commune.
      </>
    ),
  },
  {
    terme: "CNCCFP",
    id: "cnccfp",
    def: (
      <>
        Commission nationale des comptes de campagne et des financements
        politiques. Elle publie les comptes des partis et les comptes de
        campagne. Ce site les republie ; il n’estime pas ce qui n’y figure
        pas.
      </>
    ),
  },
  {
    terme: "DGF",
    id: "dgf",
    def: (
      <>
        Dotation globale de fonctionnement : concours de l’État aux
        collectivités, réparti chaque année. Un montant à zéro pour une
        commune n’est pas une donnée manquante : c’est parfois un écrêtement
        réel du calcul officiel.
      </>
    ),
  },
  {
    terme: "Budget principal",
    id: "budget-principal",
    def: (
      <>
        Le budget voté par l’assemblée de la collectivité pour ses compétences
        propres. Les budgets annexes (eau, transports, régies…) n’y sont pas.
        Tous les montants de finances locales de ce site portent sur le budget
        principal seul.
      </>
    ),
  },
  {
    terme: "OFGL",
    id: "ofgl",
    def: (
      <>
        Observatoire des finances et de la gestion publique locales. Il
        consolide les comptes des collectivités à partir des données DGFiP.
        C’est la source des pages de finances locales de ce site.
      </>
    ),
  },
  {
    terme: "Accord-cadre",
    id: "accord-cadre",
    def: (
      <>
        Contrat qui fixe un maximum et des conditions, sans commander à
        lui seul les prestations. Le montant publié est un plafond, pas du
        dépensé. Dans les totaux de ce site, un accord-cadre entre pour ce
        maximum, après écrêtement.
      </>
    ),
  },
  {
    terme: "PLF / LFI / exécution",
    id: "plf-lfi",
    def: (
      <>
        Le projet de loi de finances (PLF) est le texte déposé. La loi de
        finances initiale (LFI) est le texte voté. L’exécution est ce qui a
        été recouvré et dépensé, publié chaque mois. Ce site affiche
        l’exécution mensuelle sur{" "}
        <LienPage href="/depenses/">Dépenses</LienPage> et{" "}
        <LienPage href="/recettes/">Recettes</LienPage>
        ; la répartition par mission de 2025 est celle du PLF, pas de la
        LFI. Une LFI 2025 par mission est publiée à côté, dans le budget
        vert, en crédits budgétaires. La LFI 2026 n’est pas publiée en
        données.
      </>
    ),
  },
  {
    terme: "Budget vert",
    id: "budget-vert",
    def: (
      <>
        Annexe au PLF qui ventile les crédits par mission, programme et
        action, y compris un marquage environnemental. Sur ce site, c’est
        aussi la source d’une LFI 2025 par mission, en crédits budgétaires,
        et de la répartition 2026 — la LFI 2026 n’étant pas publiée en
        données.
      </>
    ),
  },
  {
    terme: "Chorus",
    id: "chorus",
    def: (
      <>
        Système d’information financière de l’État, où s’enregistrent les
        engagements et les paiements. Ces paiements ne sont pas en open
        data. L’exécution affichée ici vient des situations mensuelles
        publiées par la DGFiP, pas de Chorus.
      </>
    ),
  },
  {
    terme: "Mission / programme",
    id: "mission",
    def: (
      <>
        Une mission est une politique publique du budget de l’État. Elle se
        découpe en programmes, puis en actions et parfois en sous-actions.
        Une mission n’est pas un ministère : plusieurs ministères peuvent
        porter une même mission, et un ministère plusieurs missions.
      </>
    ),
  },
  {
    terme: "CP / AE",
    id: "cp-ae",
    def: (
      <>
        Crédits de paiement (CP) : ce qui peut être payé dans l’année.
        Autorisations d’engagement (AE) : ce qui peut être engagé, parfois
        sur plusieurs années. Les pages «&nbsp;par destination&nbsp;»
        affichent les deux, en brut. Ils ne sont pas comparables aux
        dépenses nettes de l’exécution mensuelle.
      </>
    ),
  },
  {
    terme: "Aide publique",
    id: "aide-publique",
    def: (
      <>
        Concours de l’État aux partis et groupements politiques, fixé par
        décret, en deux fractions. Ce site affiche le montant du décret en
        vigueur et celui inscrit aux comptes déposés : ce ne sont pas le
        même exercice, ni le même objet.
      </>
    ),
  },
  {
    terme: "Réformation",
    id: "reformation",
    def: (
      <>
        Correction apportée par la CNCCFP à un compte déposé. Elle peut
        relever ou abaisser un montant déclaré. Le chiffre affiché sur ce
        site est le montant retenu, pas le montant d’origine.
      </>
    ),
  },
  {
    terme: "S13 (ESA)",
    id: "s13-esa",
    def: (
      <>
        Secteur des administrations publiques dans le système européen de
        comptes (ESA 2010)&nbsp;: État, organismes divers d’administration
        centrale, administrations publiques locales et administrations de
        sécurité sociale. À ne pas confondre avec la source S13 de ce site
        (situations mensuelles budgétaires de la DGFiP, budget de l’État).
      </>
    ),
  },
  {
    terme: "B9 / déficit Maastricht",
    id: "b9-maastricht",
    def: (
      <>
        Indicateur de comptes nationaux (ESA 2010)&nbsp;: capacité (+) ou
        besoin (−) de financement des administrations publiques, sur une
        année civile. Un B9 négatif est un déficit. Ce n’est pas le solde
        du budget de l’État, ni l’encours de dette. Le pourcentage du PIB
        publié à côté est un fait de la même série, pas une comparaison à
        un seuil.
      </>
    ),
  },
  {
    terme: "Encours Maastricht",
    id: "encours-maastricht",
    def: (
      <>
        Stock de dette brute consolidée des administrations publiques
        (indicateur GD, secteur ESA S13), arrêté en fin de trimestre. Ce
        n’est pas un flux, pas le déficit B9, pas la dette de l’État seul.
        Voir{" "}
        <a href="#dette-maastricht" className={LIEN}>
          Dette des APU
        </a>
        .
      </>
    ),
  },
  {
    terme: "TE / TR (ESA)",
    id: "te-tr",
    def: (
      <>
        Total des dépenses (TE) et total des recettes (TR) des
        administrations publiques, flux d’année civile. Ce n’est pas
        Maastricht (B9, GD), pas l’exécution du budget de l’État, pas
        la ventilation CFAP. Voir{" "}
        <a href="#depenses-apu-esa" className={LIEN}>
          Dépenses des APU
        </a>
        ,{" "}
        <a href="#recettes-apu-esa" className={LIEN}>
          Recettes des APU
        </a>{" "}
        et{" "}
        <a href="#depenses-apu-cfap" className={LIEN}>
          Dépenses des APU par fonction
        </a>
        .
      </>
    ),
  },
  {
    terme: "CFAP",
    id: "cfap",
    def: (
      <>
        Classification des fonctions des administrations publiques
        (COFOG-99). Ventilation du flux annuel des dépenses des APU en
        dix divisions. Ce n’est pas le total TE de gov_10a_main, pas le
        budget de l’État, pas un classement. Voir{" "}
        <a href="#depenses-apu-cfap" className={LIEN}>
          Dépenses des APU par fonction
        </a>
        .
      </>
    ),
  },
  {
    terme: "CGE",
    id: "compte-general",
    def: (
      <>
        Compte général de l’État : bilan patrimonial de l’État, en
        comptabilité générale, arrêté au 31 décembre. La situation nette
        est un stock, pas un flux, pas «&nbsp;la dette de l’État&nbsp;».
        Voir{" "}
        <a href="#cge" className={LIEN}>
          Situation nette de l’État
        </a>
        .
      </>
    ),
  },
  {
    terme: "DREES",
    id: "drees",
    def: (
      <>
        Direction de la recherche, des études, de l’évaluation et des
        statistiques. Elle publie les comptes de la protection sociale :
        prestations versées, tous régimes, flux annuel. Ce n’est pas la
        LFSS. Le total est tous régimes, pas le seul régime général. Voir{" "}
        <a href="#protection-sociale" className={LIEN}>
          Prestations de protection sociale
        </a>
        .
      </>
    ),
  },
  {
    terme: "DOLE",
    id: "dole",
    def: (
      <>
        Fonds des dossiers législatifs de la DILA. Un dossier est un texte
        de l’article 39 de la Constitution (ou de l’article 53, hors forme
        simplifiée). Ce n’est pas le Journal officiel du jour. Voir{" "}
        <a href="#dossiers-legislatifs" className={LIEN}>
          Dossiers législatifs
        </a>
        .
      </>
    ),
  },
  {
    terme: "Licence Ouverte",
    id: "licence-ouverte",
    def: (
      <>
        Licence de réutilisation des informations publiques (Etalab). La
        plupart des sources de ce site la portent, pas toutes : d’autres
        relèvent d’un régime distinct — décision 2011/833/UE, publications
        officielles hors open data. Le Journal officiel «&nbsp;Lois et
        décrets&nbsp;» (métadonnées) est sous Licence Ouverte. La licence
        exacte, source par source, est sur la page{" "}
        <LienPage href="/donnees/">Données</LienPage>.
      </>
    ),
  },
];

const SOMMAIRE: { href: string; libelle: string }[] = [
  { href: "#methode", libelle: "Ce que ce site fait" },
  { href: "#lire-un-chiffre", libelle: "Comment lire un chiffre" },
  { href: "#lectures", libelle: "Journal des lectures" },
  { href: "#glossaire", libelle: "Glossaire" },
  { href: "#marches", libelle: "Commande publique" },
  { href: "#elus", libelle: "Élus et institutions" },
  { href: "#lobbying", libelle: "Lobbying" },
  { href: "#financement", libelle: "Financement de la vie politique" },
  { href: "#depenses", libelle: "Budget de l’État" },
  { href: "#dette-maastricht", libelle: "Dette des APU (Maastricht)" },
  { href: "#deficit-maastricht", libelle: "Déficit des APU (Maastricht)" },
  { href: "#depenses-apu-esa", libelle: "Dépenses des APU (ESA)" },
  { href: "#depenses-apu-cfap", libelle: "Dépenses des APU par fonction (CFAP)" },
  { href: "#recettes-apu-esa", libelle: "Recettes des APU (ESA)" },
  { href: "#cge", libelle: "Situation nette de l’État (CGE)" },
  { href: "#protection-sociale", libelle: "Prestations de protection sociale" },
  { href: "#recettes", libelle: "Recettes de l’État" },
  { href: "#recettes-plf", libelle: "Recettes non fiscales du PLF" },
  { href: "#ircom", libelle: "Impôt sur le revenu par territoire (IRCOM)" },
  { href: "#collectivites", libelle: "Finances locales" },
  { href: "#rei", libelle: "Fiscalité directe locale (REI)" },
  { href: "#frais", libelle: "Frais et train de vie" },
  { href: "#documents", libelle: "Documents officiels" },
  { href: "#dossiers-legislatifs", libelle: "Dossiers législatifs" },
  { href: "#alertes", libelle: "Alertes" },
];

export default function PageComprendre() {
  return (
    <section className="flex flex-col gap-6">
      <JsonLd donnees={BALISAGE} />
      <header className="flex flex-col gap-2">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Comprendre les données
        </h1>
        <p className="max-w-3xl text-sm leading-relaxed text-ink-secondary">
          Ce site met à portée d’un public non spécialiste des données
          publiques officielles qui, à l’état brut, sont dispersées et
          techniques. Cette page forme à leur lecture : comment fonctionne
          chaque publication, d’où elle vient, et ce qu’elle ne dit pas. Les
          chiffres vivants restent sur chaque module, avec leur date et leur
          source.
        </p>
      </header>

      <nav
        aria-label="Sommaire"
        className="max-w-3xl rounded-xl border border-card-border bg-card p-4"
      >
        <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
          Sur cette page
        </p>
        <ul className="columns-1 gap-x-8 text-sm text-ink-secondary sm:columns-2">
          {SOMMAIRE.map((s) => (
            <li key={s.href} className="break-inside-avoid py-0.5">
              <a href={s.href} className={LIEN}>
                {s.libelle}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <Card titre="Ce que ce site fait">
        <div id="methode" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            France Transparence republie des données issues de publications
            officielles et en explique le fonctionnement. Il agrège, met en
            forme, date, qualifie la fraîcheur et énonce les limites. Il ne
            produit pas de donnée. Il n’enquête pas. Il ne commente pas,
            n’interprète pas, ne qualifie pas et ne conclut pas.
          </p>
          <p>
            Une source n’entre que si elle est officielle, publiée, munie
            d’une licence qui permet la republication — ou, à défaut, si elle
            relève du régime des textes et publications officielles, cités
            avec leur adresse. Le site n’enrichit pas ces sources hors open
            data. Il ne croise que des identifiants déjà publics.
          </p>
          <p>
            Il ne qualifie d’irrégularité que ce qu’une autorité a elle-même
            qualifié. Un indicateur calculé ici n’est pas une infraction. Un
            homonyme non tranché ne donne lieu à aucune alerte nominative. Une
            donnée manquante en amont exclut le cas, plutôt que d’être
            estimée.
          </p>
          <p>
            L’accès est identique pour tous : pas de compte, pas de
            formulaire, pas d’inscription, pas de contrepartie. Le catalogue
            des sources, leur licence et leur fraîcheur mesurée sont sur la
            page <LienPage href="/donnees/">Données</LienPage>. Le code des
            traitements est public. Les lectures actuellement pratiquées, et
            celles qu’elles ont remplacées, sont datées plus bas.
          </p>
        </div>
      </Card>

      <Card titre="Comment lire un chiffre de ce site">
        <div id="lire-un-chiffre" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            Un chiffre borné porte sa borne à côté de lui : «&nbsp;12
            mois&nbsp;», «&nbsp;budget principal&nbsp;», «&nbsp;hors
            conseillers municipaux&nbsp;». Une restriction écrite plus bas
            sur la page ne compte pas.
          </p>
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <strong className="font-medium text-ink">La fenêtre.</strong>{" "}
              «&nbsp;12 mois&nbsp;» n’est pas l’année civile. C’est une
              fenêtre glissante arrêtée à la date des données de la source.
              Deux pages qui disent «&nbsp;12 mois&nbsp;» portent sur la même
              règle, pas forcément sur le même jour de coupe.
            </li>
            <li>
              <strong className="font-medium text-ink">Le tiret «&nbsp;—&nbsp;».</strong>{" "}
              Ce n’est pas un zéro. C’est une valeur absente, un
              dénominateur manquant, ou un calcul impossible. Un zéro, lui,
              est écrit 0, et c’est une mesure.
            </li>
            <li>
              <strong className="font-medium text-ink">Le badge de fraîcheur.</strong>{" "}
              Il porte la date des données, pas celle du chargement de la
              page. Une source «&nbsp;en attente d’une édition&nbsp;» n’est
              pas en panne : aucune édition plus récente n’était parue au
              moment de la construction du site.
            </li>
            <li>
              <strong className="font-medium text-ink">L’écrêtement.</strong>{" "}
              Les totaux de marchés publics plafonnent chaque marché à
              100&nbsp;M€ avant de les additionner. Un total «&nbsp;écrêté&nbsp;»
              n’est donc pas la somme des montants saisis.
            </li>
            <li>
              <strong className="font-medium text-ink">Le dénominateur.</strong>{" "}
              Un taux n’a de sens que si l’on sait sur quoi il est calculé.
              Quand le site écarte une population, il la compte à part : rien
              ne disparaît en silence.
            </li>
          </ul>
        </div>
      </Card>

      <Card titre="Journal des lectures">
        <div id="lectures" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            Ce site date ses lectures. Une lecture remplacée n’est pas
            effacée : elle reste ici, avec ce qui la remplace. Un chiffre
            vivant n’entre pas dans ce journal — les valeurs restent sur
            chaque module, avec leur date et leur source. Une incohérence
            de la source amont n’est pas corrigée en silence : elle est
            constatée et documentée, sauf si la source l’a elle-même
            corrigée.
          </p>
          <p>
            Un signalement d’erreur de lecture, qui ne porte sur personne
            en particulier, se dépose comme une{" "}
            <a
              href={CONTACT_ISSUES_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={LIEN}
            >
              issue sur le dépôt public
            </a>
            . Une demande qui porte sur une personne se fait par le canal
            indiqué sur la page{" "}
            <LienPage href="/donnees-personnelles/">
              Données personnelles
            </LienPage>
            .
          </p>
          <ul className="list-disc space-y-3 pl-5">
            <li>
              <strong className="font-medium text-ink">
                21 août 2026 — Date d’un marché.
              </strong>{" "}
              Un marché se date de sa notification initiale. À la source,
              la ligne d’un avenant porte comme date de notification la
              date de l’avenant. Lire cette date comme date du marché
              rangeait les avenants dans le mois courant. Les attributs
              affichés (montant, titulaires, objet) restent ceux de la
              version courante.
            </li>
            <li>
              <strong className="font-medium text-ink">
                21 août 2026 — Unité d’un titulaire ou d’un acheteur.
              </strong>{" "}
              Le classement groupe par entreprise (SIREN), pas par
              établissement (SIRET). Classer par SIRET émiette une
              entreprise à réseau d’agences en autant de lignes minuscules,
              dont aucune n’atteint le seuil d’entrée. Le regroupement
              s’arrête à la personne morale : il ne remonte pas au groupe.
            </li>
            <li>
              <strong className="font-medium text-ink">
                21 août 2026 — Identifiants non conformes.
              </strong>{" "}
              Un identifiant qui n’est pas un SIRET de 14 chiffres est
              écarté des classements et compté à part. Un numéro à 13
              chiffres n’est pas complété d’un zéro de tête.
            </li>
            <li>
              <strong className="font-medium text-ink">
                22 août 2026 — Un chiffre borné porte sa borne.
              </strong>{" "}
              Une restriction écrite plus bas sur la page ne compte pas.
              Fenêtre, strate, filtre de source et population exclue se
              lisent à l’endroit du chiffre.
            </li>
            <li>
              <strong className="font-medium text-ink">
                22 août 2026 — Exécution de l’État.
              </strong>{" "}
              Un cumul depuis le 1<sup>er</sup> janvier, arrêté au dernier
              mois publié, n’est pas l’année. Le dernier mois publié l’est
              avec cinq à sept semaines de latence.
            </li>
            <li>
              <strong className="font-medium text-ink">
                22 août 2026 — PLF, LFI, exécution.
              </strong>{" "}
              La répartition par mission de 2025 affichée est celle du PLF,
              pas de la LFI. Une LFI 2025 par mission est publiée dans le
              budget vert, en crédits budgétaires. La LFI 2026 n’est pas
              publiée en données.
            </li>
            <li>
              <strong className="font-medium text-ink">
                22 août 2026 — Licences.
              </strong>{" "}
              Les sources ne portent pas toutes la Licence Ouverte, ni
              toutes la même version. La licence exacte, source par source,
              est sur la page <LienPage href="/donnees/">Données</LienPage>.
            </li>
            <li>
              <strong className="font-medium text-ink">
                22 août 2026 — Stock, solde, déficit.
              </strong>{" "}
              L’encours Maastricht est un stock des APU. Le solde du
              budget général est un flux cumulé de l’État. Le déficit
              Maastricht (B9) est un flux annuel des APU. Ce ne sont pas
              le même objet&nbsp;: ils ne s’additionnent pas.
            </li>
            <li>
              <strong className="font-medium text-ink">
                23 août 2026 — Hors-champ de l’argent public.
              </strong>{" "}
              Les prestations de protection sociale publiées par la DREES
              (tous régimes, flux annuel) sont dans le champ. Restent hors
              champ&nbsp;: la loi de financement de la sécurité sociale en
              tant que texte voté, la dépense propre des opérateurs de
              l’État, les entreprises publiques.
            </li>
            <li>
              <strong className="font-medium text-ink">
                23 août 2026 — Noms dans les alertes.
              </strong>{" "}
              Les constats de la HATVP, les décisions de la CNCCFP et les
              défauts AGORA portent un nom. Les retards HATVP
              «&nbsp;présumés&nbsp;» restent des agrégats, jamais un nom.
            </li>
            <li>
              <strong className="font-medium text-ink">
                23 août 2026 — Participation électorale.
              </strong>{" "}
              L’agrégat des tuiles est la somme des départements et
              collectivités de ce scrutin, pas un total France du
              ministère.
            </li>
            <li>
              <strong className="font-medium text-ink">
                23 août 2026 — Croisement lobbying / marchés.
              </strong>{" "}
              Le croisement porte sur 24 mois de détail DECP, pas sur la
              fenêtre 12 mois du classement de la page Marchés, et
              n’applique pas le même filtre d’identifiant.
            </li>
            <li>
              <strong className="font-medium text-ink">
                24 août 2026 — Recettes non fiscales du PLF.
              </strong>{" "}
              Le détail des recettes non fiscales est celui du projet de
              loi de finances (État A, recettes brutes), pas de
              l’exécution mensuelle. Ce n’est pas la LFI votée, pas le
              rapport de l’Agence des participations de l’État.
            </li>
          </ul>
        </div>
      </Card>

      <Card titre="Glossaire">
        <div id="glossaire" className="scroll-mt-32">
          <dl className="max-w-3xl divide-y divide-card-border">
            {GLOSSAIRE.map((e) => (
              <div key={e.id} id={e.id} className="scroll-mt-32 py-3 first:pt-0 last:pb-0">
                <dt className="text-sm font-medium text-ink">{e.terme}</dt>
                <dd className="mt-1 text-sm leading-relaxed text-ink-secondary">{e.def}</dd>
              </div>
            ))}
          </dl>
        </div>
      </Card>

      <Card titre="Commande publique">
        <div id="marches" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Un marché public est un contrat conclu à titre onéreux par un
            acheteur public avec un opérateur économique, pour répondre à ses
            besoins en travaux, fournitures ou services. L’acheteur identifie
            le besoin, met en concurrence selon la procédure qui s’applique,
            attribue, puis notifie le marché au titulaire. Il publie ensuite
            les données essentielles de ce marché. La loi lui laisse jusqu’à
            deux mois pour cette publication : les fenêtres récentes sont
            donc structurellement incomplètes, et un marché «&nbsp;apparu&nbsp;»
            aujourd’hui peut avoir été notifié il y a des mois.
          </p>
          <p>
            Trois publications distinctes coexistent, et ce site les tient
            séparées. Les marchés déjà notifiés viennent des DECP. Les appels
            d’offres encore ouverts viennent du BOAMP (bulletin officiel des
            annonces de marchés publics). Les achats que l’acheteur annonce
            sans encore les lancer viennent d’APProch. Un appel d’offres n’est
            pas un marché notifié ; un achat annoncé n’est pas un appel
            d’offres.
          </p>
          <p>
            Un marché tient en plusieurs lignes à la source (titulaires ×
            modifications). Ce site le date de sa notification{" "}
            <strong className="font-medium text-ink">initiale</strong>
            : un avenant change le montant ou les titulaires affichés, pas le
            mois du marché. Lire la date de l’avenant comme date du marché
            rangerait les avenants dans le mois courant. Les totaux
            «&nbsp;12 mois&nbsp;» et «&nbsp;30 jours&nbsp;» de la page
            portent sur cette date. Voir{" "}
            <LienPage href="/marches/">Marchés publics</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            Les marchés notifiés viennent des DECP consolidées par le projet
            communautaire decp-processing. Les appels d’offres en cours
            viennent du BOAMP. Les achats annoncés viennent d’APProch.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Le montant d’un accord-cadre est un maximum, pas du dépensé. Le
            site ne dit pas si un marché a été exécuté, ni s’il a été payé, ni
            s’il était le mieux-disant. Un identifiant d’acheteur ou de
            titulaire qui n’est pas un SIRET de 14 chiffres est écarté du
            classement : valeurs illisibles, numéros étrangers, SIREN nus,
            SIREN avec espaces, numéros à 13 chiffres. Un numéro à 13 chiffres
            n’est pas complété d’un zéro de tête — rien ne prouve que le zéro
            manque en tête. Ces identifiants sont comptés, pas classés.
          </p>
          <p>
            Le classement groupe par entreprise (SIREN), pas par établissement
            (SIRET). Classer par SIRET émiette une entreprise à réseau
            d’agences en autant de lignes minuscules, dont aucune n’atteint le
            seuil d’entrée. Le regroupement s’arrête à la personne morale : il
            ne remonte pas au groupe. Deux filiales restent deux lignes.
          </p>
        </div>
      </Card>

      <Card titre="Élus et institutions">
        <div id="elus" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Les assemblées parlementaires publient leur composition, leurs
            groupes et les scrutins publics nominaux. Le ministère de
            l’Intérieur tient le répertoire national des élus, mandat par
            mandat. La HATVP publie les déclarations d’intérêts et
            d’activités des responsables concernés ; le contenu des
            déclarations de patrimoine consultables en préfecture n’est pas
            en open data. Voir{" "}
            <LienPage href="/elus/">Élus &amp; institutions</LienPage>.
          </p>
          <p>
            Une fiche nominative n’existe que pour les mandats nationaux et
            les exécutifs départementaux et régionaux. Les maires sont
            recensés ; ils n’ont pas de page dédiée. La tuile des maires
            porte les mandats maire du répertoire, pas tout le répertoire.
            Le stock «&nbsp;élus en base&nbsp;» n’est pas une fiche par
            personne. Les conseillers municipaux du RNE sont tenus en
            agrégat départemental : ils n’entrent dans aucun chiffre d’élus
            affiché, et n’ont pas de fiche.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            Le répertoire national des élus est tenu par le ministère de
            l’Intérieur. La composition, les groupes et les scrutins
            publics viennent des open data de l’Assemblée nationale et du
            Sénat. Les déclarations d’intérêts et d’activités viennent de
            la HATVP. Un second score de participation, étiqueté comme tel,
            vient de Datan.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Le site ne publie aucune nuance ou sensibilité politique. Un taux
            de participation aux scrutins n’est pas un jugement sur le
            travail d’un élu : la présidence d’une assemblée y figure
            naturellement très bas, parce qu’elle ne vote pas. Deux scores de
            participation cohabitent sur les fiches : l’un calculé par ce
            site sur les scrutins publics de l’Assemblée, l’autre publié par
            Datan. Ce sont deux méthodes, étiquetées comme telles.
          </p>
        </div>
      </Card>

      <Card titre="Lobbying">
        <div id="lobbying" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Depuis la loi du 9 décembre 2016, certaines entités qui
            entreprennent d’influer sur la décision publique s’inscrivent au
            répertoire des représentants d’intérêts tenu par la HATVP. Elles
            y déclarent leurs activités, les institutions visées et une
            fourchette de moyens. La Haute Autorité publie ce répertoire,
            le met à jour chaque jour, et constate les défauts de
            déclaration. Un «&nbsp;défaut de déclaration&nbsp;» affiché ici
            reprend ce constat, ce n’est pas un jugement du site. Voir{" "}
            <LienPage href="/lobbying/">Lobbying</LienPage>.
          </p>
          <p>
            Le répertoire français et le registre de transparence de l’Union
            européenne sont deux publications distinctes, avec des seuils et
            des obligations différents. Ce site les tient séparées. Les totaux
            du registre de l’Union incluent les travailleurs indépendants :
            ce sont des personnes physiques, comptées, non nommées. Un
            croisement d’identifiants déjà publics relie, le cas échéant, un
            titulaire de marché aussi inscrit comme représentant d’intérêts.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            Le répertoire des représentants d’intérêts et les constats de
            défaut de déclaration viennent de la HATVP. Le registre de
            transparence de l’Union européenne est une autre publication,
            tenue par le secrétariat conjoint du Parlement européen et de
            la Commission. Les marchés du croisement viennent des DECP.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Une inscription n’est pas une infraction. Une fourchette de budget
            n’est pas un montant exact. Le répertoire ne couvre pas toutes les
            formes d’influence : les seuils d’entrée, les personnes physiques
            et une partie de l’activité européenne y échappent. Le croisement
            avec les marchés publics ne dit pas qu’un marché a été obtenu par
            cette activité. Il porte sur les 24 mois de détail DECP, pas sur
            la fenêtre 12 mois du classement de la page Marchés, et
            n’applique pas le même filtre d’identifiant : les deux comptes
            ne portent pas sur la même population.
          </p>
        </div>
      </Card>

      <Card titre="Financement de la vie politique">
        <div id="financement" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Les partis et groupements politiques déposent chaque année leurs
            comptes, certifiés par un commissaire aux comptes, à la CNCCFP,
            qui les publie. Ces comptes recouvrent les dons, les cotisations
            d’adhérents et d’élus, l’aide publique, les contributions reçues
            et les autres produits. L’aide publique est fixée par décret, en
            deux fractions ; le montant du décret et celui inscrit aux
            comptes déposés ne portent pas sur le même exercice. Voir{" "}
            <LienPage href="/financement/">Financement</LienPage>.
          </p>
          <p>
            Les campagnes électorales ont des comptes distincts, arrêtés
            après chaque scrutin, eux aussi publiés par la Commission. Un
            compte de campagne n’est pas un compte de parti. Les montants en
            francs CFP n’entrent pas dans les totaux en euros.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            Les comptes des partis et les comptes de campagne viennent de
            la CNCCFP. L’enveloppe d’aide publique vient du décret en
            vigueur, distinct des montants inscrits aux comptes déposés.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Un compte publié n’est pas le patrimoine d’un parti, ni l’argent
            disponible. Une réformation par la Commission peut relever ou
            abaisser un montant déclaré : le site affiche le retenu. Les
            comptes que la Commission n’a pas publiés n’y figurent pas.
            Ce site ne produit aucun classement d’opinion, aucune intention
            de vote, aucune mesure de notoriété. Il ne publie aucune nuance
            politique.
          </p>
        </div>
      </Card>

      <Card titre="Budget de l’État">
        <div id="depenses" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Le budget de l’État se lit en trois documents distincts. Le
            projet de loi de finances (PLF) est le texte déposé. La loi de
            finances initiale (LFI) est le texte voté. L’exécution est ce qui
            a été recouvré et dépensé. L’État publie chaque mois une
            situation d’exécution : recettes nettes, dépenses nettes, solde,
            en cumuls depuis le 1<sup>er</sup> janvier. Ces situations
            paraissent avec cinq à sept semaines de latence. Voir{" "}
            <LienPage href="/depenses/">Dépenses</LienPage>.
          </p>
          <p>
            Le détail par mission et programme de 2025 est celui du PLF, pas
            de la LFI. Pour 2026, il vient du budget vert annexé au PLF :
            la LFI 2026 n’est pas publiée en données. Une LFI 2025 par
            mission figure dans ce même budget vert, en crédits budgétaires.
            Les crédits de paiement et autorisations d’engagement de ces
            pages sont bruts : ils ne sont pas comparables aux dépenses
            nettes de l’exécution mensuelle. Les paiements du système Chorus
            ne sont pas en open data.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            L’exécution mensuelle vient des situations publiées par la
            DGFiP. La répartition 2026 et la LFI 2025 par mission viennent
            du budget vert annexé au PLF. Le détail 2025 par ministère,
            programme, action et sous-action vient du PLF par destination.
            Le jaune des subventions aux associations est une annexe du
            PLF, décalée de deux exercices.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Un cumul mensuel n’est pas un rythme de dépense quotidien. Les
            mois de l’année en cours sont provisoires jusqu’à la clôture. Un
            delta d’une année sur l’autre n’est ni une hausse «&nbsp;bonne&nbsp;»
            ni une baisse «&nbsp;mauvaise&nbsp;» : il est affiché neutre. La
            mission «&nbsp;Pensions&nbsp;» pèse lourd dans le budget par
            destination : c’est un compte d’affectation spéciale, pas une
            politique publique comparable aux autres missions. Le budget
            général ne couvre pas les prestations de protection sociale
            (bloc DREES). Hors champ&nbsp;: la loi de financement de la
            sécurité sociale en tant que texte voté, la dépense propre des
            opérateurs et les entreprises publiques.
          </p>
        </div>
      </Card>

      <Card titre="Dette des APU (Maastricht)">
        <div id="dette-maastricht" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            L’encours Maastricht est un stock de dette brute consolidée, à la
            valeur faciale, des administrations publiques (secteur ESA S13 :
            État, Odac, administrations publiques locales, administrations de
            sécurité sociale), arrêté en fin de trimestre. Ce n’est pas un
            flux. L’unité native Eurostat est le million d’euros (MIO_EUR) ;
            le milliard affiché est ce million divisé par 1&nbsp;000 — pas
            l’euro des situations DGFiP divisé par un milliard. Un trimestre
            peut porter le drapeau provisoire (p). Un delta d’un trimestre
            sur l’autre n’est ni «&nbsp;bon&nbsp;» ni «&nbsp;mauvais&nbsp;».
            Voir <LienPage href="/depenses/#dette-maastricht">Dépenses</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            Eurostat, datacode gov_10q_ggdebt, DOI 10.2908/GOV_10Q_GGDEBT.
            Extrait geo=FR, sector=S13 (ESA), na_item=GD, unit=MIO_EUR.
            Réutilisation : décision 2011/833/UE (données statistiques
            Eurostat). Le secteur ESA S13 n’est pas la source S13 de ce site.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Ce n’est pas la dette de l’État seul (sous-secteur S.1311). Ce
            n’est pas la charge d’intérêts du budget général déjà publiée
            sur la même page (flux DGFiP, cumul depuis le 1<sup>er</sup>{" "}
            janvier). Ce n’est pas le déficit. Ce n’est pas un montant par
            habitant, ni un pourcentage du PIB.
          </p>
        </div>
      </Card>

      <Card titre="Déficit des APU (Maastricht)">
        <div id="deficit-maastricht" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Le déficit Maastricht est le besoin de financement annuel des
            administrations publiques (secteur ESA S13 : État, Odac,
            administrations publiques locales, administrations de sécurité
            sociale). L’indicateur s’appelle B9 : un nombre négatif est un
            besoin (déficit), un nombre positif une capacité (excédent).
            C’est un flux d’année civile, pas un stock. L’unité native
            Eurostat est le million d’euros (MIO_EUR) ; le milliard affiché
            est ce million divisé par 1&nbsp;000. Le pourcentage du PIB
            vient de la même série, lu à part ; il n’est comparé à aucun
            seuil. Un delta d’une année sur l’autre n’est ni «&nbsp;bon&nbsp;»
            ni «&nbsp;mauvais&nbsp;». Voir{" "}
            <LienPage href="/depenses/#deficit-maastricht">Dépenses</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            Eurostat, datacode gov_10dd_edpt1, DOI 10.2908/GOV_10DD_EDPT1.
            Extraits geo=FR, sector=S13 (ESA), na_item=B9, unit=MIO_EUR et
            unit=PC_GDP. C’est la notification d’avril (EDP). Réutilisation :
            décision 2011/833/UE (données statistiques Eurostat). Le
            secteur ESA S13 n’est pas la source S13 de ce site.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Ce n’est pas le solde du budget général (flux de l’État, cumul
            depuis le 1<sup>er</sup> janvier). Ce n’est pas l’encours de
            dette (stock trimestriel déjà publié sur la même page). Ce
            n’est pas le déficit de l’État seul (sous-secteur S.1311). Ce
            n’est pas un montant par habitant. Le pourcentage du PIB n’est
            comparé à aucun seuil.
          </p>
        </div>
      </Card>

      <Card titre="Dépenses des APU (ESA)">
        <div id="depenses-apu-esa" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Les dépenses des APU (ESA) sont le total des dépenses des
            administrations publiques (indicateur TE), sur une année civile.
            Le secteur ESA S13 couvre l’État, les Odac, les administrations
            publiques locales et les administrations de sécurité sociale.
            C’est un flux d’année civile, pas un cumul depuis le
            1<sup>er</sup> janvier, pas un stock. L’unité native Eurostat
            est le million d’euros (MIO_EUR) ; le milliard affiché est ce
            million divisé par 1&nbsp;000. Le pourcentage du PIB vient de
            la même série. Un delta d’une année sur l’autre n’est ni
            «&nbsp;bon&nbsp;» ni «&nbsp;mauvais&nbsp;». Voir{" "}
            <LienPage href="/depenses/#depenses-apu-esa">Dépenses</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            Eurostat, datacode gov_10a_main, DOI 10.2908/GOV_10A_MAIN.
            Extraits geo=FR, sector=S13 (ESA), na_item=TE, unit=MIO_EUR et
            unit=PC_GDP. C’est la publication annuelle des GFS (juillet).
            Réutilisation : décision 2011/833/UE (données statistiques
            Eurostat). Le secteur ESA S13 n’est pas la source S13 de ce
            site.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Ce n’est pas l’exécution du budget général (flux de l’État,
            cumul depuis le 1<sup>er</sup> janvier). Ce n’est pas une
            ventilation CFAP : celle-ci est une table Eurostat distincte
            (S49). Ce n’est pas la dépense de l’État seul (sous-secteur
            S.1311). Ce n’est pas un montant par habitant. Ce n’est pas
            le déficit (B9) ni l’encours (GD) au sens de Maastricht.
          </p>
        </div>
      </Card>

      <Card titre="Dépenses des APU par fonction (CFAP)">
        <div id="depenses-apu-cfap" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Les dépenses des APU par fonction sont le flux annuel TE,
            ventilé selon la Classification des fonctions des
            administrations publiques (CFAP, COFOG-99). Dix divisions
            (services généraux, défense, ordre public, affaires
            économiques, environnement, logements, santé, loisirs-culture-culte,
            enseignement, protection sociale) recomposent le total, dans
            l’ordre du producteur — ce n’est pas un classement. C’est un
            flux d’année civile, pas un cumul depuis le
            1<sup>er</sup> janvier, pas un stock. L’unité native Eurostat
            est le million d’euros (MIO_EUR) ; le milliard affiché est ce
            million divisé par 1&nbsp;000. Le pourcentage du PIB vient de
            la même série et n’est pas additif. Un delta d’une année sur
            l’autre n’est ni «&nbsp;bon&nbsp;» ni «&nbsp;mauvais&nbsp;». Voir{" "}
            <LienPage href="/depenses/#depenses-apu-cfap">Dépenses</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            Eurostat, datacode gov_10a_exp, DOI 10.2908/GOV_10A_EXP.
            Extraits geo=FR, sector=S13 (ESA), na_item=TE, cofog99 =
            TOTAL et GF01 à GF10, unit=MIO_EUR et unit=PC_GDP.
            Publication annuelle des GFS (juillet). Réutilisation :
            décision 2011/833/UE (données statistiques Eurostat). Le
            secteur ESA S13 n’est pas la source S13 de ce site. Le
            millésime est le TIME max de TOTAL, pas le champ
            JSON-stat updated, pas OBS_PERIOD_OVERALL_LATEST.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Ce n’est pas l’exécution du budget général. Ce n’est pas le
            total TE de la table gov_10a_main (S44) : deux tables
            Eurostat distinctes, dont les totaux ne coïncident pas. Ce
            n’est pas la dépense de l’État seul (S.1311). Ce n’est pas
            les prestations de protection sociale DREES (S45, tous
            régimes). Ce n’est pas un montant par habitant. Les groupes
            (GF0101…) ne sont pas ingérés : ils recouvrent les
            divisions. taxag n’est pas ingéré.
          </p>
        </div>
      </Card>

      <Card titre="Recettes des APU (ESA)">
        <div id="recettes-apu-esa" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Les recettes des APU (ESA) sont le total des recettes des
            administrations publiques (indicateur TR), sur une année civile.
            Le secteur ESA S13 couvre l’État, les Odac, les administrations
            publiques locales et les administrations de sécurité sociale.
            C’est un flux d’année civile, pas un cumul depuis le
            1<sup>er</sup> janvier, pas un stock. L’unité native Eurostat
            est le million d’euros (MIO_EUR) ; le milliard affiché est ce
            million divisé par 1&nbsp;000. Le pourcentage du PIB vient de
            la même série. Un delta d’une année sur l’autre n’est ni
            «&nbsp;bon&nbsp;» ni «&nbsp;mauvais&nbsp;». Voir{" "}
            <LienPage href="/recettes/#recettes-apu-esa">Recettes</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            Eurostat, datacode gov_10a_main, DOI 10.2908/GOV_10A_MAIN.
            Extraits geo=FR, sector=S13 (ESA), na_item=TR, unit=MIO_EUR et
            unit=PC_GDP. C’est la publication annuelle des GFS (juillet).
            Réutilisation : décision 2011/833/UE (données statistiques
            Eurostat). Le secteur ESA S13 n’est pas la source S13 de ce
            site.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Ce n’est pas le budget général de l’État (source S13, flux
            cumulé depuis le 1<sup>er</sup> janvier, net des dégrèvements).
            TR n’est pas un montant «&nbsp;net DGFiP&nbsp;». Ce n’est pas
            la recette de l’État seul (sous-secteur S.1311). Ce n’est pas
            un montant par habitant. Ce n’est pas le déficit (B9) ni
            l’encours (GD) au sens de Maastricht. On ne recalcule pas
            B9 = TR − TE : le déficit officiel reste S42.
          </p>
        </div>
      </Card>

      <Card titre="Situation nette de l’État (CGE)">
        <div id="cge" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Le compte général de l’État est le bilan patrimonial de
            l’État, en comptabilité générale (droits constatés), arrêté au
            31 décembre. La situation nette est le total de l’actif (I)
            moins le total du passif hors situation nette (II). C’est un
            stock, pas un flux, pas un cumul depuis le 1<sup>er</sup>{" "}
            janvier. La pièce mélange des colonnes en euros et des
            colonnes en millions d’euros ; le site convertit tout en euros
            puis affiche des milliards (euro divisé par un milliard) — pas
            le million d’euros Eurostat divisé par 1&nbsp;000. Un delta d’une
            année sur l’autre n’est ni «&nbsp;bon&nbsp;» ni
            «&nbsp;mauvais&nbsp;». Voir{" "}
            <LienPage href="/depenses/#cge">Dépenses</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            DGFiP, pièce de synthèse jointe au jeu « Données de
            comptabilité générale de l’État sur dix ans »
            (data.economie.gouv.fr,{" "}
            <code>balances_des_comptes_etat</code>). Totaux I, II et III
            lus dans l’onglet Bilan. Licence Ouverte 2.0. Le millésime est
            celui de la pièce, pas la date de modification du catalogue.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Ce n’est pas l’exécution du budget général (source S13, caisse,
            cumul depuis le 1<sup>er</sup> janvier). Ce n’est pas
            l’encours Maastricht des APU, ni le déficit B9, ni les
            agrégats ESA TE/TR. Ce n’est pas « la dette de l’État ». Les
            balances compte × programme ne sont pas sommées : un total
            2025 n’est pas publié tant que la pièce de synthèse ne le
            porte pas. Ce n’est pas un montant par habitant.
          </p>
        </div>
      </Card>

      <Card titre="Prestations de protection sociale">
        <div id="protection-sociale" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Les prestations de protection sociale sont le flux annuel des
            prestations versées, tous régimes, publié par la DREES. Ce n’est
            pas le budget de l’État, ni un agrégat ESA des APU, ni le
            bilan patrimonial. L’unité native est le million d’euros ; le
            milliard affiché est ce million divisé par 1&nbsp;000. Les
            montants sont en euros courants. Un delta d’une année sur
            l’autre n’est ni «&nbsp;bon&nbsp;» ni «&nbsp;mauvais&nbsp;».
            Le régime général (S13141) est un régime parmi d’autres, pas
            l’ensemble de la protection sociale. Voir{" "}
            <LienPage href="/depenses/#protection-sociale">Dépenses</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            DREES, jeu 305_les-comptes-de-la-protection-sociale, export
            JSON. Licence Ouverte 2.0. Le millésime est l’année des
            chiffres, jamais last_update du catalogue. Fiche
            data.gouv.fr/datasets/les-comptes-de-la-protection-sociale.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Ce n’est pas la LFSS. Ce n’est pas l’exécution du budget
            général (source S13, caisse, cumul depuis le 1<sup>er</sup>{" "}
            janvier). Ce n’est pas le total des dépenses des APU (S44,
            TE). Ce n’est pas la fonction CFAP « protection sociale »
            (S49, GF10). Ce n’est pas « la dette de l’État ». Ce n’est pas un
            montant par habitant. Ce n’est pas les recettes. Les niveaux
            2 et 3 de l’arbre ne sont pas affichés : ils recouvrent les
            niveaux 0 et 1. S13141 n’est pas toute la sécurité sociale
            (S13142 existe).
          </p>
        </div>
      </Card>

      <Card titre="Recettes de l’État">
        <div id="recettes" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Les recettes du budget général (source S13) sont publiées dans
            la même situation mensuelle que les dépenses. Elles sont nettes
            des remboursements et dégrèvements d’impôts : un impôt
            «&nbsp;net&nbsp;» n’est pas le montant mis à la charge du
            contribuable. Comme les dépenses, ce sont des cumuls depuis le
            1<sup>er</sup> janvier, et les mois de l’année en cours sont
            provisoires jusqu’à la clôture. Voir{" "}
            <LienPage href="/recettes/">Recettes</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            La même situation mensuelle de la DGFiP que celle des dépenses,
            nette des remboursements et dégrèvements. Cette source n’en
            publie, pour les recettes non fiscales, qu’un total. Le
            détail est une autre source, le PLF — voir{" "}
            <a href="#recettes-plf" className={LIEN}>
              Recettes non fiscales du PLF
            </a>
            .
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Ce n’est pas le détail des encaissements jour par jour, ni la
            fiscalité locale, ni les recettes de la sécurité sociale. Les
            prestations de protection sociale (tous régimes) sont sur la
            page Dépenses. La LFSS, comme texte voté, n’est pas un module
            de recettes. La ligne TVA ne couvre que la part revenant au
            budget général : les fractions affectées à d’autres
            administrations n’y figurent pas. Les recettes non fiscales
            d’exécution restent un seul total : le détail ci-dessous est
            un projet, pas cette exécution. L’impôt net IRCOM (par
            commune de résidence, année des revenus) est un autre objet —
            voir{" "}
            <a href="#ircom" className={LIEN}>
              Impôt sur le revenu par territoire
            </a>
            .
          </p>
        </div>
      </Card>

      <Card titre="Recettes non fiscales du PLF">
        <div id="recettes-plf" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            L’État A du projet de loi de finances détaille les recettes
            du budget général ligne par ligne, y compris les recettes
            non fiscales (participations, domaine, amendes, remboursements
            de prêts). C’est un projet, pour une année civile, en
            recettes brutes. Voir{" "}
            <LienPage href="/recettes/#recettes-plf">Recettes</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            Direction du Budget, jeu{" "}
            <code className="rounded bg-raised px-1.5 py-0.5">
              plf25-recettes-du-budget-general
            </code>
            {" "}
            sur data.economie.gouv.fr. Licence Ouverte 2.0. Millésime 2025,
            jeu publié le 11 octobre 2024 — lendemain de l’enregistrement
            du projet à l’Assemblée nationale (10 octobre 2024, texte
            n° 324). Aucun équivalent PLF 2026 ni LFI en données au
            24 août 2026.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Ce n’est pas l’exécution de la situation mensuelle (S13,
            nettes, cumul depuis le 1<sup>er</sup> janvier). Ce n’est pas
            la LFI votée. Ce n’est pas le rapport annuel de l’Agence des
            participations de l’État : les lignes 2110, 2116 et 2199
            sont celles de l’État A, pas un portefeuille nominatif. Les
            recettes fiscales de ce même fichier sont brutes : elles ne
            se comparent pas aux nettes S13 et ne sont pas additionnées
            ici. Les prélèvements sur recettes (collectivités, Union
            européenne) sont un autre objet.
          </p>
        </div>
      </Card>

      <Card titre="Impôt sur le revenu par territoire (IRCOM)">
        <div id="ircom" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            L&apos;IRCOM localise l&apos;impôt net <em>sur rôle</em> des
            foyers fiscaux, pour l&apos;année des revenus, à la commune de
            résidence. Un foyer = une déclaration. Un montant négatif est
            une restitution. Voir{" "}
            <LienPage href="/recettes/#ircom">Recettes</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">D&apos;où ça vient.</strong>{" "}
            DGFiP / DESF, jeu{" "}
            <code className="rounded bg-raised px-1.5 py-0.5">
              limpot-sur-le-revenu-par-collectivite-territoriale-ircom
            </code>
            {" "}
            sur data.gouv.fr. Licence Ouverte / Open Licence. Millésime
            mesuré le 24 août 2026 : revenus 2024, déclarés en 2025,
            fichier publié le 26 mai 2026 (campagne IRCOM 2025).
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Ce n&apos;est pas l&apos;IR de caisse de la situation mensuelle
            (S13, net, cumul depuis le 1<sup>er</sup> janvier). Ce n&apos;est
            pas le crédit d&apos;impôt relatif au PFU, exclu par la notice
            DESF. La CEHR est incluse. <code className="rounded bg-raised px-1.5 py-0.5">n.c.</code>{" "}
            est le secret statistique, pas un zéro : le total affiché est
            la somme des communes publiées. Les tranches de revenu fiscal
            de référence, les salaires et les pensions ne sont pas
            repris : ce ne sont pas de l&apos;argent public. Aucune page
            par commune.
          </p>
        </div>
      </Card>

      <Card titre="Finances locales">
        <div id="collectivites" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Les communes, départements et régions votent un budget principal
            et rendent des comptes. L’OFGL les consolide à partir des données
            DGFiP. Ce site affiche les comptes de l’ensemble des départements
            et des régions, et les agrégats communaux des communes ayant
            rendu leurs comptes — ce n’est pas le tableau nominatif des
            200 communes les plus peuplées. Tous les montants
            portent sur le budget principal seul : les budgets annexes
            (eau, transports, régies) et les dépenses portées par
            l’intercommunalité n’y sont pas. Voir{" "}
            <LienPage href="/collectivites/">Finances locales</LienPage>.
          </p>
          <p>
            Un tableau nominatif porte, lui, sur les 200 communes les plus
            peuplées. La participation électorale des communes suivies
            porte sur l’union des préfectures, des communes de plus de
            50&nbsp;000 habitants, et de ces 200 communes. Ce n’est pas
            «&nbsp;les communes de France&nbsp;». Un écart à la médiane de
            strate n’est ni une faute ni un mérite : une commune touristique
            ou une commune dont les compétences sont transférées à l’EPCI
            n’est pas comparable à sa voisine hors de cette médiane.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            Les comptes des collectivités sont consolidés par l’OFGL à
            partir des données DGFiP. La participation électorale vient des
            résultats agrégés du ministère de l’Intérieur. La DGF vient des
            montants officiels de l’exercice affiché.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Une commune absente d’un exercice provisoire n’a pas dépensé
            zéro : sa donnée n’est pas publiée. Un montant de DGF à
            zéro n’est pas une donnée manquante : c’est parfois un
            écrêtement réel du calcul officiel. L’agrégat de participation
            des tuiles est la somme des départements et collectivités de
            ce scrutin, pas un total France du ministère. Aucune nuance
            politique, aucun nom de candidat.
          </p>
        </div>
      </Card>

      <Card titre="Fiscalité directe locale (REI)">
        <div id="rei" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Le fichier de recensement des éléments d&apos;imposition (REI)
            décrit les impositions primitives du rôle général, par taxe et
            par collectivité bénéficiaire, pour une année d&apos;imposition.
            Ce n&apos;est pas le compte OFGL de la commune, pas l&apos;IRCOM,
            pas la caisse du budget général. Voir{" "}
            <LienPage href="/collectivites/#rei">Finances locales</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">D&apos;où ça vient.</strong>{" "}
            DGFiP / DESF, jeu data.gouv du REI, zip du millésime courant.
            Licence Ouverte / Open Licence version 2.0. Une cellule vide
            est un secret statistique (BOI-DJC-CADA-20), pas un zéro. Le
            produit IFER régional est répliqué sur chaque commune de la
            région : le site en prend une valeur par région.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Pas les taux, pas les bases, pas les compensations de TVA, pas
            les chambres, pas les frais d&apos;assiette de l&apos;État, pas
            les 34&nbsp;000 pages communales. Un total TFPB n&apos;est pas
            le 55&nbsp;Md€ « dus y compris annexes et frais ». Aucun
            classement de communes par pression fiscale.
          </p>
        </div>
      </Card>

      <Card titre="Frais et train de vie">
        <div id="frais" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Les indemnités, dotations et avances des responsables publics
            ont des barèmes publiés. Les comptes de l’Élysée sont audités
            par la Cour des comptes. Les justificatifs de frais des
            parlementaires ne sont ni publiés ni communicables (ordonnance
            n°&nbsp;58-1100 du 17 novembre 1958 ; refus écrits de
            l’Assemblée nationale et du Sénat du 11 juin 2026). Voir{" "}
            <LienPage href="/frais/">Frais</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            Les comptes de l’Élysée viennent des rapports de la Cour des
            comptes. Les dotations de la mission «&nbsp;Pouvoirs
            publics&nbsp;» viennent du rapport du Sénat sur la LFI. Les
            barèmes d’indemnités viennent des textes publiés. Les refus
            d’accès aux justificatifs de frais parlementaires sont des
            décisions écrites de l’Assemblée et du Sénat.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Cette page ne montre aucune note de frais individuelle. Un
            barème n’est pas un montant dépensé. La dotation de
            fonctionnement affichée est celle d’un député de métropole, pas
            «&nbsp;la&nbsp;» DFP. Un rapport de déontologue agrégé ne
            désigne personne. Les dotations des assemblées citées sont
            celles de la LFI, pas du PLF. L’absence d’une catégorie n’est
            pas un oubli du site : c’est, dans les cas documentés, un refus
            d’accès à la source.
          </p>
        </div>
      </Card>

      <Card titre="Documents officiels">
        <div id="documents" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Le Journal officiel «&nbsp;Lois et décrets&nbsp;» paraît chaque
            jour ouvrable, pas tous les jours civils : une série quotidienne
            a des trous. Ce site en republie les métadonnées (titre, type,
            date) et renvoie vers Légifrance pour le texte. Voir{" "}
            <LienPage href="/documents/">Documents</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            Les métadonnées du Journal officiel «&nbsp;Lois et
            décrets&nbsp;» viennent de la DILA. Le texte lui-même n’est pas
            recopié : le lien sort vers Légifrance.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Une nomination au JO n’est pas une biographie. Un décret n’est
            pas résumé ici. La fenêtre affichée est celle des derniers JO
            parus, pas l’intégralité de l’historique. Les autres séries du
            Journal officiel (annonces, associations, marchés) n’entrent
            pas dans cette page. Ce n’est pas le fonds DOLE.
          </p>
        </div>
        <div id="dossiers-legislatifs" className="scroll-mt-32 mt-8 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <h3 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
            Dossiers législatifs
          </h3>
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Un dossier législatif est un texte de l’article 39 de la
            Constitution (ou de l’article 53, hors forme simplifiée). La
            navette affichée est celle de la législature en cours : un projet
            d’une législature close n’est pas «&nbsp;en cours&nbsp;», même si
            son type reste «&nbsp;projet&nbsp;» dans le fichier. Voir{" "}
            <LienPage href="/documents/dossiers/">Dossiers législatifs</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            Dumps XML DILA du fonds DOLE (Freemium puis incréments), Licence
            Ouverte 2.0. Producteur : DILA ; catalogue data.gouv
            «&nbsp;dole-les-dossiers-legislatifs&nbsp;», organisation Premier
            ministre. Chaque dossier renvoie vers Légifrance (lien sortant).
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Ce n’est pas le total des propositions de loi déposées : les PPL
            n’entrent dans le fichier qu’après adoption par la première
            assemblée, depuis la réforme de 2008. Ce n’est pas l’exposé des
            motifs, ni l’échéancier d’application des lois, ni le droit
            consolidé (LEGI). Ce n’est pas le Journal officiel du jour.
          </p>
        </div>
      </Card>

      <Card titre="Alertes">
        <div id="alertes" className="scroll-mt-32 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="font-medium text-ink">Comment ça fonctionne.</strong>{" "}
            Une alerte de ce site reprend un constat déjà formulé par une
            autorité, ou un signal d’attention tiré des sources, avec sa
            règle de calcul et sa base légale. Ce n’est pas un jugement du
            site. Les constats officiels de la HATVP, les décisions de la
            CNCCFP et les défauts AGORA portent un nom ; les retards HATVP
            «&nbsp;présumés&nbsp;» sont des agrégats, jamais un nom. Voir{" "}
            <LienPage href="/alertes/">Alertes</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            Chaque alerte cite sa source, sa règle de calcul et sa base
            légale. Les constats nominatifs viennent de la HATVP, de la
            CNCCFP et d’AGORA. Les autres signaux sont calculés ici à
            partir des mêmes publications que le reste du site, jamais d’une
            source inédite.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Une alerte n’est pas une infraction constatée par ce site. Un
            homonyme non tranché ne donne lieu à aucune alerte nominative.
            Une donnée manquante en amont exclut le cas, plutôt que d’être
            estimée.
          </p>
        </div>
      </Card>
    </section>
  );
}
