# Manual Web UI Test Plan

Use this plan to verify the application through the browser. **Pass/Fail** boxes are left empty for the tester (mark `Pass` or `Fail`). Automated tests are run with `pytest tests/ -v`; this plan covers what a person must confirm on screen.

## How to use

- Prepare a test database (`alembic upgrade head`, `python -m scripts.create_admin`, optionally `python -m scripts.seed_data`) and create one user per role: BOT, USER, LEAD, MANAGER, OWNER. Use test accounts only.
- Create groups in Group Management and (for routing tests) hierarchy edges through `POST /api/v1/group-hierarchy` (`scope` SWAP, BORROW or BOTH). Example shape: parent group → child groups; leads must hold role LEAD or MANAGER in their group.
- Record the result of each test in the **Pass/Fail** column. Note actual behavior when it differs.

## Test cases


### 1. Login / registration / RBAC

**AUTH-01 — Register a new account**

| Field | Detail |
|---|---|
| Objective | Register a new account |
| Preconditions | None |
| Steps | 1. Open /register. 2. Fill Full name, Username, Email, Password, choose Groups. 3. Click Register. |
| Expected result | Message says approval is required; account is PENDING. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**AUTH-02 — Pending account cannot log in**

| Field | Detail |
|---|---|
| Objective | Pending account cannot log in |
| Preconditions | AUTH-01 done |
| Steps | 1. Open /login. 2. Enter the new credentials. 3. Click Login. |
| Expected result | Login refused: "Your account is pending approval by a Lead or above." |
| Pass/Fail | ☐ Pass  ☐ Fail |

**AUTH-03 — Lead approves a registration**

| Field | Detail |
|---|---|
| Objective | Lead approves a registration |
| Preconditions | A Lead/Manager account; AUTH-01 done |
| Steps | 1. Log in as the Lead. 2. Open the person-check **Approvals** page (Approval Dashboard). 3. Approve the new user. |
| Expected result | User leaves the pending list; the new user can now log in. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**AUTH-04 — Wrong password**

| Field | Detail |
|---|---|
| Objective | Wrong password |
| Preconditions | Existing user |
| Steps | Log in with a wrong password. |
| Expected result | "Invalid username or password."; the failed login appears in Logs (LOGIN_FAILED) for a Manager/Owner. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**AUTH-05 — Disabled account**

| Field | Detail |
|---|---|
| Objective | Disabled account |
| Preconditions | Existing user disabled by a Manager |
| Steps | Log in as the disabled user. |
| Expected result | "Your account is disabled. Contact an administrator." |
| Pass/Fail | ☐ Pass  ☐ Fail |

**AUTH-06 — Forgot password**

| Field | Detail |
|---|---|
| Objective | Forgot password |
| Preconditions | Existing user, SMTP disabled or enabled |
| Steps | 1. Click Forgot password?. 2. Submit the email. 3. Follow the reset link (from email or server log). 4. Set a new password and log in. |
| Expected result | Reset works once; reusing the link fails. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**AUTH-07 — Top-bar items per role**

| Field | Detail |
|---|---|
| Objective | Top-bar items per role |
| Preconditions | One user per role (BOT, USER, LEAD, MANAGER, OWNER) |
| Steps | Log in as each role and read the top bar. |
| Expected result | BOT/USER: Dashboard, Setups, Announcements, Approvals. LEAD adds Swap Approvals, Borrow, user Approvals, Groups, Developer Logs. MANAGER/OWNER add Products, Users, Logs. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**AUTH-08 — Unauthorized page**

| Field | Detail |
|---|---|
| Objective | Unauthorized page |
| Preconditions | BOT or USER account |
| Steps | Open /admin/users directly. |
| Expected result | 403 page; no data shown. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**AUTH-09 — Logout**

| Field | Detail |
|---|---|
| Objective | Logout |
| Preconditions | Logged in |
| Steps | Click Logout, then use the browser Back button and reload a page. |
| Expected result | Redirected to /login; protected pages not accessible. |
| Pass/Fail | ☐ Pass  ☐ Fail |


### 2. Products and templates

**PROD-01 — Create product**

| Field | Detail |
|---|---|
| Objective | Create product |
| Preconditions | Manager/Owner |
| Steps | Products → New Product → Name, Description → Save. |
| Expected result | Product listed; appears on Setups → Select a Product. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**PROD-02 — Design template: add custom column**

