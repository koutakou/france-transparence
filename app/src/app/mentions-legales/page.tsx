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

export const metadata: Metadata = {
  alternates: { canonical: "/mentions-legales/" },
  title: "Mentions légales",
  description: `Site édité à titre non professionnel par un particulier (art. 1-1, II LCEN), hébergé par ${HEBERGEUR_MENTION}. Contact, droit de réponse et licences du site.`,
};

/** Style commun des liens externes de la page. */
const LIEN = "underline decoration-dotted underline-offset-2 hover:text-ink";

export default function PageMentionsLegales() {
  return (
    <section className="mx-auto flex w-full max-w-3xl flex-col gap-6">
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
            republiées proviennent exclusivement de publications officielles
            ouvertes, diffusées sous{" "}
            <a
              href="https://www.etalab.gouv.fr/licence-ouverte-open-licence/"
              target="_blank"
              rel="noopener noreferrer"
              className={LIEN}
            >
              Licence Ouverte 2.0
            </a>{" "}
            (Etalab). L&apos;attribution, source par source (producteur, URL
            amont, licence, date des données), est publiée sur la page{" "}
            <Link href="/donnees" className={LIEN}>
              Données
            </Link>
            .
          </p>
        </div>
      </Card>
    </section>
  );
}
