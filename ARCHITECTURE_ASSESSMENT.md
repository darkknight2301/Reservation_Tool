# Architecture Assessment — Reservation Management Tool

**Phase 0 deliverable. No application code was modified to produce this document.**

Scope of inspection: full backend (FastAPI/SQLAlchemy/Alembic), server-rendered
frontend (Jinja2/HTMX/Bootstrap), SQLite schema and migration history, RBAC,
Reservation, Swap, Swap-Mapping, Approval, Groups/Users, Announcements/Email,
Excel import/export, API, audit/logs, and the existing test suite
(`tests/test_backend.py`, `tests/test_business_logic.py`,
`tests/test_integration.py`, `tests/test_frontend.py`, ~1,875 lines).

---

## 1. Current Architecture

Strict layered/clean architecture, inward dependency direction only:

```
Presentation   app/api/v1/*        (JSON, Bearer JWT)
               app/web/routers/*   (Jinja2 + HTMX, HttpOnly cookie session)
Application    app/services/*      (business rules, transaction boundaries)
Domain         app/schemas/*       (Pydantic v1 DTOs), app/core/constants.py (enums)
Persistence    app/repositories/interfaces/* (typing.Protocol contracts)
               app/repositories/sqlalchemy/*  (concrete impls)
Infrastructure app/db/*  (engine/session, RBAC seed), app/core/* (config, security, logging)
```

