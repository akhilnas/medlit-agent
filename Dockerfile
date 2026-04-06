# ---- Stage 1: builder ----
FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml .

# Install torch CPU-only first to avoid pulling the 2.5 GB CUDA variant
RUN uv pip install --system --no-cache torch --index-url https://download.pytorch.org/whl/cpu

# Install all project dependencies
RUN uv pip install --system --no-cache -e .

# Pre-download PubMedBERT model so ECS cold starts don't hit the 400MB download
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('NeuML/pubmedbert-base-embeddings')"

COPY . .

# ---- Stage 2: runtime ----
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages and source from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /root/.cache/huggingface /root/.cache/huggingface
COPY --from=builder /app /app

# Non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/v1/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
