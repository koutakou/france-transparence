# Exigences légales et bonnes pratiques pour la mise en ligne publique

Document établi le 19/08/2026 par recherche sur sources officielles (Légifrance, CNIL, HATVP, data.gouv.fr, ANSSI/cyber.gouv.fr, Sénat) puis audit du code de l'application. Périmètre : site **non commercial**, édité par un **particulier**, **sans compte utilisateur, sans publicité, sans cookie ni traceur**, republiant de l'**open data officiel** dont des données personnelles de responsables publics.

Chaque affirmation du § 1 porte sa référence (article de loi ou URL officielle, vérifiée le 19/08/2026).

---

## 1. Obligations

### 1.1 Mentions légales (LCEN) — un particulier peut rester anonyme

**État du droit 2026** : la loi SREN n° 2024-449 du 21 mai 2024 a réorganisé la LCEN (loi n° 2004-575 du 21 juin 2004). L'ancien article 6-III (mentions légales) **n'existe plus** : l'obligation d'identification est désormais portée par l'**article 1-1**, les sanctions par l'**article 1-2** — substance inchangée.
Texte : <https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000049568614> (art. 1-1, version en vigueur).

- **Éditeur professionnel** (art. 1-1, I) : nom, prénoms, domicile et téléphone (personne physique), **nom du directeur de la publication**, et hébergeur avec « nom, dénomination ou raison sociale, **adresse et numéro de téléphone** ».
- **Éditeur NON professionnel** (art. 1-1, II) — notre cas : il peut, « pour préserver son anonymat », ne tenir à la disposition du public que **le nom (ou la dénomination/raison sociale) et l'adresse de l'hébergeur**, **à la condition d'avoir communiqué à cet hébergeur ses éléments d'identification personnelle**. L'hébergeur est tenu au secret professionnel sur ces éléments, non opposable à l'autorité judiciaire (art. 1-1, III).
  - Le téléphone de l'hébergeur n'est textuellement exigé qu'au régime professionnel (I) ; le mettre quand même est la pratique prudente.
