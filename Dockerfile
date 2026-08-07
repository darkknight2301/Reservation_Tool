# Reservation Management System - production image
# Python 3.8 to match the codebase's compatibility target.
FROM python:3.8-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GUNICORN_BIND=0.0.0.0:8000

WORKDIR /opt/reservation-system

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN useradd --system --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p logs/exports logs/excel_logs \
    && chown -R appuser:appuser /opt/reservation-system

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["gunicorn", "-c", "deploy/gunicorn_conf.py", "app.main:app"]
