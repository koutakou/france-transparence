// Lignes RÉELLES de la base ingérée le 15/10/2026, colonnes lues par les
// requêtes testées (les autres restent à leur valeur par défaut). Choisies
// pour leur rôle, dit en regard de chacune.

/** meta_sources S1 (DECP) et S4 (HATVP), sans la colonne notes. */
export const META = [
  {
    "source_id": "S1",
    "nom": "DECP consolidées au format tabulaire (marchés publics)",
    "url": "https://www.data.gouv.fr/datasets/donnees-essentielles-de-la-commande-publique-consolidees-format-tabulaire",
    "licence": "Licence Ouverte 2.0",
    "frequence": "quotidienne",
    "date_donnees": "2026-10-15",
    "date_ingestion": "2026-10-15T12:28:25+00:00",
    "lignes": 493323
  },
  {
    "source_id": "S4",
    "nom": "HATVP — Répertoire des représentants d'intérêts (AGORA)",
    "url": "https://www.hatvp.fr/agora/opendata/csv/Vues_Separees_CSV.zip",
    "licence": "Licence Ouverte Etalab",
    "frequence": "quotidienne",
    "date_donnees": "2026-10-14",
    "date_ingestion": "2026-10-15T12:29:46+00:00",
    "lignes": 4101
  }
];

/**
 * lobby_entites :
 * - 22 : CCI Métropole de Bourgogne, active, SIREN titulaire d'un marché
 *   hors accord-cadre ci-dessous, fourchette de budget déclarée ;
 * - 0 : SUNROCK, active, sans fourchette, sur la liste HATVP des défauts ;
 * - 52 : CONVICTIONS' AFFAIRES PUBLIQUES, CESSÉE le 01/04/2024, avec une
 *   fourchette — hors de lobby_agg_budgets, qui ne compte que les actives.
 */
export const ENTITES = [
  {
    "id": "0",
    "identifiant_national": "497632109",
    "type_identifiant": "SIREN",
    "denomination": "SUNROCK",
    "categorie": "Société commerciale et civile (autre que cabinet d’avocats et société de conseil)",
    "active": 1,
    "date_cessation": null,
    "nb_activites_total": 0,
    "nb_activites_12m": 0,
    "budget_libelle": null,
    "defaut_declaration": 1,
    "url_fiche": "https://www.hatvp.fr/fiche-organisation/?organisation=497632109"
  },
  {
    "id": "22",
    "identifiant_national": "130029481",
    "type_identifiant": "SIREN",
    "denomination": "CHAMBRE DE COMMERCE ET D INDUSTRIE METROPOLE DE BOURGOGNE",
    "categorie": "Chambre consulaire",
    "active": 1,
    "date_cessation": null,
    "nb_activites_total": 12,
    "nb_activites_12m": 3,
    "budget_libelle": "< 10 000 €",
    "defaut_declaration": 0,
    "url_fiche": "https://www.hatvp.fr/fiche-organisation/?organisation=130029481"
  },
  {
    "id": "52",
    "identifiant_national": "881455091",
    "type_identifiant": "SIREN",
    "denomination": "CONVICTIONS' AFFAIRES PUBLIQUES",
    "categorie": "Cabinet de conseil",
    "active": 0,
    "date_cessation": "2024-04-01",
    "nb_activites_total": 15,
    "nb_activites_12m": 0,
    "budget_libelle": "≥ 10 000 € et < 25 000 €",
    "defaut_declaration": 0,
    "url_fiche": "https://www.hatvp.fr/fiche-organisation/?organisation=881455091"
  }
];

/**
 * decp_marches, un titulaire chacun :
 * 1. CCI Métropole de Bourgogne (SIREN 130029481, au répertoire), hors AC ;
 * 2. DNM ALUMINIUM (823094982), hors AC ;
 * 3. AGRIRAM (897714879), ACCORD-CADRE seulement ;
 * 4. identifiant « 00001 », hors AC — préfixe qui n'est pas un SIREN ;
 * 5. identifiant « 391 902 095 00028 » (espaces), hors AC — idem.
 */
export const MARCHES = [
  {
    "uid": "200053726000282025S00005_75200000",
    "montant_retenu": 54150.0,
    "montant_suspect": 0,
    "nb_titulaires": 1,
    "titulaires_json": "[{\"siret\":\"13002948100012\",\"nom\":\"CHAMBRE DE COMMERCE ET D INDUSTRIE METROPOLE DE BOURGOGNE\"}]",
    "date_notification": "2025-06-19",
    "techniques": "Sans objet"
  },
  {
    "uid": "218300093000182025MCH251801_45215100",
    "montant_retenu": 86870.0,
    "montant_suspect": 0,
    "nb_titulaires": 1,
    "titulaires_json": "[{\"siret\":\"82309498200027\",\"nom\":\"DNM ALUMINIUM\"}]",
    "date_notification": "2025-09-01",
    "techniques": "Sans objet"
  },
  {
    "uid": "219711033000152026ektal0000000_03221000",
    "montant_retenu": 25000.0,
    "montant_suspect": 0,
    "nb_titulaires": 1,
    "titulaires_json": "[{\"siret\":\"89771487900011\",\"nom\":\"AGRIRAM\"}]",
    "date_notification": "2026-03-17",
    "techniques": "Accord-cadre"
  },
  {
    "uid": "216200410000192026F00015_39298910",
    "montant_retenu": 360000.0,
    "montant_suspect": 0,
    "nb_titulaires": 1,
    "titulaires_json": "[{\"siret\":\"00001\",\"nom\":null}]",
    "date_notification": "2026-03-11",
    "techniques": "Sans objet"
  },
  {
    "uid": "200055127000432026143D91E7F00_45246400",
    "montant_retenu": 394000.0,
    "montant_suspect": 0,
    "nb_titulaires": 1,
    "titulaires_json": "[{\"siret\":\"391 902 095 00028\",\"nom\":null}]",
    "date_notification": "2026-02-10",
    "techniques": "Sans objet"
  }
];

/** Insère des objets dans `table` (colonnes = clés du premier objet). */
export function inserer(db, table, lignes) {
  const colonnes = Object.keys(lignes[0]);
  const ins = db.prepare(
    `INSERT INTO ${table} (${colonnes.join(", ")}) VALUES (${colonnes.map((c) => "@" + c).join(", ")})`,
  );
  for (const l of lignes) ins.run(l);
}
