# Reservation Management System — API Guide

Base path: `/api/v1`. Auth: Bearer JWT access token (`Authorization: Bearer <token>`), issued by `/auth/login`, refreshed via `/auth/refresh`. RBAC is enforced per-endpoint via permission codes (see the role matrix in USER_GUIDE.md §3 — note the **Bot** role is view-only; roles were renamed from User/Developer/Lead/Developer Lead/Owner to Bot/User/Lead/Manager/Owner). Errors return `{"error": {"message": "...", ...}}` with an appropriate HTTP status.

## Quick Reference

| Method | Endpoint | Purpose | Auth | Permission |
|---|---|---|---|---|
| POST | /auth/register | Self-register (PENDING) | No | — |
| POST | /auth/login | Login, get tokens | No | — |
| POST | /auth/refresh | Rotate refresh token | No (refresh token) | — |
| POST | /auth/logout | Revoke refresh token | Yes | — |
| POST | /auth/change-password | Change own password | Yes | — |
| POST | /auth/password-reset/request | Request reset email | No | — |
| POST | /auth/password-reset/confirm | Complete reset | No | — |
| GET | /users/me | Current user's profile | Yes | — |
| GET | /users | List users | Yes | user:view |
| POST | /users | Create user (approved) | Yes | user:manage |
| GET | /users/{id} | Get user | Yes | user:view |
| PATCH | /users/{id} | Update user | Yes | user:manage |
| DELETE | /users/{id} | Deactivate user (soft) | Yes | user:manage |
| DELETE | /users/{id}/permanent | Hard-delete user | Yes | user:manage |
| POST | /users/{id}/reactivate | Reactivate disabled/rejected user | Yes | user:manage |
| POST | /users/{id}/approval | Approve/reject pending registration | Yes | user:approve |
| GET | /products | List products | Yes | product:view |
| POST | /products | Create product | Yes | product:manage |
| GET | /products/{id} | Get product | Yes | product:view |
| PATCH | /products/{id} | Update product | Yes | product:manage |
| DELETE | /products/{id} | Delete product (blocked if setups exist) | Yes | product:manage |
| GET | /products/{id}/template | Get template (mandatory+custom columns) | Yes | product:view |
| POST | /products/{id}/template/columns | Add custom column | Yes | product:manage |
| PATCH | /products/{id}/template/columns/{col_id} | Edit custom column | Yes | product:manage |
| DELETE | /products/{id}/template/columns/{col_id} | Delete custom column | Yes | product:manage |
| POST | /products/{id}/template/columns/reorder | Reorder custom columns | Yes | product:manage |
| GET | /setups | List/filter setups | Yes | product:view |
| POST | /setups | Create setup | Yes | product:manage |
| GET | /setups/{id} | Get setup | Yes | product:view |
| PATCH | /setups/{id} | Update setup | Yes | product:manage |
| DELETE | /setups/{id} | Delete setup | Yes | product:manage |
| GET | /setups/{id}/custom-fields | Get setup's custom field values | Yes | product:view |
| PUT | /setups/{id}/custom-fields | Set setup's custom field values | Yes | product:manage |
| GET | /reservations | List reservations | Yes | reservation:view |
| POST | /reservations | Create reservation (one setup) | Yes | reservation:create |
| GET | /reservations/{id} | Get reservation | Yes | reservation:view |
| PATCH | /reservations/{id}/cancel | Cancel (unreserve) | Yes | owner (cancel_own) or reservation:cancel_any |
| GET | /swaps | List swap requests | Yes | swap:view |
| POST | /swaps | Request a column-value swap between two of your own reserved setups | Yes | swap:request |
| GET | /swaps/{id} | Get swap request | Yes | swap:view |
| PATCH | /swaps/{id}/approve | Approve pending swap | Yes | swap:approve |
| PATCH | /swaps/{id}/reject | Reject pending swap | Yes | swap:approve |
| PATCH | /swaps/{id}/cancel | Cancel own pending swap | Yes | requester only |
| POST | /swaps/mapping | Create coordinated multi-setup swap mapping | Yes | swap:approve |
| PATCH | /swaps/mapping/{batch_id}/approve | Approve every swap in a mapping batch | Yes | swap:approve |
| GET | /announcements | List announcements | Yes | announcement:view |
| POST | /announcements | Create announcement | Yes | announcement:manage |
| GET | /announcements/{id} | Get announcement | Yes | announcement:view |
| PATCH | /announcements/{id} | Update announcement | Yes | announcement:manage |
| DELETE | /announcements/{id} | Delete announcement | Yes | announcement:manage |
| GET | /groups | List groups | Yes | group:view |
| POST | /groups | Create group | Yes | group:manage |
| GET | /groups/{id} | Get group | Yes | group:view |
| PATCH | /groups/{id} | Update group | Yes | group:manage |
| DELETE | /groups/{id} | Delete group | Yes | group:manage |
| POST | /imports/setups | Import Excel (legacy, all products) | Yes | import:run |
| POST | /imports/setups/product/{id}/detect-columns | Preview new columns in upload | Yes | import:run |
| POST | /imports/setups/product/{id} | Import Excel for one product | Yes | import:run (+product:manage if accepting new columns) |
| POST | /exports/setups | Export setups (filtered) | Yes | export:run |
| POST | /exports/setups/template | Export blank import template | Yes | export:run |
| POST | /exports/setups/product/{id} | Export one product's setups (template-aware) | Yes | export:run |
| POST | /exports/reservations | Export reservations (filtered) | Yes | export:run |
| GET | /audit-logs | List audit log entries | Yes | audit:view |
| GET | /dev-logs/tree | Excel transaction log directory tree | Yes | logs:view |
| GET | /dev-logs/download | Download one rotated Excel log file | Yes | logs:view |