| Field | Detail |
|---|---|
| Objective | Design template: add custom column |
| Preconditions | PROD-01 |
| Steps | Open Design Template → Add Custom Column → key, Display Label, Type, Required → Save. |
| Expected result | Column listed; appears in the setups table and Edit Setup → Custom Fields. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**PROD-03 — Dropdown column**

| Field | Detail |
|---|---|
| Objective | Dropdown column |
| Preconditions | PROD-02 |
| Steps | Add a Dropdown column with Allowed Values `A, B`; edit a setup and choose a value. |
| Expected result | Only A/B selectable. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**PROD-04 — Reorder / delete column**

| Field | Detail |
|---|---|
| Objective | Reorder / delete column |
| Preconditions | A column with no data |
| Steps | Move the column up/down; delete an unused column. |
| Expected result | Order changes in the table; delete succeeds. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**PROD-05 — Delete product with setups**

| Field | Detail |
|---|---|
| Objective | Delete product with setups |
| Preconditions | Product with setups |
| Steps | Delete the product. |
| Expected result | Blocked with an error message; nothing deleted. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**PROD-06 — Product selection page**

| Field | Detail |
|---|---|
| Objective | Product selection page |
| Preconditions | Products with setups |
| Steps | Setups → read cards. |
| Expected result | Each card shows totals/availability; View All Setups lists all products. |
| Pass/Fail | ☐ Pass  ☐ Fail |


### 3. Excel import / export

**XLS-01 — Download blank template**

| Field | Detail |
|---|---|
| Objective | Download blank template |
| Preconditions | Manager or Owner |
| Steps | Products → Blank Template. |
| Expected result | An .xlsx downloads with the import headers. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**XLS-02 — Import new setups**

| Field | Detail |
|---|---|
| Objective | Import new setups |
| Preconditions | Valid workbook (ip_address, hostname, location…) |
| Steps | Products → Import Setups → choose file → Upload & Import. |
| Expected result | Created count shown; setups appear; each has an Original (baseline) equal to its imported values. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**XLS-03 — Import with row error**

| Field | Detail |
|---|---|
| Objective | Import with row error |
| Preconditions | Workbook with a duplicate/invalid row |
| Steps | Import it. |
| Expected result | Whole import rejected; errors listed by row; nothing created. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**XLS-04 — Import updates existing setup**

| Field | Detail |
|---|---|
| Objective | Import updates existing setup |
| Preconditions | Setup with same IP/hostname exists |
| Steps | Import a row with a changed SSD. |
| Expected result | Updated count shown; the SSD cell is highlighted as changed (import does not reset Original). |
| Pass/Fail | ☐ Pass  ☐ Fail |

**XLS-05 — New columns detected**

| Field | Detail |
|---|---|
| Objective | New columns detected |
| Preconditions | Product import with an unknown header |
| Steps | Product → Import Excel → upload. |
| Expected result | "New columns detected"; choose Add to Template & Import (columns added, data imported) or Reject Import (nothing imported). |
| Pass/Fail | ☐ Pass  ☐ Fail |

**XLS-06 — Export setups**

| Field | Detail |
|---|---|
| Objective | Export setups |
| Preconditions | USER or above |
| Steps | Setups table → Export (optionally after filtering). |
| Expected result | An .xlsx of the filtered setups downloads. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**XLS-07 — Export product template data**

| Field | Detail |
|---|---|
| Objective | Export product template data |
| Preconditions | Manager/Owner |
| Steps | Design Template → Export. |
| Expected result | Workbook includes custom columns. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**XLS-08 — Import permission**

| Field | Detail |
|---|---|
| Objective | Import permission |
| Preconditions | USER account |
| Steps | Try to open Products/import URLs. |
| Expected result | 403 / no import control. |
| Pass/Fail | ☐ Pass  ☐ Fail |


### 4. Reservation

**RES-01 — Reserve a setup**

| Field | Detail |
|---|---|
| Objective | Reserve a setup |
| Preconditions | AVAILABLE setup, USER+ |
| Steps | Tick the row → Reserve → From, Until, Reason / remarks → submit. |
| Expected result | Status RESERVED; User and Reserved Time filled; Remarks shows the reason. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**RES-02 — Reserve several setups**

