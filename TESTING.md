# TESTING.md — Manual Web UI Test Plan

Practical, execution-oriented test plan for exercising the Reservation Management System through the browser. Not a substitute for the automated `pytest` suite — this covers user-facing workflows a person clicks through.

**Roles** (lowest to highest): Bot (view-only) < User (reserve/swap-request/export) < Lead (approvals, groups, import) < Manager (products, users, audit) < Owner (everything).

**Setup**: have at least 2 test accounts ready — one **User**-tier, one **Lead**-or-above — plus a Manager/Owner account for admin setup. Record actual vs expected results in the Pass/Fail column as you go.

---

## 1. Login / Registration / RBAC

| ID | Objective | Preconditions | Steps | Expected Result | P/F |
|---|---|---|---|---|---|
| AUTH-01 | New user can self-register | Logged out | Go to `/register`. Fill username/email/full name/password, optionally select group(s). Submit. | Success message shown; account NOT logged in; status is PENDING. | |
| AUTH-02 | Weak password rejected | Logged out, on `/register` | Submit with a password missing an uppercase letter or digit (e.g. `abcdefgh`). | Inline/error message about password requirements; account not created. | |
| AUTH-03 | Pending account cannot log in | AUTH-01 account not yet approved | Go to `/login`, enter the pending account's credentials. | Error: account pending approval. Not logged in. | |
| AUTH-04 | Lead+ approves a pending user | Logged in as Lead/Manager/Owner; a PENDING user exists | Go to **Admin → Approvals**. Find the pending user, click Approve (optionally set a role). | User disappears from pending list; toast confirms approval. | |
| AUTH-05 | Approved user can log in | AUTH-04 done | `/login` with the now-approved account. | Redirected to Dashboard; navbar shows only nav items the account's role permits. | |
| AUTH-06 | Forgot / reset password | A known approved account's email | `/forgot-password`, submit the email. Then use the emailed reset link at `/reset-password?token=...`, set a new password. | Generic "if an account exists..." message shown regardless of validity (no email enumeration). Reset link lets you set a new password and log in with it; old password no longer works. | |
| AUTH-07 | Login with wrong password | Approved account | `/login` with correct username, wrong password. | Generic "invalid credentials" error; not logged in. | |
| AUTH-08 | Nav items match role permissions | Log in as Bot-tier and separately as Manager/Owner | Compare navbar items (Products Admin, Users, Approvals, Logs, Developer Logs, Groups, Announcements, Swap Approvals). | Bot sees only Dashboard/Products/reservation table (view-only); Manager/Owner sees all admin items. | |
| AUTH-09 | Direct URL access blocked for under-privileged role | Logged in as Bot or User | Manually navigate to an admin URL you shouldn't have (e.g. `/admin/products`, `/admin/users`). | 403 Forbidden page, not the admin screen. | |

## 2. Product & Template Management

| ID | Objective | Preconditions | Steps | Expected Result | P/F |
|---|---|---|---|---|---|
| PROD-01 | Create a product | Logged in as Manager/Owner | **Admin → Products** → Add Product. Enter name/description. Save. | New product appears in the list. | |
| PROD-02 | Edit a product | A product exists | Click Edit on a product row, change description, save. | Updated description shown in list. | |
| PROD-03 | Delete blocked while setups exist | Product has at least one Setup | Attempt to delete that product. | Error/toast: cannot delete while setups are assigned; product remains. | |
| PROD-04 | Design Template: add mandatory + custom columns | Product exists | Open **Template** for the product. Confirm the 8 mandatory columns are listed and not editable. Add a custom column (e.g. "Firmware", type String, required=No). | New column appears in the custom columns list; mandatory columns unchanged, no edit/delete controls on them. | |
| PROD-05 | Add a Dropdown column with allowed values | On a product's Template page | Add Custom Column, type Dropdown, enter allowed values (e.g. `SSD,HDD,NVMe`). Save. | Column saved; editing it shows the same allowed values. | |
| PROD-06 | Reorder / edit / delete custom column | At least 2 custom columns exist | Use up/down arrows to reorder one; edit another's label; delete a third. | Order, label, and removal all persist after page refresh. | |
| PROD-07 | Delete product after removing setups | Product's setups all removed/reassigned | Delete the now-empty product. | Product removed from the list successfully. | |

