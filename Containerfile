# Stage 1: Build frontend
FROM node:22-alpine AS frontend-build

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts 2>/dev/null || npm install --ignore-scripts
COPY frontend/ .
RUN npm run build

# Stage 2: Python API + bundled frontend
FROM registry.access.redhat.com/ubi9/python-311:latest

USER 0

WORKDIR /opt/app-root/src

COPY pyproject.toml .
RUN pip install --no-cache-dir ".[all]"

COPY api/ api/
COPY engine/ engine/
COPY db/ db/
COPY events/ events/
COPY constraints/ constraints/
COPY scenarios/ scenarios/
COPY alembic/ alembic/
COPY alembic.ini .

# Bundle frontend static assets
COPY --from=frontend-build /build/dist frontend/dist/

USER 1001

EXPOSE 8091

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8091"]