| Field | Detail |
|---|---|
| Objective | Reserve several setups |
| Preconditions | Two AVAILABLE setups |
| Steps | Tick both → Reserve → submit. |
| Expected result | Both reserved; result lists any failure. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**RES-03 — Overlap conflict**

| Field | Detail |
|---|---|
| Objective | Overlap conflict |
| Preconditions | RES-01 done (another user) |
| Steps | As another user, try to reserve the same setup for an overlapping time. |
| Expected result | "Setup is already reserved for an overlapping time window." |
| Pass/Fail | ☐ Pass  ☐ Fail |

**RES-04 — Invalid time range**

| Field | Detail |
|---|---|
| Objective | Invalid time range |
| Preconditions | AVAILABLE setup |
| Steps | Set Until earlier than or equal to From. |
| Expected result | Rejected with "reserved_until must be after reserved_from." |
| Pass/Fail | ☐ Pass  ☐ Fail |

**RES-05 — Non-reservable setup**

| Field | Detail |
|---|---|
| Objective | Non-reservable setup |
| Preconditions | Setup in MAINTENANCE/RETIRED |
| Steps | Try to reserve it (via API or table). |
| Expected result | Refused; setup cannot be reserved. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**RES-06 — Reservation announcement**

| Field | Detail |
|---|---|
| Objective | Reservation announcement |
| Preconditions | RES-01 form |
| Steps | Tick Wall Message and Mail Leads with a custom message when reserving. |
| Expected result | A wall announcement appears under Announcements; leads emailed (or logged if SMTP disabled). |
| Pass/Fail | ☐ Pass  ☐ Fail |

**RES-07 — Checkbox rules**

| Field | Detail |
|---|---|
| Objective | Checkbox rules |
| Preconditions | Setup reserved by another user |
| Steps | Look at that row. |
| Expected result | Checkbox disabled for a non-owner. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**RES-08 — Reservation expiry**

| Field | Detail |
|---|---|
| Objective | Reservation expiry |
| Preconditions | Reservation with a near end time, scheduler enabled |
| Steps | Wait past Until + one sweep interval. |
| Expected result | Setup returns to AVAILABLE. |
| Pass/Fail | ☐ Pass  ☐ Fail |


### 5. Unreservation

**UNR-01 — Unreserve own reservation**

| Field | Detail |
|---|---|
| Objective | Unreserve own reservation |
| Preconditions | RES-01 |
| Steps | Tick the row → Unreserve → confirm. |
| Expected result | Status AVAILABLE; audit entry CANCEL. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**UNR-02 — Lead unreserves someone else's**

| Field | Detail |
|---|---|
| Objective | Lead unreserves someone else's |
| Preconditions | Reservation by USER A; log in as Lead |
| Steps | Tick the row → Unreserve. |
| Expected result | Allowed; reservation cancelled. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**UNR-03 — USER cannot unreserve others'**

| Field | Detail |
|---|---|
| Objective | USER cannot unreserve others' |
| Preconditions | Reservation by USER A; log in as USER B |
| Steps | Try to unreserve (checkbox disabled; API PATCH /reservations/{id}/cancel). |
| Expected result | Refused: "You may only cancel your own reservations." |
| Pass/Fail | ☐ Pass  ☐ Fail |

**UNR-04 — Unreserve unaffected by swap/borrow**

| Field | Detail |
|---|---|
| Objective | Unreserve unaffected by swap/borrow |
| Preconditions | Reservation plus a pending swap on that setup |
| Steps | Unreserve. |
| Expected result | Succeeds; no swap warning; the swap request stays unchanged. |
| Pass/Fail | ☐ Pass  ☐ Fail |


### 6. Swap and swap approval

**SWP-01 — Raise a swap without a reservation**

| Field | Detail |
|---|---|
| Objective | Raise a swap without a reservation |
| Preconditions | Two setups in the user's group sharing a column; neither reserved |
| Steps | Tick exactly one setup → Swap → pick partner → select a column → Reason → submit. |
| Expected result | Request created (PENDING); routed leads emailed; appears in Approvals. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**SWP-02 — Swap button rule**

| Field | Detail |
|---|---|
| Objective | Swap button rule |
| Preconditions | Setups table |
| Steps | Tick 0, then 2 rows. |
| Expected result | Swap enabled only with exactly one row ticked. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**SWP-03 — Partner list**

