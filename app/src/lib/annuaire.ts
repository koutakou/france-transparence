/**
 * Rattachement des fiches /elus/<id> aux sections de l'annuaire. Module PUR
 * (aucun import à l'exécution), testé par `npm test` sur une base en mémoire
 * (tests/annuaire.test.mjs).
 *
 * Les parlementaires se lisent dans les tables des chambres EN EXERCICE —
 * `deputes` (AMO10 du jour) et `senateurs` (ODSEN ACTIF) —, jamais dans le
 * TYPE du JSON `elus.mandats` : ce JSON garde le mandat de député qu'un
 * sortant tenait encore au dernier RNE trimestriel. Lu là, un sénateur
 * élu en septembre 2026 était rangé parmi les « Député·es ». Les exécutifs
 * CD/CR n'ont pas de table propre : ils restent lus dans le JSON, comme le
 * fait getIdsFichesStatiques.
 */
export const SQL_SECTIONS_ANNUAIRE = `
  SELECT e.id, e.nom, e.prenom, json_extract(je.value, '$.type') AS type
    FROM elus e, json_each(e.mandats) je
   WHERE json_extract(je.value, '$.type') IN
         ('president_conseil_departemental', 'president_conseil_regional')
  UNION
  SELECT e.id, e.nom, e.prenom, 'depute' AS type
    FROM deputes d JOIN elus e ON e.uid_an = d.uid_an
  UNION
  SELECT e.id, e.nom, e.prenom, 'senateur' AS type
    FROM senateurs s JOIN elus e ON e.matricule_senat = s.matricule`;