## 3. Excel Import / Export

| ID | Objective | Preconditions | Steps | Expected Result | P/F |
|---|---|---|---|---|---|
| EXCEL-01 | Export reflects current template incl. new columns | Product has setups and at least one custom column added after setups existed | On the product's Template page, click Export. | Downloaded `.xlsx` includes mandatory columns AND the custom column(s), with current data. | |
| EXCEL-02 | Import with all known columns | Have a `.xlsx` matching the product's current template headers | Template page → Import Excel → upload file. | Rows imported; success summary shown (created/updated counts). | |
| EXCEL-03 | Import detects new columns | `.xlsx` has an extra header not in the template | Upload it via Import Excel. | "New columns detected" prompt appears, listing the extra header(s); nothing imported yet. | |
| EXCEL-04 | Accept new columns and import | Continuing EXCEL-03 | Click "Add to Template & Import". | New column added to the template; rows imported using it. | |
| EXCEL-05 | Reject new columns | Continuing EXCEL-03 (repeat upload) | Click "Reject Import" instead. | Nothing imported; template unchanged. | |
| EXCEL-06 | Import row error blocks commit | `.xlsx` with a row missing a required field or an invalid dropdown value | Upload it. | Import rejected as a whole; row-level errors listed (row #, field, message); no rows committed. | |
| EXCEL-07 | Export empty product | A product with zero setups | Template page → Export. | Downloads a header-only template (mandatory + custom columns), no data rows. | |

## 4. Setup Selection & Table

| ID | Objective | Preconditions | Steps | Expected Result | P/F |
|---|---|---|---|---|---|
| SETUP-01 | Table opens with sensible defaults | Logged in, at least 2 products/groups exist | Go to `/setups` (or click a product card). | Table pre-filters to the first product and first group (not "All"); up to 200 rows shown per page. | |
| SETUP-02 | Filter by product/group/status/location | On the setup table | Change each filter dropdown/search box in turn. | Table updates to match each filter without a full page reload. | |
| SETUP-03 | Custom columns show only for a single product | A product has a custom column | Filter table to that one product, note the custom column. Switch filter to another product. | Custom column is shown while filtered to its product, and disappears/changes when the filter switches to a different product. | |
| SETUP-04 | Edit a setup | Logged in as Manager/Owner (or product:manage role); a setup exists | Click Edit (pencil) on a row. Change a field (e.g. Location), save. | Row updates; dialog closes; toast confirms success. | |
| SETUP-05 | Edit validation error keeps dialog open | Editing a setup | Enter an IP/hostname that collides with another existing setup, save. | Error toast shown; dialog stays open so the value can be corrected. | |

## 5. Reserve

| ID | Objective | Preconditions | Steps | Expected Result | P/F |
|---|---|---|---|---|---|
| RSV-01 | Reserve a single AVAILABLE setup | Logged in as User+; an AVAILABLE setup exists | Check its box, click Reserve, set a time window + remarks, submit. | Setup status becomes RESERVED; row shows your name as reserving user; dialog closes. | |
| RSV-02 | Reserve multiple setups at once | 2+ AVAILABLE setups | Check 2+ boxes, click Reserve, submit once. | Each selected setup gets its own reservation over the same window. | |
| RSV-03 | Cannot reserve an already-reserved setup | A RESERVED setup | Its checkbox should be disabled (unless it's your own reservation). | Checkbox is disabled/unselectable for other users' reservations. | |
| RSV-04 | Bot-tier cannot reserve | Logged in as Bot-tier | Attempt to check a box / open Reserve. | Reserve control is unavailable, or the action is rejected with a permission error. | |
| RSV-05 | Announcement channel options on reserve | Reserving a setup | In the Reserve dialog, check "Mail to Group"/"Mail to Leads"/etc. Submit. | Reservation succeeds; recipients in that group/role receive the notification (verify via mail log or announcement wall if SMTP disabled). | |

## 6. Swap + Approval Workflow

| ID | Objective | Preconditions | Steps | Expected Result | P/F |
|---|---|---|---|---|---|
| SWAP-01 | Submit a swap request | Logged in as User+; you have **two** of your own setups reserved | From one reservation's row, open Swap. Pick the other setup you have reserved and a column (e.g. SSD). Submit. | Toast confirms the request was submitted for approval; dialog closes. Neither setup's data has changed yet. | |
| SWAP-02 | Cannot swap with a setup you don't have reserved | Same as SWAP-01, but only one setup reserved | Open Swap; the dropdown for "swap with" should only list your own other reserved setups. | If you have no other reserved setup, the dialog shows a message and disables Submit; you cannot pick someone else's or an available setup. | |
| SWAP-03 | Pending swap reaches the approver | SWAP-01 done | Log in as Lead/Manager/Owner. Go to **Swap Approvals** (`/admin/swap-mapping`). | The submitted request appears under "Pending Individual Swap Requests" with requester, column, and both setup names. | |
| SWAP-04 | Approve a swap request | SWAP-03 | Click Approve on the request, confirm. | Toast confirms; the column's value is now exchanged between the two setups (verify in the setup table / Setup Edit); request disappears from pending list; reservation Remarks show a swap history line with the before/after values. | |
| SWAP-05 | Reject a swap request | A second pending swap request exists | Click Reject, confirm. | Request removed from the pending list; no values changed on either setup. | |
| SWAP-06 | Only Lead+ can approve/reject | Logged in as User-tier | Try to navigate to `/admin/swap-mapping`. | 403 Forbidden — User-tier cannot approve swaps. | |
| SWAP-07 | Restore original value after a swap | SWAP-04 done | Open the affected setup's Remarks (table) or the swap's recorded previous value; use Setup Edit to manually set the column back to the recorded original value. | Value restored; confirms the pre-swap value was visible/recoverable to a User-tier-or-above account, not just via admin audit logs. | |
| SWAP-08 | Multi-node swap mapping (separate flow) | Lead+; 2+ users each have an active reservation | On **Swap Approvals**, build a mapping: reservation A → setup B, reservation B → setup A. Submit. | Mapping appears under "Pending Mapping Batches". | |
| SWAP-09 | Approve a swap mapping | SWAP-08 done | Click "Approve Mapping". | Both reservations relocate to their target setups atomically; batch disappears from pending list. | |

## 7. Unreserve

| ID | Objective | Preconditions | Steps | Expected Result | P/F |
|---|---|---|---|---|---|
| UNRES-01 | Unreserve your own setup | You have an active reservation | Select it, click Unreserve, confirm. | Setup returns to AVAILABLE; your reservation is cancelled. | |
| UNRES-02 | User-tier cannot unreserve another user's setup | Logged in as User-tier; setup reserved by someone else | Attempt to select/unreserve it. | Blocked — checkbox disabled or action rejected (`reservation:cancel_any` required). | |
| UNRES-03 | Lead+ can unreserve any setup | Logged in as Lead/Manager/Owner | Unreserve a setup reserved by a different user. | Succeeds; setup becomes AVAILABLE. | |
| UNRES-04 | Automatic expiry notification | A reservation's end time has passed without manual unreserve (or wait for the scheduled sweep) | Check Announcements and the setup owner's/reserving user's email/mail log after the sweep runs. | A CRITICAL announcement appears and an email was sent to the setup owner and reserving user; setup auto-released to AVAILABLE. | |

## 8. Announcements / Groups

| ID | Objective | Preconditions | Steps | Expected Result | P/F |
|---|---|---|---|---|---|
| ANN-01 | View announcements sorted by priority | Announcements of mixed priority exist | Go to Announcements. | Sections appear Critical → High → Normal → Low; Critical/High expanded by default, Normal/Low collapsed; click to toggle. | |
| ANN-02 | Manager/Owner creates/edits/deletes an announcement | Logged in as Manager/Owner | Create one (title/message/priority/dates); edit it; delete it. | Each action succeeds and reflects immediately in the list. | |
| ANN-03 | Lead can view but not manage | Logged in as Lead | Open Announcements. | Announcements are visible; no create/edit/delete controls available. | |
| GRP-01 | Lead+ manages groups | Logged in as Lead/Manager/Owner | **Groups** → create a group, edit its description, delete an unused one. | Each action succeeds and list updates. | |
| GRP-02 | User can belong to multiple groups | Manager/Owner editing a user (or during registration) | Select 2+ groups for one account. Save. | User's Groups column/profile shows all selected groups. | |

## 9. Logs

| ID | Objective | Preconditions | Steps | Expected Result | P/F |
|---|---|---|---|---|---|
| LOG-01 | Manager/Owner views Audit Logs | Logged in as Manager/Owner; some actions have occurred | **Admin → Logs**. | Paginated table of actions (create/update/delete/approve/login/swap/import/export) with actor, entity, timestamp. | |
| LOG-02 | Audit Log filters and pagination | On Audit Logs, 2+ pages of data exist | Filter by entity type/action/user; click Next/Previous page. | Filtered results match; pagination advances without error on every page. | |
| LOG-03 | Lead cannot see Audit Logs | Logged in as Lead | Attempt `/admin/logs`. | 403 Forbidden. | |
| LOG-04 | Lead+ views Developer (Excel) Logs | Logged in as Lead/Manager/Owner | **Admin → Developer Logs**. | Tree of rotated Excel import/export log files, each downloadable. | |
| LOG-05 | User-tier cannot see Developer Logs | Logged in as User-tier | Attempt `/admin/developer-logs`. | 403 Forbidden. | |

## 10. Permission / Negative Scenarios

| ID | Objective | Preconditions | Steps | Expected Result | P/F |
|---|---|---|---|---|---|
| PERM-01 | Bot-tier is fully view-only | Logged in as Bot | Attempt Reserve, Swap, Import, Export, any Admin page. | All blocked; only browsing products/setups/announcements works. | |
| PERM-02 | Deactivated user cannot log in | Manager/Owner deactivates a user | Attempt login with that account. | Login rejected (account disabled). | |
| PERM-03 | Session invalidated after password change | Logged in on two browsers/tabs with the same account | Change password in one; try an action in the other. | Second session is rejected; must log in again. | |
| PERM-04 | Direct API/URL access still enforces RBAC | Any under-privileged role | Try a raw browser GET to a permission-gated URL (e.g. `/admin/users`, `/admin/logs`) without using the nav. | Still blocked with 403 — UI hiding a link is not the only protection. | |

## 11. Boundary / Error Cases

| ID | Objective | Preconditions | Steps | Expected Result | P/F |
|---|---|---|---|---|---|
| EDGE-01 | Reserve with end time before start time | Reserve dialog open | Set end time earlier than start time. Submit. | Validation error; reservation not created. | |
| EDGE-02 | Overlapping reservation window | A setup already reserved for a time window | Attempt to reserve the same setup for an overlapping window (as a Lead+ testing edge cases, or after it's freed and immediately re-reserved by someone else mid-flow). | Conflict error shown; no double-booking. | |
| EDGE-03 | Swap with a column not common to both products | Two setups from different products with no shared custom column | Attempt to select that column in the Swap dialog / submit via a crafted column name. | Request rejected with a clear "not a swappable column common to both setups" error. | |
| EDGE-04 | Delete a group still referenced by users/setups | A group has members or setups assigned | Attempt to delete it. | Blocked with a clear conflict error; group remains. | |
| EDGE-05 | Excel import with wrong file type | Import dialog | Upload a non-`.xlsx` file (e.g. `.csv` renamed, or a `.txt`). | Rejected with a clear error, not a silent failure or crash. | |
| EDGE-06 | Password reset link reused | A reset link already used once (AUTH-06) | Try the same link again. | Rejected as invalid/expired (single-use enforced). | |
| EDGE-07 | Empty required fields on forms | Any create form (Product, Group, Announcement, Template Column) | Submit with a required field left blank. | Client-side and/or server-side validation blocks submission with a clear message. | |

---

### Sign-off

| Tester | Date | Build/Commit | Overall Result |
|---|---|---|---|
| | | | |
