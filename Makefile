# France Transparence — cibles de travail
# Python : venv locale .venv (python3.14) · App : Next.js dans app/ (port 3620)

PYTHON ?= python3.14
VENV   := .venv
PIP    := $(VENV)/bin/pip
PY     := $(VENV)/bin/python

# Pipelines câblés au fur et à mesure (make ingest-<source> par pipeline).
# Vide tant qu'aucun pipeline n'est écrit — `make ingest` les jouera tous.
PIPELINES :=

.PHONY: venv ingest test dev build app-install $(addprefix ingest-,$(PIPELINES))

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
