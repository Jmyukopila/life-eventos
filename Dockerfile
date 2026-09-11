# Una sola imagen sirve todo: Node construye el frontend y Django lo sirve junto a la API desde
# el mismo origen. Eso es lo que evita CORS, proxy inverso y configuración de dominios cruzados.
FROM node:24-alpine AS frontend-build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
COPY shared ./shared
COPY public ./public
RUN npm run build

FROM python:3.12-slim AS backend
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/server" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY server ./server
# dist/ queda hermano de server/, que es donde lo busca WHITENOISE_ROOT.
COPY --from=frontend-build /app/dist ./dist
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

RUN groupadd --system app && useradd --system --gid app --home /app app \
    && chown -R app:app /app
USER app

EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
