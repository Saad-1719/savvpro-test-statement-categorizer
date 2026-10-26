PY := backend/.venv/bin

.PHONY: install dev backend frontend test lint fmt eval data sample-pdf samples up lock e2e

install:
	python3 -m venv backend/.venv
	$(PY)/pip install -r backend/requirements.lock -e "backend[dev]"
	cd frontend && npm ci

dev:
	$(MAKE) -j2 backend frontend

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/pytest -q
	cd frontend && npm test

# Browser tests against the real app (starts the backend and frontend if not running).
e2e:
	cd frontend && npm run test:e2e

lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	cd frontend && npm run lint && npm run typecheck

fmt:
	cd backend && .venv/bin/ruff format . && .venv/bin/ruff check --fix .

data:
	cd backend && .venv/bin/python -m eval.generate_data

eval:
	cd backend && .venv/bin/python -m eval.evaluate

sample-pdf:
	cd backend && .venv/bin/python -m eval.make_sample_pdf

samples: sample-pdf
	cd backend && .venv/bin/python -m eval.make_test_files

up:
	docker compose up --build

# Re-pin the backend's runtime dependencies after changing pyproject.toml.
lock:
	rm -rf /tmp/sc-lock && python3 -m venv /tmp/sc-lock
	/tmp/sc-lock/bin/pip install -q ./backend
	( echo "# Exact versions of the backend's runtime dependencies (no dev tools)."; \
	  echo "# Regenerate with: make lock"; \
	  /tmp/sc-lock/bin/pip freeze --exclude-editable | grep -v "^statement-categorizer" ) > backend/requirements.lock
	rm -rf /tmp/sc-lock backend/build backend/*.egg-info
