"use client";

import { DataTable } from "@/components/ui/DataTable";
import { LienOfficiel } from "@/components/ui/LienOfficiel";
import { Money } from "@/components/ui/Money";
import {
  COLONNES_MONTANT_TOP,
  CelluleSiren,
  EtiquetteSuspect,
  NomEntreprise,
  hrefConsultation,
  tronque,
} from "@/components/ui/CellulesMarches";
import { formatPct } from "@/lib/format";
import type {
  PublicationAnnee,
  DernierMarche,
  MarcheAVenir,
  RepartitionProcedure,
  TopAcheteur,
  TopTitulaire,
} from "@/lib/queries/marches";
import type { DecisionAdlc } from "@/lib/queries/adlc";

/**
 * Tableaux de /marches à rendu personnalisé, en ÎLES CLIENT (budget de
 * 500 Ko de HTML) : même HTML statique, lisible sans JavaScript, mais le
 * payload RSC ne porte plus que les lignes au lieu de l'arbre d'éléments de
 * chaque cellule. Colonnes reprises telles quelles de la page, qui ne passe
 * que les champs affichés.
 */

export function TableTopAcheteurs({ lignes }: { lignes: Omit<TopAcheteur, "montant_total">[] }) {
  return (
    <DataTable
      colonnes={[
        { cle: "rang", entete: "Rang", type: "nombre", largeur: "3.5rem" },
        {
          cle: "nom",
          entete: "Acheteur",
          rendu: (a) => (
            <NomEntreprise nom={a.nom} siren={a.siren} dans_sirene={a.dans_sirene} max={60} />
          ),
        },
        {
          cle: "siren",
          entete: "SIREN",
          rendu: (a) => <CelluleSiren siren={a.siren} dans_sirene={a.dans_sirene} />,
        },
        {
          cle: "nb_etablissements",
          entete: "Établissements",
          type: "nombre",
        },
        { cle: "nb_marches", entete: "Marchés", type: "nombre" },
        ...COLONNES_MONTANT_TOP,
      ]}
      lignes={lignes}
      cleLigne={(a) => String(a.rang)}
    />
  );
}

export function TableTopTitulaires({ lignes }: { lignes: Omit<TopTitulaire, "montant_total">[] }) {
  return (
    <DataTable
      colonnes={[
        { cle: "rang", entete: "Rang", type: "nombre", largeur: "3.5rem" },
        {
          cle: "nom",
          entete: "Titulaire",
          rendu: (t) => (
            <NomEntreprise nom={t.nom} siren={t.siren} dans_sirene={t.dans_sirene} max={60} />
          ),
        },
        {
          cle: "siren",
          entete: "SIREN",
          rendu: (t) => <CelluleSiren siren={t.siren} dans_sirene={t.dans_sirene} />,
        },
        { cle: "categorie", entete: "Catégorie", rendu: (t) => t.categorie ?? "—" },
        {
          cle: "nb_etablissements",
          entete: "Établissements",
          type: "nombre",
        },
        { cle: "nb_marches", entete: "Marchés", type: "nombre" },
        ...COLONNES_MONTANT_TOP,
      ]}
      lignes={lignes}
      cleLigne={(t) => String(t.rang)}
    />
  );
}

export function TableProcedures({ lignes, total }: { lignes: RepartitionProcedure[]; total: number }) {
  return (
    <DataTable
      colonnes={[
        {
          cle: "valeur",
          entete: "Procédure",
          rendu: (r) => r.valeur ?? "Non renseigné",
        },
        { cle: "nb_marches", entete: "Marchés", type: "nombre" },
        {
          cle: "part",
          entete: "Part",
          type: "pourcent",
          rendu: (r) =>
            total > 0
              ? formatPct((100 * r.nb_marches) / total)
              : "—",
        },
        {
          cle: "montant_total",
          entete: "Montant (écrêté)",
          type: "montant",
          rendu: (r) =>
            r.montant_total === null ? "—" : <Money valeur={r.montant_total} />,
        },
      ]}
      lignes={lignes}
      cleLigne={(r) => r.valeur ?? "(non renseigné)"}
    />
  );
}

