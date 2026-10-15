import { type Colonne } from "@/components/ui/DataTable";
import { LienOfficiel } from "@/components/ui/LienOfficiel";
import { Money } from "@/components/ui/Money";
import { formatNombre } from "@/lib/format";
import type { TopAcheteur } from "@/lib/queries/marches";
import { urlAnnuaireEntreprise } from "@/lib/urlOfficielle";

/*
 * Cellules et colonnes de /marches, partagées par la page (rendu serveur) et
 * ses îles client (components/client/TablesMarches.tsx) : aucun import
 * serveur (le type TopAcheteur n'est qu'un type).
 */

/** Tronque proprement un libellé long (le `title` porte le texte complet). */
export function tronque(s: string | null, max: number): string {
  if (!s || s.trim() === "") return "—";
  return s.length > max ? `${s.slice(0, max - 1).trimEnd()}…` : s;
}

/** Annuaire Sirene seulement si le SIREN est dans S18 (9 chiffres, LEFT JOIN). */
export function hrefAnnuaire(a: { siren: string | null; dans_sirene: number }): string | null {
  return a.dans_sirene === 1 ? urlAnnuaireEntreprise(a.siren) : null;
}

export function NomEntreprise({
  nom,
  siren,
  dans_sirene,
  max,
}: {
  nom: string | null;
  siren: string | null;
  dans_sirene: number;
  max: number;
}) {
  const href = hrefAnnuaire({ siren, dans_sirene });
  const texte = <span title={nom ?? undefined}>{tronque(nom, max)}</span>;
  return href ? (
    <LienOfficiel href={href} source="Sirene">
      {texte}
    </LienOfficiel>
  ) : (
    texte
  );
}

export function CelluleSiren({ siren, dans_sirene }: { siren: string | null; dans_sirene: number }) {
  if (!siren) return "—";
  const href = hrefAnnuaire({ siren, dans_sirene });
  return href ? (
    <LienOfficiel href={href} source="Sirene">
      {siren}
    </LienOfficiel>
  ) : (
    siren
  );
}

/**
 * Colonnes de montant des deux classements. Le rang se fixe sur la part
 * HORS SUSPECTS ; la part que le drapeau « montant suspect » recouvre est
 * montrée dans sa propre colonne (montant, puis nombre de marchés entre
 * parenthèses) — jamais retirée, jamais additionnée à la première à
 * l'écran. Pas d'étiquette par cellule : l'en-tête la porte, et 20 cellules
 * ×2 (HTML + charge RSC) pesaient ~40 Ko sur une page déjà au-delà du
 * budget de 500 Ko.
 */
export const COLONNES_MONTANT_TOP: Colonne<
  Pick<TopAcheteur, "montant_hors_suspects" | "montant_suspects" | "nb_marches_suspects">
>[] = [
  {
    cle: "montant_hors_suspects",
    entete: "Montant hors suspects",
    type: "montant",
    rendu: (a) =>
      a.montant_hors_suspects === null ? "—" : <Money valeur={a.montant_hors_suspects} />,
  },
  {
    cle: "montant_suspects",
    entete: "Montants suspects",
    type: "montant",
    rendu: (a) =>
      a.nb_marches_suspects === 0 ? (
        "—"
      ) : (
        <>
          {a.montant_suspects === null ? "—" : <Money valeur={a.montant_suspects} />}{" "}
          <span className="text-[11px] text-ink-muted">
            ({formatNombre(a.nb_marches_suspects)})
          </span>
        </>
      ),
  },
];

/** Étiquette « suspect » : icône statut + libellé (jamais la couleur seule). */
export function EtiquetteSuspect() {
  return (
    <span
      className="inline-flex items-center gap-1 text-[11px] text-ink-muted"
      title="Montant classé suspect : anomalie signalée à la source, ou montant supérieur à 100 M€ (écrêté dans les agrégats)."
    >
      <svg width="10" height="10" viewBox="0 0 14 14" aria-hidden="true" style={{ color: "var(--status-warning)" }}>
        <path d="M7 1.5L13 12H1z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M7 5.4v3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="7" cy="10.2" r="0.9" fill="currentColor" />
      </svg>
      suspect
    </span>
  );
}

/** Fiche d'une consultation PLACE, pas le portail générique. */
export function hrefConsultation(url: string | null): string | null {
  if (!url || !url.includes("/consultation/")) return null;
  return url;
}
