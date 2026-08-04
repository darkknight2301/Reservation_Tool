# Reservation Management System — Backend

Production backend for reserving Linux CLI setups. FastAPI + SQLAlchemy + Alembic + SQLite (PostgreSQL-ready). Python 3.8 compatible.

## Setup

```bash
python3.8 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set SECRET_KEY, SEED_ADMIN_PASSWORD, etc.

alembic upgrade head
python -m scripts.create_admin        # seeds roles/permissions + Owner account
python -m scripts.seed_data           # optional sample Products/Groups/Setups

uvicorn app.main:app --reload
```

Visit `http://localhost:8000/docs` for interactive Swagger UI, `http://localhost:8000/health` for liveness.

## Roles

`USER` < `DEVELOPER` < `LEAD` < `DEVELOPER_LEAD` < `OWNER`. Permission matrix seeded in `app/core/constants.py::DEFAULT_ROLE_PERMISSIONS`, applied by `app/db/init_db.py`.

## Registration / Approval

`POST /api/v1/auth/register` creates a `PENDING` user. A `LEAD`+ approves via `POST /api/v1/users/{id}/approval`. `LEAD` may only approve users in their own Group; `DEVELOPER_LEAD`/`OWNER` approve globally.

## Key workflows

- **Reservation**: `POST /api/v1/reservations` (overlap-checked against ACTIVE reservations on the same setup).
- **Unreserve**: `PATCH /api/v1/reservations/{id}/cancel`.
- **Swap**: `POST /api/v1/swaps` → `PATCH /api/v1/swaps/{id}/approve|reject|cancel`.
- **Excel export**: `POST /api/v1/exports/setups` / `/reservations` — downloads `.xlsx`, logs to `export_logs` + `excel_transaction_logs`.
- **Excel import**: `POST /api/v1/imports/setups` (multipart) — all-or-nothing, column contract in `app/utils/excel_reader.py::SETUP_IMPORT_COLUMNS`.
- **Audit trail**: `GET /api/v1/audit-logs` (requires `audit:view`).

## Background jobs

APScheduler, in-process (`app/services/scheduler_service.py`): reservation-expiry sweep and announcement-expiry sweep, intervals configurable via `.env`.

## Deployment

See `deploy/` — `gunicorn_conf.py`, `reservation-system.service` (systemd), `nginx.conf` (TLS + reverse proxy to a unix socket).

## Migrating to PostgreSQL

Change `DATABASE_URL` in `.env` to `postgresql+psycopg2://user:pass@host:5432/db`, install `psycopg2-binary`, run `alembic upgrade head`. No application code changes required (see architecture doc, §5).

## Note on this environment

This project was generated and syntax-verified (`py_compile`) in a sandbox without network/package-install access, so it has not been run against a live `uvicorn`/`pytest` process. Run the Setup steps above in a real Python 3.8 environment before deploying.


## Folder structure

```txt
reservation-system/
├── .env.example
├── README.md
├── requirements.txt
├── alembic.ini
│
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
│
├── app/
│   ├── main.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── constants.py
│   │   ├── exceptions.py
│   │   ├── logging_config.py
│   │   └── security.py
│   │
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   └── init_db.py
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── role.py
│   │   ├── permission.py
│   │   ├── refresh_token.py
│   │   ├── group.py
│   │   ├── product.py
│   │   ├── setup.py
│   │   ├── reservation.py
│   │   ├── swap_request.py
│   │   ├── announcement.py
│   │   ├── audit_log.py
│   │   ├── export_log.py
│   │   └── excel_transaction_log.py
│   │
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── group.py
│   │   ├── product.py
│   │   ├── setup.py
│   │   ├── reservation.py
│   │   ├── swap_request.py
│   │   ├── announcement.py
│   │   ├── audit_log.py
│   │   ├── export_import.py
│   │   └── common.py
│   │
│   ├── repositories/
│   │   ├── interfaces/
│   │   │   ├── i_user_repository.py
│   │   │   ├── i_role_repository.py
│   │   │   ├── i_refresh_token_repository.py
│   │   │   ├── i_group_repository.py
│   │   │   ├── i_product_repository.py
│   │   │   ├── i_setup_repository.py
│   │   │   ├── i_reservation_repository.py
│   │   │   ├── i_swap_repository.py
│   │   │   ├── i_announcement_repository.py
│   │   │   ├── i_audit_repository.py
│   │   │   └── i_export_repository.py
│   │   └── sqlalchemy/
│   │       ├── user_repository.py
│   │       ├── role_repository.py
│   │       ├── refresh_token_repository.py
│   │       ├── group_repository.py
│   │       ├── product_repository.py
│   │       ├── setup_repository.py
│   │       ├── reservation_repository.py
│   │       ├── swap_repository.py
│   │       ├── announcement_repository.py
│   │       ├── audit_repository.py
│   │       └── export_repository.py
│   │
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── role_lookup_service.py
│   │   ├── product_service.py
│   │   ├── group_service.py
│   │   ├── setup_service.py
│   │   ├── reservation_service.py
│   │   ├── swap_service.py
│   │   ├── announcement_service.py
│   │   ├── audit_service.py
│   │   ├── export_service.py
│   │   ├── import_service.py
│   │   └── scheduler_service.py
│   │
│   ├── api/
│   │   ├── deps.py
│   │   └── v1/
│   │       ├── router.py
│   │       ├── auth.py
│   │       ├── users.py
│   │       ├── products.py
│   │       ├── groups.py
│   │       ├── setups.py
│   │       ├── reservations.py
│   │       ├── swaps.py
│   │       ├── announcements.py
│   │       ├── audit.py
│   │       ├── exports.py
│   │       └── imports.py
│   │
│   ├── utils/
│   │   ├── validators.py
│   │   ├── datetime_utils.py
│   │   ├── pagination.py
│   │   ├── excel_writer.py
│   │   └── excel_reader.py
│   │
│   └── middleware/
│       ├── request_logging.py
│       └── error_handler.py
│
├── scripts/
│   ├── create_admin.py
│   └── seed_data.py
│
├── deploy/
│   ├── gunicorn_conf.py
│   ├── reservation-system.service
│   └── nginx.conf
│
├── logs/
│   └── exports/
│
└── tests/
    ├── unit/
    │   ├── services/
    │   └── repositories/
    └── integration/
        └── api/
```


