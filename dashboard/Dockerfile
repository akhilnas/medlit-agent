FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir streamlit>=1.32.0 httpx>=0.27.0 plotly>=5.0.0

COPY dashboard/ ./dashboard/

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["streamlit", "run", "dashboard/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
