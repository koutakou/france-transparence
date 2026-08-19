# France Transparence — cibles de travail
# Python : venv locale .venv (python3.14) · App : Next.js dans app/ (port 3620)

PYTHON ?= python3.14
VENV   := .venv
PIP    := $(VENV)/bin/pip
PY     := $(VENV)/bin/python

# Ordre d'ingestion : référentiels d'abord (entites), parlement AVANT integrite
# (les élus AN/Sénat sont créés avec leurs uid, integrite les complète par
# nom+prénom+date de naissance puis ajoute maires/exécutifs).
PIPELINES := referentiels budget_mensuel budget_structure decp boamp approch \
             jorf parlement integrite lobbying financement collectivites trainvie

# NB : ne PAS déclarer les cibles ingest-<x> en .PHONY — make saute la
# recherche de règles implicites (ingest-%) pour les cibles phony.
.PHONY: venv ingest test dev build app-install

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
