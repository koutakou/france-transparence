"use client";

import { useState } from "react";
import { formatDateFr } from "@/lib/format";
import { urlSite } from "@/lib/basePath";
// Import de TYPES uniquement : `@/lib/queries/declarations` tire `@/lib/db`,
// donc better-sqlite3 — un module natif qui n'a rien à faire dans un bundle
// navigateur. Un `import type` est effacé à la compilation, la frontière
// client/serveur tient.
import type {
  DeclarationInterets,
  InteretsElu,
  LigneInteret,
  MontantDeclare,
  RubriqueDeclaree,
} from "@/lib/queries/declarations";

/**
 * Repli d'intitulé si la source n'a pas publié son propre label (le champ
 * `type_declaration_libelle` est celui de la HATVP et fait foi quand il
 * existe). Deux entrées : aucun autre type n'entre en base.
 */
const LIBELLES_TYPE_DECLARATION: Record<string, string> = {
  DI: "Déclaration d\u2019intérêts",
  DIA: "Déclaration d\u2019intérêts et d\u2019activités",
};

/**
 * Contenu des déclarations d'intérêts HATVP d'un élu — affichage VERBATIM.
 *
 * Trois partis pris, qui ne sont pas négociables et qui expliquent la forme :
 *
 * 1. **Rien n'est agrégé.** Pas de total de rémunérations, pas de « nombre
 *    d'intérêts » comparé à quoi que ce soit, pas de classement. Les libellés
 *    amont ne sont pas normalisés (« Education Nationale » / « Education
 *    nationale », « Isère(38) », « Conseillermunicipal » sont des valeurs
 *    réelles du fichier) et ne supporteraient aucun de ces calculs. Chaque
 *    montant est affiché à côté de son année et de sa mention brut/net, tel
 *    qu'il a été saisi.
 * 2. **Une donnée manquante s'affiche comme manquante.** Jamais « 0 € » là où
 *    la personne n'a rien déclaré. À l'inverse, un « 0 » réellement déclaré
 *    est affiché « 0 » : c'est une déclaration, pas une absence.
 * 3. **« Néant » et « pas de donnée » sont deux phrases différentes.** Une
 *    rubrique où la personne a coché « néant » le dit (`neant === 1`) — c'est
 *    un fait publié par la HATVP. Une rubrique dont la source ne dit rien
 *    n'affiche rien du tout. Et une fiche sans déclaration rattachée n'entre
 *    même pas ici : la page affiche alors un message d'ignorance assumée.
 *
 * Pourquoi un composant CLIENT : la fiche la plus chargée porte 424 lignes et
 * 1 805 montants. Rendues côté serveur, elles coûteraient deux fois leur poids
 * (HTML + arbre d'éléments dupliqué dans le payload RSC). Ici l'arbre ne
 * traverse pas la frontière : seules les données brutes passent, et seul ce
 * qui est visible est rendu. La troncature est TOUJOURS annoncée.
 *
 * Depuis la troncature SERVEUR (`tronquerInterets`), la page n'inline même
 * plus la queue invisible : la première déclaration arrive limitée à
 * `LIGNES_PAR_ECRAN` lignes par rubrique (`nb_lignes_total` dit alors le
 * vrai compte), les suivantes arrivent vides avec `complet: false`. Le
 * premier « Tout afficher » / « Déplier » qui touche du contenu retranché
 * charge le fragment statique `/data/elus/interets/<eluId>.json` — complet,
 * autoportant — et il REMPLACE l'état : un seul fetch par fiche, mémoïsé
 * par élu (jamais un singleton : la navigation client entre fiches servirait
 * sinon les déclarations d'un autre élu). Les deux marqueurs sont EXPLICITES :
 * un tableau vide sans marqueur reste une donnée de la source (rubrique
 * réellement vide), qui ne déclenche aucun chargement.
 *
 * Toutes les déclarations sont montrées, chacune datée, la plus récente
 * dépliée. On n'affiche jamais la seule dernière : une déclaration
 * MODIFICATIVE ne remplace pas les précédentes, elle en corrige une partie —
 * la donner seule ferait passer pour « néant » des rubriques qui ne le sont
 * pas.
 */

/**
 * Lignes rendues par rubrique avant « Tout afficher ».
 *
 * POINT DE SYNCHRONISATION : cette constante est la COPIE de
 * `LIGNES_SERVIES_PAR_RUBRIQUE` dans `lib/queries/declarations.ts`, qui ne
 * peut pas être importée ici (le module tire better-sqlite3, un module natif
 * interdit de bundle navigateur — même précédent que `DATES_SCRUTINS` dans
 * `queries/elections.ts`). Modifier l'une impose de modifier l'autre : si la
 * page servait moins de lignes que l'écran n'en affiche, la troncature
 * visuelle mordrait sur du contenu réellement absent.
 */
