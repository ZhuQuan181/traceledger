FROM node:25-bookworm-slim AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    FLOWLAB_HOME=/data \
    FLOWLAB_MAX_UPLOAD_MB=1024

COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock hatch_build.py ./

RUN uv sync --frozen --no-dev --extra api --extra data --no-install-project \
    && rm -rf /root/.cache/uv

COPY README.md README.en.md LICENSE ./
COPY src ./src
COPY --from=web /app/web/dist ./web/dist

RUN uv sync --frozen --no-dev --no-editable --extra api --extra data \
    && useradd --create-home --uid 10001 flowlab \
    && mkdir -p /data \
    && chown -R flowlab:flowlab /data

ENV PATH="/app/.venv/bin:${PATH}"

USER flowlab
VOLUME ["/data"]
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=2)"

CMD ["flowlab", "serve", "--host", "0.0.0.0", "--allow-remote", "--port", "8765"]
