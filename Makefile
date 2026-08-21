# France Transparence — cibles de travail
# Python : venv locale .venv (python3.14) · App : Next.js dans app/ (port 3620)

PYTHON ?= python3.14
VENV   := .venv
PIP    := $(VENV)/bin/pip
PY     := $(VENV)/bin/python

# Ordre d'ingestion : référentiels d'abord (entites), parlement AVANT integrite
# (les élus AN/Sénat sont créés avec leurs uid, integrite les complète par
# nom+prénom+date de naissance puis ajoute maires/exécutifs) ; elections APRÈS
# referentiels ET collectivites, dont il lit le périmètre (ref_departements
# pour les libellés, ref_villes ∪ collectivites_communes_top200 pour les communes
# suivies) — placé avant lui, il n'aurait aucune commune à agréger ;
# hatvp_declarations APRÈS integrite, dont il lit les élus appariables
# (nom+prénom+date de naissance) — placé avant lui, il n'aurait aucune fiche
# à rattacher. cada ne dépend d'aucune autre table (il n'écrit que ses propres
# agrégats) : il est placé à côté de trainvie, dont il complète le module.
# registre_ue (S40, registre de transparence de l'UE) n'a AUCUNE dépendance
# d'ordre : il n'écrit que ses propres tables ue_registre_*, ne lit rien des
# autres et ne peut pas être joint au répertoire HATVP (l'export UE ne porte
# ni SIREN ni numéro de TVA). Sa place en fin de liste est donc arbitraire —
# elle ne doit surtout pas se lire comme une dépendance à lobbying.
# sirene (S18) est en DERNIER, et cette place-là n'a rien d'arbitraire : le
# référentiel Sirene n'est pas ingéré en entier, il est restreint aux SIREN
# que les autres tables citent (decp, subventions, lobbying, collectivites,
# entites, marches_a_venir). Il lit donc le résultat de presque tous les
# autres ; placé avant eux, il n'aurait aucun SIREN à chercher et refuserait
# d'écrire (MIN_SIREN_CITES).
PIPELINES := referentiels budget_mensuel budget_structure decp boamp approch \
             jorf parlement integrite hatvp_declarations lobbying financement \
             collectivites elections trainvie cada registre_ue sirene

# NB : ne PAS déclarer les cibles ingest-<x> en .PHONY — make saute la
# recherche de règles implicites (ingest-%) pour les cibles phony.
.PHONY: venv ingest test dev build build-static serve-static app-install

venv: $(VENV)/bin/pip
$(VENV)/bin/pip: requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@touch $(VENV)/bin/pip

ingest: $(addprefix ingest-,$(PIPELINES))
ifeq ($(strip $(PIPELINES)),)
	@echo "Aucun pipeline câblé pour l'instant (voir PIPELINES dans ce Makefile)."
endif

# Règle générique : make ingest-<source> → python -m pipelines.ingest_<source>
ingest-%: venv
	$(PY) -m pipelines.ingest_$*

test: venv
	$(PY) -m pytest pipelines/tests -q

app-install:
	cd app && npm install

dev:
	cd app && npm run dev

build:
	cd app && npm run build

# Export statique (GitHub Pages) : génère app/out/ — nécessite la base
# (FRANCE_DB_PATH ou data/france.db), tout est pré-rendu au build.
build-static:
	cd app && FT_EXPORT=1 npm run build

# Sert app/out/ tel quel sur :3620. NB : en local le build se fait SANS
# NEXT_PUBLIC_BASE_PATH → site à la racine (http://localhost:3620/), alors
# que la prod GitHub Pages vit sous /france-transparence/.
serve-static:
	cd app && python3 -m http.server 3620 --directory out