| Field | Detail |
|---|---|
| Objective | Partner list |
| Preconditions | User in group G |
| Steps | Open the Swap dialog. |
| Expected result | Only setups the user can access that share a swappable column are listed; no swap-mapping options exist. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**SWP-04 — Cross-group denied**

| Field | Detail |
|---|---|
| Objective | Cross-group denied |
| Preconditions | Setup of another group |
| Steps | Try to raise a swap (API POST /api/v1/swaps) involving it. |
| Expected result | 403: "You may only request a swap for setups belonging to your group…" |
| Pass/Fail | ☐ Pass  ☐ Fail |

**SWP-05 — Time and announcement fields**

| Field | Detail |
|---|---|
| Objective | Time and announcement fields |
| Preconditions | Swap dialog |
| Steps | Fill Start time, End time, tick Wall Message; submit. |
| Expected result | Times stored; announcement created. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**SWP-06 — Approve swap**

| Field | Detail |
|---|---|
| Objective | Approve swap |
| Preconditions | SWP-01; log in as a routed lead |
| Steps | Approvals → Pending Approvals → Approve. |
| Expected result | Status COMPLETED; the values are exchanged; Original unchanged. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**SWP-07 — Reject swap**

| Field | Detail |
|---|---|
| Objective | Reject swap |
| Preconditions | SWP-01 |
| Steps | Approvals → Reject with a reason. |
| Expected result | Status REJECTED; no values change; no change-history rows. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**SWP-08 — Cancel swap**

| Field | Detail |
|---|---|
| Objective | Cancel swap |
| Preconditions | SWP-01; log in as the requester |
| Steps | Approvals → Cancel my request. |
| Expected result | Status CANCELLED; values unchanged. Another user cannot cancel it. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**SWP-09 — Approval bypass**

| Field | Detail |
|---|---|
| Objective | Approval bypass |
| Preconditions | SWP-01; log in as a Lead outside the routed set (with hierarchy configured) |
| Steps | Try Approve (Approvals page or API). |
| Expected result | No Approve button; API returns 403 "not one of the routed approvers". |
| Pass/Fail | ☐ Pass  ☐ Fail |

**SWP-10 — Expiry**

| Field | Detail |
|---|---|
| Objective | Expiry |
| Preconditions | Pending swap whose requested window has passed |
| Steps | Attempt to approve. |
| Expected result | Refused as no longer valid / EXPIRED. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**SWP-11 — Self approval by Owner/Lead**

| Field | Detail |
|---|---|
| Objective | Self approval by Owner/Lead |
| Preconditions | Requester is a Lead |
| Steps | Lead who is routed approver approves own swap. |
| Expected result | Follows the routing rule for that group (document the observed behavior). |
| Pass/Fail | ☐ Pass  ☐ Fail |


### 7. Required-column validation

**COL-01 — Only common columns selectable**

| Field | Detail |
|---|---|
| Objective | Only common columns selectable |
| Preconditions | Setup X (product 1 with custom column C1) and setup Y (product 2 without C1), both accessible |
| Steps | Open Swap for X, choose Y. |
| Expected result | C1 is greyed out "not on both setups" and cannot be selected; fixed hardware fields remain selectable. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**COL-02 — No common column**

| Field | Detail |
|---|---|
| Objective | No common column |
| Preconditions | Two setups with no swappable column in common |
| Steps | Attempt the swap through the API. |
| Expected result | Error: "These two setups have no swappable columns in common." |
| Pass/Fail | ☐ Pass  ☐ Fail |

**COL-03 — Custom column swap**

| Field | Detail |
|---|---|
| Objective | Custom column swap |
| Preconditions | Two setups whose products both have column C |
| Steps | Swap column C; approve. |
| Expected result | Custom values exchange; change history shows both rows. |
| Pass/Fail | ☐ Pass  ☐ Fail |


### 8. Changed-cell highlighting and Original vs Current

**HL-01 — Single changed cell**

| Field | Detail |
|---|---|
| Objective | Single changed cell |
| Preconditions | Setup with unchanged hardware |
| Steps | Approve a swap of SSD only. |
| Expected result | Only the SSD cell of each setup is highlighted (amber); no other cell. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**HL-02 — Multiple changed cells**