export function TableDerniersMarches({ lignes }: { lignes: Omit<DernierMarche, "rang">[] }) {
  return (
    <DataTable
      colonnes={[
        { cle: "date_notification", entete: "Notifié le", type: "date", largeur: "6.5rem" },
        {
          cle: "acheteur_nom",
          entete: "Acheteur",
          rendu: (m) => (
            <span title={m.acheteur_nom ?? undefined}>{tronque(m.acheteur_nom, 48)}</span>
          ),
        },
        {
          cle: "objet",
          entete: "Objet",
          rendu: (m) => <span title={m.objet ?? undefined}>{tronque(m.objet, 80)}</span>,
        },
        {
          cle: "titulaire_nom",
          entete: "Titulaire",
          rendu: (m) => (
            <span title={m.titulaire_nom ?? undefined}>
              {tronque(m.titulaire_nom, 36)}
              {m.nb_titulaires > 1 && (
                <span className="text-ink-muted"> +{m.nb_titulaires - 1} co-tit.</span>
              )}
            </span>
          ),
        },
        {
          cle: "montant_retenu",
          entete: "Montant",
          type: "montant",
          rendu: (m) =>
            m.montant_retenu === null ? (
              <span title="Montant non renseigné à la source">—</span>
            ) : (
              <span className="inline-flex items-baseline gap-1.5">
                <Money valeur={m.montant_retenu} />
                {(m.techniques ?? "").includes("Accord-cadre") && (
                  <span
                    className="text-[11px] text-ink-muted"
                    title="Accord-cadre : le montant notifié est un maximum, pas du dépensé."
                  >
                    max
                  </span>
                )}
                {m.montant_suspect === 1 && <EtiquetteSuspect />}
              </span>
            ),
        },
      ]}
      lignes={lignes}
      cleLigne={(m) => m.uid}
      vide="Aucun marché dans le flux"
    />
  );
}

export function TableAchatsAnnonces({ lignes }: { lignes: MarcheAVenir[] }) {
  return (
    <DataTable
      colonnes={[
        {
          cle: "date_prev_publication",
          entete: "Publication prévue",
          type: "date",
          largeur: "8rem",
        },
        {
          cle: "intitule",
          entete: "Intitulé",
          rendu: (m) => {
            const texte = (
              <span title={m.intitule ?? undefined}>{tronque(m.intitule, 70)}</span>
            );
            const href = hrefConsultation(m.lien_consultation);
            return href ? (
              <LienOfficiel href={href} source="PLACE">
                {texte}
              </LienOfficiel>
            ) : (
              texte
            );
          },
        },
        {
          cle: "acheteur_nom",
          entete: "Acheteur",
          rendu: (m) =>
            m.acheteur_nom || m.acheteur_siren ? (
              <NomEntreprise
                nom={m.acheteur_nom ?? `SIREN ${m.acheteur_siren}`}
                siren={m.acheteur_siren}
                dans_sirene={m.dans_sirene}
                max={48}
              />
            ) : (
              "—"
            ),
        },
        {
          cle: "categorie_achat",
          entete: "Catégorie",
          rendu: (m) => m.categorie_achat ?? "—",
        },
        {
          cle: "montant_estime_tranche",
          entete: "Tranche de montant",
          rendu: (m) =>
            m.montant_estime_tranche ?? (
              <span className="text-ink-muted">non publié</span>
            ),
        },
      ]}
      lignes={lignes}
      cleLigne={(m) => m.code}
      vide="Aucun achat annoncé"
    />
  );
}

export function TableAnneesPublication({ lignes }: { lignes: PublicationAnnee[] }) {
  return (
    <DataTable
      colonnes={[
        {
          cle: "annee",
          entete: "Année",
          largeur: "4.5rem",
          rendu: (a) => String(a.annee),
        },
        { cle: "nb_marches", entete: "Marchés", type: "nombre" },
        { cle: "nb_dans_delai", entete: "Dans le délai", type: "nombre" },
        { cle: "taux_dans_delai", entete: "Part", type: "pourcent" },
        {
          cle: "delai_median",
          entete: "Délai médian (j)",
          type: "nombre",
        },
        { cle: "nb_plus_un_an", entete: "Plus d’un an", type: "nombre" },
        {
          cle: "cohorte_close",
          entete: "Cohorte",
          rendu: (a) =>
            a.cohorte_close === 1 ? "Close" : "Provisoire",
        },
      ]}
      lignes={lignes}
      cleLigne={(a) => String(a.annee)}
      vide="Aucune année mesurée"
    />
  );
}

export function TableDecisionsAdlc({ lignes }: { lignes: DecisionAdlc[] }) {
  return (
    <DataTable<DecisionAdlc>
      colonnes={[
        {
          cle: "date_decision",
          entete: "Décision",
          type: "date",
        },
        {
          cle: "id_decision",
          entete: "Référence",
          rendu: (d) =>
            d.url_site ? (
              <LienOfficiel href={d.url_site} source="ADLC">
                {d.id_decision}
              </LienOfficiel>
            ) : (
              d.id_decision
            ),
        },
        {
          cle: "montant_total",
          entete: "Montant",
          type: "euros",
        },
        {
          cle: "sous_titre",
          entete: "Objet",
          rendu: (d) => (
            <span title={d.sous_titre ?? undefined}>
              {tronque(d.sous_titre, 72)}
            </span>
          ),
        },
      ]}
      lignes={lignes}
      cleLigne={(d) => d.id_decision}
    />
  );
}
