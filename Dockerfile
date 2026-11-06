# One container: FastAPI backend + built dashboard on the same origin.
# Build:  docker build -t precedent .
# Run:    docker run -p 8000:8000 --env-file backend/.env precedent
# Credentials are passed at runtime (env vars); they are never baked into the image.

FROM node:20.18-alpine AS web
WORKDIR /app
COPY contracts ./contracts
COPY cases ./cases
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci --no-audit --no-fund
COPY frontend ./frontend
RUN cd frontend && VITE_API_BASE=/ npx tsc --noEmit -p . && VITE_API_BASE=/ npx vite build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PRECEDENT_STATIC_DIR=/app/frontend/dist
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY contracts ./contracts
COPY cases ./cases
COPY data ./data
COPY intelligence ./intelligence
COPY backend/precedent ./backend/precedent
COPY --from=web /app/frontend/dist ./frontend/dist
RUN useradd --create-home app && mkdir -p backend/data && chown -R app /app/backend/data
USER app
EXPOSE 8000
CMD ["sh", "-c", "python -m uvicorn precedent.api:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000}"]
