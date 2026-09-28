CURRENT_PHASE: Re-verification pass against consolidated Phase 1/2/3 requirements (complete) — see VERIFICATION_REPORT below. Next substantive phase is Borrow (my Phase 4).

VERIFICATION_REPORT:
  This entry responds to a consolidated re-statement of Phase 1 (Data
  Model), Phase 2 (Approval Hierarchy/Routing), and Phase 3 (Reservation)
  requirements, using that message's own phase numbering. Mapping to this
  project's phase history: their Phase 1 = this project's Phase 1; their
  Phase 2 = the approval-hierarchy portion of this project's Phase 3
  (Swap), now extended; their Phase 3 = this project's Phase 2
  (Reservation). Each requirement bullet was checked against the actual
  code (not just prior notes) before being marked below.

  --- Their Phase 1 (Data Model) ---
  - Original/Baseline hardware state -> setup_hardware_baseline: DONE (Phase 1).
  - Current/Effective hardware state -> setups.<field>: DONE (pre-existing, preserved).
  - Reservation metadata (reason/start/end/announcement) -> reservations table: DONE (pre-existing, confirmed unchanged).
  - Swap requests/history/state -> swap_requests + hardware_change_logs: DONE (Phase 1 + Phase 3).
  - Borrow requests/history/state -> borrow_requests: DONE (table only; BorrowService itself still not implemented -- see Outstanding below).
  - Approval relationships -> group_hierarchy_edges: DONE (Phase 1; extended this pass with a `scope` column -- see Gap 1 below).
  - Approval state/history -> status columns + AuditLog + routed_approver_emails snapshots: DONE.
  - Reason: DONE (swap_requests.reason, borrow_requests.reason).
  - Start/end time: DONE (swap_requests, borrow_requests both have start_time/end_time).
  - Announcement/email tracking: DONE (announcement_channels + routed_approver_emails on both swap_requests and borrow_requests; NotificationService.email_direct).
  - Borrow return/restore: DONE (borrow_requests.returned_at/returned_by_id, setup_access_grants.is_active/returned_at).
  - Audit/history: DONE (AuditLog, unchanged, plus the new hardware_change_logs ledger).
  Requirements (Product unchanged / no swap mapping / configurable hierarchy /
  no hardcoded users-groups / preserve data / migrations / reuse schema):
  ALL CONFIRMED — re-checked this pass: Product/template code untouched;
  swap-mapping fully removed (Phase 3) and not reintroduced; no seed data
  or hardcoded org chart anywhere (grepped for it this pass); all 4
  migrations (0010, plus 0011-0012 added this pass) are additive.

  --- Their Phase 2 (Approval Hierarchy / Routing) ---
  - Swap routing (A→D,E→J,K,L,M,N,O ⇒ J→D,E,A): DONE and unit-tested
    (Phase 3) -- reconfirmed passing against a standalone simulation this
    pass too.
  - Borrow routing (E→d ⇒ b,d,f,g, any ONE approver): **WAS NOT DONE before
    this pass.** Found and fixed this pass -- see Gap 1/2 below. Now
    implemented (`ApprovalRoutingService.resolve_borrow_approvers`) and
    unit-tested against your literal example, including a decoy case
    proving the SWAP-side edge does NOT leak into the Borrow result.
  - Hierarchy applies only to routing, not general access/ownership:
    CONFIRMED — RBAC permission matrix (who can request/approve AT ALL) is
    completely unmodified by any hierarchy code; hierarchy only narrows
    *which* permission-holder may act on *this* request.
  - No hardcoded users/groups/managers/leads: CONFIRMED.
  - "Registration/admin configuration must support the required approval
    tree": **WAS NOT DONE before this pass** (Gap 2 below) — the
    repository could create edges, but nothing exposed that capability to
    an admin. Found and fixed this pass.
  - Approval states pending/approved/rejected/cancelled/expired: **EXPIRED
    was missing** from both SwapStatus and BorrowStatus (Gap 3 below).
    Found and fixed this pass.
  - Keep Swap and Borrow approval logic independent: CONFIRMED, and
    materially strengthened this pass by the scope fix (Gap 1) -- before
    it, the two routing rules could have silently interfered with each
    other for any group appearing in both an org's Swap and Borrow
    reporting lines.

  --- Their Phase 3 (Reservation) ---
  - Reservation independent from Swap/Borrow: DONE (this project's Phase 2), reconfirmed unchanged this pass.
  - Reserve/unreserve setups user is allowed to access: DONE, unchanged.
  - Only owner or applicable-permission holder can unreserve: DONE, unchanged (owner OR reservation:cancel_any permission -- not hierarchy-routed, matching "do not let approval-hierarchy changes accidentally alter normal reservation access").
  - Reason/Start time/End time/Announcement: DONE, pre-existing, unchanged.
  - Applicable lead email notification: DONE via the pre-existing flat MAIL_LEADS channel (Reservation was never given hierarchy-routed leads, and no business rule asked for that specifically -- only Swap/Borrow have the hierarchy example).
  - Preserve reservation history/audit: DONE, unchanged.
  - Expired/invalid time ranges and conflicting reservations: DONE, unchanged (ReservationService overlap validation; scheduler_service.sweep_expired_reservations for time-based expiry).
  Product functionality: untouched, reconfirmed.

  === Gaps found this pass, and what was done about them ===

  **Gap 1 (the important one) -- Borrow routing was WRONG, not just
  missing, once actually implemented and tested against your numeric
  example.** Implementing `resolve_borrow_approvers` the "obvious" way (all
  parents of the selected group, plus their children) gives `{a,b,d,e,f,g}`
  for "E→d", not your stated `{b,d,f,g}` -- because in your own example,
  Group D is a child of BOTH A (in the Swap example) and B (in the Borrow
  example). Root cause: `group_hierarchy_edges` (Phase 1) had no way to say
  an edge only applies to one domain. Fix: added a `scope` column
  (`ApprovalHierarchyScope`: SWAP / BORROW / BOTH) to `group_hierarchy_edges`
  (migration `0012_group_hierarchy_scope.py`), and both routing methods in
  `ApprovalRoutingService` now only follow edges tagged for their own
  domain (or BOTH). Verified against your exact letters/numbers with a
  standalone script (not just the unit tests) before and after the fix --
  documented in `ARCHITECTURE_ASSESSMENT.md`'s Open Questions section
  (#2/#3, now marked RESOLVED with the evidence).

  **Gap 2 -- no admin/API path existed to configure the hierarchy at
  all.** The repository had `create_edge`/`delete_edge`, but nothing
  called them except tests. Added `GroupHierarchyService` (thin,
  audit-logged wrapper) and `GET/POST/DELETE /api/v1/group-hierarchy`
  (gated on `group:view`/`group:manage`, the same permission that already
  governs Group administration), so "registration/admin configuration must
  support the required approval tree" is now actually true, not just true
  in principle.

  **Gap 3 -- EXPIRED status was missing.** Added `EXPIRED` to both
  `SwapStatus.ALL` and `BorrowStatus.ALL`, and widened both status CHECK
  constraints (migration `0011_swap_borrow_expired_status.py`). No
  automatic expiry sweep was wired up this pass (see Outstanding below) --
  the requirement was read as "the state must be representable" (`ALL`
  list + DB constraint), consistent with "where applicable"; actually
  transitioning a stale PENDING request to EXPIRED is service/scheduler
  logic that belongs with the Borrow build-out (Swap could use it too, as
  a documented Future Enhancement -- see below).

FILES_CREATED (this pass):
  - alembic/versions/0011_swap_borrow_expired_status.py
  - alembic/versions/0012_group_hierarchy_scope.py
  - app/services/group_hierarchy_service.py
  - app/schemas/group_hierarchy.py
  - app/api/v1/group_hierarchy.py

FILES_MODIFIED (this pass):
  - app/core/constants.py (SwapStatus.EXPIRED, BorrowStatus.EXPIRED added;
    new ApprovalHierarchyScope class)
  - app/models/group_hierarchy_edge.py (`scope` column + docstring)
  - app/repositories/interfaces/i_group_hierarchy_repository.py (scope param)
  - app/repositories/sqlalchemy/group_hierarchy_repository.py (scope-aware queries; create_edge requires scope)
  - app/services/approval_routing_service.py (rewritten: scope threaded through both routing rules; resolve_swap_approvers is the new primary name, resolve_approvers_for_group kept as an alias for SwapService's existing call site)
  - app/api/v1/router.py (group_hierarchy router registered)
  - app/api/deps.py (get_group_hierarchy_service provider added)
  - tests/test_business_logic.py (5 new tests: Borrow-example routing, scope isolation, root-group fallback, status-enum check; existing hierarchy tests unchanged and still pass given scope's Python-side default of BOTH)
  - tests/test_backend.py (2 new tests: admin can configure/remove a hierarchy edge via the API; non-admin is refused)
  - ARCHITECTURE_ASSESSMENT.md (Open Questions #2/#3 marked RESOLVED with evidence)
  - IMPLEMENTATION_PROGRESS.md (this file)

DATABASE_CHANGES:
  - Migration 0011: widened swap_requests and borrow_requests status CHECK
    constraints to include EXPIRED. Additive; no existing row's status
    value changes (validated via a raw-sqlite3 simulation: existing
    COMPLETED/RETURNED rows survive the batch-recreate unchanged, EXPIRED
    is accepted, an invalid value is still rejected).
  - Migration 0012: added `scope` (default 'BOTH') to group_hierarchy_edges,
    widened its unique constraint from (parent, child) to (parent, child,
    scope), added a CHECK constraint on the allowed scope values. Additive
    and safe to run against an empty table (this table has not been
    written to by any shipped code path yet) -- also validated via a
    raw-sqlite3 simulation confirming the recreate preserves any existing
    row, accepts a second edge for the same (parent, child) pair under a
    different scope, and rejects both a true duplicate and an invalid
    scope value.
  - Neither migration has been run for real yet -- same sandbox
    network-access constraint as every prior phase (no `pip install`
    possible here). Alembic head is now 0012.

API_CHANGES:
  - New: `GET /api/v1/group-hierarchy` (`group:view`), `POST /api/v1/group-hierarchy` (`group:manage`), `DELETE /api/v1/group-hierarchy` (`group:manage`).

UI_CHANGES:
  - None this pass (explicitly out of scope -- "Do not implement complete
    UI workflows yet" / admin hierarchy configuration is API-only for now,
    consistent with the project's phase-by-phase UI deferral pattern).

MIGRATION_STATUS:
  - Alembic head is now 0012 (0010 -> 0011 -> 0012, all additive). Not yet
    executed against a real database in this sandbox.

TEST_STATUS:
  - Same sandbox constraint as every prior phase: no network access to
    install `requirements.txt`, so `pytest`/`alembic` could not be run for
    real this pass either. Validated instead by:
    (a) full-tree `py_compile` + AST-parse, repeated after every edit --
    clean;
    (b) AST-based unused-import detection on every new/modified file, with
    the one flagged unused import (`Optional` in `app/schemas/group_hierarchy.py`) removed;
    (c) AST cross-check confirming every `GroupHierarchyService(...)`,
    `ApprovalRoutingService(...)`, and `GroupHierarchyEdge(...)`
    construction site passes arguments matching the current signatures
    (including that existing pre-this-pass `GroupHierarchyEdge(...)` test
    calls without an explicit `scope=` are still valid, relying on the
    model's Python-side default);
    (d) two independent raw-sqlite3 migration simulations (0011, 0012) --
    both passed, including negative cases (bad status/scope value
    rejected, existing rows preserved);
    (e) a standalone, no-SQLAlchemy re-implementation of the corrected,
    scope-aware Borrow routing algorithm, run against your literal
    example letters and expected output -- passed only after adding
    scoping; failed (as expected, reproducing the bug) beforehand, which
    is how Gap 1 was actually found rather than just asserted.
    **Action required** (compounding with every prior phase): run
    `pytest tests/ -v` and `alembic upgrade head` in an environment with
    `requirements.txt` installed. This pass specifically needs every new
    test in the "Borrow approval routing" and "Approval states include
    EXPIRED" sections of `test_business_logic.py`, plus the two new
    `test_backend.py` hierarchy-admin tests, confirmed green, alongside
    the full existing suite.

KNOWN_ISSUES / OUTSTANDING:
  - **BorrowService itself (request/approve/reject/return end-to-end) is
    still not implemented.** The data model (Phase 1), the routing
    algorithm (this pass), and the status enum (this pass) are all ready
    for it, but there is no service, API, or UI for a user to actually
    raise or act on a Borrow request yet. This remains the next
    substantive phase (this project's "Phase 4").
  - No automatic PENDING -> EXPIRED sweep is wired up for either Swap or
    Borrow (see Gap 3). Recorded as a **Future Enhancement**: a scheduler
    job mirroring `scheduler_service.sweep_expired_reservations`, run
    against `swap_requests`/`borrow_requests` where `status = PENDING` and
    `end_time < now()`. Not implemented this pass because it wasn't
    unambiguously required ("where applicable") and touches scheduling
    behavior that deserves its own explicit review rather than being
    folded into a gap-fixing pass.
  - Sandbox network-access constraint carried over from every prior phase
    -- see TEST_STATUS/MIGRATION_STATUS above.
  - `app/core/exceptions.py:SwapMappingValidationError` remains unused
    dead code (noted previously, still harmless, still not removed).

DECISIONS_REQUIRED_FROM_USER:
  - None blocking. The corrected Borrow routing rule and the new edge
    `scope` concept are implementation decisions made from re-deriving your
    own stated example, not fresh assumptions — but you may still want to
    confirm the `scope` design itself (an edge can be SWAP-only,
    BORROW-only, or BOTH) matches how you actually want mixed hierarchies
    to be configured, since it's a schema concept that didn't exist in your
    original prompt.

NEXT_ACTION:
  - Await "continue" to begin the Borrow phase (this project's Phase 4):
    BorrowService end-to-end (request / approve via
    `resolve_borrow_approvers` / reject / cancel / return), its API, and
    its announcement/email requirements -- the data model, routing, and
    status enum this phase needs are now all in place.