- **Directeur de la publication** : tout service de communication au public en ligne en a un (loi n° 82-652 du 29 juillet 1982, art. 93-2) ; quand l'éditeur est une personne physique, c'est elle de plein droit. En régime non professionnel anonyme, **son nom n'a pas à être publié** ; les demandes de droit de réponse sont adressées à l'hébergeur, qui les transmet sans délai au directeur de la publication (mécanisme repris de l'ancien art. 6 LCEN dans les art. 1-1 et s.).
- **Moyen de contact de l'éditeur** : la LCEN ne l'impose pas au non-professionnel anonyme. Mais le RGPD le rend **de fait nécessaire** ici (voir § 1.2 : exercice des droits, art. 12-14 RGPD). Un e-mail dédié suffit.
- **Sanction** du défaut de mentions : 1 an d'emprisonnement et 75 000 € d'amende (art. 1-2 LCEN).

**Minimum légal retenu pour ce site** : une page « Mentions légales » indiquant (a) site édité à titre non professionnel par un particulier (art. 1-1, II LCEN), (b) identité complète de l'éditeur communiquée à l'hébergeur, (c) nom/raison sociale + adresse (+ téléphone) de l'hébergeur, (d) un e-mail de contact, (e) l'hébergeur comme point d'entrée du droit de réponse.

### 1.2 RGPD — pas de bandeau, pas de DPO ; mais le site EST responsable de traitement

**Cookies** : le consentement (donc le bandeau) n'est requis que s'il y a des traceurs soumis à consentement (art. 82 de la loi n° 78-17, transposant l'art. 5(3) de la directive ePrivacy 2002/58/CE). **Un site qui ne dépose aucun cookie ni traceur n'a aucun bandeau à afficher.**
CNIL : <https://www.cnil.fr/fr/cookies-et-autres-traceurs/que-dit-la-loi>. Constat code : zéro cookie, zéro storage, zéro analytics, zéro ressource tierce (voir § 2). Point de vigilance : **vérifier en production** que la plateforme d'hébergement n'injecte pas ses propres cookies.

**Le RGPD s'applique malgré tout** : republier sur internet des données personnelles (noms d'élus, déclarations, votes, alertes nominatives) est un traitement ; l'exception « domestique » ne couvre pas une publication accessible à tous (CJUE, *Lindqvist*, C-101/01, 6 nov. 2003). Le réutilisateur de données publiées sur internet est **responsable de traitement** : CNIL, « Recommandations pour les réutilisateurs de données publiées sur internet » (juin 2024) — <https://www.cnil.fr/fr/recommandations-reutilisateurs-donnees-internet> (PDF : <https://www.cnil.fr/sites/default/files/2024-06/recommandations_reutilisateurs_donnees_publiees_sur_internet.pdf>).

**Cadre de la réutilisation de données publiques légalement publiées** :
- **Art. 86 RGPD** : les données personnelles figurant dans des documents officiels peuvent être communiquées/réutilisées selon le droit national, pour concilier accès du public aux documents officiels et protection des données.
- **Art. L. 322-2 CRPA** : la réutilisation d'informations publiques comportant des données personnelles est subordonnée au respect du RGPD/loi Informatique et Libertés.
- **Guide pratique CADA-CNIL** de la publication en ligne et de la réutilisation des données publiques (avec Etalab, oct. 2019) : <https://www.cnil.fr/fr/open-data-la-cnil-et-la-cada-publient-un-guide-pratique-de-la-publication-en-ligne-et-de-la>.
- Cas HATVP : « les déclarations publiées par la Haute Autorité sont librement réutilisables », publiées « sous la licence ouverte Etalab » — <https://www.hatvp.fr/open-data/>. **Limite pénale absolue** : ne jamais reproduire le contenu des déclarations de situation patrimoniale consultables uniquement en préfecture (art. LO 135-2 du code électoral ; sanctions à l'art. 26 de la loi n° 2013-907) — le site n'utilise que les flux open data publiés par la HATVP elle-même.

**Obligations concrètes du réutilisateur** (CNIL, reco juin 2024 ; guide CADA-CNIL) :
1. **Finalité déterminée et légitime** : information des citoyens sur la vie publique ; **base légale : intérêt légitime** (art. 6(1)(f) RGPD), solide ici car les données proviennent de publications rendues obligatoires par la loi (loi n° 2013-907 — HATVP ; loi n° 2016-1691 « Sapin II », art. 18-1 s. — répertoire des représentants d'intérêts, y compris la liste officielle des entités en défaut ; open data des assemblées ; RNE du ministère de l'Intérieur ; CNCCFP…).
2. **Vérifier la licéité de la source** : sources officielles diffusées en open data en application de textes = licite (pas de moissonnage sauvage, pas de contournement de protections).
3. **Minimisation / pas d'enrichissement** : ne traiter que les champs publiés ès qualités, jamais de croisement avec des données non publiques ni de données de vie privée.
4. **Exactitude et fraîcheur** (art. 5(1)(d) RGPD) : dater les données, ré-ingérer régulièrement, corriger vite.
5. **Information des personnes** (art. 14 RGPD) : informer individuellement 36 018 élus = « effort disproportionné » → dérogation art. 14(5)(b), à condition de **mesures appropriées = information publique générale** : une page « Données personnelles » décrivant sources, finalités, base légale, catégories de données, durées, destinataires, droits et contact.
6. **Droits des personnes** : rectification (art. 16), opposition (art. 21 — pour des élus, sur des faits publics ès qualités, l'intérêt légitime d'information prévaut en principe, mais chaque demande doit être examinée), effacement limité par la liberté d'information (art. 17(3)(a)). **Il faut donc un canal de contact** et répondre sous un mois (art. 12(3)).
7. **Registre** (art. 30 RGPD) : la CNIL le demande à « tous les organismes, publics comme privés et quelle que soit leur taille » pour les traitements **non occasionnels** (la dérogation « moins de 250 salariés » ne couvre pas un traitement permanent) — <https://www.cnil.fr/fr/RGPD-le-registre-des-activites-de-traitement>. Pour une personne physique stricto sensu, l'obligation est discutée (les textes visent des « organismes ») ; position sûre et gratuite : **tenir une fiche registre d'une page** (document interne, jamais publié pour un acteur privé).
8. **DPO : non obligatoire** (art. 37(1) RGPD : uniquement autorité/organisme public, suivi régulier et systématique à grande échelle de personnes, ou données sensibles à grande échelle — aucun des trois : le site ne suit même pas ses visiteurs).
9. **Logs serveur** : même sans cookie, l'hébergeur journalise des adresses IP (donnée personnelle). À mentionner honnêtement dans la page « Données personnelles » (finalité sécurité, durée courte, traitement opéré par l'hébergeur).

### 1.3 Licences des données

