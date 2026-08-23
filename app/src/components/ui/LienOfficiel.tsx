import type { ReactNode } from "react";

/**
 * Lien sortant vers une fiche du producteur (AN, Sénat, HATVP, BOAMP,
 * Légifrance, Sirene, registre UE). Le nom accessible est le nom de
 * l'entité, jamais « cliquez ici » ni un libellé générique seul.
 *
 * `source` n'est lu que par le lecteur d'écran (« — fiche HATVP (nouvelle
 * fenêtre) ») : le texte visible reste `children`.
 */

const CLASSE =
  "underline decoration-dotted underline-offset-2 transition-colors hover:text-accent";

export function LienOfficiel({
  href,
  source,
  children,
  className,
}: {
  href: string;
  /** Producteur, pour l'accessible name (ex. « HATVP », « Légifrance »). */
  source: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={className ? `${CLASSE} ${className}` : CLASSE}
    >
      {children}
      <span className="sr-only">{` — ${source} (nouvelle fenêtre)`}</span>
      <span aria-hidden="true"> ↗</span>
    </a>
  );
}

/**
 * Puce compacte à côté d'un nom qui mène déjà ailleurs (notre fiche, un
 * bouton de sélection). Accessible name = « AN — fiche AN de <nom> ».
 */
export function PuceOfficielle({
  href,
  libelle,
  nom,
}: {
  href: string;
  libelle: string;
  nom: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="ml-1.5 inline-flex items-center whitespace-nowrap text-[11px] text-ink-muted underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
    >
      {libelle}
      <span className="sr-only">{` — fiche ${libelle} de ${nom} (nouvelle fenêtre)`}</span>
      <span aria-hidden="true"> ↗</span>
    </a>
  );
}