| Field | Detail |
|---|---|
| Objective | Multiple changed cells |
| Preconditions | Setup |
| Steps | Approve a swap of SSD and HDD. |
| Expected result | Both SSD and HDD cells highlighted. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**HL-03 — Custom cell highlight**

| Field | Detail |
|---|---|
| Objective | Custom cell highlight |
| Preconditions | COL-03 |
| Steps | Open the table. |
| Expected result | The custom-column cell is highlighted. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**HL-04 — Original vs Current dialog**

| Field | Detail |
|---|---|
| Objective | Original vs Current dialog |
| Preconditions | HL-01 |
| Steps | Click the columns icon on the row. |
| Expected result | Original shows the first values; Current shows the new; changed count badge; Change history lists SWAP #id. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**HL-05 — Edit Setup re-baselines**

| Field | Detail |
|---|---|
| Objective | Edit Setup re-baselines |
| Preconditions | HL-01 |
| Steps | Managers: Edit Setup, change Quarch, Save. |
| Expected result | Quarch is no longer highlighted; the swapped SSD stays highlighted. |
| Pass/Fail | ☐ Pass  ☐ Fail |


### 9. Borrow, approval, any-one approval and return

**BOR-01 — Borrow menu visibility**

| Field | Detail |
|---|---|
| Objective | Borrow menu visibility |
| Preconditions | USER and Lead accounts |
| Steps | Log in as each. |
| Expected result | USER has no Borrow menu (direct /borrows → 403); Lead has Borrow. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**BOR-02 — Request a borrow**

| Field | Detail |
|---|---|
| Objective | Request a borrow |
| Preconditions | Lead E in group e; group d has a free setup and a lead d |
| Steps | Borrow → New Borrow Request → Source lead d → Setup → Hardware → Reason, Start, End, announcement → submit. |
| Expected result | Card under Pending approval shows Borrower, Source, PENDING and the routed approvers; routed leads emailed. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**BOR-03 — Setup list follows lead**

| Field | Detail |
|---|---|
| Objective | Setup list follows lead |
| Preconditions | BOR-02 dialog |
| Steps | Change Source lead. |
| Expected result | Setup list reloads for that lead's group only. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**BOR-04 — Cannot borrow own group's setup**

| Field | Detail |
|---|---|
| Objective | Cannot borrow own group's setup |
| Preconditions | Setup of the requester's own group |
| Steps | Try via API POST /api/v1/borrows. |
| Expected result | Refused: your group already holds it. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**BOR-05 — End time must be future**

| Field | Detail |
|---|---|
| Objective | End time must be future |
| Preconditions | Dialog |
| Steps | Set End time in the past. |
| Expected result | Rejected. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**BOR-06 — Duplicate borrow**

| Field | Detail |
|---|---|
| Objective | Duplicate borrow |
| Preconditions | BOR-02 pending |
| Steps | Another lead requests the same setup. |
| Expected result | Refused: pending or active borrow exists. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**BOR-07 — Approve borrow**

| Field | Detail |
|---|---|
| Objective | Approve borrow |
| Preconditions | BOR-02; log in as a routed lead |
| Steps | Borrow (or Approvals) → Approve. |
| Expected result | Moves to Currently borrowed; setup shows Borrowed by e in the table and under group e's filter; original owner unchanged. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**BOR-08 — Reject / cancel borrow**

| Field | Detail |
|---|---|
| Objective | Reject / cancel borrow |
| Preconditions | New pending borrow |
| Steps | Reject as routed lead; cancel as requester in another request. |
| Expected result | REJECTED / CANCELLED; no access granted. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**BOR-09 — Any-one approval**

| Field | Detail |
|---|---|
| Objective | Any-one approval |
| Preconditions | Hierarchy b→d,f,g (BORROW) and lead e requests from d |
| Steps | Have each of b, d, f, g approve a separate fresh request (one per run). |
| Expected result | Each single approval is sufficient; leads a and c cannot approve. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**BOR-10 — Requester cannot approve own**

| Field | Detail |
|---|---|
| Objective | Requester cannot approve own |
| Preconditions | Requester is also a routed approver |
| Steps | Try to Approve. |
| Expected result | Refused: cannot approve your own request. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**BOR-11 — Return / Get back**

