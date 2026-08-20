"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { StatStrip } from "@/components/ui/StatStrip";
import { TableTronquee } from "@/components/client/TableTronquee";
import { formatNombre, formatPct } from "@/lib/format";
import { urlSite } from "@/lib/basePath";
// IMPORTATION DE TYPES SEULEMENT (`import type`, effacée à la compilation) :
// `@/lib/queries/elections` ouvre la base SQLite via `@/lib/db`. Une
// importation de valeur embarquerait better-sqlite3 et `node:fs` dans le
// bundle navigateur, et le build échouerait sur « Can't resolve 'fs' ».
// Les formules d'affichage vivent donc ici, et elles sont PURES.
import type {
  DonneesElections,
  DonneesElectionsInline,
  Effectifs,
  LigneCompacte,
  LigneParticipation,
  Scrutin,
} from "@/lib/queries/elections";

/**
 * Participation électorale (source S26, ministère de l'Intérieur) — bloc de
 * la page /collectivites. Un scrutin à la fois : le HTML n'embarque que le
 * SCRUTIN INITIAL (choisi par `getDonneesElectionsInline`, rendu serveur
 * complet, lisible sans JavaScript) et les résumés qui dessinent les
 * 7 boutons. Les six autres scrutins vivent dans le fragment statique
 * /data/elections.json, chargé au premier changement de scrutin puis servi
 * depuis la mémoire — même mécanique que le fond de carte de
 * `CarteDepartements` (promesse mémoïsée au niveau module : une seule
 * requête, quelle que soit la suite des clics).
 *
 * Ce que ce composant N'AFFICHE PAS, et pourquoi (docs/ELECTIONS.md) :
 * - aucune nuance politique : qualification préfectorale, vide à 25,2 % sur
 *   les municipales 2026, grille incompatible entre 2020 et 2026, contestée
 *   devant le Conseil d'État ;
 * - aucun nom de candidat, à aucune étape ;
 * - aucun bureau de vote : agrégats commune et département seulement.
 *
 * Règles d'affichage tenues ici :
 * - **aucun taux n'est stocké** : tout est recalculé sur les effectifs bruts
 *   et vaut « — » (pas 0) si le dénominateur manque ;
 * - si le fragment ne se charge pas, le scrutin INITIAL reste affiché et
 *   l'échec est DIT — jamais un tableau vide, jamais des zéros ;
 * - une commune absente d'un scrutin est DITE absente, et la raison est
 *   donnée — elle n'apparaît jamais avec un taux à zéro ;
 * - l'agrégat s'appelle « ensemble des départements », jamais « France » :
 *   les électeurs inscrits hors de France n'y figurent pas ;
 * - deux familles de scrutin ne sont jamais posées côte à côte comme
 *   comparables (un tour de municipales et un tour de présidentielle ne se
 *   lisent pas sur la même échelle) — la mise en garde est écrite, pas
 *   sous-entendue.
 */

export interface ParticipationElectoraleProps {
  /** `null` si la base ou la source S26 manque : le bloc le dit et s'arrête. */
  donnees: DonneesElectionsInline | null;
}

/**
 * Fragment /data/elections.json, mémoïsé au niveau module — singleton
 * légitime : donnée GLOBALE du site, identique pour toutes les instances.
 * Même modèle que `chargerGeo()` dans `CarteDepartements`.
 */
let electionsPromesse: Promise<DonneesElections | null> | null = null;

function chargerElections(): Promise<DonneesElections | null> {
  electionsPromesse ??= fetch(urlSite("/data/elections.json"))
    .then((rep) => (rep.ok ? (rep.json() as Promise<DonneesElections | null>) : null))
    .catch(() => null);
  return electionsPromesse;
}

/**
 * Taux de participation en % — `null` si aucun inscrit connu.
 * JAMAIS 0 : une absence de dénominateur n'est pas une participation nulle.
 */
export function tauxParticipation(e: Effectifs | null | undefined): number | null {
  if (!e || !Number.isFinite(e.inscrits) || e.inscrits <= 0) return null;
  return (e.votants / e.inscrits) * 100;
}