45 endpoints total.

## Authentication

### POST /auth/register
Body: `{username, email, password, full_name, group_ids?}`. Creates a user in **PENDING** status. `password`: 8+ chars, upper+lower+digit. Response: `UserResponse` (201). Audit: CREATE User.

### POST /auth/login
Body: `{username, password}`. Response: `{access_token, refresh_token, token_type}` (200). Errors: 401 invalid credentials; 403 pending/rejected/disabled account. Audit: LOGIN or LOGIN_FAILED.

### POST /auth/refresh
Body: `{refresh_token}`. Rotates it (old one revoked). Response: new token pair.

### POST /auth/logout
Body: `{refresh_token}`. Revokes it. Audit: LOGOUT.

### POST /auth/change-password
Auth required. Body: `{current_password, new_password}`. Revokes all sessions on success.

### POST /auth/password-reset/request
Body: `{email}`. Always the same generic response, whether or not the email exists (avoids enumeration). Sends a single-use, 30-minute token by email if the account exists and is approved/active.

### POST /auth/password-reset/confirm
Body: `{token, new_password}`. 401 if invalid/expired/used. Revokes all sessions on success.

## Users

`GET /users/me` returns the caller's own profile (no permission beyond being logged in). Standard CRUD under `/users` otherwise: list/get need `user:view`; create/update/deactivate/hard-delete/reactivate need `user:manage`. `UserCreateRequest`/`UserUpdateRequest` accept `group_ids: List[int]` (multi-group; also sets the primary `group_id` to the first entry). `DELETE /users/{id}` soft-deletes (deactivates); `DELETE /users/{id}/permanent` hard-deletes and returns 409 if the user still has dependent records (reservations, swaps, announcements, exports) — deactivate instead in that case. `POST /users/{id}/approval` (`user:approve`) body `{approve: bool, role_name?, rejection_reason?}` moves a PENDING user to APPROVED (optionally assigning a role, default USER) or REJECTED.

## Products

CRUD under `/products`; list/get `product:view`, mutations `product:manage`. `DELETE /products/{id}` returns 409 if any Setup still references it.

## Product Templates

Under `/products/{id}/template...`. `GET` returns `{product_id, mandatory_columns, custom_columns}`. Custom column fields: `name, label, data_type (STRING|INTEGER|FLOAT|BOOLEAN|DATE|DATETIME|DROPDOWN), required, default_value, allowed_values, order_index`. Mandatory columns can never be targeted (409/404). Reorder body: `{column_ids: [...]}` (every existing custom column id, exactly once).

## Setups