| Field | Detail |
|---|---|
| Objective | Return / Get back |
| Preconditions | BOR-07 |
| Steps | Click Return / Get back → confirm. |
| Expected result | Status RETURNED; Borrowed by badge gone; owner group's access back; requester and source leads emailed; announcement sent on chosen channels. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**BOR-12 — Who may return**

| Field | Detail |
|---|---|
| Objective | Who may return |
| Preconditions | BOR-07 |
| Steps | Try to return as an unrelated lead. |
| Expected result | Refused; requester, borrowing-group lead, routed source approver and Owner can. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**BOR-13 — Overdue flag**

| Field | Detail |
|---|---|
| Objective | Overdue flag |
| Preconditions | Approved borrow whose End time has passed |
| Steps | Open Borrow. |
| Expected result | Overdue badge shown; borrow is not auto-returned. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**BOR-14 — Pending expiry**

| Field | Detail |
|---|---|
| Objective | Pending expiry |
| Preconditions | Pending borrow whose End time passed |
| Steps | Open Borrow/Approvals or wait one sweep. |
| Expected result | Status EXPIRED; cannot be approved. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**BOR-15 — Effective access**

| Field | Detail |
|---|---|
| Objective | Effective access |
| Preconditions | BOR-07 |
| Steps | As a group-e user open the swap dialog on the borrowed setup; as a group-d user try the same. |
| Expected result | Borrower group can raise a swap; owner group cannot until Return. |
| Pass/Fail | ☐ Pass  ☐ Fail |


### 10. Approval routing and cross-group scenarios

**RTE-01 — Swap routing**

| Field | Detail |
|---|---|
| Objective | Swap routing |
| Preconditions | Swap edges A→D,E and D,E→J..O (SWAP); setup in group J |
| Steps | Raise a swap on J's setup. |
| Expected result | Routed to leads of J, D, E and A; any one approves. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**RTE-02 — Borrow routing**

| Field | Detail |
|---|---|
| Objective | Borrow routing |
| Preconditions | Borrow edges a→d,e; b→d,f,g; c→h,i,b; lead e requests from lead d |
| Steps | Submit a borrow. |
| Expected result | Routed to b, d, f, g. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**RTE-03 — Independent domains**

| Field | Detail |
|---|---|
| Objective | Independent domains |
| Preconditions | SWAP-only and BORROW-only edges |
| Steps | Compare approvers for a swap and a borrow on the same group. |
| Expected result | Each uses only its own scope (or BOTH). |
| Pass/Fail | ☐ Pass  ☐ Fail |

**RTE-04 — No hierarchy configured**

| Field | Detail |
|---|---|
| Objective | No hierarchy configured |
| Preconditions | No edges |
| Steps | Raise a swap/borrow. |
| Expected result | Any Lead/Manager/Owner with the permission may approve (fallback). |
| Pass/Fail | ☐ Pass  ☐ Fail |

**RTE-05 — Hierarchy does not grant access**

| Field | Detail |
|---|---|
| Objective | Hierarchy does not grant access |
| Preconditions | Lead of a parent group |
| Steps | Try to raise a swap on a child group's setup. |
| Expected result | Refused unless also in that group. |
| Pass/Fail | ☐ Pass  ☐ Fail |


### 11. Announcements and emails

**ANN-01 — Create announcement**

| Field | Detail |
|---|---|
| Objective | Create announcement |
| Preconditions | Manager/Owner |
| Steps | Announcements → New Announcement → Title, Message, Priority, Start, End → Save. |
| Expected result | Visible to all users while active. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**ANN-02 — Announcement expiry**

| Field | Detail |
|---|---|
| Objective | Announcement expiry |
| Preconditions | End in the past |
| Steps | Reload after the sweep. |
| Expected result | No longer shown in active list (Show active only). |
| Pass/Fail | ☐ Pass  ☐ Fail |

**ANN-03 — Email delivery mode**

| Field | Detail |
|---|---|
| Objective | Email delivery mode |
| Preconditions | SMTP disabled |
| Steps | Perform a swap request. |
| Expected result | Server log shows "Email (SMTP disabled, not sent)" with recipients; with SMTP enabled the mails arrive. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**ANN-04 — Channel selection**

| Field | Detail |
|---|---|
| Objective | Channel selection |
| Preconditions | Reserve/Swap/Borrow dialogs |
| Steps | Tick Groups or All Users. |
| Expected result | Members of the group / all active users are emailed. |
| Pass/Fail | ☐ Pass  ☐ Fail |