const LIGNES_PAR_ECRAN = 8;

/**
 * Fragments déjà demandés, PAR ÉLU. La clé est indispensable : ce cache est
 * un état de module, il survit à la navigation client d'une fiche à l'autre —
 * un singleton servirait les déclarations du précédent élu visité. Seul un
 * chargement RÉUSSI reste mémoïsé : un échec est retiré du cache pour que le
 * clic suivant retente réellement.
 */
const fragmentsParElu = new Map<string, Promise<InteretsElu | null>>();

function chargerFragment(eluId: string): Promise<InteretsElu | null> {
  const enCours = fragmentsParElu.get(eluId);
  if (enCours) return enCours;
  const promesse = fetch(urlSite(`/data/elus/interets/${encodeURIComponent(eluId)}.json`))
    .then((rep) => (rep.ok ? (rep.json() as Promise<InteretsElu | null>) : null))
    .catch(() => null)
    .then((interets) => {
      if (!interets || !Array.isArray(interets.declarations)) {
        fragmentsParElu.delete(eluId);
        return null;
      }
      return interets;
    });
  fragmentsParElu.set(eluId, promesse);
  return promesse;
}

/**
 * Échec de chargement : une PHRASE, jamais un état qui ressemble à « néant »
 * — ne rien afficher là où l'on sait qu'il y a du contenu serait un mensonge
 * pire que l'échec lui-même.
 */
const MESSAGE_ECHEC =
  "Le détail complet n\u2019a pas pu être chargé \u2014 les documents d\u2019origine restent consultables sur la fiche HATVP.";

/** État du chargement du fragment, partagé par toute la fiche. */
type Chargeur = {
  chargement: boolean;
  echec: boolean;
  /** Lance (ou rejoint) le chargement ; résout vrai si le contenu est là. */
  demander: () => Promise<boolean>;
};

/** Valeur absente : jamais « 0 », jamais rien. */
function NonRenseigne({ quoi }: { quoi: string }) {
  return (
    <span className="text-ink-muted" title={`${quoi} : rien n’est déclaré dans la source`}>
      non renseigné
    </span>
  );
}

