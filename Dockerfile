# ---- Etapa 1: build das dependências em wheels ----
FROM python:3.12-slim AS builder
WORKDIR /build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip wheel --wheel-dir /wheels .

# ---- Etapa 2: imagem final enxuta, sem compiladores ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv

RUN useradd --create-home --uid 10001 appuser
COPY --from=builder /wheels /wheels
RUN pip install /wheels/* && rm -rf /wheels

# O código vem instalado como pacote; os dados ficam em /srv/data.
COPY data ./data
ENV KNOWLEDGE_DIR=/srv/data/knowledge \
    ORDERS_FILE=/srv/data/orders.json

USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
