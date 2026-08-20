import type { Metadata } from "next";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import {
  HEBERGEUR,
  HEBERGEUR_NATURE_SERVICE,
} from "@/lib/hebergeur";
import { CONTACT_EMAIL, CONTACT_ISSUES_URL } from "@/lib/site";
import { metadonneesPage } from "@/lib/seo";

/**
 * Page /donnees-personnelles — information des personnes concernées.
 *
 * Elle couvre DEUX traitements distincts, qu'il ne faut pas mélanger :
 *
 *   A. les VISITEURS du site — journaux du serveur web (art. 13 RGPD :
 *      l'éditeur collecte lui-même la donnée, auprès de la personne) ;
 *   B. les PERSONNES FIGURANT DANS LES DONNÉES republiées (élus, candidats,
 *      représentants d'intérêts) — art. 14 RGPD, données non collectées
 *      auprès d'elles, information collective fournie au titre de la
 *      dérogation « effort disproportionné » de l'art. 14(5)(b) : informer
 *      individuellement plus de 36 000 élus serait disproportionné
 *      (docs/deploiement/exigences-publiques.md §1.2, reco CNIL juin 2024).
 *
 * Références du volet A, vérifiées le 20/08/2026 sur la machine elle-même
 * (le site n'est plus hébergé sur une plateforme tierce : les journaux sont
 * ceux d'un nginx administré par l'éditeur, qui en est donc responsable) :
 * - /etc/nginx/nginx.conf : log_format `main` (IP complète) -> access.log ;
 *   map $ip_pseudonyme + log_format `audience` (IP tronquée /24 en IPv4,
 *   /48 en IPv6) -> audience.log ;
 * - /etc/logrotate.d/nginx : access.log et error.log, `rotate 52` (jours) ;
 * - /etc/logrotate.d/nginx-audience : audience.log, `rotate 400` (jours).
 * Toute modification de ces fichiers doit être répercutée ici : une durée de
 * conservation publiée qui ne correspond plus à la réalité est un manquement.
 *
 * L'identité de l'hébergeur citée ici vient de src/lib/hebergeur.ts : c'est
 * une donnée de déploiement, et les mentions légales en publient la même.
 */

export const metadata: Metadata = metadonneesPage({
  chemin: "/donnees-personnelles/",
  titre: "Données personnelles",
  description:
    "Visiteurs : aucun cookie ni traceur, mais des journaux de serveur — finalités, base légale, durées. Personnes figurant dans les données publiées : information de l'article 14 du RGPD. Droits et réclamation CNIL.",
});

/** Style commun des liens de la page. */
const LIEN = "underline decoration-dotted underline-offset-2 hover:text-ink";