### 12. History and audit

**AUD-01 — Audit trail**

| Field | Detail |
|---|---|
| Objective | Audit trail |
| Preconditions | Manager/Owner |
| Steps | After the flows above open Logs and filter by Entity type (Reservation, SwapRequest, BorrowRequest, SetupAccessGrant). |
| Expected result | Entries exist for create, approve/reject/cancel, return with the acting user. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**AUD-02 — Approval History**

| Field | Detail |
|---|---|
| Objective | Approval History |
| Preconditions | Completed flows |
| Steps | Approvals → Approval History; toggle Show only my requests. |
| Expected result | Swaps and borrows listed with status, Borrower ← Source and Decided by. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**AUD-03 — Borrow history**

| Field | Detail |
|---|---|
| Objective | Borrow history |
| Preconditions | BOR flows |
| Steps | Borrow → History. |
| Expected result | All RETURNED/REJECTED/CANCELLED/EXPIRED borrows listed with dates. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**AUD-04 — Visibility**

| Field | Detail |
|---|---|
| Objective | Visibility |
| Preconditions | A Lead unrelated to a borrow |
| Steps | Open Approvals. |
| Expected result | The request is not visible; Managers/Owners see everything. |
| Pass/Fail | ☐ Pass  ☐ Fail |


### 13. Negative / permission cases

**NEG-01 — BOT is read-only**

| Field | Detail |
|---|---|
| Objective | BOT is read-only |
| Preconditions | BOT account |
| Steps | Try Reserve/Swap/Export. |
| Expected result | Controls absent or 403. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**NEG-02 — Direct URL / API bypass**

| Field | Detail |
|---|---|
| Objective | Direct URL / API bypass |
| Preconditions | USER account |
| Steps | Call PATCH /api/v1/swaps/{id}/approve and /api/v1/borrows. |
| Expected result | 403. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**NEG-03 — Baseline cannot be edited via workflows**

| Field | Detail |
|---|---|
| Objective | Baseline cannot be edited via workflows |
| Preconditions | A swapped setup |
| Steps | Approve, reject, cancel or return requests; open Original vs Current. |
| Expected result | Original values stay as recorded; only Edit Setup changes them. |
| Pass/Fail | ☐ Pass  ☐ Fail |


### 14. Time and boundary cases

**BND-01 — Reservation touching windows**

| Field | Detail |
|---|---|
| Objective | Reservation touching windows |
| Preconditions | Setup reserved 10:00–11:00 |
| Steps | Reserve 11:00–12:00. |
| Expected result | Behavior follows the service overlap rule; record the observed result. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**BND-02 — Very long text**

| Field | Detail |
|---|---|
| Objective | Very long text |
| Preconditions | Reason field |
| Steps | Enter more than 500 characters in a swap/borrow reason. |
| Expected result | Rejected by validation. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**BND-03 — Start after end**

| Field | Detail |
|---|---|
| Objective | Start after end |
| Preconditions | Swap/Borrow |
| Steps | Set End time earlier than Start time. |
| Expected result | Rejected: end_time must be after start_time. |
| Pass/Fail | ☐ Pass  ☐ Fail |


### 15. Regression checks

**REG-01 — Setups table intact**

| Field | Detail |
|---|---|
| Objective | Setups table intact |
| Preconditions | Any data |
| Steps | Search, filters, column filters, pagination. |
| Expected result | All work as before; SSD/HDD columns present. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**REG-02 — Product template flows**

| Field | Detail |
|---|---|
| Objective | Product template flows |
| Preconditions | Existing products |
| Steps | Add/reorder columns, export, import. |
| Expected result | Unchanged behavior. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**REG-03 — Dashboard**

| Field | Detail |
|---|---|
| Objective | Dashboard |
| Preconditions | Any user |
| Steps | Open Dashboard. |
| Expected result | Cards Total Setups, Available Now, My Active Reservations show correct counts. |
| Pass/Fail | ☐ Pass  ☐ Fail |

**REG-04 — Old swap page**

| Field | Detail |
|---|---|
| Objective | Old swap page |
| Preconditions | Lead |
| Steps | Open Swap Approvals. |
| Expected result | Pending swaps listed with Approve/Reject. |
| Pass/Fail | ☐ Pass  ☐ Fail |
