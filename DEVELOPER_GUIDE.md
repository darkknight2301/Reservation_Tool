# Developer Guide

Audience: engineers building, extending, or operating this codebase.

## Table of Contents
1. [Architecture](#architecture)
2. [Folder Structure](#folder-structure)
3. [Security](#security)
4. [RBAC](#rbac)
5. [API Reference](#api-reference)
6. [Future Automation](#future-automation)
7. [Developer Standards](#developer-standards)
8. [Coding Guidelines](#coding-guidelines)
9. [Testing](#testing)
10. [Common Issues](#common-issues)
11. [FAQ](#faq)

---

## Architecture

Clean/layered architecture, strict inward dependency direction:

```
Presentation   → app/api/v1 (JSON, Bearer JWT)  +  app/web (Jinja2/HTMX, cookie session)
Application    → app/services  (business rules, transaction boundaries)
Domain         → app/schemas   (Pydantic v1 DTOs), app/core/constants (enums)
Persistence    → app/repositories/interfaces (Protocols) + .../sqlalchemy (impls)
Infrastructure → app/db (engine/session), app/core (config/logging/security)
```

**Rules enforced by this layering:**
- Routers (`api/v1/*`, `web/routers/*`) never touch the ORM directly — they call a Service via `Depends()`.
- Services depend on repository **interfaces** (`typing.Protocol`), never concrete SQLAlchemy classes — see `app/repositories/interfaces/`. This is what makes a future PostgreSQL swap, or unit testing with fakes, possible without touching services.
- Repositories return ORM models or `None`/empty collections; they never raise HTTP-shaped exceptions. Services translate persistence facts into domain exceptions (`app/core/exceptions.py`), and `app/middleware/error_handler.py` translates those into the JSON error envelope for the API, or web-specific handlers (`RedirectToLogin`, `ForbiddenWebError` in `app/web/deps.py`) for the browser.
- Both `api/v1` (JSON) and `web` (HTML/HTMX) routers call the **same** service layer — business logic is never duplicated between the two.
- `DATABASE_URL` is the only seam between SQLite and PostgreSQL — no dialect-specific SQL exists anywhere in models/repositories, so migrating is a config change (see INSTALLATION.md §Database).
- The **reservation** is the source of truth for "who reserved what, when" — `Setup.status` is a cached/derived column kept in sync by the service layer inside the same transaction as any reservation state change, so automation can filter `setups.status = 'AVAILABLE'` without a join.
- Interval-overlap validation (no two ACTIVE reservations on the same setup with overlapping windows) is enforced in `ReservationService`, not a DB constraint — SQLite has no portable exclusion constraint equivalent to PostgreSQL's `EXCLUDE USING gist`.
- Two independent logging systems, deliberately not merged: `AuditLog` (DB table, human/automation-queryable, append-only, permanent) vs. application logs (`app/core/logging_config.py`, structured JSON, rotated, for ops/debugging) vs. rotating Excel transaction logs (`app/utils/excel_log_rotator.py`, for the Developer Logs screen — see [Future Automation](#future-automation)).

For the full entity-relationship diagram and the original design rationale (including why Reservation/Setup/Group/Product are separate aggregates), see the project's architecture document if retained in your repo history; the schema itself is authoritative in `alembic/versions/0001_initial_schema.py` + `0002_reservation_remarks_swap_batch.py`.

---

## Folder Structure

```
reservation-system/
├── app/
│   ├── main.py                     # FastAPI app factory: middleware, routers, static, startup/shutdown
│   ├── core/                       # Config, constants/enums, exceptions, JWT/bcrypt, structured logging
│   ├── db/                         # Engine/session factory, RBAC seed routine
│   ├── models/                     # SQLAlchemy ORM models (one file per aggregate)
│   ├── schemas/                    # Pydantic v1 DTOs (request/response contracts)
│   ├── repositories/
│   │   ├── interfaces/             # Protocol-based persistence contracts
│   │   └── sqlalchemy/             # Concrete SQLAlchemy implementations
│   ├── services/                   # Business logic, one class per aggregate + a few helpers
│   ├── api/
│   │   ├── deps.py                 # DI wiring (repositories → services), Bearer-JWT auth, require_permission()
│   │   └── v1/                     # JSON API routers, one file per resource
│   ├── web/
│   │   ├── deps.py                 # Cookie-based auth, require_web_permission(), base_context()
│   │   ├── routers/                # HTML/HTMX routers, one file per screen group
│   │   ├── templates/              # Jinja2 templates (base + partials + per-screen)
│   │   └── static/{css,js,img}/    # Bootstrap-based custom CSS, vanilla JS (app.js, table.js)
│   ├── utils/                      # Pagination, Excel read/write, rotating Excel log, validators, datetime
│   └── middleware/                 # Correlation-ID/access-log middleware, global exception handlers
├── alembic/                        # Migration environment + versioned migrations
├── scripts/                        # create_admin.py, seed_data.py (one-shot management scripts)
├── deploy/                         # gunicorn_conf.py, nginx.conf, systemd unit, backup/restore/startup/shutdown
├── tests/                          # unit/{services,repositories}, integration/api (scaffolded, see Testing)
├── logs/                           # Runtime: app.log, exports/, excel_logs/ (all git-ignored)
├── requirements.txt / .env.example / alembic.ini
├── Dockerfile / docker-compose.yml
└── README.md / INSTALLATION.md / USER_GUIDE.md / DEVELOPER_GUIDE.md
```

**Naming conventions:** interfaces are prefixed `I` (`ISetupRepository`); SQLAlchemy implementations match the interface name minus the prefix (`SetupRepository`); every schema file matches its model's name; every service method that mutates state calls `AuditService.record(...)` before returning.

---

## Security

- **Transport**: TLS terminated at Nginx; the app process only listens on a unix socket / localhost — see `deploy/nginx.conf`.
- **AuthN**: JWT access + refresh token pair (`app/core/security.py`). API clients use `Authorization: Bearer <token>`; the browser uses HttpOnly, `SameSite=Strict`, `Secure` (in non-debug) cookies (`app/web/routers/auth_view.py`). Refresh tokens are tracked server-side (`refresh_tokens` table) and rotated on every use (single-use), so logout/deactivation revokes access immediately rather than waiting for token expiry.
- **AuthZ**: every protected endpoint depends on `require_permission(code)` (API) or `require_web_permission(code)` (web), which checks the current user's role against the seeded `role_permissions` mapping — never a hardcoded `if role == "X"`. Record-level nuance (e.g. "a LEAD may only approve users in their own Group") is enforced inside the relevant service method, not the route.
- **Passwords**: bcrypt via `passlib`, cost factor from `BCRYPT_ROUNDS`. Never logged, never returned in any response.
- **Injection**: 100% SQLAlchemy query-builder access; zero raw string-concatenated SQL anywhere in the codebase.
- **Input validation**: every write path validated by a Pydantic v1 schema before reaching the service layer (length limits, `EmailStr`, custom IP/hostname regex validators in `app/utils/validators.py`).
- **Path traversal**: `DeveloperLogsService.resolve_download_path()` resolves and verifies every requested log file stays within `EXCEL_LOG_DIR` before allowing a download.
- **CORS**: explicit allow-list only (`CORS_ALLOWED_ORIGINS`), never `*` in production.
- **Secrets**: `SECRET_KEY`, DB credentials, SMTP credentials — environment variables only, never committed. Production secrets live in `/etc/reservation-system/.env`, root-owned, mode `600`.
- **Audit trail**: `AuditLog` is insert-only by construction — `AuditLogRepository` exposes no `update`/`delete` method at all.

---

## RBAC

Roles (`app/core/constants.py::RoleName`), ascending privilege: `USER < DEVELOPER < LEAD < DEVELOPER_LEAD < OWNER`.

Permission matrix (`DEFAULT_ROLE_PERMISSIONS`, seeded by `app/db/init_db.py::seed_roles_and_permissions`, idempotent):

| Permission code | USER | DEVELOPER | LEAD | DEVELOPER_LEAD | OWNER |
|---|:---:|:---:|:---:|:---:|:---:|
| `user:view` | | | | ✅ | ✅ |
| `user:manage` | | | | ✅ | ✅ |
| `user:approve` | | | ✅ | ✅ | ✅ |
| `product:view` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `product:manage` | | | | ✅ | ✅ |
| `group:view` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `group:manage` | | | ✅ | ✅ | ✅ |
| `reservation:view` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `reservation:create` | | ✅ | ✅ | ✅ | ✅ |
| `reservation:cancel_own` | | ✅ | ✅ | ✅ | ✅ |
| `reservation:cancel_any` | | | ✅ | ✅ | ✅ |
| `swap:view` | | ✅ | ✅ | ✅ | ✅ |
| `swap:request` | | ✅ | ✅ | ✅ | ✅ |
| `swap:approve` | | | ✅ | ✅ | ✅ |
| `announcement:view` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `announcement:manage` | | | | ✅ | ✅ |
| `audit:view` | | | | ✅ | ✅ |
| `logs:view` | | | ✅ | ✅ | ✅ |
| `export:run` | | ✅ | ✅ | ✅ | ✅ |
| `import:run` | | | ✅ | ✅ | ✅ |

**Adding a new permission:** add the constant to `PermissionCode`, add it to the relevant role(s) in `DEFAULT_ROLE_PERMISSIONS`, re-run `python -m scripts.create_admin` (idempotent — adds missing permissions/mappings without duplicating). No code path should ever check `user.role.name == "..."` directly for authorization; always go through `RoleLookupService.role_has_permission()` / `require_permission()` / `require_web_permission()`.

**Scoped (record-level) RBAC example:** `UserService.process_approval()` — a LEAD may only approve a PENDING user whose `group_id` matches their own; DEVELOPER_LEAD/OWNER bypass this scope. See `_scope_role_names()` in `app/services/user_service.py`.

---

## API Reference

Full interactive reference: **Swagger UI at `/docs`**, ReDoc at `/redoc`, raw OpenAPI JSON at `/openapi.json` (all served automatically by FastAPI from the route/schema definitions — always current, prefer it over a hand-maintained list for exact request/response shapes).

Base path: `/api/v1`. All endpoints except `/auth/register` and `/auth/login`/`/refresh` require `Authorization: Bearer <access_token>`.

| Resource | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/change-password` |
| Users | `GET/POST /users`, `GET/PATCH/DELETE /users/{id}`, `GET /users/me`, `POST /users/{id}/approval` |
| Products | `GET/POST /products`, `GET/PATCH/DELETE /products/{id}` |
| Groups | `GET/POST /groups`, `GET/PATCH/DELETE /groups/{id}` |
| Setups | `GET/POST /setups`, `GET/PATCH/DELETE /setups/{id}` |
| Reservations | `GET/POST /reservations`, `GET /reservations/{id}`, `PATCH /reservations/{id}/cancel` |
| Swaps | `GET/POST /swaps`, `GET /swaps/{id}`, `PATCH /swaps/{id}/approve\|reject\|cancel`, `POST /swaps/mapping`, `PATCH /swaps/mapping/{batch_id}/approve` |
| Announcements | `GET/POST /announcements`, `GET/PATCH/DELETE /announcements/{id}` |
| Audit Logs | `GET /audit-logs` (read-only) |
| Exports | `POST /exports/setups`, `POST /exports/setups/template`, `POST /exports/reservations` |
| Imports | `POST /imports/setups` (multipart) |
| Developer Logs | `GET /dev-logs/tree`, `GET /dev-logs/download?path=...` |

**Response envelopes** (`app/schemas/common.py`):
```json
// Paginated list
{"items": [...], "page": 1, "page_size": 25, "total_items": 142, "total_pages": 6}

// Error (any 4xx/5xx)
{"error": {"code": "RESERVATION_CONFLICT", "message": "...", "details": {...}}}
```
`error.code` is stable and machine-branchable (see `app/core/exceptions.py` for the full hierarchy) — automation should match on `code`, not `message`.

---

## Future Automation

The system was designed from the ground up to be **directly queryable by external automation** against the SQL database, independent of the API:

- **Stable, typed columns** — no automation-hostile JSON blobs for core fields; `setups.status`, `reservations.status`, etc. are plain indexed strings with `CHECK` constraints, documented in `alembic/versions/0001_initial_schema.py`.
- **`setups.status`** is the single fast filter for "what's free right now" (`WHERE status = 'AVAILABLE'`) without needing to join `reservations`.
- **`reservations`** is the append-style source of truth for who-had-what-when; `SWAPPED`/`CANCELLED`/`COMPLETED` rows are retained, never deleted, so a full utilization history is directly queryable.
- **`audit_logs`** gives automation (or a compliance pipeline) a single append-only table to tail for every state change in the system, with `entity_type`/`entity_id`/`action` columns built for filtering.
- **`export_logs` / `excel_transaction_logs`** plus the rotating Excel files under `EXCEL_LOG_DIR` give a parallel, portable (non-DB) audit trail specifically for bulk import/export operations — useful for handing off to systems that consume Excel rather than SQL.
- **Read-only DB users**: for production, create a dedicated PostgreSQL role with `SELECT`-only grants for automation/reporting consumers, distinct from the application's read-write role — this is a deployment-time DB administration step, not something the application enforces itself.
- **API-first automation**: for anything beyond read-only reporting (creating reservations, approving swaps, etc.), prefer the JSON API over direct writes — the API enforces the same business rules (overlap checks, RBAC, audit logging) that direct SQL writes would bypass entirely.

---

## Developer Standards

- **Python 3.8 compatibility is non-negotiable**: `typing.List/Dict/Optional/Union`, never builtin generics (`list[str]`); no `match`/`case`; no walrus-adjacent 3.9+-only stdlib APIs.
- **Pydantic v1 syntax only** (`class Config: orm_mode = True`, `@validator`, not v2's `model_config`/`field_validator`).
- **Clean architecture boundaries are enforced by import direction**: if you find a router importing a repository, or a repository importing a service, that's a layering violation — fix it, don't work around it.
- **Every new resource gets**: a model (`app/models/`), a schema (`app/schemas/`), a repository interface + SQLAlchemy impl (`app/repositories/`), a service (`app/services/`), DI wiring in `app/api/deps.py`, an API router (`app/api/v1/`), and (if user-facing) a web router + templates (`app/web/`). Register new models in `app/models/__init__.py` so Alembic and relationship resolution see them.
- **Every mutating service method** calls `AuditService.record(...)` with `action`, `entity_type`, `entity_id`, and before/after snapshots where meaningful.
- **Never bypass the service layer** from a router — routers only orchestrate: parse input (FastAPI/Pydantic does this), call one service method, return its result.

## Coding Guidelines

- **PEP 8**, type hints on every function signature, docstrings on every public class/function explaining *why*, not just *what*, where the reasoning isn't obvious from the name.
- **SOLID**: one service per aggregate (SRP); extend via new classes/strategies, not by branching inside existing ones (OCP); repository implementations must be substitutable behind their interface (LSP); prefer several narrow repository interfaces over one fat one where read/write concerns diverge (ISP); services depend on interfaces, not concrete SQLAlchemy classes (DIP).
- **No placeholders, no `TODO`s, no partial implementations** — if a feature is started, finish the full path (model → schema → repo → service → API/web) before moving on.
- **Exceptions**: raise a specific subclass of `app.core.exceptions.AppError` (not a bare `Exception` or FastAPI's `HTTPException`) from services, so business logic stays framework-agnostic and testable without FastAPI in the loop.
- **Logging**: use `app.core.logging_config.get_logger(__name__)`, never `print()`. Application logs are for operators; the `AuditLog` table is for compliance/history — don't conflate the two (see [Architecture](#architecture)).
- **Formatting**: keep lines reasonably short, prefer `.format()`-style or f-strings consistently within a file (this codebase favors `.format()` in service/repository code — match the surrounding file), avoid unnecessary abbreviations in names.

---

## Testing

Directories are scaffolded (`tests/unit/{services,repositories}`, `tests/integration/api`) with `__init__.py` markers but no test cases are checked in yet — write tests as you add features, following this structure:

- **`tests/unit/services/`**: instantiate a service with **fake repository implementations** (satisfying the relevant `Protocol` in `app/repositories/interfaces/`) — no database, no FastAPI. This is the primary place to test business rules (overlap validation, swap-mapping validation, RBAC scoping, state machines).
- **`tests/unit/repositories/`**: test SQLAlchemy repositories against a real **in-memory SQLite** engine (`sqlite:///:memory:`) with `Base.metadata.create_all()` — verifies query correctness without needing the full app.
- **`tests/integration/api/`**: use FastAPI's `TestClient` against the full app (override `get_db` to point at a temporary SQLite file or in-memory DB) to test routing, DI wiring, and the request/response contract end-to-end.

Suggested tooling (not yet pinned in `requirements.txt` — add as dev dependencies):
```bash
pip install pytest pytest-cov httpx
pytest --cov=app tests/
```

**Priority test targets** given the business-rule density in this codebase: `ReservationService._assert_no_overlap`, `SwapService.create_mapping`/`approve_mapping` (node-uniqueness/availability validation), `ReservationService.cancel` (pending-swap block), `UserService.process_approval` (Group-scoped Lead approval), `ImportService` (all-or-nothing commit + row-level error reporting).

---

## Common Issues

| Symptom | Cause / Fix |
|---|---|
| `ImportError: cannot import name 'X' from 'app.services...'` after adding a service | Check for a circular import — services should only import other services that sit strictly "below" them in the dependency graph (e.g. `ReservationService` may depend on `NotificationService`, but not vice versa). |
| New model's table not created by `Base.metadata.create_all()` or missing from Alembic autogenerate | Model class not imported in `app/models/__init__.py` — SQLAlchemy only registers classes that have been imported somewhere. |
| `422 Unprocessable Entity` on a request that looks correct | Check the Pydantic schema's field constraints (`Field(..., max_length=...)`, custom `@validator`) — the error envelope's `details.errors` lists the exact field and message. |
| A new permission doesn't take effect for existing users | Re-run `python -m scripts.create_admin` (idempotently adds new permissions to `DEFAULT_ROLE_PERMISSIONS` roles) — existing `User` rows don't need touching since permissions are resolved via `role.permissions` at request time, not cached on the user. |
| HTMX partial renders raw Jinja instead of processed HTML | Missing `{% include %}` context propagation — Jinja `include` shares the parent context by default; if you switched to `{% import %}` or a macro call, pass variables explicitly. |
| Web page shows a JSON error instead of an HTML error page | The exception raised wasn't `RedirectToLogin`/`ForbiddenWebError`/`StarletteHTTPException` — web routers must let auth/permission failures raise those specific types (see `app/web/deps.py`), not a generic `AppError`, for `main.py`'s handlers to route to an HTML response. |

## FAQ

**Q: Why Pydantic v1 instead of v2?**
A: The project targets Python 3.8; Pydantic v2's compiled core (pydantic-core) and API changes are optimized for 3.9+ workflows, and v1 remains fully supported and stable for this codebase's needs.

**Q: Why isn't `Setup.status` just computed from `reservations` on every read?**
A: Automation needs a fast, single-column filter (`WHERE status = 'AVAILABLE'`) without a join; the service layer keeps it in sync transactionally instead, trading a small amount of write-path complexity for read-path speed and automation-friendliness.

**Q: Can I run multiple Gunicorn workers against SQLite in production?**
A: You can, but SQLite serializes writers at the file level, so heavy concurrent write load (many simultaneous reservations) will see lock contention. For production traffic beyond a small team, migrate to PostgreSQL (see INSTALLATION.md §Database) — no code changes required.

**Q: How do I add a new Excel export type?**
A: Add a header list + a row-builder in `ExportService`, a new `ExportType` constant, a new endpoint in `app/api/v1/exports.py` (and optionally a web route), following the existing `export_setups`/`export_reservations` pattern.

**Q: Where do I change the swap-mapping validation rules?**
A: `SwapService.create_mapping()` — the docstring enumerates every rule currently enforced (distinct reservations, distinct targets, in-cycle vs. out-of-cycle availability). Add new rules as additional `if` checks raising `SwapMappingValidationError` with a specific message.

**Q: Is there a CLI besides the two `scripts/`?**
A: Not currently. `scripts/create_admin.py` and `scripts/seed_data.py` are the only management scripts; anything else should go through the API or a new script following the same `sys.path.insert` + explicit `SessionLocal()` pattern.
