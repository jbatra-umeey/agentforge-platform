.PHONY: setup api web test demo up down
setup:
	python3 -m venv .venv
	.venv/bin/pip install --require-hashes -r requirements.lock
	.venv/bin/pip install -r requirements-dev.txt
	npm ci --prefix apps/web
	python3 scripts/init_env.py
api:
	set -a; . ./.env; set +a; PYTHONPATH=packages .venv/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
web:
	npm run dev --prefix apps/web
test:
	.venv/bin/ruff check apps/api packages scripts tests
	.venv/bin/pytest -q
	npm run build --prefix apps/web
demo:
	set -a; . ./.env; set +a; PYTHONPATH=packages/sdk .venv/bin/python scripts/demo.py
up:
	docker compose up --build --wait
down:
	docker compose down