/**
 * Part des bulletins blancs et nuls dans les VOTANTS (et non dans les
 * inscrits) : c'est la part des électeurs qui se sont déplacés sans exprimer
 * de suffrage. `null` si aucun votant connu.
 */
export function partBlancsNuls(e: Effectifs | null | undefined): number | null {
  if (!e || !Number.isFinite(e.votants) || e.votants <= 0) return null;
  return ((e.blancs + e.nuls) / e.votants) * 100;
}

/** Tuple compact + dictionnaire de libellés → ligne lisible. */
export function lireLigne(
  ligne: LigneCompacte,
  noms: Record<string, string>,
): LigneParticipation {
  const [code, inscrits, votants, blancs, nuls, exprimes] = ligne;
  return {
    code,
    // Libellé inconnu : le code, jamais un nom inventé ni une case vide.
    nom: noms[code] ?? code,
    inscrits,
    votants,
    blancs,
    nuls,
    exprimes,
  };
}

/** Colonnes communes aux deux tableaux (spécification sérialisable). */
const COLONNES = (enteteNom: string) => [
  { cle: "nom", entete: enteteNom },
  { cle: "inscrits", entete: "Inscrits", type: "nombre" as const },
  { cle: "votants", entete: "Votants", type: "nombre" as const },
  { cle: "participation", entete: "Participation (%)", type: "pourcent" as const },
  { cle: "blancs_nuls", entete: "Blancs et nuls (% des votants)", type: "pourcent" as const },
];

/** Effectifs bruts → ligne de tableau, taux compris (null → « — »). */
function versLigne(l: LigneParticipation) {
  return {
    code: l.code,
    nom: l.nom,
    inscrits: l.inscrits,
    votants: l.votants,
    participation: tauxParticipation(l),
    blancs_nuls: partBlancsNuls(l),
  };
}

/** Participations extrêmes du scrutin — bornes réelles, sans superlatif. */
function extremes(lignes: LigneParticipation[]) {
  const avecTaux = lignes
    .map((l) => ({ nom: l.nom, taux: tauxParticipation(l) }))
    .filter((l): l is { nom: string; taux: number } => l.taux !== null)
    .sort((a, b) => b.taux - a.taux);
  return { haut: avecTaux[0] ?? null, bas: avecTaux[avecTaux.length - 1] ?? null };
}

function Tuiles({ ensemble, nbDepartements }: { ensemble: Effectifs; nbDepartements: number }) {
  const participation = tauxParticipation(ensemble);
  const blancsNuls = partBlancsNuls(ensemble);
  return (
    <StatStrip
      stats={[
        {
          label: `Inscrits (${formatNombre(nbDepartements)} départements et collectivités)`,
          valeur: formatNombre(ensemble.inscrits),
        },
        { label: "Votants", valeur: formatNombre(ensemble.votants) },
        {
          label: "Participation",
          valeur: participation === null ? "—" : formatPct(participation),
        },
        {
          label: "Bulletins blancs et nuls",
          valeur: blancsNuls === null ? "—" : formatPct(blancsNuls),
        },
      ]}
    />
  );
}