# PROMPTS

## PROMPT 0  COMPLETED

```txt
You are acting as a Principal Software Architect, Senior Python Backend Engineer, Senior Frontend Engineer, DevOps Engineer, Database Architect, and Technical Writer.

We are going to build a production-grade Reservation Management System.

This is NOT a demo project.

Treat this as enterprise software that will be deployed inside an organization.

The implementation must be scalable, maintainable, secure, modular and extensible.

Never simplify features unless explicitly instructed.

Before writing code, always think through architecture.

Whenever you create code, ensure consistency with previous responses.

Never regenerate existing files unless modifications are required.

Use clean architecture.

Use SOLID principles.

Use dependency injection wherever applicable.

Follow PEP8.

Use type hints.

Use docstrings.

Keep functions small.

Avoid duplicate code.

Generate production-quality code.

## Target Python Version

The entire project MUST be compatible with **Python 3.8**.

Do NOT use language features introduced after Python 3.8.

Specifically:

- Do NOT use match-case.
- Do NOT use built-in generic types like list[str], dict[str, int], tuple[int].
- Use typing.List, typing.Dict, typing.Tuple, typing.Optional, typing.Union instead.
- Do NOT use newer asyncio features unavailable in Python 3.8.
- Use libraries that support Python 3.8.
- All generated code should execute correctly on Python 3.8 without modification.

## Preferred Technology Stack

Backend

- Python 3.8
- FastAPI
- SQLAlchemy ORM
- Alembic
- SQLite (default)
- Database abstraction for future PostgreSQL/MySQL migration
- Pydantic v1.x (Python 3.8 compatible)
- openpyxl
- bcrypt / passlib
- python-jose (JWT)
- python-dotenv

Frontend

- HTML5
- Bootstrap 5
- Jinja2
- HTMX
- Vanilla JavaScript

Deployment

- Linux
- Gunicorn + Uvicorn Workers
- Nginx Reverse Proxy
- systemd Service

Database

- SQLite by default
- SQL schema designed for future PostgreSQL migration

Future automation should directly access the SQL database.

## Development Guidelines

- Design database first.
- Follow layered architecture.
- Separate:
  - API
  - Services
  - Repository
  - Models
  - Database
  - Authentication
  - Templates
  - Static
  - Utilities
  - Configuration
- Use dependency injection wherever appropriate.
- Write reusable and testable code.
- Minimize code duplication.
- Use configuration files instead of hardcoding values.
- Implement comprehensive exception handling.
- Use structured logging.
- Add meaningful comments only where necessary.

## Documentation

Whenever generating code, also provide:

- What was implemented
- Files created or modified
- Database changes (if any)
- Manual testing steps
- Assumptions made

## Code Quality

- Never leave TODOs.
- Never omit implementation.
- Never generate placeholder methods.
- Never intentionally simplify logic.
- Generate production-ready code.
- Keep naming consistent throughout the project.
- Maintain backward compatibility with Python 3.8.

If the response reaches the token limit, continue automatically from where you stopped.

Never repeat previously generated code unless it has changed.
```

## PROMPT 1 COMPLETED