Enforced rules worth preserving as-is (they are the project's real strength):
- Routers never touch the ORM; they call a Service via `Depends()`.
- Services depend on repository **interfaces**, never concrete SQLAlchemy classes.
- Both `api/v1` (JSON) and `web` (HTML/HTMX) routers call the **same** service
  layer — no business-logic duplication between the two front doors.
- `DATABASE_URL` is the only SQLite/PostgreSQL seam; no dialect-specific SQL.
- `Setup.status` is a cached/derived column kept in sync by the service layer
  inside the same transaction as any reservation-state change (fast filter
  for automation, no join required).
- Interval-overlap validation lives in `ReservationService`, not a DB
  constraint (SQLite has no portable `EXCLUDE USING gist` equivalent).
- Three independent, deliberately-not-merged log surfaces: `AuditLog` (DB,
  permanent, append-only), application logs (rotated JSON, ops/debugging),
  and rotating Excel transaction logs (bulk import/export row outcomes).
- Every mutating service method calls `AuditService.record(...)`.
- Python 3.8 / Pydantic v1 syntax throughout — a hard constraint on any new code.

This architecture is sound and should be **preserved**. The work required by
the new business rules is almost entirely new aggregates (Borrow, an
Approval-hierarchy) and a redesign of one existing aggregate (Swap), not a
change to the layering itself.

---

## 2. Existing Reusable Components (keep, extend — do not rebuild)

| Component | Reuse plan |
|---|---|
| **RBAC core** — `Role`, `Permission`, `role_permissions`, `RoleLookupService`, `require_permission` / `require_web_permission`, data-driven `DEFAULT_ROLE_PERMISSIONS` | Reuse as the *general access* layer (who can view/create/manage). New `borrow:*` permission codes added the same way. Record-level/approval-routing logic stays **outside** this matrix per business rule 8. |
| **`AuditService`** | Reuse unchanged. New `entity_type` values (`SwapRequest` semantics change, `BorrowRequest`, `ApprovalHierarchyEdge`) recorded through the same `record()` call. |
| **`NotificationService` / `EmailService` / `AnnouncementService`** | Reuse the fan-out pattern (`WALL` / `MAIL_LEADS` / `MAIL_GROUP` / `MAIL_ALL`). Extend `_group_lead_emails` into a hierarchy-aware "applicable lead emails" resolver (see §6) and add Swap/Borrow-specific message builders next to the existing reservation one. |
| **`TemplateService` + EAV (`ProductTemplateColumn` / `SetupCustomFieldValue`)** | Reuse untouched — Products/templates must keep current behavior per business rule 7. The EAV pattern (add capability without a migration) is also the right pattern to reuse for hardware baseline/effective value storage (§5). |
| **`ImportService` / `ExportService`, `excel_reader.py`, `excel_writer.py`, `excel_log_rotator.py`** | Reuse the engine and row-level `ExcelTransactionLog` pattern. Header lists (`_SETUP_HEADERS`) and the Setup Table export need new columns for baseline vs effective hardware and Borrow/Swap-pending indicators. |
| **`ReservationService`** overlap validation, cancel-permission logic, `sweep_expired_reservations` scheduler hook | Reuse the overlap-window algorithm and the ownership/`cancel_any` permission check. Remove the current *Swap→Reservation* coupling (see §3.1) so Reservation truly has zero dependency on Swap/Borrow state, per the explicit architectural requirement. |
| **`SetupService`** status state machine (`AVAILABLE → RESERVED → MAINTENANCE → RETIRED`) | Reuse. Setup identity fields (`ip_address`, `hostname`) and lifecycle stay exactly as-is; only the *hardware* fields need an Original/Effective split. |
| **`UserService.process_approval` / `_scope_role_names`** | Reuse the *pattern* (route by a resolvable "approver scope" function) but replace the flat `group_id` equality check with the new hierarchy resolver for Swap/Borrow approval routing. User registration approval itself is out of scope for the new rules and is left unchanged. |
| **`GroupService`**, `Group` model | Reuse Group as the access/ownership unit. It needs one additive change (§5) — an explicit hierarchy edge table — not a redesign. |
| **Web dialog / HTMX pattern** (`reserve_dialog.html`, `table.js`, `hx_trigger`, `_table_body.html`) | Reuse the interaction pattern (checkbox-driven action buttons, HTMX partial re-render, toast triggers) for the new Swap and Borrow dialogs and for cell highlighting. |
| **Test fixtures** (`conftest.py`: `client`, `db_session`, `make_user`, `make_setup`, role-specific user fixtures) | Reuse directly; extend with hierarchy/group-tree fixtures for the new approval tests. |
| **Scheduler (`scheduler_service.py`)** | Reuse the background-sweep pattern for a future "auto-expire stale Borrow" job if ever needed (not required by current rules; noted as a Future Enhancement only). |

---

## 3. Current Reservation / Swap Design (as built today)

### 3.1 Reservation
`Reservation` is already its own aggregate (`reservations` table) and is
close to the target model:
- `ReservationService.create()` validates the setup is not `MAINTENANCE`/`RETIRED`
  and that the requested window doesn't overlap any `ACTIVE` reservation on
  that setup (service-layer check, not a DB constraint).
- `cancel()` enforces owner-or-`reservation:cancel_any`.
- **Existing coupling to remove:** `cancel()` currently calls
  `swap_repository.get_pending_by_reservation_id()` and **blocks unreserving
  while a swap is pending**. This is a real dependency of Reservation on
  Swap state, which conflicts with the new requirement "Swap must not depend
  on whether the setup is reserved" / "avoid making Reservation, Swap and
  Borrow dependent on each other." It needs to be removed or re-homed once
  Swap no longer relocates the reservation itself (see 3.2) — once a Swap is
  a pure hardware-field change, there is nothing for an unreserve to
  conflict with.
- Reservation does not grant hardware ownership today (correct, matches the
  new rule) and does not auto-approve anything (correct).

### 3.2 Swap (current implementation — will change substantially)
`SwapRequest` today conflates **two different concepts** that the new
business rules explicitly separate:

1. **A column-value exchange** between two setups (`current_setup_id` /
   `requested_setup_id`, one or more `column_name`s) — this is close to the
   new "Swap = hardware configuration change" concept, *but*
2. **A reservation relocation**: `SwapService.approve()` unconditionally
   marks the requester's *original* reservation `SWAPPED` and creates a
   *brand-new* `ACTIVE` reservation on the *requested* setup, and requires
   the requested setup to be `AVAILABLE` (i.e. not reserved by anyone).
   `Setup.status` flips `current→AVAILABLE`, `requested→RESERVED`.

In other words, today's "Swap" actually **moves the user to a different
physical setup**, which is precisely what the new spec wants to be
possible only for a genuinely different concept (there is no Borrow at
all today; nothing in the current model represents "keep my setup, change
one card in it" without also moving me). The dialog's own copy
(`swap_dialog.html`: *"Neither setup's reservation is affected"*) is
**already inconsistent with what the code does** — a pre-existing bug
worth noting, not something introduced by this redesign.

Other current Swap characteristics:
- No `start_time`/`end_time`, no `announcement_channels`, no
  "applicable lead emails" selection on `SwapCreateRequest` — business
  rule 2 is not met today.
- Approval is a single flat permission check (`swap:approve`, held by
  `LEAD`/`MANAGER`/`OWNER` **globally**) — any Lead anywhere can approve any
  Swap anywhere. There is no concept of "the Lead responsible for this
  setup/group" and no hierarchy routing at all.
- Hardware fields are mutated **in place** on `setups`. The only "history" is
  (a) a human-readable line appended to `Reservation.remarks`
  (`"user swapped 'ssd' (X -> Y) between A and B at ..."`), and
  (b) `SwapRequest.previous_current_value` / `previous_requested_value`
  (a single JSON snapshot captured only at approval time, only for that one
  request). **There is no durable, queryable Original/Baseline hardware
  state** — if a setup is swapped twice, the first swap's "previous" value is
  not retrievable from anywhere except by manually reading the remarks text
  or the audit log's JSON blobs. This does not satisfy "Every change must be
  traceable back to the original state" / "Do not destroy original hardware
  information."
- Rejecting a swap correctly leaves effective hardware untouched (good,
  matches the new rule) — this piece of logic is reusable.
- Approval/rejection is audited (good, reusable).

### 3.3 Swap-Mapping (separate feature, targeted for removal)
`SwapService.create_mapping()` / `approve_mapping()`, the
`/admin/swap-mapping` screen (`swap_mapping_view.py`,
`admin/swap_mapping.html`, `admin/_swap_mapping_batches.html`), and the
`POST /swaps/mapping` / `PATCH /swaps/mapping/{batch_id}/approve` API
endpoints implement a **coordinated multi-node reservation relocation**
(A→B, B→A, C→D in one atomic batch, keyed by `batch_id`). Business rule 6
("Remove/avoid swap-mapping functionality") maps directly onto this
feature. It is structurally separate from the single-swap flow (own
methods, own validation, shares only the `swap_requests` table via
`batch_id`), so it can be removed/hidden without disturbing the rest of
Swap. `swap_requests.batch_id` is otherwise unused once mapping is removed.

### 3.4 Borrow
**Does not exist in any form.** No model, schema, repository, service, API
router, web router, or template references "borrow" anywhere in the
codebase. This is a net-new aggregate.

---

## 4. Current Approval Model

Two independent approval workflows exist today, **neither** matches the
configurable, hierarchy-based routing the new rules require:

1. **User registration approval** (`UserService.process_approval`,
   `_scope_role_names`): a `LEAD` may approve a `PENDING` user only if
   `user.group_id == acting_user.group_id` (flat equality, single level, no
   hierarchy); `MANAGER`/`OWNER` approve globally. This is scoped by *role
   permission* (`user:approve`, held by LEAD/MANAGER/OWNER) plus this one
   record-level check. Out of scope for the new rules (registration approval
   is untouched by the business rules given), but it is the only existing
   precedent for "record-level approval scoping layered on top of a role
   permission," and its pattern (a small resolver function consulted by the
   service) is the right shape to reuse for Swap/Borrow.

2. **Swap approval** (`SwapService.approve`/`reject`): gated only by the
   flat `swap:approve` permission (any LEAD/MANAGER/OWNER, anywhere) — **no
   group/hierarchy scoping at all**. This does not implement "Lead Approval"
   in the sense the new spec means (a *specific* lead or chain of leads tied
   to the requesting group), and does not implement the multi-level,
   configurable hierarchy shown in the Swap/Borrow examples.

There is currently **no data structure anywhere that represents a
lead/manager hierarchy or an approver graph**. `Group` is flat (no parent,
no designated lead/manager reference beyond "a User with role LEAD whose
`group_id` happens to equal this group's id"). This is the single largest
gap relative to the new requirements and is discussed in §7/§9.

---

## 5. Current Database Model

Nine Alembic revisions (`0001`…`0009`), SQLite in dev / Postgres-ready via
`DATABASE_URL`, no dialect-specific SQL anywhere.

Core tables (fields trimmed to what matters for this assessment):

- **`roles`** (id, name) / **`permissions`** (id, code) / **`role_permissions`** (m2m) — RBAC, data-driven, unchanged by prior revisions except `0007`'s role rename (`USER→BOT`, `DEVELOPER→USER`, `DEVELOPER_LEAD→MANAGER`, in place, same row ids, so no FK breakage).
- **`users`** (role_id, **group_id** [single primary group, nullable], status, is_active, approval fields) + **`user_groups`** m2m (`0004`, additive — lets a user belong to *additional* groups without changing what `group_id` means to existing scoped-RBAC code).
- **`groups`** (id, name, description) — **flat**, no parent/child, no explicit lead/manager reference.
- **`products`** (id, name) and **`product_template_columns`** + **`setup_custom_field_values`** (`0003`) — the EAV custom-column system; fully reusable, out of scope for the new rules (business rule 7: keep Product functionality unchanged).
- **`setups`** — one row per hardware setup, product_id, group_id (single owning group, nullable), `owner_id`, identity fields (`ip_address`, `hostname` — unique, immutable-in-practice), and the *swappable* hardware fields directly as columns: `ssd`, `hdd`, `hardware_info`, `capacity`, `form_factor`, `adapter`, `aardvark`, `quarch`, `apc`, `remote_server`, plus `location`, `remarks`, `status`. **These columns hold only the current value — there is no original/baseline row anywhere.**
- **`reservations`** — setup_id, user_id, window, status (`ACTIVE/COMPLETED/CANCELLED/SWAPPED`), `remarks` (Text, `0002` renamed from `purpose` and widened — doubles as free-text swap history, see §3.2).
- **`swap_requests`** — reservation_id, requester_id, current/requested setup ids, `column_name` (comma-separated, widened `0009`), `previous_current_value`/`previous_requested_value` (`0008`, single-snapshot only), status, `batch_id` (`0002`, mapping feature).
- **`announcements`**, **`audit_logs`**, **`export_logs`**, **`excel_transaction_logs`**, **`refresh_tokens`**, **`password_reset_tokens`** — infrastructure/logging, fully reusable as-is.

### Database limitations relative to the new requirements
1. **No Original/Baseline hardware storage** — only one live value per field per setup (§3.2).
2. **No group hierarchy / approver graph** — `groups` has no self-referential or graph edge table; nothing encodes "D and E report to A" or "D has parents A and B" (§4, §9).
3. **No Borrow-related tables at all.**
4. **`Group` is a single-owner model for `setups.group_id`** — the spec says "Hardware/setup resources may be shared across groups"; today a Setup belongs to exactly one Group or none. Borrow's temporary cross-group access transfer has nowhere to live without a new access/grant concept (an "owning group" vs "currently-effective access holder" distinction).
5. **`swap_requests` conflates two behaviors** (§3.2) — reusing this table for the new, narrower "Swap = hardware change on the same setup, no relocation" meaning is possible, but the relocation-specific columns (`requested_setup_id` really meaning "new home setup") and the mapping-only `batch_id` become semantically overloaded if not cleaned up.
6. **No `start_time`/`end_time`/announcement/lead-email columns** on `swap_requests`, and nothing analogous for Borrow yet.

---

## 6. Current Access / RBAC Model

- **General access** (can I *see*/*use* this feature at all): role → permission matrix (`DEFAULT_ROLE_PERMISSIONS`), enforced by `require_permission`/`require_web_permission`. This layer is correct and should stay exactly as-is per business rule 8 ("Approval hierarchy applies ONLY to approval routing, not general access/ownership") — i.e. do **not** fold hierarchy logic into the permission matrix.
- **Record-level access** (can I act on *this* record): today only two instances exist — Reservation cancel (`owner OR reservation:cancel_any`) and User-approval group-scoping. Setup/Group "ownership" is a single FK (`setups.group_id`), not a layered model.
- **Ownership vs Reservation vs Swap-permission vs Borrow-permission vs temporary-borrowed-access** are **not currently distinguished** — the spec's explicit instruction ("Do not use a single 'owner' field to represent all of these concepts") is *already violated* by the current `setups.owner_id` + `setups.group_id` pair being the only access-related fields on Setup. This must be split (§9).

---

## 7. Required Database / API / UI Changes (summary — detailed design is Phase 1)

### Database (additive; no destructive migration)
- `setup_hardware_baseline` (or equivalent immutable snapshot) — one row per
  setup, captured once (at creation / first migration backfill from current
  `setups` values), never updated by the app. Preserves ORIGINAL.
- Keep `setups.<hardware fields>` as CURRENT/EFFECTIVE (already the case) —
  reused, not renamed, to avoid breaking Product/Setup functionality
  (business rule 7).
- A structured **hardware change ledger** (setup_id, field_name, old_value,
  new_value, source [`SWAP`/`BORROW`], source_request_id, actor, timestamp) —
  replaces the free-text remarks-based "history," gives per-field diffing
  for the UI highlight requirement, and is what "only changed cells
  highlighted" reads from.
- **Approval hierarchy** as an explicit, data-driven graph table (edges
  between Groups and/or designated Lead/Manager users — exact shape is an
  open question, see §9) plus a small `ApprovalRoutingService` that walks it.
  No hardcoded org chart in code.
- `swap_requests`: add `reason` (already have it), `start_time`, `end_time`,
  `announcement_channels`, and drop the relocation behavior from the service
  layer (columns can stay for backward read-compatibility with existing
  rows, but `approve()` stops creating/relocating reservations).
- New `borrow_requests` table: requester (lead/manager), source group/lead,
  target setup or specific hardware field(s), status, reason, start/end
  time, announcement channels, approver set snapshot, approved_by,
  returned_at, plus its own audit trail.
- New `access_grant`-style concept (or reuse `borrow_requests` itself as the
  source of truth for "who currently has effective access") so Setup
  ownership (`group_id`) — the ORIGINAL owning group — is never overwritten
  by a Borrow; effective access is computed/derived, not destructively
  written over `setups.group_id`.
- Migration risk mitigation: every new table is additive; no existing column
  is dropped or renamed. `swap_mapping`-only columns/rows are simply no
  longer written by new code but remain queryable for historical audit.

### API
- New `POST/GET /api/v1/borrows`, `PATCH /api/v1/borrows/{id}/approve|reject`,
  `POST /api/v1/borrows/{id}/return`.
- `swaps` endpoints keep their shape but the request/response schema and
  service semantics change (no relocation; new fields per business rule 2).
- Remove or explicitly deprecate `POST /swaps/mapping` and
  `PATCH /swaps/mapping/{batch_id}/approve` (business rule 6).
- New read endpoint(s) for the approval-hierarchy configuration (admin-only,
  `group:manage`-gated) so it is data-editable, not hardcoded.

### UI
- Reserve/Swap/Borrow become three visibly distinct actions/dialogs (today
  only Reserve/Swap/Unreserve exist as buttons; the Swap dialog's own copy
  already misdescribes what happens).
- Cell-level "changed" highlighting on the Setup Table: needs a way to know,
  per visible cell, whether `current != baseline` — driven by the new
  baseline table/ledger, rendered as a CSS class per `<td>` (today
  `styles.css` has no such class at all — this is wholly new work, not a
  tweak).
- "Return Borrowed Resource" action + Borrowed-status/source-group/
  borrowing-group indicators on the table.
- Swap-mapping screen (`/admin/swap-mapping`) removed from navigation (business rule 6).

---

## 8. Migration Risks

| Risk | Mitigation |
|---|---|
| Existing `swap_requests` rows represent relocations under the old semantics; new code reads Swap as "no relocation." | Keep old rows as historical/read-only (already-completed swaps stay `COMPLETED` with their existing relocation history intact); only *new* swap requests follow the new no-relocation rule. Do not rewrite history. |
| `Reservation.remarks` currently carries swap history as free text that other features (Setup Table "Remarks" column) render directly. | Leave existing remarks text alone; new hardware-change ledger is additive and does not require removing the old text trail. |
| Removing/hiding swap-mapping could orphan existing `batch_id`-linked rows in reporting/automation that queries by `batch_id`. | Don't drop the column; stop writing new mapping batches; document the column as legacy in the developer guide. |
| A group-hierarchy table is new and initially empty — approval routing has no rows to route through until an admin configures it. | Define an explicit "no hierarchy configured" fallback (e.g. fall back to today's flat `swap:approve`/`group:manage` behavior) rather than silently blocking all approvals during rollout; call this out for confirmation in Phase 1 (see open question in §9). |
| SQLite lacks portable exclusion/graph-integrity constraints; a hierarchy graph with cycles is possible if entered carelessly through the future admin UI. | Validate acyclicity in the service layer at edge-creation time (same pattern already used for interval-overlap: application-level validation, not a DB constraint). |
| `setups.owner_id`/`group_id` currently double as informal "access" fields; several existing services/UI read them directly. | Do not repurpose or remove them — introduce the new access/grant concept **alongside** them, and have Borrow computations read the new table first, falling back to `group_id` when no active borrow exists. Preserves all current call sites. |
| Test suite currently asserts today's Swap-relocates-the-reservation behavior (`test_workflow_reserve_swap_verify_history`, `test_swap_request_then_approve`, etc.). | These tests must be updated in Phase 6 to match the new no-relocation Swap semantics; flagged now so it isn't a surprise later. Reservation/RBAC/Import-Export tests are unaffected and must keep passing unmodified. |

---

## 9. Edge Cases to Resolve in Phase 1+

- A setup with **zero** prior swaps: baseline == current trivially; the
  highlight logic must render "nothing changed" cleanly.
- A field swapped **twice**: baseline must still reflect the *original*
  value from setup creation, not the most recent pre-swap value — this is
  exactly why a snapshot-only `previous_*_value` column (today's design) is
  insufficient and a durable baseline table is required.
- Swap requested on a column that a Borrow has already made
  effectively-foreign to the group (ordering between the two independent
  domains touching the same setup concurrently) — needs an explicit
  "does not depend on" rule confirmed, not just asserted by prose.
- Borrow of a **specific hardware field** vs an **entire setup** — the
  prompt explicitly leaves this for Phase 1 investigation/decision; current
  schema has no hook for "borrow just the NVMe, not the whole setup."
- Return of a borrowed resource while the borrower currently has an
  **active Reservation** on it, or a **pending Swap** referencing it —
  return-time state transition must be explicit (documented in Phase 4, not
  assumed here).
- Approval hierarchy with **no path to a Lead** for a given group (orphan
  group) — needs a defined fallback (reject at creation time vs. escalate to
  Owner) rather than an approval request nobody can ever act on.
- Rejecting a Borrow must leave the source group's access, effective
  hardware, and the borrower's permissions completely untouched (mirrors the
  existing, already-correct Swap-reject behavior).

---

## 10. Recommended Target Architecture

No change to the layered architecture itself. Additively:

```
Setup
├── Group ownership (existing: setups.group_id) — ORIGINAL owning group, never overwritten
├── Access Grant / effective-access resolution (NEW) — derived: owning group unless an active Borrow says otherwise
├── Reservation (existing aggregate, decoupled from Swap/Borrow state)
├── Hardware Baseline (NEW, immutable snapshot) — ORIGINAL
├── Hardware Effective (existing setups.<field> columns) — CURRENT
├── Hardware Change Ledger (NEW, append-only) — per-field diff history, feeds UI highlighting
├── Swap Transactions (redesigned SwapRequest: hardware-only, no relocation, reason/start/end/announcement/lead-emails)
└── Borrow Transactions (NEW aggregate: request/approve-by-any-one-of-set/return, its own history)
```

Approval routing becomes a **cross-cutting service** consulted by both Swap
and Borrow (`ApprovalRoutingService`, reading the new data-driven hierarchy
graph), not logic embedded in either domain service — keeping Swap and
Borrow themselves independent of each other while sharing one configurable
routing mechanism, per the architectural requirement.

Reservation, Swap, and Borrow become three sibling services operating on
the same `Setup`/`Group` resources, each with its own repository/table,
none importing the others' repositories — mirroring the existing
`ReservationService` / `SwapService` separation, extended to three.

---

## 11. Recommended Implementation Phases

Matches the phase plan already agreed for this engagement:

1. **Phase 0 — Understand** *(this document; complete)*.
2. **Phase 1 — Data Model**: hardware baseline + ledger, approval-hierarchy
   graph table(s) + `ApprovalRoutingService`, redesigned `swap_requests`
   schema fields, new `borrow_requests` schema, access-grant concept.
   Alembic migrations, additive only.
3. **Phase 2 — Reservation**: remove the Swap-pending coupling in
   `ReservationService.cancel`; otherwise validate existing behavior against
   the "independent of Swap/Borrow" rule and keep it.
4. **Phase 3 — Swap**: rebuild `SwapService` around hardware-only change +
   hierarchy-routed approval + baseline/ledger updates; retire the
   swap-mapping code path.
5. **Phase 4 — Borrow**: new service end-to-end, including Return + its
   announcement/email/audit requirements.
6. **Phase 5 — Frontend**: three distinct dialogs, cell highlighting,
   Borrow status indicators, remove swap-mapping screen from nav.
7. **Phase 6 — Validation**: update the swap-relocation-specific tests,
   add Borrow/hierarchy tests, leave Reservation/RBAC/Import-Export tests
   untouched and passing.

---

## Phase 1 Assumptions Adopted

You said "continue" rather than answering the open questions below, so
Phase 1 proceeded on the following documented, reversible assumptions
(schema only — none of these are baked into service logic yet, so a
different answer later mainly changes Phase 3/4 routing logic, not the
tables):

1. **Hierarchy node type → Groups.** `group_hierarchy_edges` connects
   `Group` rows. A Group's Lead/Manager is still resolved from existing
   `User` data (role + `group_id`), not a new column — keeps "who is a
   Group's lead" changeable via ordinary user management.
2. **Graph shape → DAG.** Modeled as directed edges
   (`parent_group_id, child_group_id`), not a single `parent_group_id`
   column, specifically because your Borrow example has `D` under two
   parents (`A` and `B`). This supports both a tree-shaped and a
   multi-parent hierarchy without a schema change either way.
3. **Routing rule → deferred to Phase 3/4 as a configurable traversal**,
   not hardcoded into the schema. The edge table is generic enough to
   support either "full ancestor closure" (Swap example) or "target +
   siblings + parent" (Borrow example) — the exact rule becomes a small,
   named function in `ApprovalRoutingService` that can be swapped without
   another migration.
4. **Swap approval semantics → assumed OR (any one qualifying approver),
   same as Borrow's explicit "ANY ONE approval is sufficient."** Not yet
   enforced anywhere (no approval service exists yet); flagged here so it
   is a visible assumption, not a silent one, when Phase 3 implements it.
5. **Borrow granularity → both, at the schema level.**
   `BorrowRequest.hardware_field_name` is nullable: `NULL` = whole-setup
   borrow, a field name = single-hardware-field borrow. Which of the two
   (or both) the UI actually exposes is a Phase 4/5 decision, not a Phase 1
   one.
6. **Fallback before a hierarchy is configured → left for Phase 3/4.** No
   schema decision was needed for this one; noted again there.

If any of these assumptions is wrong, only the traversal logic in
`ApprovalRoutingService` (not yet written) and possibly which columns a
future UI exposes need to change — the tables added in Phase 1 accommodate
either answer.

## Open Questions (materially affect Phase 1 design — need your decision before Phase 1 starts)

1. **Hierarchy node type**: do the letters in your Swap/Borrow examples
   (A, D, E, J, K…) represent **Groups** (with one-or-more designated Lead
   users each) or **individual Lead/Manager users** directly? This decides
   whether the new table is a Group-hierarchy or a User-reports-to graph.
2. **Graph shape**: your Swap example (`A → D,E → J,K,L,M,N,O`) reads as a
   tree, but your Borrow example (`A → D,E; B → D,F,G`) has **D under two
   parents (A and B)** — i.e. a DAG, not a tree. Should the hierarchy be
   modeled uniformly as a DAG (a node can have multiple parents) for both
   Swap and Borrow routing, or are the two hierarchies genuinely different
   shapes?
3. **Routing rule**: for Swap, `J`'s approval routes to `D,E,A` — the full
   ancestor chain. For Borrow, `E` requesting from `d` routes to `b,d,f,g` —
   `d` itself, `d`'s siblings, and `d`'s parent. Please confirm whether
   Swap routing = "all ancestors of the requester's group" and Borrow
   routing = "the target lead + that lead's siblings + that lead's parent,"
   or state the general rule you want encoded so it isn't hardcoded per
   example.
4. **Approval semantics for Swap**: Borrow is explicit — "ANY ONE approval
   is sufficient." Is Swap approval also OR-semantics (first responder in
   the routed set wins), or does Swap require a different rule (e.g. the
   single direct Lead only, escalating only if unresolved)?
5. **Borrow granularity**: should the system support (a) whole-setup
   borrowing, (b) specific-hardware-field borrowing, or (c) both, as
   selectable at request time? This changes the `borrow_requests` schema
   shape materially (setup-level FK vs field-level FK-or-name).
6. **Fallback behavior** before any hierarchy is configured: should
   Swap/Borrow approval fall back to today's flat `swap:approve` permission
   (any Lead+) until an admin populates the hierarchy, or should
   creation be blocked entirely until a route exists for that group?

I have proceeded only as far as Phase 0 allows without guessing these
answers, per your instruction not to assume ambiguous business rules where
the ambiguity would materially change behavior.