`GET /setups` filters: `product_id, group_id, status, location, search` + pagination. `POST`/`PATCH /setups/{id}` (`product:manage`) set mandatory fields (ip_address, hostname, owner_id, group_id, location, remarks, status, hardware fields); status changes go through a state-machine check. Custom field values are managed separately via `/setups/{id}/custom-fields` (`GET` → `{setup_id, values}`; `PUT` body `{values: {...}}`, validated against the setup's product template — type-checked, required-field-checked, dropdown-value-checked; 422 on violation).

## Reservation

`POST /reservations` body: `{setup_id, reserved_from, reserved_until, remarks?, announcement_channels?, announcement_message?}` — **one setup per call**; reserving several setups means calling this once per setup (the web UI does this in a loop). `PATCH /reservations/{id}/cancel` unreserves, callable by the owning user (`reservation:cancel_own`) or anyone with `reservation:cancel_any`.

## Swap

A swap exchanges the value of **one field** between two setups the requester currently has reserved -- it never relocates a reservation.

`POST /swaps` body: `{reservation_id, requested_setup_id, column_name, reason?}` (`swap:request`). `reservation_id` must be the caller's own ACTIVE reservation; `requested_setup_id` must also currently be reserved by the *same* caller (self-reserved rule); `column_name` must be one of the fixed hardware fields (`ssd, hdd, hardware_info, capacity, form_factor, adapter, aardvark, quarch, apc, remote_server`) or, when the two setups belong to different products, a custom template column present on *both* products. 422/409 if any of that doesn't hold. On success, a PENDING swap is created and Leads+ are notified (`MAIL_LEADS`) that approval is needed.

`PATCH /swaps/{id}/approve` (`swap:approve`) re-verifies both setups are still self-reserved by the requester, then swaps `column_name`'s value between the two Setup rows (or, for a custom column, the two `SetupCustomFieldValue` rows) and marks the request COMPLETED. Neither reservation nor setup status changes. `PATCH /swaps/{id}/reject` (`swap:approve`) body `{reason?}`. `PATCH /swaps/{id}/cancel` — the requester withdraws their own still-pending request.

**Separately**, `POST /swaps/mapping` (`swap:approve`) body `{mappings: [{reservation_id, target_setup_id}, ...] (min 2), reason?}` is an unrelated, coordinated *reservation-relocation* workflow: every reservation and every target setup must appear exactly once; creates one PENDING swap per mapping entry as a batch. `PATCH /swaps/mapping/{batch_id}/approve` approves every swap in that batch atomically (this path still relocates reservations as before).

## Announcements

`GET` (list/single) needs `announcement:view` (every role has it); create/update/delete need `announcement:manage` (Manager/Owner only — Lead can view but not manage). Fields: `title, message, priority, start_date, end_date`. Listed sorted by priority severity (CRITICAL > HIGH > NORMAL > LOW), then most recent first. The scheduler also creates CRITICAL announcements automatically when a reservation expires without being unreserved.

## Groups

CRUD; list/get `group:view`, mutations `group:manage`.

## Excel Import

- `POST /imports/setups` — legacy, unscoped import (headers must match the fixed `SETUP_IMPORT_COLUMNS` set; `product_name` column resolves the product per row).
- `POST /imports/setups/product/{id}/detect-columns` — multipart file upload; returns `{product_id, known_columns, new_columns, total_rows}` without importing.
- `POST /imports/setups/product/{id}?accept_new_columns=bool` — multipart file upload; validated against the product's template. Unknown columns + `accept_new_columns=false` → `committed=false`, `new_columns` populated, nothing imported. `accept_new_columns=true` → columns added (as String) to the template first, then import proceeds. Response: `ImportResultResponse {batch_id, total_rows, created_count, updated_count, error_count, errors, committed, new_columns}`. Row errors block commit entirely (all-or-nothing). Audit: IMPORT per created/updated setup; transaction log rows written per row.

## Excel Export

- `POST /exports/setups` — filtered setups, fixed columns.
- `POST /exports/setups/template` — blank import template (fixed columns only).
- `POST /exports/setups/product/{id}` — one product, mandatory + its current custom columns, in template order; empty header-only template if no setups exist yet.
- `POST /exports/reservations` — filtered reservations.

All return a downloadable `.xlsx` `FileResponse`. Audit: EXPORT.

## Logs / Audit

- `GET /audit-logs` (`audit:view` — Manager/Owner only): filter by `entity_type, entity_id, user_id, action` + pagination. Returns actor, action, entity, old/new value snapshot, timestamp.
- `GET /dev-logs/tree` / `GET /dev-logs/download?path=...` (`logs:view` — Manager, Owner): browse/download rotated Excel import/export transaction log files. `download` resolves `path` against the logs directory only — traversal outside it is rejected. **Lead no longer has this permission** (removed in the latest role rework).

## Status Codes

| Status | Meaning |
|---|---|
| 200 | Success |
| 201 | Created |
| 400/422 | Validation error |
| 401 | Authentication failed / invalid or expired token |
| 403 | Authenticated but not authorized (missing permission, account not approved/disabled) |
| 404 | Not found |
| 409 | Conflict (business rule violation, e.g. delete blocked, duplicate name) |
| 500 | Unhandled server error |

## Workflow Examples

- **Login → browse setups**: `POST /auth/login` → `GET /setups?product_id=1`
- **Reserve**: `GET /setups?product_id=1&status=AVAILABLE` → `POST /reservations` (once per setup)
- **Swap a column between two of your own setups**: `POST /swaps` (`reservation_id`, `requested_setup_id`, `column_name`) → `PATCH /swaps/{id}/approve`
- **Coordinated reservation relocation (separate workflow)**: `POST /swaps/mapping` → `PATCH /swaps/mapping/{batch_id}/approve`
- **Unreserve**: `PATCH /reservations/{id}/cancel`
- **Design a template then import**: `POST /products/{id}/template/columns` (repeat) → `POST /imports/setups/product/{id}/detect-columns` → `POST /imports/setups/product/{id}?accept_new_columns=true`
- **Export current data**: `POST /exports/setups/product/{id}`
- **Approve a new user**: `GET /users?status=PENDING` → `POST /users/{id}/approval`
- **Forgot password**: `POST /auth/password-reset/request` → `POST /auth/password-reset/confirm`
