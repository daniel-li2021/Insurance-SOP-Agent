FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/app/data
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10001 --create-home claimflow
COPY backend/ ./backend/
COPY docs/fixtures/ ./docs/fixtures/
COPY --from=frontend /build/dist ./frontend/dist
RUN mkdir -p /app/data && chown -R claimflow:claimflow /app
USER claimflow
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/health',timeout=3)"
CMD ["sh", "-c", "exec uvicorn backend.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers"]
