# Licences — code et données

Ce dépôt réunit deux choses de nature juridique différente. Les confondre serait
une erreur, et sur un projet de transparence, une erreur visible.

## Le code : AGPL-3.0-or-later

Tout le code de ce dépôt — pipelines d'ingestion, application web, scripts de
déploiement — est publié sous **GNU Affero General Public License, version 3 ou
ultérieure**. Le texte intégral est dans le fichier `LICENSE`.

Pourquoi l'AGPL et pas une licence permissive : ce projet demande à
l'administration de publier ce qu'elle produit. Il serait incohérent qu'une
version modifiée de cet outil puisse être exploitée comme service en ligne sans
que ses modifications soient elles-mêmes publiées. C'est précisément la clause
que l'AGPL ajoute à la GPL, et c'est celle qui compte pour un logiciel dont
l'usage normal est d'être servi sur le web plutôt que distribué.

Conséquence pratique : vous pouvez utiliser, étudier, modifier et redéployer ce
code, y compris commercialement. Si vous le faites tourner comme service
accessible au public, vous devez proposer aux utilisateurs de ce service le code
source de votre version.

## Les données : licences de leurs producteurs, pas la nôtre

**Les données ingérées ne sont pas couvertes par l'AGPL et ne peuvent pas
l'être** : elles ne nous appartiennent pas. Chaque source conserve la licence
sous laquelle son producteur l'a publiée — pour l'essentiel la **Licence Ouverte
2.0 (Etalab)**, qui autorise la réutilisation, y compris commerciale, sous
réserve de mentionner la paternité et la date de mise à jour.

La licence exacte de chaque source figure dans la table `meta_sources` de la
base et sur la page `/donnees` du site, à côté de sa date de fraîcheur mesurée.
C'est la référence à consulter avant toute réutilisation.

**Deux points de vigilance** :

- Certaines sources envisagées ou ingérées peuvent porter des clauses plus
  restrictives que la Licence Ouverte — notamment des clauses **non
  commerciales** (CC BY-NC-SA). Une telle clause interdit certaines
  réutilisations que la Licence Ouverte autoriserait. Vérifiez source par
  source ; ne présumez pas d'une licence uniforme.
- Les données publiées ici concernent des **personnes réelles** (élus,
  candidats, représentants d'intérêts). Leur caractère public n'annule pas le
  RGPD : voir la page « Données personnelles » du site.

## Fraîcheur et exactitude

Aucune garantie n'est donnée sur l'exactitude des données. Elles sont reprises
des publications officielles, avec leur date réelle affichée. Quand une source
cesse d'être mise à jour en amont, le site le signale plutôt que de masquer le
vieillissement derrière une date de génération fraîche.

Une erreur constatée peut être signalée : voir les mentions légales du site pour
le canal de contact.