```txt
Using the master prompt already provided, design the complete Reservation Management System.

Requirements

The system reserves Linux CLI setups.

Each setup belongs to a Product.

Each setup contains

IP

Hostname

SSD

HDD

Hardware Information

Capacity

Form Factor

Owner

Adapter

Aardvark

Quarch

APC

Remote Server

Location

Remarks

Reserved Time

Future automation will query SQL directly.

Design the complete architecture.

Include

Folder structure

Database ER diagram

Normalized SQL schema

Authentication flow

RBAC

API structure

Service layer

Repository layer

Logging architecture

Excel logging architecture

Announcement architecture

Swap architecture

Reservation architecture

Import/Export architecture

Configuration management

Security architecture

Deployment architecture

Project folder structure

Explain every design decision.

Do not write application code yet.

Produce architecture documents first.
```

## PROMPT 2  BACKEND-COMPLETED

```
Using the approved architecture, generate the entire backend.

Requirements

FastAPI

SQLAlchemy ORM

Alembic

SQLite

JWT Authentication

bcrypt passwords

REST APIs

Role Based Access Control

Roles

User

Lead

Developer

Developer Lead

Owner

Registration

Login

Approval workflow

Product CRUD

Group CRUD

Reservation CRUD

Swap

Unreserve

Announcement

Excel Import

Excel Export

Excel Transaction Logging

Application Logging

Audit Logs

Validation

Repository Layer

Service Layer

Dependency Injection

Configuration

Background Jobs

Database initialization

Migration

Seed admin user

Generate every required Python file.

Do not omit implementation.

Continue automatically until backend is complete.
```

## PROMPT 3 FRONTEND-PENDING

```
Generate the complete frontend.

Technology

Bootstrap 5

HTMX

Jinja2

Vanilla JavaScript

Modern responsive UI.

Screens

Login

Register

Dashboard

Product Selection

Reservation Table

Reserve Dialog

Swap Dialog

Unreserve Dialog

Announcement Manager

Product Management

Group Management

User Management

Approval Dashboard

Logs Dashboard

Requirements

Sticky table header

Column filters

Dropdown filters

Pagination

Search

Responsive

Dark mode ready

Toast notifications

Confirmation dialogs

Loading animations

Cards

Icons

Status badges

Reservation table columns

Tick

Sr No

IP

Hostname

User

Form Factor

Capacity

Aardvark

Quarch

APC

Remote Server

Hardware Info

Adapter

Owner

Location

Reserved Time

Remarks

Checkbox only enabled for

Available setup

or

Reserved by current user

Reserve

Swap

Unreserve

Buttons disabled until selection exists.

Generate all HTML

CSS

JavaScript

Templates

Static assets.
```

## PROMPT 4 Bussinse Logic-PENDING

```
Implement every business rule.

Reservation

Preview selected setups

Back button

Announcement options

Wall Message

Mail Leads

Groups

All Users

Remarks textbox

Reservation expiry

Confirm

Swap

Allow mapping

A→B

B→A

C→D

Validate

Every node appears once.

Reject invalid swaps.

Append remarks

"user@mail.com swapped drive from A to B at HH:MM DD/MM/YYYY"

Track complete history.

Unreserve

Prevent unreserve if swap not restored.

Display warning.

Announcements

Wall messages

Mail notifications

Group notifications

Products

Dynamic products

Import Excel

Export Excel

Generate empty template if product has no data.

Developer Logs

Tree view

Download logs

Transaction logs

Excel logs

Logs/

Month_Year/

Timestamp_00001.xlsx

Timestamp_00002.xlsx

Automatically rotate Excel files after 40MB.

Generate complete implementation.
```

## PROMPT 5 DOCUMENTATION-PENDING

```
Generate production-quality documentation.

Create

README.md

INSTALLATION.md

USER_GUIDE.md

DEVELOPER_GUIDE.md

Include

Architecture

Folder Structure

Installation

Linux Deployment

Python Setup

Environment Variables

Database

Alembic

Running Server

Creating Admin

Managing Products

Managing Users

Reservation Workflow

Swap Workflow

Announcements

Logs

Excel Logs

Backup

Restore

Security

RBAC

API Reference

Future Automation

Developer Standards

Coding Guidelines

Testing

Common Issues

FAQ

Generate complete documentation.

Also create deployment scripts

requirements.txt

.env.example

Dockerfile

docker-compose.yml

systemd service

Nginx reverse proxy configuration

backup.sh

restore.sh

startup.sh

shutdown.sh
```


## RESUME PROMPT if prompt stopped in between due to lack of tokens

```
Resume this project from where we left off.

Rules:
- Do NOT repeat or summarize previous work unless absolutely necessary.
- Infer context from the conversation history.
- Continue from the last unfinished task only.
- If the last response was cut off, continue from the exact point where it stopped.
- Keep responses as concise as possible.
- Do not explain decisions unless I ask.
- Minimize token usage.
- If a critical detail is missing, ask only one short question instead of making assumptions.
- Output only the code/changes/commands required to continue.
- Preserve the existing architecture, naming, style, and conventions.
- Do not regenerate files or code that are already complete; provide only the delta (new or modified parts).

Continue now.
```