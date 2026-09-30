# Reservation Management System — Developer Guide

Server-rendered FastAPI application (Bootstrap 5 + HTMX + Jinja2) with a JSON API under `/api/v1`. Python 3.8 compatible; SQLAlchemy 1.4, Pydantic 1.10, Alembic. Default database is SQLite (PostgreSQL-ready). See `INSTALLATION.md` for deployment and `API_GUIDE.md` for endpoints.

## 1. Architecture

Layered, contract-driven:

```
Web routers (app/web/routers) ─┐
API routers (app/api/v1)      ─┼─> Services (app/services) ─> Repository interfaces (app/repositories/interfaces)
                                                                  └─> SQLAlchemy repositories (app/repositories/sqlalchemy) ─> Models (app/models)
Schemas (app/schemas, Pydantic) validate/serialise at the edges.
```

- **Services** hold all business rules and raise typed errors (`app/core/exceptions.py`); routers only translate HTTP/HTML.
- **Repositories** are the only code that queries the database; services depend on Protocol interfaces.
- **Dependency injection** is wired in `app/api/deps.py` (`get_*_service` / `get_*_repository`, `require_permission`).
- **Independence rule:** Reservation, Swap and Borrow do not depend on each other. `ReservationService` has no Swap/Borrow code; `SwapService` and `BorrowService` never read or write reservations. The approval hierarchy only routes approvals — it never grants access.

## 2. Directory structure

| Path | Content |
|---|---|
| `app/main.py` | App factory, middleware, router registration, scheduler start |
| `app/core/` | `config.py` (settings), `constants.py` (roles, permissions, statuses), `exceptions.py`, `security.py`, logging |
| `app/models/` | SQLAlchemy models; `baseline_capture.py` registers baseline mapper events |
| `app/schemas/` | Pydantic request/response models |
| `app/repositories/` | `interfaces/` (Protocols) and `sqlalchemy/` implementations |
| `app/services/` | Business logic (swap, borrow, reservation, routing, import/export, notifications, scheduler…) |
| `app/api/v1/` | JSON API routers; `app/api/deps.py` DI |
| `app/web/` | `routers/` (HTML/HTMX views), `templates/`, `static/` (`js/table.js`, `css/styles.css`), `deps.py` |
| `app/middleware/` | Error handler (`AppError` → JSON/HTML), request logging |
| `alembic/versions/` | Migrations `0001`–`0013` |
| `scripts/` | `create_admin.py`, `seed_data.py` |
| `deploy/` | Service, nginx/apache, gunicorn, backup/restore scripts |
| `tests/` | Pytest suite (see §15) |
| `docs/` | Sphinx site (see §16) |

## 3. Authentication and RBAC

- Register → user is `PENDING`; a Lead/above approves (`UserStatus`: PENDING, APPROVED, REJECTED, DISABLED). Login issues a JWT access token + rotating refresh token (API) or a cookie session (web). Passwords use bcrypt. Password reset uses single-use tokens (`password_reset_tokens`).
- Roles (`RoleName`): `BOT` < `USER` < `LEAD` < `MANAGER` < `OWNER`. Legacy Python attribute names (`USER`, `DEVELOPER`, `DEVELOPER_LEAD`) map to the stored strings BOT/USER/MANAGER — always compare with `RoleName.*` constants, not string literals.
- Permissions are rows (`permissions`, `role_permissions`) seeded from `constants.py`. Enforce with `require_permission(PermissionCode.X)` (API) and `require_web_permission` (web). Templates read `current_user_permissions`.
- Borrow permissions (`borrow:view/request/approve/return`) belong to LEAD, MANAGER, OWNER; `BorrowService` additionally checks the role and group membership.
- Fine-grained rules live in services (owner-only cancel, routed-approver checks, group access).

## 4. Data model

Core: `users`, `roles`, `permissions`, `groups`, `user_groups`, `products`, `setups`, `reservations`, `announcements`, `audit_logs`, `export_logs`, `excel_transaction_logs`, `refresh_tokens`, `password_reset_tokens`.

