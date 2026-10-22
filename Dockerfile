# ==========================================
# Etapa 1: Builder
# ==========================================
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements* pyproject* ./
COPY src/ ./src/

RUN pip install --user --no-cache-dir fastapi uvicorn pydantic

# ==========================================
# Etapa 2: Runtime (Imagen OCI final)
# ==========================================
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /root/.local /root/.local
COPY src/ ./src/
COPY datos/ ./datos/

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["uvicorn", "aula.api.app:app", "--host", "0.0.0.0", "--port", "8000"]