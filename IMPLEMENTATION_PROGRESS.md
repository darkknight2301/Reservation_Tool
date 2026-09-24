CURRENT_PHASE: Phase 1 — Data Model (complete)

COMPLETED:
- Phase 0 (Understand) — see prior entry / ARCHITECTURE_ASSESSMENT.md.
- Phase 1 (Data Model), built entirely additively on top of Phase 0's
  findings, adopting the 6 documented assumptions in
  ARCHITECTURE_ASSESSMENT.md ("Phase 1 Assumptions Adopted") since no
  explicit answers were given:
  - Added `setup_hardware_baseline` (immutable ORIGINAL hardware snapshot,
    one row per Setup, backfilled from existing `setups` rows by the
    migration).
  - Added `hardware_change_logs` (append-only, per-field CURRENT/EFFECTIVE
    change history — replaces relying on free-text remarks or a single
    "previous value" slot; this is what the future UI cell-highlighting
    feature will query).
  - Added `group_hierarchy_edges` (directed-edge DAG table for a
    configurable/data-driven approval hierarchy — supports a Group having
    more than one parent, per the Borrow routing example).
  - Added `borrow_requests` (new Borrow aggregate: requester, source/target
    group, setup or specific hardware field, reason/start/end/announcement,
    status, routed-approver snapshot, approval/return tracking) and
    `setup_access_grants` (derived "temporary effective access" — never
    overwrites `Setup.group_id`).
  - Widened `swap_requests`' legacy relocation columns
    (`reservation_id`/`current_setup_id`/`requested_setup_id`) to nullable
    and added `setup_id`/`start_time`/`end_time`/`announcement_channels`/
    `routed_approver_emails` for the redesigned, non-relocating Swap that
    Phase 3 will implement. No existing row/column was dropped, renamed, or
    rewritten.
  - Added `borrow:view`/`borrow:request`/`borrow:approve`/`borrow:return`
    permission codes, granted only to LEAD/DEVELOPER_LEAD/OWNER (never
    USER/DEVELOPER) in `DEFAULT_ROLE_PERMISSIONS`, per "Borrow privilege is
    only for Group Leads and their Managers."
  - Added `BorrowStatus` and `HardwareChangeSource` enums to
    `app/core/constants.py`.
