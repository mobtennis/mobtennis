.PHONY: help install install-backend install-web install-mobile backend web mobile seed test fmt clean

# Use uv if available; otherwise fall back to a local venv + pip.
PY ?= $(shell command -v python3.13 || command -v python3.12 || command -v python3)
HAS_UV := $(shell command -v uv 2>/dev/null)

ifdef HAS_UV
  PYRUN = cd backend && uv run
  PYINSTALL = cd backend && uv sync
else
  PYRUN = cd backend && . .venv/bin/activate && PYTHONPATH=. python
  PYINSTALL = cd backend && $(PY) -m venv .venv && . .venv/bin/activate && pip install -e . && pip install pytest ruff
endif

help:
	@echo "Tennismob — make targets"
	@echo "  install        install backend & web deps"
	@echo "  install-backend  python deps only"
	@echo "  install-web    npm deps only"
	@echo "  backend        run FastAPI dev server"
	@echo "  web            run Next.js dev server"
	@echo "  seed           ingest Jeff Sackmann CSVs into SQLite (~3 min)"
	@echo "  test           run backend tests"
	@echo "  fmt            format backend (ruff)"
	@echo "  clean          remove caches & build artefacts"

install: install-backend install-web install-mobile

install-backend:
	$(PYINSTALL)

install-web:
	cd web && npm install

install-mobile:
	cd mobile && npm install

backend:
ifdef HAS_UV
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
else
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
endif

web:
	cd web && npm run dev

mobile:
	cd mobile && npm run ios

seed:
	$(PYRUN) -m scripts.sackmann_ingest

test:
	$(PYRUN) -m pytest

fmt:
	$(PYRUN) -m ruff format . && $(PYRUN) -m ruff check --fix .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf backend/.pytest_cache backend/.ruff_cache web/.next web/node_modules/.cache
