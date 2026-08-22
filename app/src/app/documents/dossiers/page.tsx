import type { Metadata } from "next";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { JsonLd } from "@/components/JsonLd";
import { NoticeLecture } from "@/components/ui/NoticeLecture";
import { DataTable, type Colonne } from "@/components/ui/DataTable";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { KpiTile } from "@/components/ui/KpiTile";
import { libelleTypeDole } from "@/lib/dole-libelles";
import { formatNombre } from "@/lib/format";
import {
  getDole,
  libelleLegislatureDole,
  perimetreDoleNavette,
  perimetreDoleStock,
  type DoleNavetteLigne,
} from "@/lib/queries/dole";
import { jsonLdPage, metadonneesPage } from "@/lib/seo";

/**
 * Dossiers législatifs DILA (S43, fonds DOLE). Page STATIQUE, distincte
 * du Journal officiel du jour (S3). Pas d'onglet de navigation : lien
 * interne depuis /documents. Liens Légifrance sortants uniquement.
 */

const CHEMIN = "/documents/dossiers/";
const TITRE = "Dossiers législatifs";
const DESCRIPTION =
  "Dossiers législatifs DILA : stock du fichier, navette de la législature en cours, lois et ordonnances publiées. Liens vers Légifrance.";

export const metadata: Metadata = metadonneesPage({
  chemin: CHEMIN,
  titre: TITRE,
  description: DESCRIPTION,
});

const BALISAGE = jsonLdPage({
  chemin: CHEMIN,
  nom: TITRE,
  description: DESCRIPTION,
  ariane: [
    { nom: "Accueil", chemin: "/" },
    { nom: "Documents", chemin: "/documents/" },
    { nom: TITRE },
  ],
});

const COLONNES_NAVETTE: Colonne<DoleNavetteLigne>[] = [
  { cle: "titre", entete: "Titre" },
  {
    cle: "type",
    entete: "Type",
    largeur: "11rem",
    rendu: (l) => libelleTypeDole(l.type),
  },
  { cle: "date_modif", entete: "Mise à jour", type: "date", largeur: "8rem" },
  {
    cle: "derniere_etape",
    entete: "Dernière étape",
    rendu: (l) => l.derniere_etape || "—",
  },
  {
    cle: "lien_legifrance",
    entete: "Lien",
    largeur: "7rem",
    rendu: (l) => (
      <a
        href={l.lien_legifrance}
        target="_blank"
        rel="noopener noreferrer"
        className="whitespace-nowrap text-ink-secondary underline decoration-dotted underline-offset-2 transition-colors hover:text-ink"
      >
        Légifrance<span aria-hidden="true"> ↗</span>
        <span className="sr-only"> (nouvelle fenêtre)</span>
      </a>
    ),
  },
];

export default async function DossiersLegislatifsPage() {
  const dole = getDole();

  if (!dole) {
    return (
      <section className="flex flex-col gap-6">
        <JsonLd donnees={BALISAGE} />
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
          Dossiers législatifs
        </h1>
        <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
          <p>
            La table des dossiers législatifs est absente de la base. Aucun
            chiffre n’est affiché. Retour aux{" "}
            <Link
              href="/documents/"
              className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
            >
              documents du Journal officiel
            </Link>
            .
          </p>
        </div>
      </section>
    );
  }

  const libLeg = libelleLegislatureDole(dole.legislatureCourante);

  return (
    <section className="flex flex-col gap-6">
      <JsonLd donnees={BALISAGE} />
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="max-w-3xl">
          <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
            Dossiers législatifs
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-secondary">
            Métadonnées des dossiers législatifs du fonds DILA (DOLE)&nbsp;:
            où en est un texte, sans classement. Distinct du{" "}
            <Link
              href="/documents/"
              className="underline decoration-dotted underline-offset-2 hover:text-ink"
            >
              Journal officiel du jour
            </Link>
            . La navette ci-dessous est celle de la {libLeg}.
          </p>
        </div>
        <FreshnessBadge
          dateDonnees={dole.meta.date_donnees}
          source={dole.meta.nom}
          frequence={dole.meta.frequence}
          url={dole.meta.url}
        />
      </header>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiTile
          label="Dossiers au fichier"
          valeur={formatNombre(dole.nbDossiers)}
          perimetre={perimetreDoleStock(dole)}
        />
        <KpiTile
          label="En navette"
          valeur={formatNombre(dole.nbNavette)}
          perimetre={perimetreDoleNavette(dole.legislatureCourante)}
        />
        <KpiTile
          label="Lois publiées au fichier"
          valeur={formatNombre(dole.nbLoisPubliees)}
          perimetre="lois publiées au fichier DILA, toutes législatures du stock"
        />
        <KpiTile
          label="Ordonnances publiées au fichier"
          valeur={formatNombre(dole.nbOrdonnancesPubliees)}
          perimetre="ordonnances publiées au fichier DILA, toutes législatures du stock"
        />
      </div>

      <NoticeLecture
        ancre="dossiers-legislatifs"
        commentLire={
          <p>
            Chaque dossier est un texte de l’article 39 de la Constitution
            (ou de l’article 53, hors forme simplifiée). La navette affichée
            est celle de la législature en cours : un projet d’une
            législature close n’est pas «&nbsp;en cours&nbsp;», même si son
            type reste «&nbsp;projet&nbsp;» dans le fichier.
          </p>
        }
        provenance={
          <p>
            Dumps XML DILA du fonds DOLE (Freemium puis incréments,
            last-write-wins), Licence Ouverte 2.0. Producteur&nbsp;: DILA ;
            catalogue data.gouv «&nbsp;dole-les-dossiers-legislatifs&nbsp;»,
            organisation Premier ministre. Chaque dossier renvoie vers
            Légifrance (lien sortant, le texte n’est pas recopié ici).
          </p>
        }
        limites={
          <p>
            Ce n’est pas le total des propositions de loi déposées : les PPL
            n’entrent dans le fichier qu’après adoption par la première
            assemblée, depuis la réforme de 2008. Ce n’est pas l’exposé des
            motifs, ni l’échéancier d’application des lois, ni le droit
            consolidé (LEGI). Ce n’est pas le Journal officiel du jour
            (source S3, page Documents).
          </p>
        }
      />

      <Card
        titre={`Navette — ${libLeg}`}
        sousTitre="Projets de loi, propositions de loi et projets d’ordonnance de la législature en cours, du plus récemment mis à jour au plus ancien"
      >
        <DataTable
          hauteurMax="36rem"
          colonnes={COLONNES_NAVETTE}
          lignes={dole.navette}
          cleLigne={(l) => l.dossier_id}
          vide="Aucun dossier en navette pour la législature en cours"
        />
      </Card>
    </section>
  );
}
