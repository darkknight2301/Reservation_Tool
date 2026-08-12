# Reservation Management System

Production backend + server-rendered frontend for reserving Linux CLI hardware setups. FastAPI, SQLAlchemy, Alembic, SQLite (PostgreSQL-ready), JWT auth, RBAC, Bootstrap 5 + HTMX UI.

Python 3.8 compatible.

## Documentation

| Document | Purpose |
|---|---|
| [INSTALLATION.md](INSTALLATION.md) | Linux deployment, Python setup, environment variables, database/Alembic, running the server, creating the admin, backup/restore |
| [USER_GUIDE.md](USER_GUIDE.md) | Managing products/users, reservation workflow, swap workflow, announcements, logs, Excel logs |
| [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) | Architecture, folder structure, security/RBAC, API reference, future automation, coding standards, testing, common issues, FAQ |

## Quick start

```bash
python3.8 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit SECRET_KEY, SEED_ADMIN_PASSWORD, etc.
alembic upgrade head
python -m scripts.create_admin
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/login` (web UI) or `http://localhost:8000/docs` (API). See INSTALLATION.md for full details.

## Roles

`USER` < `DEVELOPER` < `LEAD` < `DEVELOPER_LEAD` < `OWNER` — see DEVELOPER_GUIDE.md §RBAC for the full permission matrix.

## Dynamic Product Templates

Each Product can have its own table/template: a fixed set of mandatory columns
(IP, User, Owner, Reservation, Remark, Location, Group, Product) plus any
number of product-specific custom columns (String, Integer, Float, Boolean,
Date, DateTime, or Dropdown). Authorized users (`product:manage`) design a
product's template from **Product Management → Template** in the web UI, or
via the `/api/v1/products/{id}/template` API.

Custom columns are stored as data (`product_template_columns` +
`setup_custom_field_values`), so adding one never requires a database
migration. The Setup table, and Excel import/export for a single product, use
that product's current template automatically. Importing a workbook with
columns not yet in the template does not silently drop them — the import is
held and the caller is prompted to "Add to Template & Import" or reject it
(`POST /api/v1/imports/setups/product/{id}/detect-columns` and
`POST /api/v1/imports/setups/product/{id}?accept_new_columns=true|false`).
Product-scoped export: `POST /api/v1/exports/setups/product/{id}`.

## License / Ownership

Internal enterprise deployment. No external distribution license included by default.
