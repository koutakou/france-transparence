import type { Metadata } from "next";
import Link from "next/link";
import { Fragment } from "react";
import { Card } from "@/components/ui/Card";
import {
  HEBERGEUR,
  HEBERGEUR_MENTION,
  HEBERGEUR_NATURE_SERVICE,
  HEBERGEUR_SUPPORT_LIBELLE,
  HEBERGEUR_TELEPHONE_LIEN,
} from "@/lib/hebergeur";
import { CONTACT_EMAIL, CONTACT_ISSUES_URL, REPO_URL } from "@/lib/site";
import { JsonLd } from "@/components/JsonLd";
import { jsonLdPage, metadonneesPage } from "@/lib/seo";

/**
 * Page /mentions-legales — obligations d'identification de la LCEN
 * (loi n° 2004-575 du 21 juin 2004, art. 1-1 dans sa rédaction issue de la
 * loi SREN n° 2024-449 du 21 mai 2024).
 *
 * Régime retenu : ÉDITEUR NON PROFESSIONNEL ANONYME (art. 1-1, II LCEN) —
 * seuls le nom et l'adresse de l'hébergeur sont publiés, l'identité complète
 * de l'éditeur étant communiquée à l'hébergeur. Le nom du directeur de la
 * publication n'a pas à être publié dans ce régime (art. 93-2 de la loi
 * n° 82-652 du 29 juillet 1982 ; docs/deploiement/exigences-publiques.md §1.1).
 *
 * L'identité de l'hébergeur n'est PAS écrite ici : c'est une donnée de
 * déploiement (elle change avec la machine, pas avec le code). Elle vient de
 * src/lib/hebergeur.ts, qui porte aussi la traçabilité de sa vérification.
 */

// Chemin, titre et description nommés UNE FOIS : les métadonnées et le
// balisage JSON-LD décrivent la même page, ils ne peuvent donc pas la
// décrire différemment le jour où l'un des deux est retouché. La description
// cite l'hébergeur RÉEL (src/lib/hebergeur.ts) : si la machine change, les
// deux descriptions changent ensemble.
const CHEMIN = "/mentions-legales/";
const TITRE = "Mentions légales";
const DESCRIPTION = `Site édité à titre non professionnel par un particulier (art. 1-1, II LCEN), hébergé par ${HEBERGEUR_MENTION}. Contact, droit de réponse et licences du site.`;

export const metadata: Metadata = metadonneesPage({
  chemin: CHEMIN,
  titre: TITRE,
  description: DESCRIPTION,
});

// `AboutPage` : seule page du site dont l'objet est LE SITE LUI-MÊME — qui
// l'édite, qui l'héberge, comment le joindre — et non les données publiques
// qu'il met en scène. C'est un sous-type de `WebPage`, donc rien n'est perdu
// pour un consommateur qui l'ignore.
//
// AUCUN nœud `Organization` ici, alors que la page nomme l'hébergeur : le
// balisage décrirait ALORS L'HÉBERGEUR comme l'entité de cette page, et
// l'éditeur — un particulier qui use du régime d'anonymat de l'art. 1-1, II
// LCEN — ne peut pas davantage être balisé sans le nommer. Le seul nœud
// d'identité du site, le `Project` de l'accueil, n'est pas une personne
// morale : le poser en `mainEntity` de mentions légales laisserait croire à
// un éditeur constitué, ce que la page dit précisément ne pas être le cas.
const BALISAGE = jsonLdPage({
  chemin: CHEMIN,
  nom: TITRE,
  description: DESCRIPTION,
  type: "AboutPage",
  ariane: [{ nom: "Accueil", chemin: "/" }, { nom: TITRE }],
});

/** Style commun des liens externes de la page. */
const LIEN = "underline decoration-dotted underline-offset-2 hover:text-ink";

