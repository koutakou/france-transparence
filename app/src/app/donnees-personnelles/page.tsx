import type { Metadata } from "next";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { CONTACT_ISSUES_URL } from "@/lib/site";

/**
 * Page /donnees-personnelles — information générale prévue par l'article 14
 * du RGPD, fournie au titre de la dérogation « effort disproportionné » de
 * l'art. 14(5)(b) : informer individuellement plus de 36 000 élus serait
 * disproportionné, la mesure appropriée est cette page publique
 * (docs/deploiement/exigences-publiques.md §1.2, reco CNIL juin 2024).
 *
 * Références vérifiées le 19/08/2026 :
 * - GitHub Pages, journalisation des IP des visiteurs : « When a GitHub
 *   Pages site is visited, the visitor's IP address is logged and stored
 *   for security purposes » —
 *   https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages#data-collection
 * - GitHub General Privacy Statement :
 *   https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement
 */

export const metadata: Metadata = {
  title: "Données personnelles",
  description:
    "Information prévue par l'article 14 du RGPD : finalité, base légale, catégories de données de responsables publics republiées, droits des personnes — et zéro collecte sur les visiteurs.",
};

/** Style commun des liens de la page. */
const LIEN = "underline decoration-dotted underline-offset-2 hover:text-ink";

export default function PageDonneesPersonnelles() {
  return (
    <section className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Données personnelles
        </h1>
        <p className="text-sm text-ink-secondary">
          Information générale prévue par l&apos;article 14 du règlement (UE)
          2016/679 (RGPD), fournie au titre de son article 14(5)(b) : ce site
          republie des données publiques concernant plusieurs dizaines de
          milliers de responsables publics, que cette page informe
          collectivement.
        </p>
      </header>

      <Card titre="Responsable du traitement">
        <p className="text-sm leading-relaxed text-ink-secondary">
          L&apos;éditeur du site, particulier non professionnel (voir les{" "}
          <Link href="/mentions-legales" className={LIEN}>
            mentions légales
          </Link>
          ), est responsable du traitement. Il est joignable via le canal de
          contact du site :{" "}
          <a
            href={CONTACT_ISSUES_URL}
            target="_blank"
            rel="noopener noreferrer"
            className={LIEN}
          >
            les issues GitHub du dépôt
          </a>{" "}
          (une adresse e-mail dédiée sera ajoutée prochainement).
        </p>
      </Card>

      <Card titre="Finalité et base légale">
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

      <Card titre="Données traitées et personnes concernées">
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

      <Card titre="Visiteurs : aucune collecte">
        <div className="flex flex-col gap-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            Le site ne collecte <strong className="text-ink">aucune donnée
            sur ses visiteurs</strong> : zéro cookie, zéro traceur,
            pas de mesure d&apos;audience, pas de compte, pas de formulaire.
            Il n&apos;appelle aucun service tiers depuis le navigateur.
            Aucun bandeau de consentement n&apos;est donc requis.
          </p>
          <p>
            Seuls subsistent les journaux techniques de l&apos;hébergeur :
            GitHub Pages enregistre l&apos;adresse IP des visiteurs à des fins
            de sécurité (traitement opéré par GitHub, Inc. — voir la{" "}
            <a
              href="https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages#data-collection"
              target="_blank"
              rel="noopener noreferrer"
              className={LIEN}
            >
              documentation GitHub Pages
            </a>{" "}
            et la{" "}
            <a
              href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement"
              target="_blank"
              rel="noopener noreferrer"
              className={LIEN}
            >
              politique de confidentialité de GitHub
            </a>
            ).
          </p>
        </div>
      </Card>

      <Card titre="Vos droits">
        <div className="flex flex-col gap-3 text-sm leading-relaxed text-ink-secondary">
          <p>
            Toute personne concernée dispose des droits d&apos;accès
            (art. 15 RGPD), de rectification (art. 16) et d&apos;opposition
            (art. 21), dans les limites que la liberté d&apos;information
            apporte au droit à l&apos;effacement (art. 17(3)(a)). Les demandes
            se font via{" "}
            <a
              href={CONTACT_ISSUES_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={LIEN}
            >
              les issues GitHub du dépôt
            </a>{" "}
            et sont traitées sous un mois (art. 12(3) RGPD).
          </p>
          <p>
            <strong className="text-ink">Période électorale</strong> — les
            demandes de rectification émanant de candidats ou de leurs
            représentants sont traitées en priorité, sous 48 heures.
          </p>
          <p>
            Toute personne peut également adresser une réclamation à la CNIL :{" "}
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