Template/custom data: `product_template_columns` (per-product column definitions), `setup_custom_field_values` (EAV current values).

Workflow tables: `swap_requests`, `borrow_requests`, `setup_access_grants` (one row per approved borrow), `group_hierarchy_edges` (parent, child, `scope` = SWAP | BORROW | BOTH).

Original/Current hardware: `setup_hardware_baseline` (one row per setup, the ten fixed hardware fields), `setup_custom_field_baselines` (setup, template column, value), `hardware_change_logs` (per-field ledger: old/new value, `source` SWAP/BORROW/…, `source_request_id`, user).

## 5. Original vs Current hardware model

- **Current/effective** = the live values: fixed columns on `setups` and rows in `setup_custom_field_values`.
- **Original/baseline** = insert-only snapshot. `app/models/baseline_capture.py` (SQLAlchemy `after_insert` events) writes the baseline when a `Setup` or the first `SetupCustomFieldValue` is inserted, so every creation path (API, import, seed, tests) is covered. Baselines are never updated by Swap/Borrow.
- **Re-baseline** happens only in Setup Edit (web form and `PATCH /api/v1/setups/{id}`): `HardwareStateService.rebaseline_edited_fields` copies the *changed* fields' new values into the baseline. Excel import does not re-baseline.
- `HardwareStateService.changed_fields(setups)` compares Original vs Current generically (fixed field names come from `BASELINE_FIELD_NAMES`, derived from the baseline table; custom fields from template columns; None/blank/whitespace are equal). `compare()` and `history()` feed the *Original vs Current* dialog. `_table_body.html` adds class `rms-cell-changed` to each changed cell — no per-field logic.
- Migration `0013` backfills baselines from current values; history before that cannot be reconstructed.

## 6. Reservation

`ReservationService`: create (setup must exist and not be MAINTENANCE/RETIRED; overlap with any ACTIVE reservation raises `ReservationConflictError` — checked in the service, not via a DB constraint), cancel (owner or `reservation:cancel_any`), `sweep_expired_reservations` (ACTIVE → COMPLETED, setup → AVAILABLE). `Reservation.remarks` stores the reason; `announcement_channels` trigger `NotificationService.broadcast_reservation_event`. Statuses: ACTIVE, CANCELLED, COMPLETED. `RESERVATION_MIN_LEAD_MINUTES` is enforced in `ReservationService._assert_min_lead_time`: when > 0, `reserved_from` must be at least that many minutes from now (422 `VALIDATION_ERROR`); 0 (default) disables it. It is read at call time and applies to reservations only, not Swap/Borrow times.

## 7. Swap

`SwapService` (`swap_requests`). Statuses: PENDING → COMPLETED | REJECTED | CANCELLED | EXPIRED.

