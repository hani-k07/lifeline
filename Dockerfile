FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=prod \
    DB_PATH=/data/lifeline.db \
    LOG_FILE=/data/logs/lifeline.log

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN useradd --create-home app && mkdir -p /data && chown -R app /data /app
USER app
VOLUME /data
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

# Creates the database on first start and migrates it afterwards; APP_ENV=prod seeds hospitals only (no demo users).
CMD ["sh", "-c", "python -m scripts.setup_db && exec streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true --browser.gatherUsageStats false"]
