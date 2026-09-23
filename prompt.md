You are working on an existing Reservation Tool. I will provide the previous working code as a ZIP along with its existing documentation.

Do NOT start coding immediately.

First inspect the complete ZIP, documentation, database/schema, frontend, backend, business logic, RBAC and existing tests.

The goal is to evolve the existing tool according to the new requirements below while preserving useful existing functionality.

Let your reasoning determine the best architecture, database model and implementation approach. Do not blindly follow the old design.

## Core domain

A setup generally contains:

* 1 IP
* 2 or more HDDs
* 1 or more NVMe SSDs
* Other peripherals/hardware

Setups belong to groups.

Hardware/setup resources may be shared across groups based on project requirements.

There are now three independent concepts:

1. Reservation — who can use a setup
2. Swap — hardware configuration change
3. Borrow — temporary transfer of setup/hardware access across groups

These must NOT be tightly coupled unless required by the business rules below.

## Important data principle

Maintain two views of hardware information:

1. ORIGINAL / BASELINE

   * What the setup originally contains.
   * Must remain unchanged as the reference state.

2. CURRENT / EFFECTIVE

   * What hardware is currently assigned after approved swaps/borrows.
   * Must be updated through controlled transactions.

Every change must be traceable back to the original state.

Do not destroy original hardware information.

## 1. RESERVATION

Reservation is independent of Swap and Borrow.

Rules:

* A user can reserve only setups accessible to their group/lead.
* Reservation privilege depends on group/setup access.
* Only the reserving user or their lead can unreserve the setup.
* Reservation does not grant hardware ownership.
* Reservation does not automatically approve Swap or Borrow.
* Swap must not depend on whether the setup is reserved.
* Borrow must not depend on the reservation mechanism except where access must be transferred according to the Borrow rules.

Preserve appropriate existing reservation behavior where it is still valid.

## 2. SWAP

Swap is a hardware configuration change.

Workflow:

User
→ Select accessible setup
→ Specify required hardware changes
→ Submit Swap Request
→ Lead Approval
→ Apply approved hardware change
→ Update CURRENT/EFFECTIVE hardware
→ Preserve ORIGINAL hardware
→ Maintain complete transaction/history

Rules:

* Swap does not depend on Reservation.
* Only members with access to the relevant setup/group can raise a Swap request.
* Swap requires the appropriate lead approval.
* After approval, the effective hardware information must be visible to the all user. (keep color code to update in UI Table)
* Original hardware information must remain available.
* Multiple hardware changes must be supported where the existing design permits.
* Rejecting a swap must not modify effective hardware.
* Approval/rejection must be auditable.

## 3. BORROW

Borrow is different from Swap.

Borrow privilege is only for:

* Group Leads
* Their Managers, where supported by the existing role model

Scenario:

A lead/manager does not have the required setup or specific hardware.

They:

1. Review available setups/hardware.
2. Select required resource.
3. Raise Borrow request to another group lead/manager.
4. Source group approves/rejects.
5. If approved:

   * Required setup/hardware access is transferred to borrower.
   * Appropriate reservation/swap privileges move from the source group's members to the borrower according to the business rules.
   * Effective hardware/access information is updated.
   * Original hardware information remains preserved.
   * Full transaction history is maintained.
   * Borrower receives access required to use the resource.

Do NOT assume that borrowing means physically moving hardware. Determine from the existing model whether the system should represent:

* whole setup borrowing
* specific hardware borrowing
* both

and design accordingly.

## RETURN BORROWED RESOURCE

There must be one clear action for the borrowing lead/manager to return borrowed resources.

Example:

"Return Borrowed Setup"

When returned:

* Access goes back to the source group.
* Current/effective state is restored appropriately.
* Borrow history remains.
* Original state remains untouched.
* Relevant users lose access according to the business rules.
* Announcement is generated.
* Email notification is generated.
* Audit trail is maintained.

Determine the safest state-transition model from the existing architecture.

## ACCESS MODEL

The system must distinguish:

* Group ownership/access
* User access
* Reservation
* Swap permission
* Borrow permission
* Temporary borrowed access

Do not use a single "owner" field to represent all of these concepts.

Design an explicit access model if required.

## IMPORTANT ARCHITECTURAL REQUIREMENT

Avoid making Reservation, Swap and Borrow dependent on each other.

Think of them as separate state/transaction domains operating on shared setup/hardware resources.

For example:

Setup
├── Group Access
├── Reservation State
├── Effective Hardware State
├── Original Hardware State
├── Swap Transactions
└── Borrow Transactions

Choose the actual implementation structure based on the existing codebase.

## DEVELOPMENT APPROACH

Work in phases.

### Phase 0 — Understand

Do NOT modify code.

Inspect:

* ZIP
* Existing documentation
* Database/schema
* Models
* APIs
* Frontend
* RBAC
* Reservation workflow
* Existing Swap workflow
* Existing approval workflow
* Excel import/export
* Logs/audit
* Tests

Produce a concise:

ARCHITECTURE_ASSESSMENT.md

Include:

* Current architecture
* Existing reusable components
* Current reservation model
* Current swap model
* Current approval model
* Current group/access model
* Current database limitations
* Required architectural changes
* Data migration risks
* Recommended target architecture

