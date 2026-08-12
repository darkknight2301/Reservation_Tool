# Installation Guide

## Table of Contents
1. [Python Setup](#python-setup)
2. [Linux Deployment (LAN-Only)](#linux-deployment-lan-only)
3. [Environment Variables](#environment-variables)
4. [Database](#database)
5. [Alembic Migrations](#alembic-migrations)
6. [Running the Server](#running-the-server)
7. [Creating the Admin (Owner) Account](#creating-the-admin-owner-account)
8. [Managing Products (initial setup)](#managing-products-initial-setup)
9. [Backup](#backup)
10. [Restore](#restore)
11. [Docker](#docker)
12. [Common Issues](#common-issues)

---

## Python Setup

Requires **Python 3.8** (the codebase avoids any 3.9+ syntax/typing features).

```bash
python3.8 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Verify:
```bash
python -c "import fastapi, sqlalchemy, alembic, pydantic, jose, passlib, openpyxl, apscheduler; print('OK')"
```

---

## Linux Deployment (LAN-Only)

This deployment is **not exposed to the public internet**. Access is restricted to your internal
network via Apache's `Require ip` allow-list (`deploy/apache.conf`), so a request from outside your
declared subnet(s) is rejected before it ever reaches the application. Edit the CIDR ranges in
`deploy/apache.conf` (both `<VirtualHost>` blocks) to match your actual internal network before deploying.

An OS-level firewall (e.g. `ufw`/`firewalld`) is still good practice as defense in depth, but is left to
your own infrastructure standards rather than shipped as part of this project.

Additionally:
- **Internal-only DNS/hostname** — give the server an internal-only name (e.g. `reservation-system.internal`
  via `/etc/hosts` or an internal DNS zone); never register a publicly resolvable domain for it.
- The application process itself only ever binds a **unix socket** (`deploy/gunicorn_conf.py`), never a
  public TCP port, so it isn't reachable at all except through Apache's proxy.

```
LAN clients ── Apache (443, Require ip allow-list) ── unix socket ── Gunicorn/Uvicorn workers ── DB
```

1. Create a dedicated service user and directory:
   ```bash
   sudo useradd --system --home /opt/reservation-system --shell /usr/sbin/nologin reservation-system
   sudo mkdir -p /opt/reservation-system /etc/reservation-system
   sudo chown -R reservation-system:reservation-system /opt/reservation-system
   ```
2. Deploy the application code to `/opt/reservation-system` and create the venv there (see [Python Setup](#python-setup)).
3. Place your production `.env` at `/etc/reservation-system/.env` (see [Environment Variables](#environment-variables)) — never commit real secrets to the repo. Set `CORS_ALLOWED_ORIGINS` to your internal hostname only (e.g. `https://reservation-system.internal`), never a public origin.
4. Install Apache and the modules required by `deploy/apache.conf`:
   ```bash
   sudo apt-get install apache2 libapache2-mod-proxy-uds
   sudo a2enmod ssl proxy proxy_http proxy_uds headers rewrite expires
   ```
5. Generate a certificate for internal TLS (a public CA cannot issue one for a non-publicly-resolvable name, which is expected here — either use this self-signed script or your organization's internal CA):
   ```bash
   sudo ./deploy/generate_self_signed_cert.sh reservation-system.internal
   ```
6. Edit `deploy/apache.conf`'s `Require ip` directives (both `<VirtualHost>` blocks) to match your actual internal subnet(s), and set `ServerName` to your internal hostname.
7. Install the systemd unit and Apache config:
   ```bash
   sudo cp deploy/reservation-system.service /etc/systemd/system/
   sudo cp deploy/apache.conf /etc/apache2/sites-available/reservation-system.conf
   sudo a2ensite reservation-system.conf
   sudo a2dissite 000-default   # avoid the default vhost catching requests
   sudo systemctl daemon-reload
   sudo systemctl enable --now reservation-system
   sudo apachectl configtest && sudo systemctl reload apache2
   ```
8. From a machine **on the LAN**, confirm `curl -sk https://reservation-system.internal/health` returns `{"status": "ok"}`. From a machine **outside** the allowed CIDR(s), confirm the same request is refused with `403 Forbidden` (this is the check that actually matters).

**Docker Compose users:** `docker-compose.yml` already binds the container's port to `127.0.0.1:8000` only — Apache on the host is still the thing LAN clients talk to; the container itself is never reachable directly, even from other machines on the LAN. In `deploy/apache.conf`, comment the unix-socket `<Location />` block and uncomment the `http://127.0.0.1:8000/` alternative already present in the file.

**Do not**, under any circumstances:
- Port-forward 80/443 from a router/NAT to this host.
- Set `CORS_ALLOWED_ORIGINS` to `*` or a public domain.
- Change the Docker port mapping to `0.0.0.0:8000:8000` or `8000:8000` (this bypasses Apache's `Require ip` allow-list entirely).
- Request a public CA certificate for the internal hostname (a public cert implies public DNS resolution, which defeats the point).

For a container-based deployment instead, see [Docker](#docker).

---

## Environment Variables

All configuration is sourced from environment variables (`app/core/config.py::Settings`), loaded from `.env` in development or `EnvironmentFile=` in production. Copy `.env.example` and edit:

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | `development` \| `staging` \| `production` \| `test` |
| `APP_DEBUG` | `false` | Enables FastAPI debug mode; keep `false` in production |
| `SECRET_KEY` | *(insecure placeholder)* | **Change this.** Signs JWTs. Use `openssl rand -hex 32` |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `BCRYPT_ROUNDS` | `12` | Password hashing cost factor |
| `DATABASE_URL` | `sqlite:///./reservation_system.db` | SQLAlchemy connection string; see [Database](#database) |
| `DATABASE_ECHO` | `false` | Log all SQL statements (debugging only) |
| `LOG_LEVEL` | `INFO` | Root logging level |
| `LOG_DIR` | `./logs` | Rotating application log directory |
| `LOG_FILE_MAX_BYTES` | `10485760` | App log rotation size |
| `LOG_FILE_BACKUP_COUNT` | `10` | App log rotated backups kept |
| `EXPORT_DIR` | `./logs/exports` | Generated Excel export files |
| `MAX_EXPORT_ROWS` | `50000` | Safety cap on export row count |
| `EXCEL_LOG_DIR` | `./logs/excel_logs` | Rotating Excel transaction log root (Developer Logs) |
| `EXCEL_LOG_ROTATE_MAX_BYTES` | `41943040` (40MB) | Rotate to a new Excel log file past this size |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:8000` | Comma-separated allow-list. In production, set to your internal hostname only (e.g. `https://reservation-system.internal`) — never `*` or a public domain, see [Linux Deployment (LAN-Only)](#linux-deployment-lan-only) |
| `RESERVATION_MIN_LEAD_MINUTES` | `0` | Minimum lead time before a reservation can start |
| `SWAP_REQUIRE_SAME_PRODUCT` | `true` | Restrict single swaps to the same Product |
| `SEED_ADMIN_USERNAME` / `_EMAIL` / `_PASSWORD` / `_FULL_NAME` | see `.env.example` | Used only by `scripts/create_admin.py` |
| `ENABLE_SCHEDULER` | `true` | Enables the in-process APScheduler background jobs |
| `RESERVATION_SWEEP_INTERVAL_MINUTES` | `5` | Reservation-expiry sweep interval |
| `ANNOUNCEMENT_SWEEP_INTERVAL_MINUTES` | `15` | Announcement-expiry sweep interval |
| `SMTP_ENABLED` | `false` | When `false`, notification emails are logged, not sent |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` / `SMTP_USE_TLS` / `SMTP_FROM_ADDRESS` | see `.env.example` | Outbound mail settings for Announcements |

**Never commit a real `.env`.** In production, secrets are injected via systemd's `EnvironmentFile=/etc/reservation-system/.env`, owned by root, mode `600`.

---

## Database

Default: **SQLite** at `DATABASE_URL=sqlite:///./reservation_system.db` — zero setup, suitable for small/medium deployments.

### Migrating to PostgreSQL

1. `pip install psycopg2-binary`
2. Set `DATABASE_URL=postgresql+psycopg2://user:password@host:5432/reservation_system`
3. `alembic upgrade head`

No application code changes are required — every model/repository uses SQLAlchemy Core/ORM constructs only (no SQLite-specific SQL), and the schema's `CHECK` constraints are ANSI-standard. See DEVELOPER_GUIDE.md §Architecture for details.

---

## Alembic Migrations

```bash
# Apply all migrations (creates every table from scratch on a fresh DB)
alembic upgrade head

# Check current revision
alembic current

# Create a new migration after changing a model
alembic revision --autogenerate -m "describe the change"

# Roll back one revision
alembic downgrade -1
```

Migration history: `0001_initial_schema.py` (full initial schema) → `0002_reservation_remarks_swap_batch.py` (renames `reservations.purpose` → `remarks`, adds `swap_requests.batch_id`).

Always review autogenerated migrations before applying — Alembic cannot detect every change (e.g. `CHECK` constraint edits) automatically.

---

## Running the Server

**Development:**
```bash
uvicorn app.main:app --reload
```

**Production** (via systemd, see [Linux Deployment](#linux-deployment)):
```bash
sudo systemctl start reservation-system
sudo systemctl status reservation-system
journalctl -u reservation-system -f
```

Or manually with Gunicorn:
```bash
gunicorn -c deploy/gunicorn_conf.py app.main:app
```

Convenience wrapper scripts are provided: [`deploy/startup.sh`](deploy/startup.sh) and [`deploy/shutdown.sh`](deploy/shutdown.sh).

---

## Creating the Admin (Owner) Account

Seeds every Role/Permission (idempotent) and creates the initial `OWNER` account from `SEED_ADMIN_*` settings:

```bash
python -m scripts.create_admin
```

Log in at `/login` with `SEED_ADMIN_USERNAME` / `SEED_ADMIN_PASSWORD`, then **change the password immediately** via the user menu → the account API also supports `POST /api/v1/auth/change-password`.

Optional sample data (Products/Groups/Setups) for local development:
```bash
python -m scripts.seed_data
```

---

## Managing Products (initial setup)

After creating the admin, log in and go to **Products** (nav bar) to create your first Product, then **Groups** for organizational teams, then use **Product Management → Import Setups** (or the API `POST /api/v1/imports/setups`) to bulk-load hardware. See USER_GUIDE.md §Managing Products for the full workflow and Excel column contract.

---

## Backup

```bash
./deploy/backup.sh
```

- SQLite: copies the `.db` file (via `sqlite3 .backup`, safe for a live DB) plus the `logs/` directory (exports, Excel transaction logs, app logs) into a timestamped archive under `backups/`.
- PostgreSQL: set `DATABASE_URL` accordingly; the script detects the dialect and uses `pg_dump` instead.

Schedule via a systemd timer or cron, e.g. daily at 02:00:
```
0 2 * * * /opt/reservation-system/deploy/backup.sh >> /var/log/reservation-system-backup.log 2>&1
```

## Restore

```bash
./deploy/restore.sh backups/reservation-system-backup-20260101-020000.tar.gz
```

Stops the service, restores the database file (or runs `pg_restore`) and the `logs/` directory from the archive, then restarts the service. **This overwrites the current database — take a fresh backup first if unsure.**

---

## Docker

```bash
docker compose up -d --build
docker compose exec app alembic upgrade head
docker compose exec app python -m scripts.create_admin
```

See `Dockerfile` and `docker-compose.yml` at the project root. The compose file mounts a named volume for the SQLite file and a bind mount for `logs/`, so data survives container recreation. Set real values in a `.env` file next to `docker-compose.yml` (loaded automatically by Compose).

`docker-compose.yml` binds the container's port to `127.0.0.1:8000` only — it is **not** reachable from the network directly. Run Apache on the Docker host per [Linux Deployment (LAN-Only)](#linux-deployment-lan-only) (with its `Require ip` allow-list) to actually expose it to LAN clients; do not change the compose port mapping to `0.0.0.0:8000:8000`.

---

## Common Issues

| Symptom | Cause / Fix |
|---|---|
| `sqlite3.OperationalError: database is locked` | Multiple Gunicorn workers writing to SQLite concurrently under heavy load. Reduce workers, or migrate to PostgreSQL for multi-worker production use. |
| `alembic.util.exc.CommandError: Can't locate revision` | Migration history mismatch — check `alembic_version` table matches the versions present in `alembic/versions/`. |
| 401 on every request from the browser | `access_token` cookie missing/expired — log in again. Check `SECRET_KEY` hasn't changed (invalidates all existing tokens). |
| Emails not sent | `SMTP_ENABLED=false` (default) — messages are logged, not sent. Set `SMTP_ENABLED=true` and configure `SMTP_*`. |
| Import rejected with "missing required column(s)" | The uploaded workbook's header row doesn't match `app/utils/excel_reader.py::SETUP_IMPORT_COLUMNS`. Download the Blank Template from Product Management first. |
| Static assets 404 in production | Confirm Apache is serving `/static/` (see `deploy/apache.conf`'s `Alias` directive) and that the app was started with `app/web/static` present relative to its working directory. |
| `403 Forbidden` from a machine that should have access | Your client's IP isn't inside the CIDR ranges listed in `deploy/apache.conf`'s `Require ip` directives (both `<VirtualHost>` blocks) — update them to match your actual internal subnet(s) and reload Apache. |
| `AH00526`/`Invalid command 'ProxyPass'` on `apachectl configtest` | `mod_proxy`/`mod_proxy_http`/`mod_proxy_uds` aren't enabled — run `sudo a2enmod ssl proxy proxy_http proxy_uds headers rewrite expires` then reload Apache. |

See DEVELOPER_GUIDE.md §Common Issues and §FAQ for backend/developer-facing troubleshooting.
