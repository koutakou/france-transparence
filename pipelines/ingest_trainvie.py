"""P13 — Frais & train de vie : faits sourcés et opacités documentées.

Alimente le module UI « Frais & train de vie » (SOURCES.md, source S31) :
le module pédagogique qui explique ce qui est publié (chaque chiffre sourcé)
et ce qui ne l'est pas (chaque manque documenté avec sa base juridique).

Tables créées (idempotent, contenu = constantes sourcées, aucune donnée fictive) :

- trainvie_faits : un fait chiffré publié par une source officielle.
    id, categorie ('indemnites_parlementaires', 'frais_mandat', 'controles',
    'elysee', 'institutions', 'cabinets', 'elus_locaux'), libelle,
    valeur (> 0), unite ('euros', 'euros_par_mois', 'personnes', 'pourcent',
    'deplacements', 'justificatifs'), assiette ('brut', 'net' ou NULL),
    periode (ex. '2026', '2024'), institution, source_nom, source_url,
    date_source, notes.

    `assiette` n'est jamais déduite : elle vaut 'brut' ou 'net' quand la
    source le dit explicitement (barèmes AN et Sénat, barème DGCL, dont les
    plafonds sont bruts), et NULL partout où la question n'a pas de sens —
    enveloppes de frais, dotations budgétaires, effectifs, totaux. C'est ce
    qui empêche la page de comparer un net à un brut sans le dire.

- trainvie_opacites : un manque documenté (ce que le pouvoir ne publie pas).
    id, sujet, ce_qui_manque, base_du_refus, source_nom, source_url,
    date (date du document, du refus ou du constat).

Matière première : docs/recherche/05-frais-indemnites.md (chiffres officiels
vérifiés le 19/08/2026, URLs testées). Les 22 URLs sources ont été re-vérifiées
le 19/08/2026 (curl -sI, toutes 200) ; les montants parlementaires ont été
re-confirmés sur les pages AN/Sénat elles-mêmes. Écartés faute d'URL officielle
vivante portant le chiffre : historique AFM 5 950 € (2024-2025), IRFM 5 372,80 €
(2017), traitements des membres du Gouvernement (décret 2012-983 : Légifrance
en 403 anti-robot, montants recalculés par la presse seulement).

Rejouable à volonté : les deux tables sont intégralement reconstruites à
chaque passage (DELETE + INSERT dans une transaction), puis `upsert_meta()`
actualise la ligne S31.

Usage :
    python -m pipelines.ingest_trainvie                  # ingestion
    python -m pipelines.ingest_trainvie --verifier-urls  # + contrôle HTTP des sources
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter

from pipelines import db
from pipelines.common import obtenir_logger, session_http

log = obtenir_logger("ingest_trainvie")

SOURCE_ID = "S31"

CATEGORIES = (
    "indemnites_parlementaires",
    "frais_mandat",
    "controles",
    "elysee",
    "institutions",
    "cabinets",
    "elus_locaux",
)

# ---------------------------------------------------------------------------
# Sources officielles (toutes testées vivantes le 19/08/2026, HTTP 200)
# ---------------------------------------------------------------------------

URL_AN_SITUATION = (
    "https://www.assemblee-nationale.fr/dyn/synthese/deputes-groupes-parlementaires/"
    "la-situation-materielle-du-depute"
)
URL_SENAT_INDEMNITE = (
    "https://www.senat.fr/connaitre-le-senat/role-et-fonctionnement/"
    "lindemnite-parlementaire.html"
)
URL_AN_DFP = "https://www.assemblee-nationale.fr/dyn/deontologie/fiches-pratiques/frais-de-mandat"
URL_SENAT_FRAIS = (
    "https://www.senat.fr/connaitre-le-senat/role-et-fonctionnement/les-frais-de-mandat.html"
)
URL_AN_DEONTOLOGUE = (
    "https://www.assemblee-nationale.fr/dyn/dyn/contenu/visualisation/1110434/file/"
    "Rapport_Deontologue_2025.pdf"
)
URL_SENAT_CDP = (
    "https://www.senat.fr/fileadmin/cru-1783325159/Organisation_interne/"
    "Comite_de_deontologie/Rapports_d_activite/RapportActivite2024-2025.pdf"
)
URL_CCOMPTES_ELYSEE_2024_PAGE = (
    "https://www.ccomptes.fr/fr/publications/les-comptes-et-la-gestion-des-services-"
    "de-la-presidence-de-la-republique-exercice-2024"
)
URL_CCOMPTES_ELYSEE_2024_PDF = (
    "https://www.ccomptes.fr/sites/default/files/2025-07/"
    "20250716-Comptes-et-gestion-presidence-de-la-Republique-2024.pdf"
)
URL_CCOMPTES_ELYSEE_2023_PDF = (
    "https://www.ccomptes.fr/sites/default/files/2024-07/"
    "20240729-S2024-1053-Comptes-et-gestion-de-la-presidence-de-la-Republique_2023.pdf"
)
URL_SENAT_RAP_LFI2026 = "https://www.senat.fr/rap/l25-139-322/l25-139-322_mono.html"
URL_JAUNE_CABINETS_2026 = (
    "https://www.assemblee-nationale.fr/dyn/dyn/contenu/visualisation/1090016/file/"
    "20-Jaune2026_Cabinets.pdf"
)
URL_DGCL_BAREME_2026 = (
    "https://www.collectivites-locales.gouv.fr/files/files/"
    "1.%20Connaitre%20les%20acteurs%20et%20les%20institutions/"
    "2.%20Fonction%20publique%20territoriale/La%20lettre%20FPT/"
    "ANNEXE%201%20-%20montants%20plafonds%20indemnit%C3%A9s%20%C3%A9lus%20locaux"
    "%202026%20-%20VF.pdf"
)
URL_DGCL_ETAT_RECAP = (
    "https://www.collectivites-locales.gouv.fr/files/files/"
    "1.%20Connaitre%20les%20acteurs%20et%20les%20institutions/3.%20Elus%20locaux/"
    "fiche_pratique_%C3%A9tat_r%C3%A9capitulatif_annuel_des_indemnit%C3%A9s_"
    "per%C3%A7ues_par_les_%C3%A9lus.pdf"
)
URL_REFUS_2026 = (
    "https://www.lecourrierdesstrateges.fr/notes-de-frais-des-parlementaires-"
    "lassemblee-et-le-senat-opposent-le-secret/"
)
URL_NEXT_FRAIS_REPRESENTATION = (
    "https://next.ink/6725/108060-frais-representation-ministres-demandes-cada-"
    "pour-plus-transparence/"
)
URL_SEBAN_CE_2023 = (
    "https://www.seban-associes.avocat.fr/les-notes-de-frais-des-elus-locaux-"
    "et-agents-publics-sont-des-documents-administratifs-communicables/"
)
URL_DATAGOUV_FRAIS_MANDAT = "https://www.data.gouv.fr/api/1/datasets/?q=frais%20de%20mandat"

SRC_AN_SITUATION = (
    "Assemblée nationale — fiche de synthèse n° 7 « La situation matérielle du député » "
    "(màj janvier 2026)"
)
SRC_SENAT_INDEMNITE = "Sénat — « L'indemnité parlementaire » (senat.fr)"
SRC_AN_DFP = (
    "Assemblée nationale — fiche pratique déontologie « Frais de mandat » "
    "(DFP, arrêté du Bureau n° 34/XVII du 02/07/2025)"
)
SRC_SENAT_FRAIS = "Sénat — « Les frais de mandat » (senat.fr)"
SRC_AN_DEONTOLOGUE = (
    "Rapport du déontologue de l'Assemblée nationale du 13/05/2026 (exercice 2024)"
)
SRC_SENAT_CDP = "Comité de déontologie parlementaire du Sénat — rapport d'activité 2024-2025"
SRC_CCOMPTES_2024 = (
    "Cour des comptes — « Les comptes et la gestion des services de la présidence "
    "de la République », exercice 2024 (publié le 18/07/2025)"
)
SRC_CCOMPTES_2023 = (
    "Cour des comptes — « Les comptes et la gestion des services de la présidence "
    "de la République », exercice 2023 (publié le 29/07/2024)"
)
SRC_SENAT_RAP_LFI2026 = (
    "Rapport Sénat n° 139 (2025-2026), tome III annexe 32 — mission « Pouvoirs publics » "
    "(LFI 2026, loi n° 2026-103 du 19/02/2026)"
)
SRC_JAUNE_CABINETS = (
    "Jaune budgétaire PLF 2026 « Personnels affectés dans les cabinets ministériels » "
    "(situation au 01/07/2025)"
)
SRC_DGCL_BAREME = (
    "DGCL — barème des indemnités maximales des élus locaux au 01/01/2026 "
    "(collectivites-locales.gouv.fr, màj 17/02/2026)"
)

# ---------------------------------------------------------------------------
# Faits sourcés (chaque valeur vient de docs/recherche/05-frais-indemnites.md ;
# URL de la source officielle testée vivante le 19/08/2026)
# ---------------------------------------------------------------------------

# (id, categorie, libelle, valeur, unite, periode, institution,
#  source_nom, source_url, date_source, notes)
FAITS: list[dict] = [
    # --- Indemnités parlementaires (barèmes publiés) ---------------------
    dict(id="ip-total-brut", assiette="brut", categorie="indemnites_parlementaires",
         libelle="Indemnité parlementaire mensuelle brute (base + résidence + fonction)",
         valeur=7637.39, unite="euros_par_mois", periode="2026",
         institution="Assemblée nationale et Sénat",
         source_nom=SRC_AN_SITUATION, source_url=URL_AN_SITUATION,
         date_source="2026-01",
         notes="Valeur au 01/01/2024, toujours en vigueur en 2026 ; identique députés/sénateurs."),
    dict(id="ip-base", assiette="brut", categorie="indemnites_parlementaires",
         libelle="Indemnité de base", valeur=5931.95, unite="euros_par_mois",
         periode="2026", institution="Assemblée nationale et Sénat",
         source_nom=SRC_AN_SITUATION, source_url=URL_AN_SITUATION,
         date_source="2026-01", notes=None),
    dict(id="ip-residence", assiette="brut", categorie="indemnites_parlementaires",
         libelle="Indemnité de résidence (3 % de la base)", valeur=177.96,
         unite="euros_par_mois", periode="2026",
         institution="Assemblée nationale et Sénat",
         source_nom=SRC_AN_SITUATION, source_url=URL_AN_SITUATION,
         date_source="2026-01", notes=None),
    dict(id="ip-fonction", assiette="brut", categorie="indemnites_parlementaires",
         libelle="Indemnité de fonction (25 % de base + résidence)", valeur=1527.48,
         unite="euros_par_mois", periode="2026",
         institution="Assemblée nationale et Sénat",
         source_nom=SRC_AN_SITUATION, source_url=URL_AN_SITUATION,
         date_source="2026-01", notes=None),
    dict(id="ip-net-depute", assiette="net", categorie="indemnites_parlementaires",
         libelle="Indemnité nette mensuelle avant impôt d'un député", valeur=5953.34,
         unite="euros_par_mois", periode="2026", institution="Assemblée nationale",
         source_nom=SRC_AN_SITUATION, source_url=URL_AN_SITUATION,
         date_source="2026-01", notes=None),
    dict(id="ip-net-senateur", assiette="net", categorie="indemnites_parlementaires",
         libelle="Indemnité nette mensuelle avant impôt d'un sénateur", valeur=5676.12,
         unite="euros_par_mois", periode="2026", institution="Sénat",
         source_nom=SRC_SENAT_INDEMNITE, source_url=URL_SENAT_INDEMNITE,
         date_source="2026-08-19",
         notes="Net inférieur à celui d'un député (cotisation pension plus élevée) ; "
               "page consultée le 19/08/2026."),
    dict(id="ip-ecretement-cumul", assiette="brut", categorie="indemnites_parlementaires",
         libelle="Plafond d'écrêtement des indemnités de mandats locaux cumulés",
         valeur=2965.98, unite="euros_par_mois", periode="2026",
         institution="Assemblée nationale et Sénat",
         source_nom=SRC_AN_SITUATION, source_url=URL_AN_SITUATION,
         date_source="2026-01",
         # Le multiplicateur légal de 1,5 porte sur le TOTAL, indemnité de base
         # comprise, et non sur les seules indemnités locales : la note disait
         # « 1,5 fois l'indemnité parlementaire de base » en face de 2 965,98 €,
         # ce qui envoyait sur 8 897,93 € quiconque refaisait le calcul. La base
         # occupant déjà 5 931,95 €, il reste bien la moitié de cette base pour
         # les mandats locaux. Les deux énoncés sont vrais, mais pas du même objet.
         notes="Les indemnités de mandats locaux ne peuvent porter le total, "
               "indemnité parlementaire de base comprise, au-delà d'une fois et "
               "demie cette base : elles sont donc plafonnées à la moitié de "
               "l'indemnité de base."),
    dict(id="isf-presidente-an", assiette="brut", categorie="indemnites_parlementaires",
         libelle="Indemnité spéciale de fonction de la présidente de l'Assemblée nationale",
         valeur=7698.50, unite="euros_par_mois", periode="2026",
         institution="Assemblée nationale",
         source_nom=SRC_AN_SITUATION, source_url=URL_AN_SITUATION,
         date_source="2026-01", notes="S'ajoute à l'indemnité parlementaire ; brut mensuel."),
    dict(id="isf-questeur-an", assiette="brut", categorie="indemnites_parlementaires",
         libelle="Indemnité spéciale de fonction d'un questeur de l'Assemblée nationale",
         valeur=5300.36, unite="euros_par_mois", periode="2026",
         institution="Assemblée nationale",
         source_nom=SRC_AN_SITUATION, source_url=URL_AN_SITUATION,
         date_source="2026-01", notes=None),
    dict(id="isf-president-senat", assiette="brut", categorie="indemnites_parlementaires",
         libelle="Indemnité spéciale de fonction du président du Sénat",
         valeur=7591.58, unite="euros_par_mois", periode="2026", institution="Sénat",
         source_nom=SRC_SENAT_INDEMNITE, source_url=URL_SENAT_INDEMNITE,
         date_source="2026-08-19", notes="Page consultée le 19/08/2026."),
    dict(id="isf-questeur-senat", assiette="brut", categorie="indemnites_parlementaires",
         libelle="Indemnité spéciale de fonction d'un questeur du Sénat",
         valeur=4444.97, unite="euros_par_mois", periode="2026", institution="Sénat",
         source_nom=SRC_SENAT_INDEMNITE, source_url=URL_SENAT_INDEMNITE,
         date_source="2026-08-19", notes="Page consultée le 19/08/2026."),

    # --- Frais de mandat (enveloppes publiées, usage non publié) ---------
    dict(id="dfp-metropole", categorie="frais_mandat",
         libelle="Dotation de fonctionnement parlementaire (DFP) d'un député de métropole",
         valeur=7238.04, unite="euros_par_mois", periode="2026",
         institution="Assemblée nationale",
         source_nom=SRC_AN_DFP, source_url=URL_AN_DFP, date_source="2026-01-01",
         notes="Créée au 01/01/2026 (arrêté du Bureau n° 34/XVII du 02/07/2025) par fusion "
               "de l'avance de frais de mandat et de la dotation matérielle des députés."),
    dict(id="dfp-outremer-max", categorie="frais_mandat",
         libelle="DFP maximale d'un député d'outre-mer et des collectivités du Pacifique",
         valeur=7720.17, unite="euros_par_mois", periode="2026",
         institution="Assemblée nationale",
         source_nom=SRC_AN_DFP, source_url=URL_AN_DFP, date_source="2026-01-01",
         notes="Fourchette publiée : 7 512,75 € à 7 720,17 €."),
    dict(id="dfp-hors-de-france-max", categorie="frais_mandat",
         libelle="DFP maximale d'un député des Français établis hors de France",
         valeur=8239.10, unite="euros_par_mois", periode="2026",
         institution="Assemblée nationale",
         source_nom=SRC_AN_DFP, source_url=URL_AN_DFP, date_source="2026-01-01",
         notes="Fourchette publiée : 7 768,85 € à 8 239,10 €."),
    dict(id="afm-senat", categorie="frais_mandat",
         libelle="Avance générale de frais de mandat (AFM) d'un sénateur",
         valeur=6600.0, unite="euros_par_mois", periode="2026", institution="Sénat",
         source_nom=SRC_SENAT_FRAIS, source_url=URL_SENAT_FRAIS,
         date_source="2026-08-19",
         notes="Portée de 5 900 € à 6 600 € par le Bureau du 16/11/2023, effet 2024 ; "
               "majorée outre-mer/Français de l'étranger ; justification a posteriori "
               "dans l'application JULIA. Page consultée le 19/08/2026."),
    dict(id="afm-senat-hebergement", categorie="frais_mandat",
         libelle="Avance dédiée d'hébergement parisien d'un sénateur",
         valeur=1500.0, unite="euros_par_mois", periode="2026", institution="Sénat",
         source_nom=SRC_SENAT_FRAIS, source_url=URL_SENAT_FRAIS,
         date_source="2026-08-19",
         notes="Sauf élus parisiens ou logés. Page consultée le 19/08/2026."),
    dict(id="afm-senat-informatique", categorie="frais_mandat",
         libelle="Avance dédiée informatique d'un sénateur (par période de 3 ans)",
         valeur=6000.0, unite="euros", periode="2026", institution="Sénat",
         source_nom=SRC_SENAT_FRAIS, source_url=URL_SENAT_FRAIS,
         date_source="2026-08-19", notes="6 000 € pour 3 ans. Page consultée le 19/08/2026."),
    dict(id="afm-senat-representation-autorites", categorie="frais_mandat",
         libelle="Frais de représentation des autorités du Sénat (vice-présidents, questeurs…)",
         valeur=750.0, unite="euros_par_mois", periode="2026", institution="Sénat",
         source_nom=SRC_SENAT_FRAIS, source_url=URL_SENAT_FRAIS,
         date_source="2026-08-19", notes="Page consultée le 19/08/2026."),
    dict(id="credit-collaborateurs-an", categorie="frais_mandat",
         libelle="Crédit mensuel pour la rémunération des collaborateurs d'un député",
         valeur=11463.0, unite="euros_par_mois", periode="2026",
         institution="Assemblée nationale",
         source_nom=SRC_AN_SITUATION, source_url=URL_AN_SITUATION,
         date_source="2026-01",
         notes="Jusqu'à 5 collaborateurs ; revalorisé comme la fonction publique."),

    # --- Contrôles des frais de mandat (publiés, agrégés, anonymes) ------
    dict(id="ctrl-an-pct-controles", categorie="controles",
         libelle="Part des députés contrôlés sur leurs frais de mandat (exercice 2024)",
         valeur=100.0, unite="pourcent", periode="2024",
         institution="Assemblée nationale",
         source_nom=SRC_AN_DEONTOLOGUE, source_url=URL_AN_DEONTOLOGUE,
         date_source="2026-05-13",
         notes="« 100 % des députés contrôlés sur près de 100 % de leurs dépenses » "
               "(effet dissolution : soldes XVIe législature + relevés XVIIe)."),
    dict(id="ctrl-an-demandes-renseignements", categorie="controles",
         libelle="Députés ayant reçu une demande de renseignements ou justificatifs",
         valeur=311.0, unite="personnes", periode="2024",
         institution="Assemblée nationale",
         source_nom=SRC_AN_DEONTOLOGUE, source_url=URL_AN_DEONTOLOGUE,
         date_source="2026-05-13", notes=None),
    dict(id="ctrl-an-demandes-reversement", categorie="controles",
         libelle="Députés ayant reçu une demande de reversement complémentaire",
         valeur=84.0, unite="personnes", periode="2024",
         institution="Assemblée nationale",
         source_nom=SRC_AN_DEONTOLOGUE, source_url=URL_AN_DEONTOLOGUE,
         date_source="2026-05-13", notes="Anonymat absolu des députés concernés."),
    dict(id="ctrl-an-total-reversements", categorie="controles",
         libelle="Total des reversements demandés aux députés (exercice 2024)",
         valeur=276335.0, unite="euros", periode="2024",
         institution="Assemblée nationale",
         source_nom=SRC_AN_DEONTOLOGUE, source_url=URL_AN_DEONTOLOGUE,
         date_source="2026-05-13",
         notes="Arrêté au 31/12/2025 ; moins de 1 % de l'avance de frais de mandat versée."),
    dict(id="ctrl-senat-controles", categorie="controles",
         libelle="Sénateurs contrôlés sur leurs frais de mandat (exercice 2024)",
         valeur=362.0, unite="personnes", periode="2024", institution="Sénat",
         source_nom=SRC_SENAT_CDP, source_url=URL_SENAT_CDP, date_source="2025",
         notes="73 contrôles approfondis (40-60 % des dépenses) et 289 transversaux "
               "(20-30 %), sous supervision de la CNCC, ~20 experts-comptables."),
    dict(id="ctrl-senat-approfondis", categorie="controles",
         libelle="Contrôles approfondis menés au Sénat (exercice 2024)",
         valeur=73.0, unite="personnes", periode="2024", institution="Sénat",
         source_nom=SRC_SENAT_CDP, source_url=URL_SENAT_CDP, date_source="2025",
         notes="Couvrent 40 à 60 % des dépenses des sénateurs concernés."),
    dict(id="ctrl-senat-justificatifs-julia", categorie="controles",
         libelle="Justificatifs enregistrés dans l'application JULIA (exercice 2024)",
         valeur=149685.0, unite="justificatifs", periode="2024", institution="Sénat",
         source_nom=SRC_SENAT_CDP, source_url=URL_SENAT_CDP, date_source="2025",
         notes="Moyenne de 413 justificatifs par sénateur."),
    dict(id="ctrl-senat-frais-declares", categorie="controles",
         libelle="Frais de mandat nets déclarés par les sénateurs en 2024",
         valeur=29900000.0, unite="euros", periode="2024", institution="Sénat",
         source_nom=SRC_SENAT_CDP, source_url=URL_SENAT_CDP, date_source="2025",
         notes="+6,7 % après revalorisation de l'avance ; +14,6 % sur 2018-2024, "
               "inférieur à l'inflation (16,2 %). Aucun montant de reversement publié."),

    # --- Élysée (le train de vie le mieux audité : Cour des comptes) -----
    dict(id="elysee-dotation-2024", categorie="elysee",
         libelle="Dotation de l'État à la présidence de la République (LFI 2024)",
         valeur=122563852.0, unite="euros", periode="2024",
         institution="Présidence de la République",
         source_nom=SRC_CCOMPTES_2024, source_url=URL_CCOMPTES_ELYSEE_2024_PDF,
         date_source="2025-07-18", notes="+11 % après des années de dérapage."),
    dict(id="elysee-dotation-2026", categorie="elysee",
         libelle="Dotation de l'État à la présidence de la République (LFI 2026)",
         valeur=122563852.0, unite="euros", periode="2026",
         institution="Présidence de la République",
         source_nom=SRC_SENAT_RAP_LFI2026, source_url=URL_SENAT_RAP_LFI2026,
         date_source="2026-02-19", notes="Reconduite à l'identique depuis 2024."),
    dict(id="elysee-charges-2024", categorie="elysee",
         libelle="Charges de la présidence de la République (exercice 2024)",
         valeur=123300000.0, unite="euros", periode="2024",
         institution="Présidence de la République",
         source_nom=SRC_CCOMPTES_2024, source_url=URL_CCOMPTES_ELYSEE_2024_PDF,
         date_source="2025-07-18", notes="-2 % par rapport à 2023 ; produits 130 M€."),
    dict(id="elysee-excedent-2024", categorie="elysee",
         libelle="Excédent de l'exercice 2024 de la présidence de la République",
         valeur=6700000.0, unite="euros", periode="2024",
         institution="Présidence de la République",
         source_nom=SRC_CCOMPTES_2024, source_url=URL_CCOMPTES_ELYSEE_2024_PDF,
         date_source="2025-07-18", notes="Après un déficit de 8,3 M€ en 2023."),
    dict(id="elysee-deplacements-nb-2024", categorie="elysee",
         libelle="Déplacements présidentiels (exercice 2024)",
         valeur=94.0, unite="deplacements", periode="2024",
         institution="Présidence de la République",
         source_nom=SRC_CCOMPTES_2024, source_url=URL_CCOMPTES_ELYSEE_2024_PDF,
         date_source="2025-07-18",
         notes="Dont 34 internationaux (10,5 M€), 3 outre-mer (2,1 M€)."),
    dict(id="elysee-deplacements-cout-2024", categorie="elysee",
         libelle="Coût des déplacements présidentiels (exercice 2024)",
         valeur=20100000.0, unite="euros", periode="2024",
         institution="Présidence de la République",
         source_nom=SRC_CCOMPTES_2024, source_url=URL_CCOMPTES_ELYSEE_2024_PDF,
         date_source="2025-07-18",
         notes="Les 5 voyages les plus chers : 4,88 M€, soit 46 % du coût international ; "
               "remboursements avions au ministère des Armées : 1,4 M€."),
    dict(id="elysee-charges-2023", categorie="elysee",
         libelle="Charges de la présidence de la République (exercice 2023)",
         valeur=124200000.0, unite="euros", periode="2023",
         institution="Présidence de la République",
         source_nom=SRC_CCOMPTES_2023, source_url=URL_CCOMPTES_ELYSEE_2023_PDF,
         date_source="2024-07-29", notes="Dotation 2023 : 110,5 M€."),
    dict(id="elysee-deficit-2023", categorie="elysee",
         libelle="Déficit de l'exercice 2023 de la présidence de la République",
         valeur=8300000.0, unite="euros", periode="2023",
         institution="Présidence de la République",
         source_nom=SRC_CCOMPTES_2023, source_url=URL_CCOMPTES_ELYSEE_2023_PDF,
         date_source="2024-07-29",
         notes="Résultat négatif (-8,3 M€), à l'origine de l'alerte de la Cour des comptes."),

    # --- Coût des institutions (mission « Pouvoirs publics », LFI 2026) --
    dict(id="lfi2026-an", categorie="institutions",
         libelle="Dotation de l'Assemblée nationale (LFI 2026)",
         valeur=607647569.0, unite="euros", periode="2026",
         institution="Assemblée nationale",
         source_nom=SRC_SENAT_RAP_LFI2026, source_url=URL_SENAT_RAP_LFI2026,
         date_source="2026-02-19",
         notes="Gelée depuis 2025 ; solde budgétaire 2026 prévu -34,14 M€, "
               "couvert par prélèvement sur réserves."),
    dict(id="lfi2026-senat", categorie="institutions",
         libelle="Dotation du Sénat, jardin et musée du Luxembourg compris (LFI 2026)",
         valeur=353470900.0, unite="euros", periode="2026", institution="Sénat",
         source_nom=SRC_SENAT_RAP_LFI2026, source_url=URL_SENAT_RAP_LFI2026,
         date_source="2026-02-19",
         notes="Gelée depuis 2025 ; prélèvement 2026 sur réserves : 22,14 M€."),
    dict(id="lfi2026-chaines", categorie="institutions",
         libelle="Dotation des chaînes parlementaires LCP-AN et Public Sénat (LFI 2026)",
         valeur=35596900.0, unite="euros", periode="2026",
         institution="Chaînes parlementaires",
         source_nom=SRC_SENAT_RAP_LFI2026, source_url=URL_SENAT_RAP_LFI2026,
         date_source="2026-02-19", notes="+1 % par rapport à 2025."),
    dict(id="lfi2026-conseil-constitutionnel", categorie="institutions",
         libelle="Dotation du Conseil constitutionnel (LFI 2026)",
         valeur=20000000.0, unite="euros", periode="2026",
         institution="Conseil constitutionnel",
         source_nom=SRC_SENAT_RAP_LFI2026, source_url=URL_SENAT_RAP_LFI2026,
         date_source="2026-02-19", notes="+11,5 % par rapport à 2025."),
    dict(id="lfi2026-cjr", categorie="institutions",
         libelle="Dotation de la Cour de justice de la République (LFI 2026)",
         valeur=900000.0, unite="euros", periode="2026",
         institution="Cour de justice de la République",
         source_nom=SRC_SENAT_RAP_LFI2026, source_url=URL_SENAT_RAP_LFI2026,
         date_source="2026-02-19", notes="-8,5 % par rapport à 2025."),
    dict(id="lfi2026-mission-total", categorie="institutions",
         libelle="Total de la mission « Pouvoirs publics » (LFI 2026)",
         valeur=1140179221.0, unite="euros", periode="2026",
         institution="État — mission Pouvoirs publics",
         source_nom=SRC_SENAT_RAP_LFI2026, source_url=URL_SENAT_RAP_LFI2026,
         date_source="2026-02-19", notes="+0,21 % par rapport à la LFI 2025."),

    # --- Cabinets ministériels (jaune budgétaire PLF 2026) ---------------
    dict(id="cab-membres", categorie="cabinets",
         libelle="Membres des cabinets ministériels (au 01/07/2025)",
         valeur=521.0, unite="personnes", periode="2025", institution="Gouvernement",
         source_nom=SRC_JAUNE_CABINETS, source_url=URL_JAUNE_CABINETS_2026,
         date_source="2025-07-01",
         notes="36 directeurs, 47 directeurs adjoints, 55 chefs/chefs adjoints, "
               "379 conseillers, 4 autres (gouvernement Bayrou)."),
    dict(id="cab-support", categorie="cabinets",
         libelle="Agents « fonctions support » des cabinets ministériels (au 01/07/2025)",
         valeur=2220.0, unite="personnes", periode="2025", institution="Gouvernement",
         source_nom=SRC_JAUNE_CABINETS, source_url=URL_JAUNE_CABINETS_2026,
         date_source="2025-07-01",
         notes="Dont 1 244 assistance, 325 intendance, 249 sécurité bâtiments, "
               "225 chauffeurs, 177 protection."),
    dict(id="cab-total", categorie="cabinets",
         libelle="Effectif total des cabinets ministériels, support compris (au 01/07/2025)",
         valeur=2741.0, unite="personnes", periode="2025", institution="Gouvernement",
         source_nom=SRC_JAUNE_CABINETS, source_url=URL_JAUNE_CABINETS_2026,
         date_source="2025-07-01", notes="521 membres + 2 220 agents support."),
    dict(id="cab-isp-total", categorie="cabinets",
         libelle="Indemnités pour sujétions particulières des cabinets (enveloppes 2025)",
         valeur=27361062.0, unite="euros", periode="2025", institution="Gouvernement",
         source_nom=SRC_JAUNE_CABINETS, source_url=URL_JAUNE_CABINETS_2026,
         date_source="2025-07-01",
         notes="Cabinet du Premier ministre : 6,3 M€ pour 494 personnes dont 75 membres."),

    # --- Élus locaux (barème DGCL au 01/01/2026, plafonds bruts mensuels) -
    dict(id="local-ib1027", assiette="brut", categorie="elus_locaux",
         libelle="Indice brut terminal 1027 de la fonction publique (valeur mensuelle)",
         valeur=4110.52, unite="euros_par_mois", periode="2026",
         institution="Communes et EPCI",
         source_nom=SRC_DGCL_BAREME, source_url=URL_DGCL_BAREME_2026,
         date_source="2026-02-17",
         notes="Base de calcul de toutes les indemnités d'élus locaux "
               "(art. L. 2123-20 et s. CGCT)."),
    dict(id="local-maire-moins-500", assiette="brut", categorie="elus_locaux",
         libelle="Indemnité maximale d'un maire (commune de moins de 500 habitants)",
         valeur=1155.06, unite="euros_par_mois", periode="2026", institution="Communes",
         source_nom=SRC_DGCL_BAREME, source_url=URL_DGCL_BAREME_2026,
         date_source="2026-02-17", notes="28,1 % de l'IB 1027."),
    dict(id="local-maire-500-999", assiette="brut", categorie="elus_locaux",
         libelle="Indemnité maximale d'un maire (500 à 999 habitants)",
         valeur=1820.96, unite="euros_par_mois", periode="2026", institution="Communes",
         source_nom=SRC_DGCL_BAREME, source_url=URL_DGCL_BAREME_2026,
         date_source="2026-02-17", notes="44,3 % de l'IB 1027."),
    dict(id="local-maire-1000-3499", assiette="brut", categorie="elus_locaux",
         libelle="Indemnité maximale d'un maire (1 000 à 3 499 habitants)",
         valeur=2289.56, unite="euros_par_mois", periode="2026", institution="Communes",
         source_nom=SRC_DGCL_BAREME, source_url=URL_DGCL_BAREME_2026,
         date_source="2026-02-17", notes="55,7 % de l'IB 1027."),
    dict(id="local-maire-3500-9999", assiette="brut", categorie="elus_locaux",
         libelle="Indemnité maximale d'un maire (3 500 à 9 999 habitants)",
         valeur=2396.44, unite="euros_par_mois", periode="2026", institution="Communes",
         source_nom=SRC_DGCL_BAREME, source_url=URL_DGCL_BAREME_2026,
         date_source="2026-02-17", notes="58,3 % de l'IB 1027."),
    dict(id="local-maire-10000-19999", assiette="brut", categorie="elus_locaux",
         libelle="Indemnité maximale d'un maire (10 000 à 19 999 habitants)",
         valeur=2778.71, unite="euros_par_mois", periode="2026", institution="Communes",
         source_nom=SRC_DGCL_BAREME, source_url=URL_DGCL_BAREME_2026,
         date_source="2026-02-17", notes="67,6 % de l'IB 1027."),
    dict(id="local-maire-20000-49999", assiette="brut", categorie="elus_locaux",
         libelle="Indemnité maximale d'un maire (20 000 à 49 999 habitants)",
         valeur=3699.47, unite="euros_par_mois", periode="2026", institution="Communes",
         source_nom=SRC_DGCL_BAREME, source_url=URL_DGCL_BAREME_2026,
         date_source="2026-02-17", notes="90 % de l'IB 1027."),
    dict(id="local-maire-50000-99999", assiette="brut", categorie="elus_locaux",
         libelle="Indemnité maximale d'un maire (50 000 à 99 999 habitants)",
         valeur=4521.58, unite="euros_par_mois", periode="2026", institution="Communes",
         source_nom=SRC_DGCL_BAREME, source_url=URL_DGCL_BAREME_2026,
         date_source="2026-02-17", notes="110 % de l'IB 1027."),
    dict(id="local-maire-100000-plus", assiette="brut", categorie="elus_locaux",
         libelle="Indemnité maximale d'un maire (100 000 habitants et plus)",
         valeur=5960.26, unite="euros_par_mois", periode="2026", institution="Communes",
         source_nom=SRC_DGCL_BAREME, source_url=URL_DGCL_BAREME_2026,
         date_source="2026-02-17",
         notes="145 % de l'IB 1027, majoration possible de 40 % (dont Marseille, Lyon)."),
    dict(id="local-adjoint-100000-max", assiette="brut", categorie="elus_locaux",
         libelle="Indemnité maximale d'un adjoint au maire (100 000 habitants et plus, majorée)",
         valeur=2980.13, unite="euros_par_mois", periode="2026", institution="Communes",
         source_nom=SRC_DGCL_BAREME, source_url=URL_DGCL_BAREME_2026,
         date_source="2026-02-17", notes="Fourchette publiée : 2 712,95 € à 2 980,13 €."),
    dict(id="local-conseiller-municipal", assiette="brut", categorie="elus_locaux",
         libelle="Indemnité maximale d'un conseiller municipal",
         valeur=246.63, unite="euros_par_mois", periode="2026", institution="Communes",
         source_nom=SRC_DGCL_BAREME, source_url=URL_DGCL_BAREME_2026,
         date_source="2026-02-17", notes="6 % de l'IB 1027."),
]

# ---------------------------------------------------------------------------
# Opacités documentées (ce qui n'est PAS publié, et pourquoi)
# ---------------------------------------------------------------------------

OPACITES: list[dict] = [
    dict(id="justificatifs-parlementaires",
         sujet="Justificatifs et notes de frais des parlementaires",
         ce_qui_manque="Aucun justificatif, aucune note de frais, aucun relevé individuel "
                       "de député ou de sénateur n'est publié ni communicable ; la recherche "
                       "« frais de mandat » sur l'API data.gouv.fr renvoie 0 dataset "
                       "(vérifié les 19/08/2026).",
         base_du_refus="Ordonnance n° 58-1100 du 17/11/1958 (autonomie des assemblées, hors "
                       "CADA/CRPA), confirmée par le Conseil d'État en mars 2025 ; refus écrits "
                       "des deux chambres du 11/06/2026 à Transparence Citoyenne — l'AN invoque "
                       "le secret professionnel du déontologue, le Sénat la confidentialité "
                       "prévue par son Règlement.",
         source_nom="Refus AN/Sénat du 11/06/2026 (Le Courrier des Stratèges) ; "
                    "ord. 58-1100 ; CE mars 2025",
         source_url=URL_REFUS_2026, date="2026-06-11"),
    dict(id="indemnites-parlementaires-versees",
         sujet="Indemnités parlementaires réellement versées",
         ce_qui_manque="Aucun fichier open data des indemnités réellement versées par "
                       "parlementaire (retenues pour absences, écrêtements de cumul) : "
                       "seules les grilles de barèmes sont publiées.",
         base_du_refus="Autonomie des assemblées (ordonnance n° 58-1100) ; aucune obligation "
                       "de publication individuelle.",
         source_nom=SRC_AN_SITUATION + " — seuls les barèmes y figurent",
         source_url=URL_AN_SITUATION, date="2026-01"),
    dict(id="frais-representation-ministres",
         sujet="Frais de représentation des ministres",
         ce_qui_manque="Enveloppes annuelles connues uniquement par questions écrites et par "
                       "la presse (150 000 € ministre, 120 000 € ministre délégué, 100 000 € "
                       "secrétaire d'État) ; aucun texte réglementaire publié ne les fixe, "
                       "aucune publication de leur usage.",
         base_du_refus="Aucun texte publié (recommandation d'un décret par l'Observatoire de "
                       "l'éthique publique jamais suivie) ; réponse officielle : Chorus ne "
                       "permet pas d'extraire le détail ; demandes CADA 2018-2019 restées "
                       "largement sans effet, alors que les ministères sont soumis au CRPA.",
         source_nom="Next INpact, « Frais de représentation des ministres : des demandes CADA "
                    "pour plus de transparence » (23/07/2019)",
         source_url=URL_NEXT_FRAIS_REPRESENTATION, date="2019-07-23"),
    dict(id="remunerations-cabinets",
         sujet="Rémunérations détaillées des cabinets ministériels",
         ce_qui_manque="Les tableaux de rémunérations brutes annuelles par cabinet ont disparu "
                       "du jaune budgétaire depuis le PLF 2024 ; dernières données riches : "
                       "jaune PLF 2023 (exercice 2022, moyenne 8 495 € brut/mois). Recul "
                       "vérifié par téléchargement des éditions PLF 2024, 2025 et 2026.",
         base_du_refus="Aucune justification publiée ; la note d'introduction du jaune PLF 2026 "
                       "continue pourtant de décrire le principe de cette publication.",
         source_nom=SRC_JAUNE_CABINETS + " — tableaux de rémunérations absents",
         source_url=URL_JAUNE_CABINETS_2026, date="2025-07-01"),
    dict(id="indemnites-locales-versees",
         sujet="Indemnités réellement versées aux élus locaux",
         ce_qui_manque="L'état récapitulatif annuel des indemnités (art. L. 2123-24-1-1 CGCT, "
                       "loi Engagement et proximité de 2019) est communiqué aux conseillers "
                       "avant le vote du budget, mais jamais centralisé : aucune obligation de "
                       "mise en ligne, aucun open data national — la donnée existe dans plus de "
                       "34 000 communes sans être agrégeable. Le Répertoire national des élus "
                       "liste les mandats sans les indemnités.",
         base_du_refus="Aucune obligation légale de publication en ligne ni de centralisation "
                       "nationale.",
         source_nom="DGCL — fiche pratique « état récapitulatif annuel des indemnités perçues "
                    "par les élus » (constat au 19/08/2026)",
         source_url=URL_DGCL_ETAT_RECAP, date="2026-08-19"),
    dict(id="contraste-elus-locaux-communicables",
         sujet="Notes de frais des exécutifs locaux : communicables, mais au cas par cas",
         ce_qui_manque="Aucune publication spontanée ni centralisée des notes de frais des "
                       "élus locaux ; l'accès suppose une demande individuelle de chaque "
                       "citoyen, collectivité par collectivité.",
         base_du_refus="A contrario : le Conseil d'État a jugé le 08/02/2023 (notes de frais "
                       "de la maire de Paris) que notes de frais et reçus de déplacement, "
                       "restauration et représentation sont des documents administratifs "
                       "communicables à toute personne — le Parlement est donc l'exception, "
                       "pas la règle.",
         source_nom="CE, 8 février 2023 (analyse Seban & Associés)",
         source_url=URL_SEBAN_CE_2023, date="2023-02-08"),
    dict(id="reversements-senat",
         sujet="Montants des reversements exigés des sénateurs",
         ce_qui_manque="Le Sénat ne publie aucun montant de reversement à l'issue de ses "
                       "contrôles (7 contrôles complémentaires sur l'exercice 2024), là où "
                       "l'Assemblée nationale publie un total agrégé (276 335 €).",
         base_du_refus="Choix de publication du Sénat : agrégats seuls, anonymat, "
                       "confidentialité prévue par son Règlement.",
         source_nom=SRC_SENAT_CDP,
         source_url=URL_SENAT_CDP, date="2025"),
    dict(id="elysee-exercice-2025-non-paru",
         sujet="Comptes de l'Élysée, exercice 2025",
         ce_qui_manque="Le rapport de la Cour des comptes sur l'exercice 2025 n'est pas paru "
                       "au 19/08/2026 ; un seul rapport PDF par an, 12 à 18 mois après les "
                       "dépenses, sans données infra-annuelles ni open data.",
         base_du_refus="Calendrier de publication de la Cour des comptes ; aucune obligation "
                       "de délai ; l'Élysée ne publie pas lui-même de page budget à jour.",
         source_nom="Cour des comptes — page « exercice 2024 » (dernier rapport paru)",
         source_url=URL_CCOMPTES_ELYSEE_2024_PAGE, date="2026-08-19"),
]

# Faits du rapport 05 écartés faute d'URL officielle vivante portant le chiffre
# (règle : jamais de chiffre sans source vérifiable) — gardés ici pour mémoire :
# - AFM député 5 950 €/mois (2024-2025) et IRFM 5 372,80 € net/mois (2017) :
#   absents de la fiche AN « frais de mandat » actuelle (vérifié le 19/08/2026) ;
# - traitements des membres du Gouvernement (PM ≈ 16 038 €…) : décret 2012-983
#   sur Légifrance en 403 anti-robot, montants recalculés par la presse.
ECARTES = ("afm-an-5950-historique", "irfm-2017", "traitements-gouvernement")

# ---------------------------------------------------------------------------
# Schéma
# ---------------------------------------------------------------------------

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS trainvie_faits (
    id          TEXT PRIMARY KEY,
    categorie   TEXT NOT NULL CHECK (categorie IN
                  ({", ".join("'" + c + "'" for c in CATEGORIES)})),
    libelle     TEXT NOT NULL,
    valeur      REAL NOT NULL CHECK (valeur > 0),
    unite       TEXT NOT NULL,
    -- Assiette d'une rémunération : 'brut', 'net', ou NULL quand la question
    -- ne se pose pas (enveloppe de frais, dotation, effectif, total).
    -- POURQUOI cette colonne : les barèmes publiés mélangent les deux
    -- assiettes sans le dire, et le module les affiche côte à côte. Un
    -- sénateur touche 5 676,12 € NETS d'indemnité, un questeur du Sénat
    -- 4 444,97 € BRUTS d'indemnité de fonction : sans qualification, la
    -- page laisse conclure que le second gagne moins que le premier, ce
    -- qui est faux. Aucune valeur n'est modifiée, seule l'assiette que la
    -- source énonce est rendue explicite.
    assiette    TEXT CHECK (assiette IS NULL OR assiette IN ('brut', 'net')),
    periode     TEXT NOT NULL,
    institution TEXT NOT NULL,
    source_nom  TEXT NOT NULL,
    source_url  TEXT NOT NULL CHECK (source_url LIKE 'http%'),
    date_source TEXT NOT NULL,
    notes       TEXT
);
CREATE INDEX IF NOT EXISTS idx_trainvie_faits_categorie
    ON trainvie_faits(categorie);

CREATE TABLE IF NOT EXISTS trainvie_opacites (
    id            TEXT PRIMARY KEY,
    sujet         TEXT NOT NULL,
    ce_qui_manque TEXT NOT NULL,
    base_du_refus TEXT NOT NULL,
    source_nom    TEXT NOT NULL,
    source_url    TEXT NOT NULL CHECK (source_url LIKE 'http%'),
    date          TEXT NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


def ingester(conn: sqlite3.Connection | None = None) -> tuple[int, int]:
    """Reconstruit trainvie_faits et trainvie_opacites, met à jour meta_sources.

    Idempotent : les tables sont vidées puis re-remplies dans une transaction.
    Retourne (nb_faits, nb_opacites).
    """
    fermer = conn is None
    conn = db.init_db(conn=conn)
    conn.executescript(_SCHEMA)
    # `CREATE TABLE IF NOT EXISTS` n'ajoute pas de colonne à une table déjà
    # présente, et la base servie survit d'un déploiement à l'autre : la
    # colonne `assiette` est posée explicitement sur les bases antérieures
    # (migration idempotente, même patron que campagnes_2024.marqueur_etoile).
    colonnes = {r["name"] for r in conn.execute("PRAGMA table_info(trainvie_faits)")}
    if "assiette" not in colonnes:
        # SQLite ne sait pas attacher un CHECK à une colonne ajoutée après
        # coup : la contrainte du schéma ne vaut que pour les bases neuves
        # (CI, poste de développement). Le vocabulaire est de toute façon
        # tenu par ce pipeline seul, et par les tests.
        conn.execute("ALTER TABLE trainvie_faits ADD COLUMN assiette TEXT")
        conn.commit()
        log.info("migration : colonne trainvie_faits.assiette ajoutée")
    try:
        with conn:
            conn.execute("DELETE FROM trainvie_faits")
            conn.execute("DELETE FROM trainvie_opacites")
            conn.executemany(
                """
                INSERT INTO trainvie_faits
                    (id, categorie, libelle, valeur, unite, assiette, periode,
                     institution, source_nom, source_url, date_source, notes)
                VALUES (:id, :categorie, :libelle, :valeur, :unite, :assiette,
                        :periode, :institution, :source_nom, :source_url,
                        :date_source, :notes)
                """,
                # `assiette` n'est renseignée que sur les rémunérations dont la
                # source énonce l'assiette ; ailleurs elle reste absente plutôt
                # que devinée.
                [{"assiette": None, **fait} for fait in FAITS],
            )
            conn.executemany(
                """
                INSERT INTO trainvie_opacites
                    (id, sujet, ce_qui_manque, base_du_refus,
                     source_nom, source_url, date)
                VALUES (:id, :sujet, :ce_qui_manque, :base_du_refus,
                        :source_nom, :source_url, :date)
                """,
                OPACITES,
            )

        db.upsert_meta(
            conn,
            source_id=SOURCE_ID,
            nom="Corpus officiel « train de vie » (constantes sourcées)",
            url=URL_CCOMPTES_ELYSEE_2024_PAGE,
            licence="Publications officielles (hors open data)",
            frequence="à parution (annuelle)",
            # Document source le plus récent : rapport du déontologue de l'AN
            # publié le 13/05/2026 (exercice 2024).
            date_donnees="2026-05-13",
            lignes=len(FAITS) + len(OPACITES),
            notes=f"{len(FAITS)} faits sourcés + {len(OPACITES)} opacités documentées "
                  "(05-frais-indemnites.md, URLs re-vérifiées le 19/08/2026 ; "
                  "rapport Cour des comptes Élysée exercice 2025 non paru, à surveiller).",
        )

        par_categorie = Counter(f["categorie"] for f in FAITS)
        for cat in CATEGORIES:
            log.info("faits %-27s : %d", cat, par_categorie[cat])
        log.info("total : %d faits, %d opacités", len(FAITS), len(OPACITES))
        return len(FAITS), len(OPACITES)
    finally:
        if fermer:
            conn.close()


# ---------------------------------------------------------------------------
# Vérification des URLs sources (optionnelle, réseau)
# ---------------------------------------------------------------------------


def verifier_urls(timeout: float = 3.0) -> dict[str, int | str]:
    """HEAD sur chaque URL source distincte ; retourne {url: code HTTP ou erreur}.

    200/301/302 = vivante (même critère que la vérification du 19/08/2026).
    """
    urls = sorted(
        {f["source_url"] for f in FAITS} | {o["source_url"] for o in OPACITES}
    )
    s = session_http(total_retries=1)
    resultats: dict[str, int | str] = {}
    for url in urls:
        try:
            r = s.head(url, timeout=timeout, allow_redirects=False)
            resultats[url] = r.status_code
        except Exception as exc:  # noqa: BLE001 — on rapporte, on ne masque pas
            resultats[url] = type(exc).__name__
        etat = resultats[url]
        niveau = log.info if etat in (200, 301, 302) else log.warning
        niveau("source %s → %s", url, etat)
    return resultats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="P13 — frais & train de vie : faits sourcés et opacités documentées."
    )
    parser.add_argument(
        "--verifier-urls", action="store_true",
        help="vérifie en plus que chaque URL source répond (HEAD, 3 s)",
    )
    args = parser.parse_args(argv)

    nb_faits, nb_opacites = ingester()
    if args.verifier_urls:
        resultats = verifier_urls()
        mortes = {u: c for u, c in resultats.items() if c not in (200, 301, 302)}
        if mortes:
            log.warning("%d URL(s) source(s) ne répondent plus : %s",
                        len(mortes), mortes)
            return 1
    log.info("P13 terminé : %d faits, %d opacités.", nb_faits, nb_opacites)
    return 0


if __name__ == "__main__":
    sys.exit(main())
