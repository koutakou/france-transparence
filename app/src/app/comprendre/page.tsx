import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { JsonLd } from "@/components/JsonLd";
import { jsonLdPage, metadonneesPage } from "@/lib/seo";

/**
 * Page /comprendre — appareil pédagogique du site.
 *
 * Elle décrit la méthode actuellement pratiquée : republication de données
 * officielles, lecture, provenance, limites. Elle ne porte aucun chiffre
 * qui dérive (les valeurs vivantes restent sur les pages de données),
 * aucune projection, et ne présente pas l'éditeur comme une personne
 * morale — l'association porteuse n'a pas encore la capacité juridique.
 *
 * Vocabulaire : les mots de la loi du 19 juillet 1977 n'apparaissent nulle part.
 */

const CHEMIN = "/comprendre/";
const TITRE = "Comprendre les données";
const DESCRIPTION =
  "Comment lire les chiffres de ce site : glossaire, provenance des sources, ce que ces données disent et ce qu’elles ne disent pas.";

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
        Il recense les mandats, y compris plus de cinq cent mille conseillers
        municipaux. Ce site n’ingère pas ces conseillers nom par nom : ils
        n’entrent dans aucun chiffre d’élus affiché, et n’ont pas de fiche.
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
    terme: "Licence Ouverte",
    id: "licence-ouverte",
    def: (
      <>
        Licence de réutilisation des informations publiques (Etalab). La
        plupart des sources de ce site la portent, pas toutes : trois
        relèvent d’un autre régime (publications officielles hors open data,
        texte du JORF, décision 2011/833/UE). La licence exacte, source par
        source, est sur la page{" "}
        <LienPage href="/donnees/">Données</LienPage>.
      </>
    ),
  },
];

