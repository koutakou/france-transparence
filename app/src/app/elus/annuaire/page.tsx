import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/JsonLd";
import { Card } from "@/components/ui/Card";
import { urlSite } from "@/lib/basePath";
import { formatNombre } from "@/lib/format";
import { getAnnuaireFiches } from "@/lib/queries/annuaire-elus";
import { jsonLdPage, metadonneesPage } from "@/lib/seo";

/**
 * Annuaire des fiches d'élus : un lien HTML vers chaque fiche /elus/<id>.
 * Sans lui, les tableaux de /elus (premier écran seulement, le reste au
 * geste depuis un fragment JSON) laissaient la plupart des fiches sans
 * aucun lien entrant : atteignables par le sitemap ou par la recherche
 * JavaScript, invisibles sans JavaScript et pour un robot qui ne lit pas
 * le sitemap. Aucun compte n'est écrit ici : il dérive à chaque ingestion.
 */
const CHEMIN = "/elus/annuaire/";
const TITRE = "Annuaire des fiches d’élus";
const DESCRIPTION =
  "Toutes les fiches individuelles publiées par le site — député·es, sénateur·rices, président·es de conseil régional et départemental — en ordre alphabétique.";

export const metadata: Metadata = metadonneesPage({
  chemin: CHEMIN,
  titre: TITRE,
  description: DESCRIPTION,
});

const BALISAGE = jsonLdPage({
  chemin: CHEMIN,
  nom: TITRE,
  description: DESCRIPTION,
  type: "CollectionPage",
  ariane: [
    { nom: "Accueil", chemin: "/" },
    { nom: "Élus & institutions", chemin: "/elus/" },
    { nom: TITRE },
  ],
});

export default function PageAnnuaireElus() {
  const sections = getAnnuaireFiches();
  return (
    <section className="flex flex-col gap-6">
      <JsonLd donnees={BALISAGE} />
      <header className="flex flex-col gap-2">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">{TITRE}</h1>
        <p className="max-w-3xl text-sm text-ink-secondary">
          Un lien vers chaque fiche individuelle du site, par type de mandat et en ordre
          alphabétique. Une fiche que les données rattachent à deux de ces mandats figure
          dans les deux listes.
          Groupes, départements et taux de participation se lisent sur la page{" "}
          <Link
            href="/elus/"
            className="underline decoration-dotted underline-offset-2 hover:text-ink"
          >
            Élus &amp; institutions
          </Link>
          .
        </p>
      </header>
      {sections === null ? (
        <p className="text-sm text-ink-muted">Base de données absente : aucune fiche à lister.</p>
      ) : (
        sections.map((s) => (
          <Card key={s.titre} titre={`${s.titre} (${formatNombre(s.fiches.length)})`}>
            {/* Liens <a> simples, style posé UNE FOIS sur la liste : un
                composant Link par fiche (props sérialisées dans le payload
                RSC, classes répétées) faisait passer la page au-dessus de
                500 Ko. La navigation complète vers une fiche est voulue :
                aucun préchargement de mille fiches. */}
            <ul className="columns-1 gap-6 text-[13px] leading-7 sm:columns-2 lg:columns-3 [&>li]:break-inside-avoid [&_a]:text-ink-secondary [&_a]:underline [&_a]:decoration-dotted [&_a]:underline-offset-2 [&_a:hover]:text-ink">
              {s.fiches.map((f) => (
                <li key={f.id}>
                  <a href={urlSite(`/elus/${encodeURIComponent(f.id)}/`)}>
                    {f.prenom ? `${f.nom} ${f.prenom}` : f.nom}
                  </a>
                </li>
              ))}
            </ul>
          </Card>
        ))
      )}
    </section>
  );
}