- **Create:** setups must differ and not be MAINTENANCE/RETIRED; `_assert_has_setup_access` on **both** setups (group access; Owner always; ungrouped setup open; a setup lent out via an active grant is held by the borrower group, not the owner group); requested columns must exist on both setups (`swappable_columns`: fixed fields + custom columns present on both products' templates); routed approver emails are snapshotted; optional reason/start/end/announcement.
- **Approve:** `_assert_can_approve` (routed approvers via `ApprovalRoutingService.resolve_approvers_for_group(current_setup.group_id)`; Owner override; empty routing falls back to the flat `swap:approve` permission). Missing baselines are captured first, values exchanged in one transaction, one `hardware_change_logs` row per changed field per setup, audit entries written. Original is untouched.
- **Reject/Cancel** change nothing. Requester cancels own PENDING swaps only.
- No swap-mapping functionality exists (removed; `SwapRequest.setup_id` is a legacy unused column).
- `SWAP_REQUIRE_SAME_PRODUCT` (default `true`) is enforced in `SwapService.create` (422 if the setups' products differ) and in `swappable_columns`, so the Swap dialog only lists same-product partners. Set it to `false` to allow cross-product swaps for columns present on both setups.

## 8. Borrow

`BorrowService` (`borrow_requests`, `setup_access_grants`). Statuses: PENDING → COMPLETED (approved, currently borrowed) → RETURNED; PENDING → REJECTED | CANCELLED | EXPIRED.

- **Create:** requester role LEAD/MANAGER/OWNER with a `group_id`; `source_lead_id` must be an active approved Lead/Manager; setup must belong to that lead's group and not to the requester's; not MAINTENANCE/RETIRED; no other PENDING/COMPLETED borrow and no active grant on the setup; optional `hardware_field_name` (fixed field or product custom column; informational); `end_time` must be in the future.
- **Routing:** `resolve_borrow_approvers(source_group_id)` — the source group's lead(s), its parent's leads and sibling groups' leads under that parent, using BORROW/BOTH edges (example: E selects lead d → b, d, f, g). Any ONE approves; requester cannot; Owner can; empty routing falls back to `borrow:approve`.
- **Approve:** creates one active `SetupAccessGrant(granted_to_group_id=borrower)`, status COMPLETED. `Setup.group_id` and hardware values are never modified; the effective holder is the active grant's group. `SetupRepository.list` (group filter) and `get_active_grant_group_ids` use this.
- **Return:** requester, lead of the borrowing group, routed source approver or Owner; closes the grant (`is_active=false`, `returned_at`), status RETURNED, emails requester + source leads, announces on the chosen channels.
- **Expiry:** PENDING requests past `end_time` become EXPIRED lazily (`list`/`approve`) and via the `borrow_sweep` scheduler job. Approved borrows are not auto-returned; the UI shows *Overdue*.

## 9. Approval routing

`ApprovalRoutingService` reads `group_hierarchy_edges`; nothing is hardcoded. Swap routing = requester-setup group plus all ancestors (SWAP/BOTH edges); Borrow routing as in §8. Approver roles considered: LEAD and MANAGER (users matched by primary `group_id`). Manage edges with `GET/POST/DELETE /api/v1/group-hierarchy` (`group:manage`); there is no web screen for it.

## 10. Email and announcement flow

`NotificationService.broadcast_reservation_event(channels, message, setup, acting_user)` supports `WALL` (creates a 7-day announcement), `MAIL_LEADS`, `MAIL_GROUP`, `MAIL_ALL`. Swap/Borrow additionally call `email_direct` for routed approvers/requester regardless of channels. `EmailService.send_email` sends via SMTP only when `SMTP_ENABLED=true`; otherwise it logs the message. The announcement sweep deactivates expired announcements.

## 11. Excel import/export

`ImportService` upserts setups (key: IP or hostname); required headers `ip_address`, `hostname`, `location`; any row error rejects the whole import; product-scoped import detects unknown columns (`detect-columns`) and either adds them to the template (`accept_new_columns=true`) or rejects. Parsing: `app/utils/excel_reader.py` (`SETUP_IMPORT_COLUMNS`); writing: `excel_writer.py`. Each import/export writes an `ExcelTransactionLog`/`ExportLog` row and rotating Excel log files. Creating setups through import fires the baseline hook; updating them does not change baselines.

## 12. Audit and history

`AuditService.record(user_id, action, entity_type, entity_id, old_value, new_value)` → `audit_logs` (viewable at **Logs**, `GET /api/v1/audit-logs`). Domain history: `swap_requests`, `borrow_requests`, `setup_access_grants`, `hardware_change_logs`.

## 13. Web layer

Full pages extend `base.html`; HTMX partials (`_*.html`) are swapped into targets and signal toasts through `HX-Trigger` (`app/web/htmx_utils.py`). Key routers: `setups_view` (table, reserve/swap/unreserve dialogs, hardware compare, edit), `borrows_view`, `approvals_view` (unified Swap+Borrow approvals with least-visibility filter), `swap_approvals_view` (older swap-only page), `products_view`, `users_view`, `groups_view`, `announcements_view`, `audit_view`, `docs_view` (serves `docs/_build/html` at `/documentation`).

## 14. Configuration and migrations

Settings are read from environment/`.env` (`app/core/config.py`): `APP_ENV`, `SECRET_KEY`, token lifetimes, `DATABASE_URL`, log/export/Excel-log directories, `SMTP_*`, `CORS_ALLOWED_ORIGINS`, `SEED_ADMIN_*`, `ENABLE_SCHEDULER`, `RESERVATION_SWEEP_INTERVAL_MINUTES` (also used by the borrow sweep), `ANNOUNCEMENT_SWEEP_INTERVAL_MINUTES`, `RESERVATION_MIN_LEAD_MINUTES`, `SWAP_REQUIRE_SAME_PRODUCT`. Never commit `.env`; set a real `SECRET_KEY`.

Migrations: `alembic upgrade head` (head `0013`), `alembic downgrade -1`, `alembic revision -m "…"`. Keep changes additive/backward compatible.

## 15. Local setup, workflow, testing

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # set SECRET_KEY, SEED_ADMIN_PASSWORD
alembic upgrade head
python -m scripts.create_admin
uvicorn app.main:app --reload
pytest tests/ -v
```

Tests: `tests/test_backend.py`, `test_business_logic.py`, `test_frontend.py`, `test_integration.py`, `tests/unit/models/test_phase1_data_model.py`, plus `test_phase4_completion.py`, `test_phase5_borrow.py`, `test_phase6_ui.py`. Fixtures (`conftest.py`) provide users per role, `make_user`, `make_setup`, `product`, `auth_headers`, `web_login`. Workflow: change service + tests together, keep routers thin, add a migration for any schema change, run the full suite.

## 16. Documentation build

Sphinx sources are in `docs/` and include the root Markdown files (no duplication). `pip install -r docs/requirements.txt && sphinx-build -b html docs docs/_build/html`; the app serves the result at `/documentation`.

## 17. Debugging and troubleshooting

- Logs: `LOG_DIR` (default `./logs`); **Developer Logs** page in the UI; set `LOG_LEVEL=DEBUG`, `DATABASE_ECHO=true` for SQL.
- Emails "not sent": `SMTP_ENABLED` is false — see the log line *Email (SMTP disabled, not sent)*.
- No highlight/baseline: check the row exists in `setup_hardware_baseline`; rows created before migration `0013` are backfilled by it.
- Approver can't approve: check `group_hierarchy_edges` scope (SWAP vs BORROW vs BOTH) and that the user's role is LEAD/MANAGER with the right primary group.
- Scheduler jobs not running: `ENABLE_SCHEDULER=false` or running multiple workers (use one scheduler process).

## 18. Extension points

- New workflow: model + migration → repository interface/impl → service → API router (`app/api/v1`) → web router → register in `app/main.py`/`router.py` and `deps.py`.
- New hardware field: add the column to `setups` and `setup_hardware_baseline` (baseline fields are derived from the table), plus schemas/import/export headers; comparison and highlighting need no change.
- New notification channel: extend `AnnouncementChannel` and `NotificationService.broadcast_reservation_event`.
- New approval domain: add an `ApprovalHierarchyScope` value and a resolver in `ApprovalRoutingService`.

## 19. Known limitations

- Runtime behaviour of the Swap/Borrow/Approvals/baseline features has been reviewed and statically checked but must be confirmed by running the test suite and the manual plan in `TESTING.md`.
- Borrow is setup-level access with manual return; there is no auto-return.
- Swap candidate list is capped at 500 setups; Approvals lists 200 items per tab.
- Deleting a template column that already has values is blocked by an existing foreign key.
- The older `/admin/swap-approvals` page coexists with `/approvals`.
- Hierarchy edges can only be managed via the API.