**Licence Ouverte 2.0 (Etalab)** — texte : <https://www.data.gouv.fr/pages/legal/licences/etalab-2.0/>.
Obligation unique du réutilisateur : « mentionner la paternité de l'“Information” : sa source (a minima le nom du “Concédant”) et la date de la dernière mise à jour », satisfiable par une URL. Réutilisation commerciale libre, bases dérivées libres, **aucun partage à l'identique**. → Afficher, par source : producteur + lien + date de mise à jour. C'est ce que fait la page /donnees.

**ODbL 1.0** — <https://opendatacommons.org/licenses/odbl/summary/> : attribution, **share-alike sur les bases dérivées** (« if you publicly use any adapted version of this database, or works produced from an adapted database, you must also offer that adapted database under the ODbL »), keep open. Concrètement : si une source ODbL était intégrée à `france.db` et que le site (« produced work ») est public, il faudrait **offrir en téléchargement, sous ODbL, le sous-ensemble dérivé** (les tables issues de la source ODbL, ou le diff), et ces tables ne pourraient pas être re-licenciées en LO 2.0.

**Constat décisif (vérifié en base le 21/08/2026, table `meta_sources`)** : sur les **29 sources ingérées, 26 sont en Licence Ouverte** (variantes : LO 2.0, fr-lo, etalab-2.0, LO Etalab, LO (AN), LO (IGN/Etalab), mention DILA) ; deux sont des entrées « publications officielles / texte JORF » (constantes factuelles issues d'actes officiels, hors droit d'auteur, citées avec URL) ; la dernière, le registre de transparence de l'Union européenne, relève de la **décision 2011/833/UE** sur la réutilisation des documents de la Commission — réutilisation libre, sans partage à l'identique. **Aucune source ODbL n'est en base** — OFGL est en LO 2.0. L'ODbL ne concernerait que des sources non ingérées (HowTheyVote, données Parlement européen ODbL+DbCL, historique NosDéputés). **La SQLite actuelle n'a donc aucune obligation de re-partage.** Corollaire : le footer ne mentionne que la Licence Ouverte, l'ODbL en ayant été retirée comme inexacte (voir § 3).

### 1.4 Période électorale (sénatoriales du 27/09/2026)

**Fait** : décret n° 2026-301 du 21 avril 2026 portant convocation des collèges électoraux le dimanche 27 septembre 2026 (série 2, 178 sièges, suffrage indirect — grands électeurs) — <https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000053925339> ; <https://senatoriales2026.senat.fr/>. Dépôt des candidatures : 7-11 septembre 2026.