/** « 2024 : 43 491 € (net) » — verbatim, jamais recalculé ni cumulé. */
function Montants({ montants }: { montants: MontantDeclare[] | undefined }) {
  if (!montants || montants.length === 0) return null;
  return (
    <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
      {montants.map((m) => (
        <li key={m.annee} className="text-xs text-ink-secondary tabular-nums">
          <span className="text-ink-muted">{m.annee}</span>{" "}
          <span className="text-ink">{m.montant} €</span>
          {m.brut_net ? (
            <span className="text-ink-muted"> ({m.brut_net.toLowerCase()})</span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

/** Petit couple « étiquette : valeur » des participations financières. */
function Detail({ label, valeur }: { label: string; valeur: string | undefined }) {
  if (valeur === undefined) return null;
  return (
    <span className="text-xs text-ink-secondary">
      {label} <span className="text-ink tabular-nums">{valeur}</span>
    </span>
  );
}

function Ligne({ ligne }: { ligne: LigneInteret }) {
  const periode = [ligne.date_debut, ligne.date_fin].filter(Boolean).join(" → ");
  return (
    <li className="py-2.5" style={{ borderBottom: "1px solid var(--viz-grid)" }}>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="text-sm font-semibold text-ink">
          {ligne.libelle ?? <NonRenseigne quoi="Entité déclarée" />}
        </span>
        {ligne.description && (
          <span className="text-[13px] text-ink-secondary">{ligne.description}</span>
        )}
        {periode && <span className="text-xs text-ink-muted">{periode}</span>}
        {ligne.conservee === 1 && (
          <span className="rounded-full border border-card-border px-1.5 py-0.5 text-[10px] uppercase tracking-[0.08em] text-ink-muted">
            conservée
          </span>
        )}
      </div>
      {(ligne.evaluation !== undefined ||
        ligne.capital_detenu !== undefined ||
        ligne.nombre_parts !== undefined ||
        ligne.remuneration_libre !== undefined ||
        ligne.organisation_conseil !== undefined) && (
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5">
          <Detail label="évaluation déclarée" valeur={ligne.evaluation} />
          <Detail label="capital détenu" valeur={ligne.capital_detenu} />
          <Detail label="nombre de parts" valeur={ligne.nombre_parts} />
          <Detail label="rémunération déclarée" valeur={ligne.remuneration_libre} />
          <Detail label="organisme de conseil" valeur={ligne.organisation_conseil} />
        </div>
      )}
      <Montants montants={ligne.montants} />
      {ligne.commentaire && (
        <p className="mt-1 text-xs leading-relaxed text-ink-muted">{ligne.commentaire}</p>
      )}
    </li>
  );
}

function Rubrique({ rubrique, chargeur }: { rubrique: RubriqueDeclaree; chargeur: Chargeur }) {
  const [tout, setTout] = useState(false);
  // `nb_lignes_total` présent = la PAGE ne porte pas tout (troncature
  // serveur) : « Tout afficher » doit d'abord charger le fragment. Absent,
  // la troncature n'est que visuelle et le clic est purement local.
  const aCharger = rubrique.nb_lignes_total !== undefined;
  const nbTotal = rubrique.nb_lignes_total ?? rubrique.lignes.length;
  const tronque = !tout && (aCharger || rubrique.lignes.length > LIGNES_PAR_ECRAN);
  const affichees = tronque ? rubrique.lignes.slice(0, LIGNES_PAR_ECRAN) : rubrique.lignes;

  async function toutAfficher() {
    if (!aCharger) {
      setTout(true);
      return;
    }
    // Le fragment remplace les déclarations chez le parent : cette rubrique
    // reviendra complète (sans `nb_lignes_total`), et `tout` la déplie.
    if (await chargeur.demander()) setTout(true);
  }

  return (
    <div className="mt-4 first:mt-0">
      {/* h3 et non h4 : ces rubriques sont les enfants directs du h2
          « Intérêts déclarés » de la fiche, sans niveau intermédiaire. Un h4
          sautait le h3 et rompait la séquence des titres — un lecteur d'écran
          qui navigue de titre en titre y perd le fil, et l'audit heading-order
          le relevait sur les 1 053 fiches. Le style ne change pas, seul le
          niveau sémantique. */}
      <h3 className="text-xs font-semibold uppercase tracking-[0.08em] text-ink-secondary">
        {rubrique.libelle}
      </h3>
      {rubrique.lignes.length === 0 ? (
        // `neant === 1` est un FAIT déclaré ; `null` est un silence de la
        // source, sur lequel on ne dit rien plutôt que d'inventer.
        rubrique.neant === 1 ? (
          <p className="mt-1 text-sm text-ink-muted">
            Néant déclaré — la personne a indiqué n’avoir rien à déclarer dans cette rubrique.
          </p>
        ) : (
          <p className="mt-1 text-sm text-ink-muted">
            Rubrique non renseignée dans cette déclaration.
          </p>
        )
      ) : (
        <>
          <ul className="mt-1 flex flex-col">
            {affichees.map((l) => (
              <Ligne key={l.id} ligne={l} />
            ))}
          </ul>
          {tronque && (
            <p className="mt-2 flex flex-wrap items-center gap-3 text-xs text-ink-muted" aria-live="polite">
              <span>
                Affichage des {LIGNES_PAR_ECRAN} premières lignes sur {nbTotal}.
              </span>
              {aCharger && chargeur.chargement ? (
                <span role="status">Chargement…</span>
              ) : (
                <button
                  type="button"
                  onClick={toutAfficher}
                  className="inline-flex min-h-11 items-center rounded-lg border border-card-border bg-raised px-3 text-ink transition-colors hover:bg-hover"
                >
                  Tout afficher ({nbTotal})
                </button>
              )}
              {aCharger && chargeur.echec && !chargeur.chargement && (
                <span className="text-ink-secondary">{MESSAGE_ECHEC}</span>
              )}
            </p>
          )}
        </>
      )}
    </div>
  );
}

function Declaration({
  declaration,
  ouverteParDefaut,
  chargeur,
}: {
  declaration: DeclarationInterets;
  ouverteParDefaut: boolean;
  chargeur: Chargeur;
}) {
  const [ouverte, setOuverte] = useState(ouverteParDefaut);
  // `complet === false` (marqueur EXPLICITE posé par `tronquerInterets`) :
  // le contenu de cette déclaration n'est pas dans la page, « Déplier » doit
  // le charger. Une déclaration sans rubrique DANS LA SOURCE n'a pas ce
  // marqueur et se déplie à vide, comme avant, sans aucun fetch.
  const aCharger = declaration.complet === false;

  function basculer() {
    if (!ouverte && aCharger) void chargeur.demander();
    setOuverte((o) => !o);
  }
  const type =
    declaration.type_declaration_libelle ??
    LIBELLES_TYPE_DECLARATION[declaration.type_declaration] ??
    declaration.type_declaration;
  const contexte = [declaration.qualite_declarant, declaration.organe_libelle]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="mt-4 first:mt-0 rounded-lg border border-card-border p-3 sm:p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink">
            {type}
            {declaration.modificative === 1 ? " (modificative)" : ""}
          </p>
          <p className="mt-0.5 text-xs text-ink-muted">
            {declaration.date_depot
              ? `Déposée le ${formatDateFr(declaration.date_depot)}`
              : "Date de dépôt non publiée"}
            {contexte ? ` · ${contexte}` : ""}
          </p>
        </div>
        <button
          type="button"
          onClick={basculer}
          aria-expanded={ouverte}
          className="inline-flex min-h-11 items-center rounded-lg border border-card-border bg-raised px-3 text-xs text-ink transition-colors hover:bg-hover"
        >
          {ouverte ? "Replier" : `Déplier (${declaration.nb_lignes} ligne${declaration.nb_lignes > 1 ? "s" : ""})`}
        </button>
      </div>
      {ouverte &&
        (aCharger ? (
          // Contenu retranché pas encore arrivé : dire l'attente ou l'échec,
          // JAMAIS un vide qui ressemblerait à « rien à déclarer ».
          <p className="mt-3 text-sm text-ink-muted" aria-live="polite">
            {chargeur.chargement ? (
              <span role="status">Chargement…</span>
            ) : (
              <span className="text-ink-secondary">{MESSAGE_ECHEC}</span>
            )}
          </p>
        ) : (
          <div className="mt-3">
            {declaration.rubriques.map((r) => (
              <Rubrique key={r.rubrique} rubrique={r} chargeur={chargeur} />
            ))}
          </div>
        ))}
    </div>
  );
}

export interface InteretsDeclaresProps {
  /**
   * Déclarations de la plus récente à la plus ancienne (cf. getInteretsElu),
   * TRONQUÉES par le serveur (cf. tronquerInterets) : la page n'inline que ce
   * que le premier écran affiche.
   */
  declarations: DeclarationInterets[];
  /** Id de l'élu de CETTE fiche — clé du cache et nom du fragment. */
  eluId: string;
  /**
   * Vrai si le fragment `/data/elus/interets/<eluId>.json` a été généré au
   * build (élu apparié). Faux, aucun clic ne déclenche de requête — un fetch
   * voué au 404 serait un bug, pas une dégradation.
   */
  fragmentDisponible: boolean;
}

export function InteretsDeclares({
  declarations,
  eluId,
  fragmentDisponible,
}: InteretsDeclaresProps) {
  // Une fois le fragment chargé, il REMPLACE les déclarations tronquées :
  // même forme, mêmes uuid (l'état local des sous-composants survit), plus
  // aucun marqueur de troncature — l'écran redevient exactement celui
  // d'avant la troncature serveur, tout étant local.
  const [completes, setCompletes] = useState<DeclarationInterets[] | null>(null);
  const [chargement, setChargement] = useState(false);
  const [echec, setEchec] = useState(false);

  async function demander(): Promise<boolean> {
    if (completes) return true;
    if (!fragmentDisponible) {
      setEchec(true);
      return false;
    }
    setChargement(true);
    setEchec(false);
    const interets = await chargerFragment(eluId);
    setChargement(false);
    if (!interets) {
      setEchec(true);
      return false;
    }
    setCompletes(interets.declarations);
    return true;
  }

  const chargeur: Chargeur = { chargement, echec, demander };
  const affichees = completes ?? declarations;

  if (affichees.length === 0) return null;
  return (
    <div>
      {affichees.map((d, i) => (
        // Seule la plus récente est dépliée d'emblée : les autres restent
        // accessibles d'un clic — un seul téléchargement, au premier clic
        // qui touche du contenu retranché.
        <Declaration
          key={d.uuid}
          declaration={d}
          ouverteParDefaut={i === 0}
          chargeur={chargeur}
        />
      ))}
      {affichees.length > 1 && (
        <p className="mt-3 text-[11px] leading-relaxed text-ink-muted">
          {affichees.length} déclarations publiées sont rattachées à cette fiche, de la plus
          récente à la plus ancienne. Une déclaration modificative ne remplace pas les
          précédentes : elle en corrige une partie. Elles ne se lisent donc pas l’une à la place
          de l’autre.
        </p>
      )}
    </div>
  );
}
