# ACTIONS HUMAINES — ce qui exige physiquement Mickael

État au 20/08/2026, relu le 15/10/2026 (sections 1 et 2 mises à jour ce jour ; section datée du 15/10/2026 ajoutée en tête après l'audit du même jour). Les deux actions les plus attendues (domaine, e-mail de contact) sont **faites** : le site vit sur https://francetransparence.fr, servi par nginx depuis un serveur dédié, et les pages légales portent une adresse de contact dédiée. Ce fichier ne garde que ce qui reste ouvert.

## 11/11/2026 — Venv du serveur : dépendances figées

`requirements.txt` passe de bornes basses (`duckdb>=1.3`) à des versions exactes, transitives comprises. Au premier `ft-deploy` qui suit la fusion, `git pull` rend ce fichier plus récent que `.venv/bin/pip`. Au premier `make ingest-…`, la règle `$(VENV)/bin/pip` du `Makefile` lance alors `pip install --upgrade pip`, puis `pip install -r requirements.txt`, **avec l'interpréteur de la venv existante** (`.venv/bin/python`). Elle ne rappelle `$(PYTHON)` (`python3.14` par défaut) que si la venv n'a pas d'interpréteur exécutable. Une venv existante n'a donc besoin ni de `python3.14` ni d'un `PYTHON=…` passé par `ft-deploy`, et elle ne change pas d'interpréteur. **PyPI doit rester joignable à ce moment-là.** Un échec arrête le cycle avant la bascule : le site de la veille reste servi. `make test` vérifie ensuite que la venv porte exactement les versions figées (`pipelines/tests/test_dependances.py`, qui passe sous Python 3.10 à 3.14 et ne regarde ni pip ni setuptools). Changer d'interpréteur reste un geste explicite : supprimer `.venv`, puis `make venv PYTHON=…`.

1. **Avant toute montée de DuckDB en 2.x** (point 2), relever l'interpréteur et les versions de la venv, et la façon dont `ft-deploy` appelle `make` :
   ```sh
   sudo -u ftweb /srv/france-transparence/app/.venv/bin/python -V
   sudo -u ftweb /srv/france-transparence/app/.venv/bin/pip freeze
   command -v python3.14 python3
   grep -n 'make\|PYTHON\|venv' /usr/local/bin/ft-deploy
   ```
   Les versions figées ont des roues pour CPython 3.10 à 3.14 en Linux x86_64 (glibc 2.26 ou plus récente ; Ubuntu 22.04 a 2.35), vérifié sur PyPI le 11/11/2026, et la suite hors réseau passe sous Python 3.10 comme sous 3.14.
2. **Ne monter DuckDB en 2.x que si cet interpréteur est en 3.11 ou plus.** DuckDB 2.0 n'a aucune roue pour Python 3.10. La CI joue Python 3.14 : une proposition Dependabot `duckdb==2.0.0` y passerait au vert, puis échouerait à l'installation sur un serveur en 3.10. `.github/dependabot.yml` ignore donc `duckdb>=2.0.0` : lever cet `ignore` une fois l'interpréteur relevé en 3.11 ou plus. Le code et les tests passent sous 1.5.6 et sous 2.0.0.
3. **L'arrêt des publications depuis le 08/11 n'est très probablement pas dû à DuckDB 2.** `requirements.txt` n'avait pas changé depuis le commit initial du 20/08 (4b95cbc) : `make` ne réinstallait donc rien. Et le serveur a publié du 22/10 au 08/11, alors que DuckDB 2.0 faisait échouer la suite de tests dès qu'il était installé. Sa cause reste à lire dans `/var/log/france-transparence/deploiement.log` et `journalctl -u ft-deploy`.

## 11/11/2026 — Journal officiel : ce que donnera le premier cycle du serveur, et ce qu'il faut y lire

Le 08/11/2026 la DILA a renouvelé son dépôt JORFSIMPLE et en a retiré toutes les livraisons antérieures : le 11/11 il ne proposait plus que deux éditions quotidiennes (10/11 et 11/11). `ft-deploy` ingère chaque nuit dans une base **neuve** ([RUNBOOK](deploiement/RUNBOOK.md)) : la fenêtre du JO n'a donc jamais tenu que par ce que le dépôt listait encore, et il n'existe pas de « base de la veille » à reprendre.

Le correctif du 11/11 fait trois choses : un index sans livraison nocturne ne tue plus le cycle ; chaque nocturne téléchargée est copiée, avec son empreinte SHA-256, dans un coffre hors de `data/raw` ; une livraison que l'index ne liste plus est relue depuis une copie locale vérifiée (coffre, ou `data/raw/jorf` si le fichier y est encore). Poids mesuré : 4,7 Mo pour 30 nocturnes, rétention de 60 jours, soit de l'ordre de 10 Mo.

**Ce que le dépôt ne sait pas, et qui décide du premier cycle** : si `data/raw/jorf` porte encore, sur le serveur, les nocturnes téléchargées avant le 08/11. La purge de 23 h les retire, sauf si `jorf/` figure dans `/etc/france-transparence/cache-long.conf` ou si la purge n'a pas tourné pendant les cycles en échec depuis le 09/11.

1. **Avant le premier cycle** qui suit la fusion, relever (lecture seule) :
   ```sh
   ls -l /srv/france-transparence/app/data/raw/jorf | tail -40
   grep -n 'jorf' /etc/france-transparence/cache-long.conf
   ```
   - des `JORFSIMPLE_202610*` et `JORFSIMPLE_202611*` d'avant 06 h sont encore là : le premier cycle les relit, la fenêtre revient à une trentaine de JO **dès ce cycle**, et ils entrent au coffre. Ne rien purger à la main avant ;
   - le dossier est vide ou ne porte que les nocturnes du jour : le premier cycle publie les seuls JO que le dépôt propose (2 le 11/11, un de plus par parution), `/documents` l'affiche comme « Fenêtre réduite : N JO sur les 30 visés… », et la fenêtre regagne un JO par parution — trente JO au bout d'une trentaine de parutions, soit cinq à six semaines. Les JO du 06/10 au 08/11 ne reviendront pas d'eux-mêmes : ils ne sont plus dans le dépôt, et les sauvegardes de la base ne sont pas des livraisons que le pipeline sait relire.
2. **Après le premier cycle**, vérifier que le coffre s'est rempli, et lequel :
   ```sh
   grep -n '\[jorf\].*\(coffre\|relue\|fenêtre\)' /var/log/france-transparence/deploiement.log | tail -12
   ls -l /data/france-transparence/amont/S3-JORFSIMPLE /srv/france-transparence/app/data/amont/S3-JORFSIMPLE 2>/dev/null | tail
   ```
   Le pipeline écrit d'abord dans le coffre de `archive_amont.py` (`/data/france-transparence/amont/S3-JORFSIMPLE`). S'il n'est pas inscriptible par l'utilisateur qui ingère (`ftweb`), il se replie sur `data/amont/S3-JORFSIMPLE` dans l'arbre `app`, hors de `data/raw` et ignoré par git. La ligne « coffre … : N nocturne(s) ajoutée(s) » dit lequel a servi. « aucun coffre inscriptible » = rien n'est conservé, et la prochaine régénération du stock DILA réduira de nouveau la fenêtre : donner alors le dossier à `ftweb`, par exemple
   ```sh
   install -d -o ftweb -g ftweb -m 700 /srv/france-transparence/app/data/amont/S3-JORFSIMPLE
   ```
3. **Vérifier que rien ne vide `data/amont`** : ni la purge de 23 h (elle doit ne viser que `data/raw`), ni un `git clean` de `ft-deploy`. Relever :
   ```sh
   grep -n 'clean\|find .*-delete\|-mmin\|rm -' /usr/local/bin/ft-deploy
   ```
   Si le repli dans l'arbre est celui qui sert, l'inscrire dans la sauvegarde locale n'est pas utile (10 Mo reconstructibles tant que le dépôt DILA les propose), mais il ne doit pas être effacé entre deux cycles.
4. **Jours suivants** : `ft-fraicheur` et la phrase d'en-tête de `/documents` disent le nombre de JO et leurs bornes. Une ligne « aucun JO entre le … et le … » signale des jours que ni le dépôt ni les copies ne couvrent.

La réintégration depuis `jorf_textes_archive`, écrite le même jour, ne joue que sur une base qui persiste d'un cycle à l'autre : elle est sans effet sur le serveur tel qu'il ingère aujourd'hui.

## 11/11/2026 — Alertes : ce que le dépôt ne peut pas faire à votre place

Du 22/10 au 11/11/2026, la validation quotidienne a échoué vingt et un jours de suite et le site est resté figé à partir du 08/11 sans que personne soit prévenu : le dépôt n'avait aucun abonné, et l'issue d'échec ni personne d'assigné ni mention. Les issues d'alerte sont désormais assignées au propriétaire du dépôt et le mentionnent, et une vigie quotidienne regarde le site du dehors (RUNBOOK § 7). Restent quatre gestes :

1. **Vérifier qu'une alerte arrive réellement.** Une issue `site-fige` (ou `publication-echec`) ouverte par `github-actions` vous est assignée et vous mentionne : le courriel ou la notification correspondante est-il arrivé ? L'API ne permet pas de le vérifier depuis le dépôt (le jeton n'a pas le scope `notifications`). Sinon : https://github.com/settings/notifications — activer le courriel pour « Participating, @mentions and custom », et « Actions : failed workflows only ».
2. **S'abonner au dépôt** : Watch → Custom → Issues (ou All activity). `gh api repos/koutakou/france-transparence/subscribers` rendait `[]` le 11/11/2026. C'est le second canal, indépendant du code d'alerte.
3. **Rendre le check `tests-python-3-10` requis** sur `main` (Settings → Branches), à côté de `construire`, une fois vu vert : il rejoue les tests des pipelines sous Python 3.10, pour qu'une montée de dépendance qui abandonne cet interpréteur soit refusée avant la fusion. À ne garder requis que tant que la venv du serveur peut être en 3.10 (section « Venv du serveur », ci-dessus).
4. **Faire sortir l'alerte du serveur.** `ft-alerte` écrit dans le journal systemd et pousse vers un webhook « si l'un est configuré » ; le gel du 08/11 n'a atteint personne. La vigie le verra désormais, mais une fois par jour et seulement si GitHub fonctionne. À poser sur le serveur : un envoi réel (courriel vers la boîte de contact) à chaque échec de `ft-deploy`, répété chaque jour tant que `current` n'a pas basculé, avec le nombre de jours dans l'objet. Et, pour le gel en cours : `ft-etat`, puis `/var/log/france-transparence/deploiement.log`.

## 11/11/2026 — `ft-deploy` ingère-t-il dans une base neuve ou dans la base du dernier cycle ? Trois secours en dépendent

Les secours « publication précédente » de `jorf`, `dole` et `ingest-parlement` (dump `export_sens` vide, borne de 3 jours) lisent la base **du cycle en cours** (`db.publication_precedente`, `cycle_precedent`). Ils ne jouent que si cette base porte déjà un cycle réussi. Or le dépôt se contredit sur ce point, et seul `/usr/local/bin/ft-deploy` le tranche :

- **base neuve** : c'est ce que disent le [RUNBOOK § 1](deploiement/RUNBOOK.md) (« make ingest (base SQLite neuve) »), la section Journal officiel ci-dessus et `ingest_jorf.py` ;
- **base qui persiste** : c'est ce que supposent le RUNBOOK § 4 (une table réécrite à la main avec un acquittement P15, puis « `ft-deploy` tout court », qui ne passe que si le cycle relit cette table), `docs/HATVP-DECLARATIONS.md` (contrôles inter-cycles « qui ne vivent que sur le serveur ») et `ingest_decp.py` (`_reconcilier_schema` : « la base servie est persistante et migrée »). Et `make ingest` ne supprime pas `data/france.db` : la base n'est neuve que si `ft-deploy` l'efface ou en désigne une autre.

Ce qui est sûr : **la CI ingère toujours dans une base neuve**. Le cycle planifié saute la restauration du cache ; un autre événement n'ingère que si aucun cache ne correspond, et sinon n'ingère pas du tout. Les secours n'y jouent donc jamais. Si le serveur ingère lui aussi dans une base neuve, une panne de ces trois sources fait échouer le cycle comme avant, en tout-ou-rien. C'est honnête (la veille reste servie), mais la nuit entière est perdue.

1. **Relever** (lecture seule) :
   ```sh
   grep -n 'france\.db\|FT_DB_PATH\|FRANCE_DB_PATH\|make ingest\|rm \|mv \|cp \|sqlite3' /usr/local/bin/ft-deploy
   ls -l --time-style=long-iso /srv/france-transparence/app/data/france.db*
   sqlite3 -readonly /srv/france-transparence/app/data/france.db \
     "SELECT 'votes_recents_archive', count(*), min(archive_le) FROM votes_recents_archive
      UNION ALL SELECT 'jorf_textes_archive', count(*), min(archive_le) FROM jorf_textes_archive;"
   ```
   Une base neuve n'archive que ce que son propre cycle a fait sortir de la fenêtre. Mesuré sur une base neuve ingérée le 11/11/2026 : les deux tables sont **vides** ; au plus, elles porteraient des dates `archive_le` de ce seul cycle. Des lignes datées d'avant le dernier cycle prouvent que la base persiste. Si `ft-deploy` désigne une autre base que `data/france.db`, poser la même question à celle-là.
2. **Si la base est neuve**, la recommandation est de faire partir `ft-deploy` d'une **copie** de la base du dernier cycle publié, posée à l'endroit où ingère `make ingest` avant son lancement, jamais du fichier servi lui-même. C'est ce qui rendrait effectifs les secours `jorf`, `dole` et ODSEN. Vérifié dans le code le 11/11/2026, cette copie ne change rien pour les tables que leur pipeline remplace en entier à chaque cycle, par `DELETE` puis `INSERT` ou par `DROP` puis recréation, en transaction :
   - `referentiels`, `budget_mensuel` (et `budget_mensuel_ruptures`), `budget_structure`, `decp`, `boamp`, `approch`, `lobbying`, `financement`, `collectivites`, `elections`, `trainvie`, `cada`, `registre_ue`, `dette_maastricht`, `deficit_maastricht`, `dole`, `agregats_apu`, `cge`, `protection_sociale`, `recettes_plf`, `ircom`, `rei`, `cofog_apu`, `comptes_apu_insee`, `odac_insee`, `adlc`, `sirene` ;
   - dans `parlement` : `deputes` et `groupes_an` (suppression de la législature puis réinsertion), `senateurs` (remplacement puis suppression des absents), `votes_senat`, `scrutins_senat` et `participation_senat` ;
   - la table partagée `alertes` : chaque pipeline n'en supprime que ses propres types.

   **Ce qui n'est PAS remplacé**, et changerait donc de comportement :
   - `elus` n'est jamais vidée. P9 complète et met à jour les fiches, et date la fin des mandats des sortants ; P7 complète et supprime les seuls doublons qu'il rattrape. Avec une base copiée, les fiches des élus sortis de la chambre **restent publiées**, mandat clos, alors qu'une base neuve ne les recrée pas. Le nombre de fiches, le sitemap et les redirections 301 changent : à relire avant de basculer.
   - `scrutins` est en `INSERT OR REPLACE`, jamais vidée. C'est sans effet aujourd'hui : le fichier amont porte toute la législature.
   - `jorf_textes` est une fenêtre glissante, avec réintégration depuis `jorf_textes_archive`. Les tables `*_archive` (JO, votes AN et Sénat, annonces BOAMP) sont en `INSERT OR IGNORE` : elles **croissent** d'un cycle à l'autre et ne sont pas servies.
   - Les contrôles inter-cycles de P15 (`hatvp_decl_*`, comparées au cycle précédent avant d'être recréées) et le plafond de rattrapages de P7 deviendraient **actifs**. Un cycle pourrait alors échouer et exiger un acquittement nommé (RUNBOOK § 4), ce qui est leur rôle.
   - Le **schéma** : `CREATE TABLE IF NOT EXISTS` ne migre pas une base copiée. Seuls `decp` (`_reconcilier_schema`) et `boamp` (`migrer_ao_en_cours`) migrent leurs tables. Une proposition qui change le schéma d'une autre table casserait le cycle serveur sans que la CI, sur base neuve, le voie : c'est déjà arrivé (f336df8, 0597ad0). Il faudrait donc soit une migration dans chaque pipeline concerné, soit, en cas d'échec de schéma, un repli vers une base neuve.
3. **Si la base persiste déjà**, les secours sont effectifs sur le serveur, et c'est le RUNBOOK § 1 (« base SQLite neuve »), la section Journal officiel ci-dessus et `ingest_jorf.py` qu'il faut corriger.

## 15/10/2026 — À faire sur le serveur et sur GitHub

L'audit du 15/10/2026 et les quinze propositions fusionnées le même jour (JOURNAL.md, décisions 35-46) laissent des gestes qu'aucune fusion ne fait : les scripts `ft-*`, nginx, la zone DNS et les réglages GitHub vivent hors du dépôt. Les correctifs fusionnés le 15/10 n'arrivent en ligne qu'au cycle `ft-deploy` du 16/10 : sauf mention contraire, chaque geste serveur ci-dessous se fait **après** ce cycle.

### Serveur

1. **Poser les redirections d'élus** (PR #112 et #113), en régime « courant » de [REDIRECTIONS-ELUS.md](REDIRECTIONS-ELUS.md), donc APRÈS le déploiement de la table par `ft-deploy`, et jamais pendant qu'il tourne. La table passe à 23 lignes : 8 anciennes fiches de députés devenus sénateurs y entrent, et 2 lignes en sortent, dont les cibles ont quitté le Sénat le 27/09 (elles menaient à un 404 depuis le 05/10).
   ```sh
   /root/poser-301-d22.sh --essai
   /root/poser-301-d22.sh
   ```
   Lire ensuite la ligne `ft-controle-301` de `/var/log/france-transparence/deploiement.log`. Attendu : **23/23**. Si `poser-301-d22.sh` ou `ft-controle-301` porte un compte écrit en dur (le lot du 26/08 en avait 17), l'adapter.
2. **Retirer le `security.txt` posé à la main** (PR #114). Il est désormais généré au build (`Contact: mailto:` d'abord, puis le signalement privé GitHub), mais une configuration nginx hors dépôt sert encore l'ancien fichier, qui renvoie vers les issues publiques.
   ```sh
   sudo grep -rn 'security.txt\|well-known' /etc/nginx/
   ```
   Retirer la `location` ou le fichier dédié, **sans toucher à `acme-challenge`**, puis `ft-nginx-reload` (jamais `systemctl reload nginx` seul). Vérifier ensuite : `curl -s https://francetransparence.fr/.well-known/security.txt`, qui doit commencer par `Contact: mailto:`.
3. **Poser deux fois les gardes de la CI dans `ft-deploy`** (PR #119 et #122 ; « toute garde se pose deux fois »). Le `package.json` de l'app est dans le sous-dossier `app/` de l'arbre `/srv/france-transparence/app`.
   - `npm test`, juste après le `npm ci` de l'app et avant `npm run build`, dans le même répertoire et sous le même `set -e`. Essai préalable, sans base, environ 1 s : `cd /srv/france-transparence/app/app && npm test`.
   - Le budget de poids, juste après le build statique, dans le même répertoire : `node scripts/poids-pages.mjs out`, comme le joue la CI. La commande sort en échec si une page dépasse 500 Ko : **à décider** si, côté serveur, elle bloque la bascule ou avertit seulement, pour ne pas geler la publication. Dans les deux cas, garder sa sortie dans le journal du cycle : elle liste les pages les plus lourdes même au vert.
   - Vérifier au même passage que les comptages de fiches des scripts serveur supportent le nouveau sous-dossier `out/elus/annuaire/` (PR #118) : un script qui compte les dossiers de `out/elus` y voit une entrée de plus qu'il n'y a de fiches.
4. **Ne pas mettre en cache les fragments d'appels d'offres** (PR #115 et #122). Le navigateur charge la tranche horaire qu'il vit (`/data/marches/ao-toutes/<heure>.json`, `/data/accueil/ao-cloture/<heure>.json`), et `/data/marches/ao.json` au clic sur une famille. Ces fichiers sont servis aujourd'hui, comme tout `/data/`, avec `Cache-Control: public, max-age=3600, stale-while-revalidate=86400` (relevé le 15/10/2026). Or une tranche du même nom existe dans deux builds successifs, puisque la réserve couvre 48 h : un navigateur peut donc resservir la version de la veille, avec des avis annulés ou modifiés depuis. Poser `Cache-Control: no-cache` (revalidation à chaque chargement, 304 si rien n'a changé) sur ces trois chemins. ⚠️ Un `add_header` dans une `location` fille fait perdre TOUS les `add_header` hérités : y reprendre les en-têtes de sécurité (HSTS, CSP, `nosniff`…). Contrôle : `curl -sI https://francetransparence.fr/data/marches/ao.json`.
5. **HTTPS de `francetransparence.org`** (audit du site, constat 8 ; zone OVH). Le port 443 refuse la connexion, l'apex n'a aucun enregistrement A ni AAAA, et la redirection web OVH de `www` et `m` est en HTTP seul. Elle perd aussi la barre finale du chemin, ce qui ajoute un second 301. Deux voies :
   - pointer l'apex, `www` et `m` vers l'adresse du serveur, émettre un certificat pour les trois noms, et ajouter un bloc nginx qui renvoie `301 https://francetransparence.fr$request_uri` en HTTP comme en HTTPS (plus un CAA `letsencrypt.org`) ;
   - si le `.org` ne sert à rien : supprimer `www` et `m` plutôt que de servir du HTTP seul.
6. **Brotli** (constat 21) : `curl -H 'Accept-Encoding: br'` reçoit l'accueil non compressé, alors que gzip est servi partout. Il faut le module `ngx_brotli` avec `brotli_static on;` et des `.br` produits par `ft-precompresser` à côté des `.gz`, si le module existe pour la version de nginx installée. Gain typique de 15 à 20 % sur HTML et JS.
7. **IPv6** (constat 25, facultatif) : aucun AAAA pour l'apex ni `www`. Si le serveur dispose d'un bloc IPv6 : publier un AAAA et écouter `[::]:80` et `[::]:443`.
8. **Conservation réelle des journaux face à celle que publie `/donnees-personnelles`** (audit CI/docs, constat 17 ; **à trancher en priorité**, car une durée publiée fausse est un manquement à l'information due aux personnes). La page annonce `access.log` (IP complète) conservé 52 jours et `audience.log` (IP tronquée) 400 jours. Elle annonce aussi que la mesure d'audience lit `access.log` pour les périodes qu'`audience.log` ne couvre pas. Le serveur sert le site depuis le 20/08 ; la série d'audience commence pourtant au 15/09. Soit le repli sur `access.log` (fichiers tournés et compressés compris) n'est pas implémenté, soit la conservation réelle diffère de celle publiée. Établir lequel :
   ```sh
   grep -A10 -E 'access|audience' /etc/logrotate.d/nginx /etc/logrotate.d/nginx-audience
   ls -l --time-style=+%F /var/log/nginx/access.log* /var/log/nginx/audience.log*
   ```
   Lire la première ligne du plus ancien fichier de chaque série (`zcat -f <fichier> | head -1`) et la liste des fichiers qu'ouvre le script de série d'audience.
   - Si les journaux remontent bien au 20-24/08 : corriger le script (repli sur les rotations compressées).
   - S'ils commencent plus tard : la page publique et le registre art. 30 doivent dire la date de début réelle et sa cause (proposition de fusion sur `app/src/app/donnees-personnelles/page.tsx`).

   Au même passage :
   - établir pourquoi le 06/10 est une journée partielle dans les journaux ;
   - confirmer que `/var/log/nginx` est hors du périmètre de `ft-sauvegarde-distante`, puisque la page affirme que les journaux ne sont pas sauvegardés à l'extérieur.
9. **Basse priorité** (constats 22 à 24 de l'audit du site) :
   - `/api/` et `/data/` rendent la page 403 brute de nginx : `error_page 403 =404 /404.html;` ;
   - `http://francetransparence.fr/elus` fait deux sauts de 301 : rediriger le bloc `:80` directement vers l'URL canonique ;
   - retirer `interest-cohort=()` de `Permissions-Policy` (FLoC abandonné, Chromium le journalise).

### GitHub

1. **Protection de `main`** : activer `enforce_admins` (Settings → Branches → « Do not allow bypassing the above settings »). Relevé le 15/10/2026 : `enforce_admins: false` et `strict: false`. La PR #106 a été fusionnée avec `construire` en échec, et `main` est tombé dans la minute. Pour une panne amont passagère, relancer le check plutôt que contourner. Activer aussi `strict` (branche à jour avant fusion) est recommandé par l'audit.
2. **Dependabot** : `.github/dependabot.yml` propose les mises à jour, mais les **alertes** et **correctifs de sécurité** ne dépendent que des réglages (Settings → Code security → « Dependabot alerts » et « Dependabot security updates »), relevés désactivés le 15/10/2026.
3. **Label `publication-echec`** — FAIT le 11/11/2026 (description relevée ce jour : « La validation CI a échoué — le site en ligne n'est pas concerné »). Elle disait « le site sert la veille », alors que la CI ne publie rien. Commande jouée :
   ```sh
   gh label edit publication-echec --repo koutakou/france-transparence --description "La validation CI a échoué — le site en ligne n'est pas concerné"
   ```
   L'issue #105 sera fermée par le premier cycle planifié vert qui suit la fusion du job `suivre`.
4. **Clé SSH de déploiement** (audit CI/docs, constat 20). La clé dite « dédiée » est une clé d'authentification du COMPTE, sans passphrase : elle donne l'écriture sur tous les dépôts du compte. Le dépôt n'a aucune deploy key (`gh api repos/koutakou/france-transparence/keys` rend `[]`). Remplacer par une vraie clé de déploiement du dépôt, en écriture :
   ```sh
   gh repo deploy-key add <clé publique>.pub --repo koutakou/france-transparence --allow-write --title france-transparence-deploy
   ```
   Supprimer ensuite la clé de compte (`gh ssh-key list` pour son identifiant, puis `gh ssh-key delete <identifiant>`), et adapter `deploy/creer-repo-github.sh` et le RUNBOOK.

### Décisions éditoriales

1. **Tri des particules** (PR #118) : « de Courson » se range aujourd'hui à la lettre D, nom trié tel qu'il s'écrit. Le ranger sous C (particule ignorée) serait une règle d'usage à choisir et à écrire.
2. **Adresse de contact et anonymat de l'éditeur** (audit du site, constat 27 ; PR #114). `/mentions-legales` invoque le régime de l'éditeur non professionnel non identifié (art. 1-1, II LCEN), mais l'adresse de contact publiée sur cette page et sur `/donnees-personnelles` contient le nom et le prénom de l'éditeur. Choisir : une adresse non nominative si l'anonymat est voulu, ou l'identification assumée et un texte simplifié. Ce n'est pas signalé comme une erreur légale, mais comme une incohérence à lever.
3. **Signaler à la HATVP l'organe erroné du dossier `rne-21dc0877411d1a6f`** (PR #123) : Jonathan ABIENSO est, au RNE, 1er vice-président de la CC de l'Ouest Guyanais ; la HATVP le déclare vice-président du « Territoire de la Côte Ouest » (La Réunion), dont les quinze vice-présidents du RNE sont exactement les quinze autres de la page HATVP. Le lien est conservé sur le site ; la valeur amont ne se rectifie pas ici, elle se signale au producteur.
4. **Choix pris au plus prudent par les correctifs, à valider** : date du module Frais (S31) au 11/06/2026, date des refus écrits AN/Sénat (#108) ; deux comparaisons aux enveloppes 2021-2023 retirées, « au moins » 18 mois de marchés dits incomplets, phrase des destinataires du lobbying reformulée (#115).

## Ce qui n'est plus à faire

### Domaine — FAIT

`francetransparence.fr` est enregistré et en service. Sa zone pointe l'apex **et** `www` vers l'adresse IPv4 du serveur dédié (Scaleway Dedibox, Ubuntu 22.04) qui sert le site ; TLS et redirection 301 HTTP→HTTPS sont posés côté nginx.

> **AVERTISSEMENT — l'ancienne consigne DNS de ce fichier est devenue dangereuse.**
> Jusqu'au 20/08/2026, ce document demandait de poser `CNAME www → koutakou.github.io.` et quatre `A` apex vers les adresses de GitHub Pages. **Ne posez pas ces enregistrements.** Ils détourneraient le domaine du serveur qui sert réellement le site, vers un hôte qui n'héberge plus qu'une page de redirection : le site entier deviendrait injoignable et la redirection tournerait en boucle sur elle-même. La zone actuelle est correcte ; la seule raison de la toucher serait un changement de serveur, et alors seule l'adresse IP change.

### E-mail de contact — FAIT

Une adresse dédiée est publiée sur `/mentions-legales` et `/donnees-personnelles` comme canal d'exercice des droits (elle vit dans `app/src/lib/site.ts`, constante `CONTACT_EMAIL`, et le script serveur `ft-localiser` vérifie à chaque déploiement qu'elle n'a pas dérivé). Les issues GitHub restent un canal secondaire.

### Montée en gamme d'hébergement — SANS OBJET

Le site n'est plus sur GitHub Pages : la question de la bande passante Pages (~100 Go/mois) et celle d'un « vrai » serveur pour retrouver des en-têtes HTTP maîtrisés sont réglées par le serveur dédié actuel, qui sert les en-têtes de sécurité complets (HSTS, CSP, `nosniff`, `frame-ancestors`) et pré-compresse le site au build. L'étude comparative de plateformes reste consultable comme document daté : [deploiement/plateformes.md](deploiement/plateformes.md).

## Ce qui reste ouvert

### 1. VPS OVH de l'ancien `koutakou.fr` : à vérifier au manager (peut-être de l'argent dépensé pour rien)

`~/.ssh/config` de la machine de travail référence un VPS OVH (hôte `koutakou.fr` ; adresse et port y figurent, ils ne sont pas recopiés dans ce dépôt public). Au **19/08/2026** : ping OK, mais tous ports fermés — serveur pare-feuté, réinstallé ou réattribué. **Toujours non vérifié au 15/10/2026**, près de deux mois plus tard. À vérifier sur https://www.ovh.com/manager/ : s'il est encore facturé sans servir, le résilier. Il n'a plus de rôle à jouer dans l'architecture : le site a son serveur.

### 2. Renouvellements à surveiller

Deux échéances peuvent éteindre le site sans prévenir, et aucune ne se règle depuis le dépôt :

- le **nom de domaine** `francetransparence.fr` (renouvellement annuel chez le registrar) ;
- l'**abonnement au serveur dédié** (facturation Scaleway).

Le certificat TLS, lui, se renouvelle automatiquement. Poser un rappel calendaire sur ces deux échéances coûte cinq minutes et évite la panne la plus bête possible.

Une troisième échéance n'éteint pas le site mais sa seule sentinelle indépendante : **GitHub désactive les workflows planifiés d'un dépôt public après 60 jours sans activité**. Faute de commit sur `main`, la validation CI quotidienne (`publication.yml`) cesserait de tourner, sans qu'aucune issue ne s'ouvre — un run qui n'a pas lieu n'échoue pas. Toute fusion sur `main` repousse l'échéance. Si GitHub l'a déjà désactivée : `gh workflow enable publication.yml --repo koutakou/france-transparence`, ou le bouton « Enable workflow » de l'onglet Actions.
