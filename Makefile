.PHONY: install test dev build migrate lint clean

install:
	pip3 install -e ".[dev,api]"
	cd frontend && npm install

test:
	python3 -m pytest tests/ -q
	python3 -m behave tests/bdd/features/
	cd frontend && npm test

test-unit:
	python3 -m pytest tests/unit/ -v

test-integration:
	python3 -m pytest tests/integration/ -v

test-property:
	python3 -m pytest tests/property/ -v

test-contract:
	python3 -m pytest tests/contract/ -v

test-bdd:
	python3 -m behave tests/bdd/features/

test-frontend:
	cd frontend && npm test

dev:
	podman-compose up --build

dev-down:
	podman-compose down -v

build:
	podman build -f Containerfile -t geolux-api .
	podman build -f Containerfile.frontend -t geolux-frontend .

build-api:
	podman build -f Containerfile -t geolux-api .

build-frontend:
	podman build -f Containerfile.frontend -t geolux-frontend .

migrate:
	python3 -m alembic upgrade head

lint:
	python3 -m ruff check .
	cd frontend && npx tsc --noEmit

typecheck:
	cd frontend && npx tsc --noEmit

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/dist frontend/node_modules
	rm -rf *.egg-info

helm-template:
	helm template geolux deploy/helm/geolux/

helm-template-dev:
	helm template geolux deploy/helm/geolux/ -f deploy/helm/geolux/values-dev.yaml

helm-template-prod:
	helm template geolux deploy/helm/geolux/ -f deploy/helm/geolux/values-prod.yaml
