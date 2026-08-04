"""Gunicorn configuration for running the FastAPI app with Uvicorn workers."""
import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", "unix:/run/reservation-system/gunicorn.sock")
worker_class = "uvicorn.workers.UvicornWorker"
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 60))
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