export default function PageMentionsLegales() {
  return (
    <section className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <JsonLd donnees={BALISAGE} />
      <header className="flex flex-col gap-2">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Mentions légales
        </h1>
        <p className="text-sm text-ink-secondary">
          Informations prévues par l&apos;article 1-1 de la loi n° 2004-575 du
          21 juin 2004 pour la confiance dans l&apos;économie numérique (LCEN),
          dans sa rédaction issue de la loi n° 2024-449 du 21 mai 2024.
        </p>
      </header>

      <Card titre="Éditeur">
        <div className="flex flex-col gap-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            Ce site est édité <strong className="text-ink">à titre non
            professionnel par un particulier</strong>, en application de
            l&apos;article 1-1, II, de la LCEN. Conformément à ce texte,
            l&apos;éditeur a communiqué ses éléments d&apos;identification
            personnelle à l&apos;hébergeur, qui les tient à la disposition de
            l&apos;autorité judiciaire et est tenu au secret professionnel à
            leur égard.
          </p>
          <p>
            En régime d&apos;édition non professionnelle, le nom du directeur
            de la publication n&apos;est pas publié (art. 93-2 de la loi
            n° 82-652 du 29 juillet 1982 ; art. 1-1, II et III LCEN).
          </p>
        </div>
      </Card>

      <Card titre="Hébergeur">
        <div className="flex flex-col gap-3 text-sm leading-relaxed text-ink-secondary">
          <p className="text-ink">
            {HEBERGEUR.raisonSociale}
            {HEBERGEUR.adresse.map((ligne) => (
              <Fragment key={ligne}>
                <br />
                {ligne}
              </Fragment>
            ))}
            <br />
            {HEBERGEUR.pays}
          </p>
          <p>{HEBERGEUR.formeJuridique}</p>
          {/*
            Téléphone : exigé par l'art. 1-1, III de la LCEN au même titre que
            la raison sociale et l'adresse. Un formulaire de support ne s'y
            substitue pas — c'est la mention qui manquait jusqu'au 20/08/2026.
          */}
          <p>
            Téléphone :{" "}
            <a href={HEBERGEUR_TELEPHONE_LIEN} className={LIEN}>
              {HEBERGEUR.telephone}
            </a>
          </p>
          <p>
            Service d&apos;hébergement :{" "}
            <a
              href={HEBERGEUR.serviceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={LIEN}
            >
              {HEBERGEUR.serviceNom}
            </a>{" "}
            ({HEBERGEUR_NATURE_SERVICE}). L&apos;hébergeur peut être contacté
            via son support :{" "}
            <a
              href={HEBERGEUR.supportUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={LIEN}
            >
              {HEBERGEUR_SUPPORT_LIBELLE}
            </a>{" "}
            ou son{" "}
            <a
              href={HEBERGEUR.contactUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={LIEN}
            >
              formulaire de contact
            </a>
            .
          </p>
          <p>
            Les demandes de droit de réponse peuvent être adressées à
            l&apos;hébergeur, qui les transmet sans délai au directeur de la
            publication.
          </p>
        </div>
      </Card>

      <Card titre="Contact">
        <div className="flex flex-col gap-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            Le site dispose d&apos;une adresse de contact :{" "}
            <a href={`mailto:${CONTACT_EMAIL}`} className={LIEN}>
              {CONTACT_EMAIL}
            </a>
            . C&apos;est par elle que passent les demandes qui concernent une
            personne — rectification, opposition, exercice des droits prévus
            par le RGPD : elles n&apos;ont pas à être rendues publiques.
          </p>
          <p>
            Les signalements d&apos;erreur qui ne portent sur aucune donnée
            personnelle (chiffre faux, lien mort, source mal citée) peuvent
            aussi être déposés publiquement sur{" "}
            <a
              href={CONTACT_ISSUES_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={LIEN}
            >
              les issues GitHub du dépôt
            </a>
            , où ils profitent à tout le monde.
          </p>
          <p className="text-xs text-ink-muted">
            Les demandes portant sur des données personnelles sont traitées
            selon les modalités décrites sur la page{" "}
            <Link href="/donnees-personnelles" className={LIEN}>
              Données personnelles
            </Link>
            .
          </p>
        </div>
      </Card>

      <Card titre="Licences">
        <div className="flex flex-col gap-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            <strong className="text-ink">Code source du site</strong> — publié
            dans le dépôt{" "}
            <a
              href={REPO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={LIEN}
            >
              koutakou/france-transparence
            </a>
            , sous la licence indiquée dans ce dépôt.
          </p>
          <p>
            <strong className="text-ink">Données</strong> — les données
            republiées proviennent exclusivement de publications officielles.
            Leur licence, en revanche, n&apos;est pas uniforme : la plupart des
            sources sont diffusées sous{" "}
            <a
              href="https://www.etalab.gouv.fr/licence-ouverte-open-licence/"
              target="_blank"
              rel="noopener noreferrer"
              className={LIEN}
            >
              Licence Ouverte
            </a>{" "}
            (Etalab), d&apos;autres relèvent d&apos;un régime distinct —
            décision 2011/833/UE pour les documents de la Commission
            européenne, textes publiés au Journal officiel, publications
            officielles hors open data. La licence exacte est indiquée source
            par source sur la page{" "}
            <Link href="/donnees" className={LIEN}>
              Données
            </Link>
            , avec le producteur, l&apos;URL amont et la date des données :
            c&apos;est elle qui fait foi, et non le présent résumé.
          </p>
        </div>
      </Card>
    </section>
  );
}