Do not implement Phase 1 until this assessment is complete.

### Phase 1 — Data Model

Redesign only the required data structures.

Support:

* Original hardware
* Current/effective hardware
* Group access
* User access
* Reservation
* Swap request/state/history
* Borrow request/state/history
* Approval
* Return/restore
* Audit trail

Preserve existing data through migration.

Do not delete original information.

### Phase 2 — Reservation

Implement/adjust only Reservation.

Validate:

* Group access
* User access
* Lead access
* Reserve
* Unreserve
* Permission boundaries

Ensure Reservation is independent of Swap/Borrow.

### Phase 3 — Swap

Implement/adjust:

* Swap request
* Hardware change definition
* Approval
* Approval/rejection
* Effective hardware update
* Original hardware preservation
* History/audit
* User visibility

Ensure Swap is independent of Reservation.

### Phase 4 — Borrow

Implement:

* Lead/manager-only Borrow
* Resource discovery
* Borrow request
* Source-group approval
* Setup/hardware access transfer
* Effective hardware update
* Reservation/Swap access transfer where required
* History/audit
* Return action
* Announcement
* Email

### Phase 5 — Frontend

Update the UI to clearly separate:

* Reserve
* Swap
* Borrow
* Return Borrowed Resource

Do not overload one workflow with another.

Show:

* Current state
* Original state where useful
* Pending approval
* Borrowed status
* Source group
* Borrowing group
* Hardware changes
* Reservation status

Use the existing UI style.

### Phase 6 — Validation

Use the existing test framework and documentation.

Test the important state transitions and permission boundaries.

Do not rewrite unrelated tests.

Update tests only where the new business model genuinely requires it.

## THINKING RULE

You are responsible for determining:

* Best database structure
* State transitions
* API design
* UI workflow
* Migration strategy
* Permission model
* Approval model
* Handling of conflicting operations
* Edge cases

Do not ask me to design these unless the existing code contains an ambiguity that cannot safely be resolved.

Prefer the smallest maintainable change to the existing architecture.

## CONTEXT / TOKEN SAFETY

This is a large change.

Never redo completed work.

Maintain:

IMPLEMENTATION_PROGRESS.md

After every completed phase update it with:

CURRENT_PHASE:
COMPLETED:
FILES_CREATED:
FILES_MODIFIED:
DATABASE_CHANGES:
API_CHANGES:
UI_CHANGES:
MIGRATION_STATUS:
TEST_STATUS:
KNOWN_ISSUES:
NEXT_ACTION:

If context/output is close to the limit:

1. Finish the current atomic change.
2. Save all files.
3. Update IMPLEMENTATION_PROGRESS.md.
4. Do not start another phase.
5. Respond exactly:

CHECKPOINT SAVED — enter `continue` to resume.

When I enter `continue`:

* Read IMPLEMENTATION_PROGRESS.md.
* Inspect the current repository state.
* Resume from NEXT_ACTION.
* Do NOT repeat completed work.
* Do NOT regenerate completed files.
* Do NOT redo analysis already recorded.
* Continue from the exact checkpoint.

## IMPORTANT

Do not implement everything in one response.

Start ONLY with Phase 0 — understand and assess the existing system.

After Phase 0 is complete, stop and wait for:

continue

Do not modify application code during Phase 0.

-----------

continue

Proceed with Phase 1 — Data Model.

Use ARCHITECTURE_ASSESSMENT.md and the existing code as the source of truth.

Implement only the required data-model/migration changes.

Preserve all existing data.

Do not start Phase 2.

Update IMPLEMENTATION_PROGRESS.md when complete.

----------

continue

Proceed with Phase 2 — Reservation.

Implement and validate the new Reservation rules using the architecture established in Phase 0/1.

Keep Reservation independent of Swap and Borrow.

Do not start Phase 3.

Update IMPLEMENTATION_PROGRESS.md.

-----------

continue

Proceed with Phase 3 — Swap.

Implement the complete Swap request → approval → effective hardware update → history flow.

Keep Swap independent of Reservation and Borrow.

Preserve ORIGINAL hardware and update CURRENT/EFFECTIVE hardware only through approved transactions.

Do not start Phase 4.

Update IMPLEMENTATION_PROGRESS.md.


----------

continue

Proceed with Phase 4 — Borrow.

Implement the Lead/Manager Borrow workflow, source-group approval, temporary access transfer, effective hardware state, history and Return Borrowed Resource workflow including announcement/email.

Do not start Phase 5.

Update IMPLEMENTATION_PROGRESS.md.

----------

continue

Proceed with Phase 5 — Frontend.

Update the UI to clearly separate Reservation, Swap, Borrow and Return Borrowed Resource workflows.

Follow the existing UI design and RBAC.

Do not start Phase 6.

Update IMPLEMENTATION_PROGRESS.md.


---------

continue

Proceed with Phase 6 — Validation.

Run the existing test suite and validate the major business workflows and permission boundaries.

Fix production-code issues found during validation where appropriate.

Do not redesign unrelated functionality.

Update IMPLEMENTATION_PROGRESS.md with the final status and remaining issues.

--------