const SOMMAIRE: { href: string; libelle: string }[] = [
  { href: "#methode", libelle: "Ce que ce site fait" },
  { href: "#lire-un-chiffre", libelle: "Comment lire un chiffre" },
  { href: "#glossaire", libelle: "Glossaire" },
  { href: "#marches", libelle: "Commande publique" },
  { href: "#elus", libelle: "Élus et institutions" },
  { href: "#lobbying", libelle: "Lobbying" },
  { href: "#financement", libelle: "Financement de la vie politique" },
  { href: "#depenses", libelle: "Budget de l’État" },
  { href: "#collectivites", libelle: "Finances locales" },
  { href: "#frais", libelle: "Frais et train de vie" },
  { href: "#documents", libelle: "Documents officiels" },
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
          techniques. Cette page dit comment les lire, d’où elles viennent, et
          ce qu’elles ne disent pas. Les chiffres vivants restent sur chaque
          module, avec leur date et leur source.
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
        <div id="methode" className="scroll-mt-20 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            France Transparence republie des données issues de publications
            officielles. Il agrège, met en forme, date, qualifie la fraîcheur
            et énonce les limites. Il ne produit pas de donnée. Il n’enquête
            pas. Il ne commente pas, n’interprète pas, ne qualifie pas et ne
            conclut pas.
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
            traitements est public.
          </p>
        </div>
      </Card>

      <Card titre="Comment lire un chiffre de ce site">
        <div id="lire-un-chiffre" className="scroll-mt-20 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
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

      <Card titre="Glossaire">
        <div id="glossaire" className="scroll-mt-20">
          <dl className="max-w-3xl divide-y divide-card-border">
            {GLOSSAIRE.map((e) => (
              <div key={e.id} id={e.id} className="scroll-mt-20 py-3 first:pt-0 last:pb-0">
                <dt className="text-sm font-medium text-ink">{e.terme}</dt>
                <dd className="mt-1 text-sm leading-relaxed text-ink-secondary">{e.def}</dd>
              </div>
            ))}
          </dl>
        </div>
      </Card>

      <Card titre="Commande publique">
        <div id="marches" className="scroll-mt-20 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            Un marché public est un contrat conclu à titre onéreux par un
            acheteur public avec un opérateur économique, pour répondre à ses
            besoins en travaux, fournitures ou services. Après attribution,
            l’acheteur notifie le marché au titulaire, puis en publie les
            données essentielles. La loi lui laisse jusqu’à deux mois pour
            cette publication : les fenêtres récentes sont donc
            structurellement incomplètes, et un marché «&nbsp;apparu&nbsp;»
            aujourd’hui peut avoir été notifié il y a des mois.
          </p>
          <p>
            <strong className="font-medium text-ink">D’où ça vient.</strong>{" "}
            Les marchés notifiés viennent des DECP consolidées. Les appels
            d’offres en cours viennent du BOAMP (bulletin officiel des
            annonces de marchés publics). Les achats annoncés viennent
            d’APProch. Voir{" "}
            <LienPage href="/marches/">Marchés publics</LienPage>.
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
            (SIRET). Il s’arrête à la personne morale : il ne remonte pas au
            groupe. Deux filiales restent deux lignes.
          </p>
        </div>
      </Card>

      <Card titre="Élus et institutions">
        <div id="elus" className="scroll-mt-20 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            Les assemblées parlementaires publient leur composition, leurs
            groupes et les scrutins publics nominaux. Le ministère de
            l’Intérieur tient le répertoire national des élus. La HATVP publie
            les déclarations d’intérêts des responsables concernés. Voir{" "}
            <LienPage href="/elus/">Élus &amp; institutions</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Une fiche nominative n’existe que pour les mandats nationaux et
            les exécutifs départementaux et régionaux. Les maires sont
            recensés ; ils n’ont pas de page dédiée. Les conseillers
            municipaux du RNE n’entrent dans aucun chiffre d’élus affiché. Le
            site ne publie aucune nuance ou sensibilité politique. Un taux de
            participation aux scrutins n’est pas un jugement sur le travail
            d’un élu : la présidence d’une assemblée y figure naturellement
            très bas, parce qu’elle ne vote pas.
          </p>
          <p>
            Deux scores de participation cohabitent sur les fiches : l’un
            calculé par ce site sur les scrutins publics de l’Assemblée, l’autre
            publié par Datan. Ce sont deux méthodes, étiquetées comme telles.
          </p>
        </div>
      </Card>

      <Card titre="Lobbying">
        <div id="lobbying" className="scroll-mt-20 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            Depuis la loi du 9 décembre 2016, certaines entités qui
            entreprennent d’influer sur la décision publique s’inscrivent au
            répertoire des représentants d’intérêts et y déclarent leurs
            activités, les institutions visées et une fourchette de moyens.
            La HATVP publie ce répertoire et constate les défauts de
            déclaration. Voir{" "}
            <LienPage href="/lobbying/">Lobbying</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Une inscription n’est pas une infraction. Une fourchette de budget
            n’est pas un montant exact. Le répertoire ne couvre pas toutes les
            formes d’influence : les seuils d’entrée, les personnes physiques
            et une partie de l’activité européenne y échappent. Le croisement
            avec les marchés publics identifie les titulaires aussi inscrits
            comme représentants d’intérêts ; il ne dit pas qu’un marché a été
            obtenu par cette activité. Ce croisement n’applique pas le même
            filtre de conformité d’identifiant que le classement des marchés :
            les deux comptes ne portent pas sur la même population.
          </p>
        </div>
      </Card>

      <Card titre="Financement de la vie politique">
        <div id="financement" className="scroll-mt-20 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            Les partis déposent chaque année leurs comptes certifiés à la
            CNCCFP, qui les publie. Les campagnes électorales ont des comptes
            distincts, arrêtés après chaque scrutin. L’aide publique aux
            partis est fixée par décret. Voir{" "}
            <LienPage href="/financement/">Financement</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Un compte publié n’est pas le patrimoine d’un parti, ni l’argent
            disponible. Une réformation par la Commission peut relever ou
            abaisser un montant déclaré : le site affiche le retenu. Les
            comptes des municipales en cours d’instruction n’y figurent pas
            tant que la Commission ne les a pas publiés. Ce site ne produit
            aucun classement d’opinion, aucune intention de vote, aucune
            mesure de notoriété.
          </p>
        </div>
      </Card>

      <Card titre="Budget de l’État">
        <div id="depenses" className="scroll-mt-20 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            L’État publie chaque mois une situation d’exécution : recettes
            nettes, dépenses nettes, solde, en cumuls depuis le 1<sup>er</sup>{" "}
            janvier. Le détail par mission et programme est celui du projet
            de loi de finances et du budget voté, pas celui des paiements
            jour par jour. Les paiements du système Chorus ne sont pas en
            open data. Voir <LienPage href="/depenses/">Dépenses</LienPage> et{" "}
            <LienPage href="/recettes/">Recettes</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Un cumul mensuel n’est pas un rythme de dépense quotidien. Les
            mois de l’année en cours sont provisoires jusqu’à la clôture. La
            mission «&nbsp;Pensions&nbsp;» pèse lourd dans le budget par
            destination : c’est un compte d’affectation spéciale, pas une
            politique publique comparable aux autres missions. Les
            administrations de sécurité sociale, la dépense propre des
            opérateurs et les entreprises publiques sont hors champ.
          </p>
        </div>
      </Card>

      <Card titre="Finances locales">
        <div id="collectivites" className="scroll-mt-20 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            Les communes, départements et régions votent un budget principal
            et rendent des comptes. L’OFGL les consolide. Ce site affiche les
            comptes de l’ensemble des départements et régions, et ceux des
            200 communes les plus peuplées. La participation électorale
            porte, elle, sur l’union de deux listes déjà connues du site :
            les préfectures et communes de plus de 50&nbsp;000 habitants
            (points de la carte), et ces 200 communes. Voir{" "}
            <LienPage href="/collectivites/">Finances locales</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Un montant de fonctionnement n’inclut pas les budgets annexes ni
            les dépenses portées par l’intercommunalité. Une commune absente
            d’un exercice provisoire n’a pas dépensé zéro : sa donnée n’est
            pas encore publiée. Un écart à la médiane de strate n’est ni une
            faute ni un mérite. La participation affichée est celle des
            inscrits des communes et départements suivis, pas «&nbsp;la
            France&nbsp;» : les Français établis hors de France n’y sont pas.
            Aucune nuance politique, aucun nom de candidat.
          </p>
        </div>
      </Card>

      <Card titre="Frais et train de vie">
        <div id="frais" className="scroll-mt-20 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            Les indemnités, dotations et avances des responsables publics
            ont des barèmes publiés. Les comptes de l’Élysée sont audités
            par la Cour des comptes. Les justificatifs de frais des
            parlementaires ne sont ni publiés ni communicables (ordonnance
            n°&nbsp;58-1100 du 17 novembre 1958 ; refus écrits de
            l’Assemblée nationale et du Sénat du 11 juin 2026). Voir{" "}
            <LienPage href="/frais/">Frais</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Cette page ne montre aucune note de frais individuelle. Un
            barème n’est pas un montant dépensé. Un rapport de déontologue
            agrégé ne désigne personne. L’absence d’une catégorie n’est pas
            un oubli du site : c’est, dans les cas documentés, un refus
            d’accès à la source.
          </p>
        </div>
      </Card>

      <Card titre="Documents officiels">
        <div id="documents" className="scroll-mt-20 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            Le Journal officiel «&nbsp;Lois et décrets&nbsp;» paraît chaque
            jour ouvrable. Ce site en republie les métadonnées (titre, type,
            date) et renvoie vers Légifrance pour le texte. Voir{" "}
            <LienPage href="/documents/">Documents</LienPage>.
          </p>
          <p>
            <strong className="font-medium text-ink">Ce que ça ne dit pas.</strong>{" "}
            Une nomination au JO n’est pas une biographie. Un décret n’est
            pas résumé ici. La fenêtre affichée est celle des derniers JO
            parus, pas l’intégralité de l’historique.
          </p>
        </div>
      </Card>
    </section>
  );
}