export function ParticipationElectorale({ donnees }: ParticipationElectoraleProps) {
  const resumes = donnees?.resumes ?? [];
  const [idChoisi, setIdChoisi] = useState<string | null>(null);
  // Fragment complet une fois chargé ; undefined = jamais demandé,
  // null = demandé mais indisponible (l'échec est dit, l'initial reste).
  const [complet, setComplet] = useState<DonneesElections | null | undefined>(undefined);
  const [chargement, setChargement] = useState(false);

  if (!donnees || resumes.length === 0) {
    return (
      <Card titre="Participation électorale">
        <p className="text-sm text-ink-muted">
          La source S26 (résultats électoraux agrégés du ministère de l&apos;Intérieur)
          n&apos;est pas encore ingérée dans la base locale — lancer{" "}
          <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code>. Aucune donnée
          fictive n&apos;est affichée.
        </p>
      </Card>
    );
  }

  // Le scrutin initial (règle « dernier premier tour », tenue dans
  // `getDonneesElectionsInline` — une seule vérité) est le SEUL inline : il
  // reste affiché tant que le scrutin demandé n'est pas disponible.
  const initial = donnees.scrutinInitial;
  const idVoulu = idChoisi ?? initial.id;
  const scrutin: Scrutin =
    idVoulu === initial.id
      ? initial
      : (complet?.scrutins.find((s) => s.id === idVoulu) ?? initial);
  // L'échec ne se dit que si un AUTRE scrutin que l'initial est attendu.
  const echec = complet === null && idVoulu !== initial.id && !chargement;

  const choisirScrutin = (id: string) => {
    setIdChoisi(id);
    if (id === initial.id || complet) return;
    // Premier changement de scrutin : on va chercher le fragment complet.
    // La promesse module ne part qu'une fois, les clics suivants la partagent.
    setChargement(true);
    void chargerElections().then((d) => {
      setComplet(d && d.scrutins.length > 0 ? d : null);
      setChargement(false);
    });
  };

  const noms = donnees.noms;
  const lignesDep = scrutin.departements.map((l: LigneCompacte) => lireLigne(l, noms));
  const lignesCommunes = scrutin.communes.map((l: LigneCompacte) => lireLigne(l, noms));
  const { haut, bas } = extremes(lignesDep);
  const nbCommunes = scrutin.communes.length;
  const nbSuivies = donnees.nbCommunesSuivies;
  const communesManquantes = nbSuivies - nbCommunes;
  const estSecondTour = scrutin.tour === 2;

  // Fréquence réelle de la source, abrégée pour le badge (« par scrutin »).
  const badge = (
    <FreshnessBadge
      dateDonnees={donnees.meta.date_donnees}
      source="Ministère de l'Intérieur"
      frequence={donnees.meta.frequence}
      url={donnees.meta.url}
      mention="participation seulement"
    />
  );

  return (
    <Card
      titre="Participation électorale"
      sousTitre={
        scrutin.date
          ? `${scrutin.libelle} — scrutin du ${new Intl.DateTimeFormat("fr-FR", {
              day: "2-digit",
              month: "long",
              year: "numeric",
              timeZone: "Europe/Paris",
            }).format(new Date(scrutin.date))}`
          : scrutin.libelle
      }
      droite={badge}
    >
      {/* ------------------------------------------------ choix du scrutin */}
      <div className="mb-2 flex flex-wrap gap-2" role="group" aria-label="Choix du scrutin">
        {resumes.map((s) => {
          // Pendant le chargement, le bouton visé est marqué actif ; en cas
          // d'échec, la marque revient au scrutin réellement AFFICHÉ.
          const actif = chargement ? s.id === idVoulu : s.id === scrutin.id;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => choisirScrutin(s.id)}
              aria-pressed={actif}
              className={`rounded-lg border px-2.5 py-1 text-xs transition-colors ${
                actif
                  ? "border-raised-border bg-raised text-ink"
                  : "border-card-border bg-card text-ink-muted hover:bg-hover hover:text-ink-secondary"
              }`}
            >
              {s.libelle}
            </button>
          );
        })}
      </div>

      {/* Bandeau d'état à hauteur RÉSERVÉE (aucun saut de layout) : cadre
          « Chargement… » pendant le fetch du fragment, constat d'échec sinon.
          En échec le scrutin initial reste affiché — jamais un tableau vide,
          jamais des zéros. */}
      <div className="mb-2 min-h-[1.5rem] text-xs" aria-live="polite">
        {chargement && (
          <p
            role="status"
            className="inline-block rounded-lg border border-card-border bg-card px-2.5 py-1 text-ink-muted"
          >
            Chargement du scrutin…
          </p>
        )}
        {echec && (
          <p
            role="status"
            className="inline-block rounded-lg border border-card-border bg-card px-2.5 py-1 text-ink-muted"
          >
            Les données de ce scrutin n&apos;ont pas pu être chargées — le scrutin affiché
            reste « {initial.libelle} ».
          </p>
        )}
      </div>

      <Tuiles ensemble={scrutin.ensembleDepartements} nbDepartements={scrutin.departements.length} />

      {/* Mise en garde éditoriale : elle précède les tableaux, elle n'est pas
          reléguée en note de bas de bloc. */}
      <p className="mt-3 max-w-3xl text-xs text-ink-secondary">
        Les taux ci-dessus portent sur l&apos;<strong className="font-medium text-ink">ensemble
        des départements et collectivités</strong> ({formatNombre(scrutin.departements.length)} à ce
        scrutin), et non sur la France entière : les électeurs inscrits auprès des consulats
        (« Français établis hors de France ») ne relèvent d&apos;aucun département et ne sont pas
        comptés ici — le taux publié par le ministère, qui les inclut, diffère donc de quelques
        dixièmes de point.{" "}
        <strong className="font-medium text-ink">
          Les {formatNombre(resumes.length)} scrutins proposés ne se comparent pas entre eux
        </strong>{" "}
        : une participation municipale et une participation présidentielle ne mesurent ni le même
        corps électoral, ni le même enjeu, ni le même mode de scrutin. Comparer des départements
        entre eux au sein d&apos;un même scrutin a un sens ; comparer deux scrutins n&apos;en a pas.
      </p>

      {haut && bas && (
        <p className="mt-2 text-xs text-ink-secondary">
          De {formatPct(bas.taux)} de participation ({bas.nom}) à {formatPct(haut.taux)} ({haut.nom}).
        </p>
      )}

      {/* ------------------------------------------------ deux tableaux */}
      <div className="mt-4 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div>
          <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
            Par département et collectivité
          </h3>
          <TableTronquee
            colonnes={COLONNES("Département")}
            lignes={lignesDep.map(versLigne)}
            cleChamp="code"
            premierEcran={12}
            libellePluriel="départements et collectivités"
            hauteurMax="420px"
          />
        </div>
        <div>
          <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
            Communes suivies par le site
          </h3>
          <TableTronquee
            colonnes={COLONNES("Commune")}
            lignes={lignesCommunes.map(versLigne)}
            cleChamp="code"
            premierEcran={12}
            libellePluriel="communes"
            feminin
            hauteurMax="420px"
            vide="Aucune des communes suivies ne figure à ce scrutin."
          />
          {/* Une commune absente est DITE absente : jamais une ligne à zéro. */}
          <p className="mt-2 text-[11px] text-ink-muted">
            {formatNombre(nbCommunes)} des {formatNombre(nbSuivies)} communes suivies par le site
            figurent à ce scrutin.
            {communesManquantes > 0 && (
              <>
                {" "}
                Les {formatNombre(communesManquantes)} autres n&apos;y ont pas voté : aucune ligne
                n&apos;est fabriquée pour elles, et leur absence ne vaut pas participation nulle.
                {estSecondTour
                  ? " À un second tour, une commune manque parce que son conseil a été élu dès le premier."
                  : " Saint-Barthélemy (97701) et Saint-Martin (97801) élisent un conseil territorial, pas un conseil municipal (collectivités de l’article 74 de la Constitution) ; Uvea (98613) relève de Wallis-et-Futuna, territoire sans communes, dont le ministère publie les résultats sous une entité unique."}
              </>
            )}
          </p>
        </div>
      </div>

      {/* ------------------------------------------------ ce qui n'est pas là */}
      <p className="mt-4 max-w-3xl text-[11px] text-ink-muted">
        Participation seulement. Les <strong className="font-medium text-ink-secondary">nuances
        politiques ne sont pas publiées</strong> : elles sont attribuées par les préfectures et non
        déclarées par les candidats, elles manquent sur un quart des communes aux municipales 2026,
        leur grille a changé entre 2020 et 2026 et elle est contestée devant le Conseil
        d&apos;État. Aucun nom de candidat n&apos;est ingéré ni affiché. Le détail par bureau de
        vote existe à la source mais n&apos;est pas repris ici. Méthode complète et sources :
        docs/ELECTIONS.md.
      </p>
    </Card>
  );
}