- Registered every new model in `app/models/__init__.py` (required for
  Alembic autogenerate / `Base.metadata.create_all` / relationship
  resolution, per the project's own "Common Issues" note).
- Updated `DEVELOPER_GUIDE.md`: RBAC permission matrix now lists the four
  new `borrow:*` codes; Architecture section gained a "Reservation / Swap /
  Borrow redesign (in progress)" note describing exactly what Phase 1
  added and what remains for later phases.
- Added `tests/unit/models/test_phase1_data_model.py` (13 tests) covering:
  baseline capture/independence from current value, baseline uniqueness,
  multi-change ledger history (the specific gap the old single-snapshot
  design had), ledger source CHECK constraint, a Group with two parents
  (DAG shape), hierarchy self-loop + duplicate-edge rejection, Borrow
  round-trip of reason/start/end/announcement, whole-setup vs
  specific-hardware-field Borrow, access-grant derivation without
  overwriting `Setup.group_id`, access-grant uniqueness per Borrow, and
  both new-style and legacy-style `SwapRequest` rows inserting cleanly
  side-by-side.

FILES_CREATED:
- app/models/group_hierarchy_edge.py
- app/models/setup_hardware_baseline.py
- app/models/hardware_change_log.py
- app/models/borrow_request.py
- app/models/setup_access_grant.py
- alembic/versions/0010_borrow_hierarchy_hardware_history.py
- tests/unit/models/__init__.py
- tests/unit/models/test_phase1_data_model.py

FILES_MODIFIED:
- app/core/constants.py (BorrowStatus, HardwareChangeSource enums;
  borrow:* PermissionCode entries; borrow:* grants added to LEAD /
  DEVELOPER_LEAD role permission lists; OWNER already inherits via
  `list(PermissionCode.ALL)`)
- app/models/swap_request.py (legacy relocation columns widened to
  nullable; added setup_id/start_time/end_time/announcement_channels/
  routed_approver_emails; added `setup` relationship; docstring updated
  to explain the legacy-vs-new-style row distinction)
- app/models/group.py (added `parent_edges`/`child_edges` relationships to
  GroupHierarchyEdge)
- app/models/__init__.py (registered the 5 new model classes)
- ARCHITECTURE_ASSESSMENT.md (added "Phase 1 Assumptions Adopted" section
  documenting the 6 assumptions used in lieu of explicit answers)
- IMPLEMENTATION_PROGRESS.md (this file)
- DEVELOPER_GUIDE.md (RBAC table + Architecture section, as above)

DATABASE_CHANGES:
- Alembic revision 0010 (down_revision 0009), entirely additive:
  5 new tables (`setup_hardware_baseline`, `hardware_change_logs`,
  `group_hierarchy_edges`, `borrow_requests`, `setup_access_grants`),
  1 backfill INSERT...SELECT (setup_hardware_baseline from current
  `setups` values), 5 new nullable columns + nullable-widening of 3
  existing columns on `swap_requests` (via `batch_alter_table`, same
  pattern as migrations 0002/0009). No table dropped, no column removed,
  no existing row's data altered.
- Validated by hand against a simulated SQLite schema reproducing the
  state as of migration 0009 (this sandbox has no network access to
  `pip install` the real dependencies, so Alembic itself could not be
  executed) — confirmed: all CREATE TABLE / CHECK constraint / UNIQUE
  constraint / INSERT...SELECT backfill / batch-alter-equivalent
  statements execute without error, existing rows survive unmodified, and
  the two CHECK constraints (hardware-change source, hierarchy self-loop)
  correctly reject bad data. See conversation history for the validation
  script.
  **Still needs to be run for real** (`alembic upgrade head`) in an
  environment with the project's actual dependencies installed before
  merging — recommended as the first step of Phase 2.

API_CHANGES:
- (none — Phase 1 is data-model only, per the approved phase plan)

UI_CHANGES:
- (none — Phase 1 is data-model only)

MIGRATION_STATUS:
- Revision 0010 written and logic-validated (see DATABASE_CHANGES above)
  but not yet executed against a real Alembic/SQLAlchemy environment. Not
  yet applied to any actual database.

TEST_STATUS:
- New tests written (tests/unit/models/test_phase1_data_model.py,
  13 tests) but not executed — this sandbox has no network access to
  install the project's dependencies (fastapi/sqlalchemy/alembic/etc. are
  not available here). All new/modified Python files were verified to
  compile cleanly (`py_compile`) and AST-parse correctly. The DDL these
  models correspond to was independently validated via a raw-sqlite3
  simulation (see DATABASE_CHANGES).
  **Action required**: run `pytest tests/unit/models/test_phase1_data_model.py
  -v` and the full existing suite (`pytest tests/`) in an environment with
  `requirements.txt` installed, to confirm both the new tests pass and no
  existing test regressed. This is the recommended first step of Phase 2.

KNOWN_ISSUES:
- Sandbox has no network access, so `alembic upgrade head` and `pytest`
  could not actually be executed in this session — see MIGRATION_STATUS /
  TEST_STATUS. All validation done here is static (compilation, AST
  parsing) or via a hand-built raw-SQL simulation of the migration's DDL.
- Carried over from Phase 0: `swap_dialog.html` still describes the old
  ("neither reservation is affected" -- but it actually is) behavior; not
  touched in Phase 1 (UI/service changes are Phase 3/5).
- The approval-hierarchy tables (`group_hierarchy_edges`) are empty by
  design until Phase 3/4 ships an admin UI/API to populate them and a
  fallback-behavior decision is made for the interim (see Phase 1
  Assumption 6 / Open Question 6 in ARCHITECTURE_ASSESSMENT.md).

DECISIONS_REQUIRED_FROM_USER:
- None blocking to proceed to Phase 2 (Reservation). The 6 open questions
  from Phase 0 still stand and will matter more concretely once Phase 3/4
  (Swap/Borrow service logic + approval routing) begins — you can keep
  deferring them, or confirm/correct the assumptions adopted above at any
  point before then.
- Recommend running the real migration + full test suite (see
  MIGRATION_STATUS/TEST_STATUS) in your own environment before Phase 2
  starts, to catch anything this sandbox's dependency-less validation
  couldn't.

NEXT_ACTION:
- Await "continue" to begin Phase 2 — Reservation: remove the
  Swap-pending coupling in `ReservationService.cancel` (see
  ARCHITECTURE_ASSESSMENT.md section 3.1) and validate the rest of
  Reservation's existing behavior against the "independent of Swap/Borrow"
  rule, per the approved phase plan. Do not start Phase 3 until Phase 2 is
  reported complete and approved.
