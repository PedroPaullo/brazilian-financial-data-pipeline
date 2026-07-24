FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN mkdir -p data/processed data/operations reports logs

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/health')"
CMD ["python", "-m", "src.railway_entrypoint"]