**Ce qui est du droit (s'applique à quiconque diffuse, y compris un site web)** :
- **Art. L. 49 code électoral** (<https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000039446215>) : à partir de la **veille du scrutin à 0 h**, interdiction de « diffuser ou faire diffuser par tout moyen de communication au public par voie électronique tout message ayant le caractère de propagande électorale ». Un contenu d'information factuelle, permanent et non partisan n'est pas de la propagande ; publier à ce moment-là un contenu appelant à voter pour/contre le serait.
- **Art. L. 48-2** : interdiction de porter à la connaissance du public un **élément nouveau de polémique électorale** à un moment tel que les adversaires ne puissent plus utilement répondre.
- **Art. L. 52-2** : aucun résultat, partiel ou définitif, avant la fermeture du dernier bureau de vote.
- **Sondages** : embargo la veille et le jour du scrutin (loi n° 77-808, art. 11) — sans objet, le site n'en publie pas.
- **Art. L. 52-1** (publicité commerciale à des fins électorales pendant les 6 mois précédant le scrutin) : vise la propagande payante — sans objet pour un site sans publicité.

**Ce qui n'est PAS du droit applicable ici** :
- Les règles d'équité/égalité des temps de parole (Arcom) ne s'imposent qu'aux **services de communication audiovisuelle** (loi n° 86-1067) — pas aux sites web édités par des particuliers.
- Le règlement (UE) 2024/900 sur la transparence de la **publicité politique** vise les services de publicité fournis contre rémunération — hors champ pour un site non commercial sans publicité.

**Précaution (pas d'obligation)** : neutralité de traitement — le site publie des métriques nominatives sur des sortants potentiellement candidats (participation, loyauté, alertes) ; à l'approche du scrutin, tout classement éditorialisant serait perçu comme une prise de position. Voir § 5.

### 1.5 Sécurité (ANSSI) — recommandations, pas d'obligation de niveau

Aucune obligation légale de « niveau de sécurité » pour un site vitrine de particulier (NIS2 ne vise pas ce cas) ; seule s'applique l'obligation générale de sécurité proportionnée de l'art. 32 RGPD — surface ici minimale (lecture seule, aucune donnée de visiteur collectée).

Références ANSSI : « Recommandations pour la mise en œuvre d'un site web : maîtriser les standards de sécurité côté navigateur » v2.0 (<https://messervices.cyber.gouv.fr/documents-guides/anssi-guide-recommandations_mise_en_oeuvre_site_web_maitriser_standards_securite_cote_navigateur-v2.0.pdf>) et « Recommandations de sécurité relatives à TLS » v1.2 (<https://messervices.cyber.gouv.fr/documents-guides/NP_TLS_NoteTech.pdf>) ; CNIL « Sécuriser les sites web » (<https://www.cnil.fr/fr/securite-securiser-les-sites-web>). En pratique : HTTPS partout (TLS 1.2/1.3), HSTS (`Strict-Transport-Security: max-age=31536000; includeSubDomains`), CSP, `X-Content-Type-Options: nosniff`, `frame-ancestors 'none'`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` minimale, dépendances à jour. Côté app : API en lecture seule, SQL paramétré, plafond 500 lignes — déjà en place.

---

## 2. Ce que l'app couvre déjà (constaté dans le code et sur le site servi le 21/08/2026)

- **Zéro cookie, zéro traceur, zéro tiers** : aucun `cookie`/`localStorage`/`sessionStorage`/analytics/police externe/CDN dans `app/src` (greps exhaustifs), aucun appel réseau au runtime (l'app ne lit que `data/france.db` ; affiché et vérifié). → Pas de bandeau à prévoir, conformité ePrivacy par construction.
- **Crédits et licences par source** : `app/src/app/donnees/page.tsx` affiche le catalogue des 29 sources avec **licence, date des données, date d'ingestion, fréquence, URL amont** (satisfait l'obligation LO 2.0 « source + date de dernière mise à jour »), plus un bloc « Licences et crédits » nominatif (DILA, HATVP, CNCCFP, ministère de l'Intérieur, AN, Sénat, OFGL, DGFiP, INSEE, IGN/Etalab, Datan avec méthodologie liée, decp-processing/Colin Maudry) et la doc des exports JSON quotidiens (chaque fichier porte un bloc `meta` : source, licence, dates).
- **Fraîcheur mesurée et affichée** (exigence d'exactitude art. 5(1)(d)) : badge de fraîcheur par source avec règle documentée, décalages structurels assumés.
- **Alertes nominatives déjà conformes aux bonnes pratiques CNIL** : « Déclaration non déposée » = **constat officiel HATVP repris tel quel** (statut natif de `liste.csv`, daté, URL de la page nominative HATVP, base légale citée) ; les « retards présumés » — la seule inférence maison — restent **agrégés, non nominatifs** ; défauts lobbying = liste officielle HATVP « flag public officiel, repris tel quel ». Minimisation : `/api/elus.json` sert des « champs publics uniquement ».
- **Pas d'enrichissement hors open data** : les pipelines ne consomment que les flux officiels listés ; rien issu des déclarations consultables en préfecture.

## 3. Mise en œuvre — état constaté le 21/08/2026

Les points de conformité relevés à l'établissement de ce document sont en place sur le site servi, et chacun est vérifiable d'une commande :

1. **`/mentions-legales`** — régime d'éditeur non professionnel anonyme (art. 1-1, II LCEN) : mention d'identification, absence assumée de directeur de la publication (art. 93-2 de la loi n° 82-652), et bloc hébergeur complet — **Scaleway SAS, 8 rue de la Ville l'Évêque, 75008 Paris**, forme sociale et numéro RCS inclus.
2. **`/donnees-personnelles`** — information générale au titre de l'art. 14(5)(b) RGPD : responsable de traitement, finalité, base légale, catégories de données et personnes concernées, sources (renvoi à /donnees), absence de cookie et de collecte sur les visiteurs, logs techniques de l'hébergeur, durées de conservation, droits et droit de réclamation auprès de la CNIL.
3. **E-mail de contact dédié** — une adresse dédiée (et non l'adresse personnelle de l'éditeur) est publiée sur les deux pages ci-dessus comme canal d'exercice des droits ; elle vit dans `app/src/lib/site.ts` et `ft-localiser` vérifie à chaque déploiement qu'elle n'a pas dérivé.
4. **Footer sans « ODbL »** — la mention inexacte a été retirée : le sigle n'apparaît nulle part dans l'export servi (`grep -rl ODbL` sur le site généré ne renvoie rien).
5. **Lien vers le texte de la Licence Ouverte 2.0** sur `/donnees` et dans le footer (<https://www.etalab.gouv.fr/licence-ouverte-open-licence/>).
6. **Aucun cookie posé par la plateforme** : `curl -sI https://francetransparence.fr` ne renvoie aucun `Set-Cookie` — cohérent avec l'absence de cookie côté application (§ 2).
7. **En-têtes de sécurité servis par nginx**, et non plus relégués dans un `<meta http-equiv>` : `Strict-Transport-Security`, `Content-Security-Policy` (dont `frame-ancestors 'none'` et `form-action 'none'`, tous deux inopérants en meta), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`.

**Point non couvert** : aucune fiche de registre au titre de l'art. 30 RGPD n'est tenue hors ligne à ce jour (§ 4).

## 4. Risques résiduels honnêtes

- **Republication de données personnelles d'élus : FAIBLE.** Données publiées en exécution d'obligations légales, réutilisation prévue par le cadre (art. 86 RGPD, L. 322-2 CRPA, licences ouvertes), finalité d'information, minimisation effective, fraîcheur affichée, alertes nominatives = constats officiels datés et sourcés. Le risque ne devient réel que si le site perd son contact et ses pages d'information (§ 3) ou si une donnée défavorable périmée reste affichée : fenêtre d'obsolescence ≤ 7 jours entre deux ingestions HATVP + correction sur demande = résiduel faible. S'interdire durablement tout enrichissement hors open data (le croisement avec des données non publiques ferait basculer l'analyse).
- **Anonymat LCEN vs transparence RGPD : FAIBLE mais réel.** L'art. 14 RGPD demande « l'identité et les coordonnées du responsable du traitement » ; le compromis retenu (éditeur non professionnel anonyme + e-mail de contact effectif + identité détenue par l'hébergeur) est la pratique établie des sites citoyens, jamais sanctionnée à notre connaissance, mais un plaignant tatillon pourrait la contester. Réponse rapide aux demandes = meilleure défense.
- **ODbL : NUL aujourd'hui** (aucune source ODbL en base, vérifié), à re-vérifier à chaque ajout de source (le point de bascule est l'ingestion, pas l'affichage).
- **Registre art. 30 pour une personne physique : zone grise** doctrinale ; le sujet se traite par une fiche d'une page tenue hors ligne (traitement « republication de données publiques d'élus », finalité, base légale, catégories, sources, durées, mesures de sécurité), non publiée. Elle n'existe pas à ce jour (§ 3).
- **Exactitude des scores tiers (Datan)** : scores calculés par un tiers, crédités avec méthode liée — conforme ; le risque d'un score contesté se traite par la rectification/contextualisation, pas par la licence.

## 5. Période électorale — règles éditoriales en vigueur

Le décret de convocation cité au § 1.4 ouvre une période électorale ; les règles que le site s'applique alors sont les suivantes.

1. **Gel éditorial la veille et le jour du scrutin** : aucune publication nouvelle nominative sur des candidats ou des sortants (site et éventuels relais sociaux), aucun résultat avant les heures légales (art. L. 49 et L. 52-2 c. élect. — prudence au-delà du strict champ « propagande »). Les données permanentes et datées du site restent en ligne : ce n'est pas de la propagande.
2. **Aucun classement éditorialisant en période électorale**, du dépôt des candidatures à la clôture du scrutin : pas de « top/flop sénateurs », pas de superlatifs ; uniquement les métriques existantes, brutes, sourcées, avec méthodologie liée et date visible — et aucune « révélation » nominative de dernière minute qu'un intéressé ne pourrait plus utilement contester (esprit de l'art. L. 48-2).
3. **Fraîcheur et rectification prioritaires** : ré-ingestion HATVP/parlement vérifiée chaque semaine, mention de date visible sur les pages sénateurs, traitement en 48 h de toute demande de rectification émanant d'un candidat pendant la période — au lieu du délai d'un mois du RGPD, délai réduit déjà annoncé sur `/donnees-personnelles`.

---
*Références vérifiées le 19/08/2026. Ce document est une analyse de conformité préparatoire rédigée sans avocat ; il cite ses sources pour permettre la contre-vérification.*