export default function PageDonneesPersonnelles() {
  /** Adresse de contact, cliquable — définie une seule fois, dans site.ts. */
  const contactEmail = (
    <a href={`mailto:${CONTACT_EMAIL}`} className={LIEN}>
      {CONTACT_EMAIL}
    </a>
  );

  return (
    <section className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Données personnelles
        </h1>
        <p className="text-sm text-ink-secondary">
          Cette page décrit{" "}
          <strong className="text-ink">deux traitements distincts</strong>, qui
          n&apos;ont ni les mêmes personnes concernées, ni les mêmes finalités,
          ni les mêmes durées :
        </p>
        <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm text-ink-secondary">
          <li>
            <strong className="text-ink">A. les visiteurs du site</strong> —
            aucun cookie ni traceur, mais des journaux tenus par le serveur web
            (information prévue par l&apos;article 13 du règlement (UE)
            2016/679, dit RGPD) ;
          </li>
          <li>
            <strong className="text-ink">
              B. les personnes figurant dans les données publiées
            </strong>{" "}
            — élus, candidats, représentants d&apos;intérêts : republication de
            données publiques (information collective prévue par
            l&apos;article 14 du RGPD, fournie au titre de son
            article 14(5)(b)).
          </li>
        </ul>
      </header>

      <Card titre="Responsable du traitement">
        <div className="flex flex-col gap-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            Pour ces deux traitements, le responsable est{" "}
            <strong className="text-ink">l&apos;éditeur du site</strong>,
            particulier non professionnel (voir les{" "}
            <Link href="/mentions-legales" className={LIEN}>
              mentions légales
            </Link>
            ). Le site n&apos;est pas hébergé sur une plateforme tierce : il
            est servi par un {HEBERGEUR_NATURE_SERVICE}, loué chez{" "}
            {HEBERGEUR.raisonSociale} et situé en {HEBERGEUR.pays}, que
            l&apos;éditeur administre lui-même. C&apos;est donc lui, et non
            l&apos;hébergeur, qui répond des journaux décrits ci-dessous.
          </p>
          <p>
            Il est joignable par e-mail à {contactEmail} — une demande qui
            concerne une personne n&apos;a pas à être rendue publique.
          </p>
        </div>
      </Card>

      <Card
        titre="A. Visiteurs : aucun traceur, mais des journaux de serveur"
        sousTitre="Information de l'article 13 du RGPD"
      >
        <div className="flex flex-col gap-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            Le site ne dépose <strong className="text-ink">rien</strong> sur
            l&apos;appareil de ses visiteurs : zéro cookie, zéro traceur, zéro
            stockage local, pas de compte, pas de formulaire. Il n&apos;appelle
            aucun service tiers depuis le navigateur et n&apos;embarque aucun
            script de mesure d&apos;audience. Aucun bandeau de consentement
            n&apos;est requis : l&apos;article 82 de la loi Informatique et
            Libertés ne vise que les accès et les inscriptions dans
            l&apos;équipement du visiteur, et il n&apos;y en a aucun.
          </p>
          <p>
            <strong className="text-ink">
              Le serveur web, en revanche, tient des journaux d&apos;accès.
            </strong>{" "}
            Ils enregistrent, pour chaque requête : une adresse IP, la date et
            l&apos;heure, l&apos;adresse de la page demandée, le code de
            réponse, le volume transmis, la page d&apos;origine éventuelle et
            l&apos;identifiant du navigateur (<em>User-Agent</em>). Une adresse
            IP est une donnée à caractère personnel ; ces journaux relèvent donc
            du RGPD. Il y en a{" "}
            <strong className="text-ink">deux, séparés à dessein</strong> :
          </p>
          <ul className="flex list-disc flex-col gap-1.5 pl-5">
            <li>
              <strong className="text-ink">
                Un journal de sécurité, à adresse IP complète
              </strong>{" "}
              (<code>access.log</code>, ainsi que le journal d&apos;erreurs).
              Finalité : la{" "}
              <strong className="text-ink">sécurité du service</strong> —
              détecter et bloquer les attaques (blocage automatique des adresses
              abusives), analyser un incident. Conservation :{" "}
              <strong className="text-ink">52 jours</strong>, puis suppression
              automatique.
            </li>
            <li>
              <strong className="text-ink">
                Un journal d&apos;audience, à adresse IP tronquée
              </strong>{" "}
              (<code>audience.log</code>) : les derniers chiffres de
              l&apos;adresse sont remplacés par un zéro au moment même de
              l&apos;écriture (un quart d&apos;adresse en IPv4, la moitié en
              IPv6), de sorte que le fichier ne permet plus de remonter à un
              abonné. Finalité : la{" "}
              <strong className="text-ink">
                mesure d&apos;audience du site
              </strong>
              , sous forme exclusivement statistique et agrégée. C&apos;est le
              journal que l&apos;outil de statistiques lit en priorité ; pour les
              périodes qu&apos;il ne couvre pas — avant sa mise en place, ou les
              heures d&apos;une journée qu&apos;il n&apos;a pas vues — le journal
              de sécurité est lu à sa place, sans que cela prolonge sa
              conservation ni n&apos;en fasse sortir la moindre adresse.
              Conservation :{" "}
              <strong className="text-ink">400 jours</strong>, cette durée plus
              longue étant permise par la pseudonymisation ; elle sert à
              comparer une année à la suivante.
            </li>
          </ul>
          <p>
            <strong className="text-ink">Base légale</strong> — l&apos;intérêt
            légitime (art. 6(1)(f) RGPD) : assurer la sécurité d&apos;un service
            en accès libre, et en connaître la fréquentation. La journalisation
            est également une mesure de sécurité au sens de l&apos;article 32 du
            RGPD. La conservation retenue est délibérément inférieure à la
            fourchette de six mois à un an admise par la CNIL pour les journaux
            (délibération n° 2021-122 du 14 octobre 2021).
          </p>
          <p>
            <strong className="text-ink">Destinataires</strong> —{" "}
            <strong className="text-ink">aucun</strong>. Les journaux ne quittent
            pas le serveur : ils ne sont ni sauvegardés à l&apos;extérieur, ni
            transmis à un tiers, ni croisés avec un autre fichier. Seul
            l&apos;éditeur y accède, par une connexion d&apos;administration.
            L&apos;hébergeur fournit la machine et n&apos;exploite pas ces
            données pour son compte. Rien de tout cela n&apos;est transféré hors
            de l&apos;Union européenne ; seuls les courriels envoyés à
            l&apos;adresse de contact ci-dessus transitent par la messagerie
            Proton, en Suisse — pays reconnu comme offrant un niveau de
            protection adéquat par la Commission européenne.
          </p>
          <p>
            <strong className="text-ink">
              Aucun profilage, aucune décision automatisée à l&apos;égard
              d&apos;une personne
            </strong>{" "}
            — les journaux ne servent jamais à suivre un individu ni à établir un
            profil. Les statistiques produites sont agrégées et ne contiennent
            aucune adresse IP. Le seul traitement automatisé est le blocage
            temporaire d&apos;une adresse qui attaque le serveur.
          </p>
        </div>
      </Card>

      <Card
        titre="B. Données publiées : finalité et base légale"
        sousTitre="Information de l'article 14 du RGPD"
      >
        <div className="flex flex-col gap-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="text-ink">Finalité</strong> — l&apos;information
            du public sur la vie publique : l&apos;usage de l&apos;argent
            public, les mandats électifs, le lobbying et le financement de la
            vie politique.
          </p>
          <p>
            <strong className="text-ink">Base légale</strong> —
            l&apos;intérêt légitime (art. 6(1)(f) RGPD) : les données
            proviennent de publications rendues obligatoires par la loi. Leur
            réutilisation s&apos;inscrit dans le cadre prévu pour les données
            personnelles figurant dans des documents officiels : article 86 du
            RGPD et article L. 322-2 du code des relations entre le public et
            l&apos;administration (CRPA).
          </p>
        </div>
      </Card>

      <Card titre="B. Données traitées et personnes concernées">
        <div className="flex flex-col gap-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            Le site traite exclusivement des{" "}
            <strong className="text-ink">
              données de responsables publics issues de publications
              officielles ouvertes
            </strong>{" "}
            : élus et titulaires de mandats (répertoire national des élus,
            données des assemblées), déclarations d&apos;intérêts et
            constats publiés par la HATVP, répertoire des représentants
            d&apos;intérêts, comptes des partis et comptes de campagne
            (CNCCFP), votes et activités parlementaires.
          </p>
          {/*
            Art. 14(1)(d) RGPD : quand les données ne sont pas collectées
            auprès de la personne concernée, les CATÉGORIES de données doivent
            être énumérées — pas seulement les sources. Jusqu'au 20/08/2026,
            cette page listait les sources et taisait les catégories : un élu
            ne pouvait pas savoir, en la lisant, que sa date de naissance
            complète figurait sur sa fiche. Elle y figure bien : 1 053 fiches
            la portent, en clair et dans le balisage schema.org, parce que le
            répertoire national des élus et les jeux des assemblées la
            publient. La publier reste licite ; ne pas le dire ne l'était pas.
          */}
          <p>
            <strong className="text-ink">Catégories de données publiées</strong>{" "}
            : nom et prénom ; <strong className="text-ink">date de
            naissance</strong> et âge ; sexe ; profession ou catégorie
            socio-professionnelle ; mandats, fonctions et dates de mandat ;
            circonscription ou collectivité de rattachement ; groupe et
            appartenance politiques ; votes et activités parlementaires ;
            existence et date des déclarations HATVP ainsi que les constats
            publiés par elle ;{" "}
            <strong className="text-ink">
              le contenu des déclarations d&apos;intérêts publiées par la HATVP
            </strong>{" "}
            — mandats et fonctions électives, participations aux organes
            dirigeants d&apos;un organisme, participations financières directes
            dans le capital d&apos;une société, activités professionnelles des
            cinq dernières années, activités de consultant, fonctions bénévoles
            et observations —, ainsi que les{" "}
            <strong className="text-ink">
              montants de rémunération déclarés, année par année
            </strong>{" "}
            qui y figurent, reproduits mot pour mot et datés ; montants déclarés
            dans les comptes de partis et de campagne. Aucune coordonnée privée n&apos;est publiée : ni
            adresse postale personnelle, ni téléphone, ni adresse
            électronique, ni donnée relevant de l&apos;article 9 du RGPD.
          </p>
          {/*
            Même faute que celle décrite plus haut, re-commise le 20/08/2026 au
            soir : deux sources ont été ajoutées (avis de la CADA, registre de
            transparence de l'UE) sans que cette page dise ce qu'elles font
            paraître. Elle le dit maintenant. La CADA n'apporte AUCUNE donnée
            nominative — seuls des dénombrements sont ingérés, jamais le texte
            des avis, qui nomme des responsables publics. Le registre de l'UE,
            lui, publie des organisations, et l'ingestion écarte la catégorie
            « Self-employed individuals » : mais ce filtre est CELUI DE L'UE,
            et il laisse passer des consultants individuels que le registre a
            rangés ailleurs (« Professional consultancies »). Le dire vaut
            mieux que prétendre qu'aucune personne physique ne subsiste, et
            mieux qu'un filtre sur la forme des noms : sur 1 638 inscrits
            français, un critère « deux mots sans marqueur de personne morale »
            en capte 266, presque tous de vraies organisations. On ne devine
            pas la nature juridique d'une entité d'après son nom.
          */}
          <p>
            <strong className="text-ink">
              Représentants d&apos;intérêts inscrits au registre de l&apos;Union
              européenne
            </strong>{" "}
            — depuis le 20/08/2026, le site republie les organisations inscrites
            au registre de transparence commun au Parlement européen et à la
            Commission : raison sociale, acronyme, catégorie, ville du siège,
            fourchette de coûts déclarée. Les personnes accréditées auprès du
            Parlement ne sont jamais reprises, et la catégorie « travailleurs
            indépendants » du registre est exclue de toute liste nominative —
            ses membres ne sont que dénombrés. Cette exclusion suit la
            classification établie par l&apos;Union : quelques consultants
            exerçant en nom propre peuvent donc y échapper si le registre les a
            classés parmi les cabinets de conseil.{" "}
            <strong className="text-ink">
              Si vous êtes dans ce cas, écrivez à {contactEmail} : votre
              inscription sera retirée des listes nominatives du site
            </strong>{" "}
            — sans que cela change quoi que ce soit au registre officiel, qui
            reste seul maître de ce qu&apos;il publie. Le site republie toujours
            moins que lui : ni code postal, ni effectifs, ni dates
            d&apos;inscription, ni accréditations.
          </p>
          <p>
            <strong className="text-ink">Avis et conseils de la CADA</strong>{" "}
            — cette source, ajoutée le même jour, n&apos;apporte{" "}
            <strong className="text-ink">aucune donnée nominative</strong> :
            seuls des dénombrements par administration, année et sens de
            l&apos;avis sont conservés. Le texte des décisions, qui nomme des
            responsables publics dans ses motifs, n&apos;est jamais ingéré.
          </p>
          <p>
            <strong className="text-ink">
              Ce que la source contient et que le site ne publie pas
            </strong>{" "}
            — le contenu des déclarations de situation patrimoniale (biens
            immobiliers, comptes bancaires, valeurs mobilières, assurances-vie,
            véhicules, emprunts) n&apos;est jamais repris : sa divulgation est
            punie par l&apos;article LO 135-2 du code électoral. Ne sont pas
            repris non plus, par choix éditorial et non par obligation,
            l&apos;employeur et la profession du conjoint ni l&apos;identité des
            collaborateurs : ce sont des données sur des tiers qui n&apos;exercent
            aucun mandat.
          </p>
          <p>
            La liste complète des sources — producteur, URL amont, licence,
            date des données, date d&apos;ingestion — est publiée sur la page{" "}
            <Link href="/donnees" className={LIEN}>
              Données
            </Link>
            . La base est reconstruite régulièrement à partir de ces seules
            publications : les durées de conservation sont alignées sur les
            publications amont.
          </p>
          <p>
            <strong className="text-ink">
              Aucun transfert, aucun enrichissement
            </strong>{" "}
            — les données ne sont ni transmises à des tiers, ni croisées avec
            des données non publiques, ni enrichies hors sources publiques
            officielles.
          </p>
        </div>
      </Card>

      <Card titre="Vos droits">
        <div className="flex flex-col gap-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="text-ink">
              Si vous figurez dans les données publiées
            </strong>{" "}
            (volet B) — vous disposez des droits d&apos;accès (art. 15 RGPD), de
            rectification (art. 16) et d&apos;opposition (art. 21), dans les
            limites que la liberté d&apos;information apporte au droit à
            l&apos;effacement (art. 17(3)(a)).
          </p>
          <p>
            <strong className="text-ink">
              Si vous êtes visiteur du site
            </strong>{" "}
            (volet A) — vous disposez, sur les journaux, des droits d&apos;accès
            (art. 15), de rectification (art. 16), d&apos;effacement (art. 17),
            de limitation (art. 18) et d&apos;opposition (art. 21), cette
            dernière pouvant être écartée pour ce qui relève strictement de la
            sécurité du service. Une demande doit préciser la ou les adresses IP
            concernées et la période : sans cela, la recherche est impossible et
            l&apos;éditeur n&apos;est pas tenu de collecter des informations
            supplémentaires pour vous identifier (art. 11 RGPD). Le journal
            d&apos;audience, dont les adresses sont tronquées, ne permet par
            construction d&apos;identifier personne.
          </p>
          <p>
            <strong className="text-ink">Comment exercer ces droits</strong> —
            les demandes se font par e-mail à {contactEmail}, et sont
            traitées sous un mois (art. 12(3) RGPD). Rien n&apos;oblige à
            passer par un canal public pour exercer un droit.
          </p>
          <p>
            Les <strong className="text-ink">signalements d&apos;erreur</strong>{" "}
            qui ne portent pas sur des données personnelles (chiffre faux, lien
            mort, source mal citée) restent les bienvenus sur{" "}
            <a
              href={CONTACT_ISSUES_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={LIEN}
            >
              les issues publiques du dépôt
            </a>
            .
          </p>
          <p>
            <strong className="text-ink">Période électorale</strong> — les
            demandes de rectification émanant de candidats ou de leurs
            représentants sont traitées en priorité, sous 48 heures.
          </p>
          <p>
            Toute personne peut également adresser une réclamation à
            l&apos;autorité de contrôle, la Commission nationale de
            l&apos;informatique et des libertés (CNIL) :{" "}
            <a
              href="https://www.cnil.fr/"
              target="_blank"
              rel="noopener noreferrer"
              className={LIEN}
            >
              www.cnil.fr
            </a>
            .
          </p>
        </div>
      </Card>
    </section>
  );
}
