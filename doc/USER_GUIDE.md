# User Guide

Audience: end users and administrators using the web UI at `/login`.

## Table of Contents
1. [Roles at a Glance](#roles-at-a-glance)
2. [Registration & Approval](#registration--approval)
3. [Managing Products](#managing-products)
4. [Managing Groups](#managing-groups)
5. [Managing Users](#managing-users)
6. [Reservation Workflow](#reservation-workflow)
7. [Swap Workflow](#swap-workflow)
8. [Announcements](#announcements)
9. [Logs](#logs-audit-log)
10. [Excel Logs (Developer Logs)](#excel-logs-developer-logs)
11. [FAQ](#faq)

---

## Roles at a Glance

| Role | Can do |
|---|---|
| **USER** | View products, setups, reservations, swaps, announcements (read-only) |
| **DEVELOPER** | Above, plus create/cancel own reservations, request swaps, run exports |
| **LEAD** | Above, plus approve registrations/swaps *within their own Group*, manage Groups, import setups, view Developer Logs |
| **DEVELOPER_LEAD** | Above, but globally (any Group), plus manage Products/Users/Announcements, view the Audit Log |
| **OWNER** | Full system access |

Your role and its permissions are shown next to your name in the top-right of the navbar.

---

## Registration & Approval

1. Go to `/register`, fill in your details, submit. Your account is created in **PENDING** status.
2. A **LEAD** (within your Group) or **DEVELOPER_LEAD**/**OWNER** (any Group) must approve you before you can log in.
3. Approvers see pending accounts on the **Approval Dashboard** (nav bar, visible only if you hold `user:approve`). Each card lets the approver pick the role to assign and either **Approve** or **Reject** (with an optional reason).
4. Once approved, log in at `/login`. If rejected or later deactivated, login is blocked with a clear message.

---

## Managing Products

**Products** classify what a Setup *is* (a product line). Go to **Products** (nav) → **Product Management** (if you hold `product:manage`) to:

- **New Product**: name + description.
- **Edit** / **Delete** (blocked while any Setup is still assigned to it).
- **Export** (per-product): downloads an `.xlsx` of every Setup under that product. If the product has **no Setups yet**, this automatically generates a **blank import-ready template** instead of an empty file — fill it in and re-import.
- **Blank Template**: download the generic Setup import template at any time (`Product Management` toolbar).
- **Import Setups**: upload an `.xlsx` workbook. The import is **all-or-nothing** — if any row fails validation, nothing is committed and every row error is listed (row number, field, message) so you can fix the file in one pass and re-upload.

**Import column contract** (row 1 headers, order-independent):
`product_name, group_name, ip_address, hostname, ssd, hdd, hardware_info, capacity, form_factor, owner_username, adapter, aardvark, quarch, apc, remote_server, location, remarks`

`product_name` must match an existing Product name; `group_name`/`owner_username` are optional but must match existing records if provided. Existing setups are matched by `ip_address`/`hostname` and **updated**; new ones are **created**.

---

## Managing Groups

**Groups** represent organizational teams — independent of Products. A Setup can be *owned* by a Group (for maintenance), and a User can *belong* to a Group (for Lead-scoped approvals). Go to **Groups** (nav, requires `group:manage`) to create/edit/delete. Deletion is blocked while any user or setup still references the group.

---

## Managing Users

Go to **Users** (nav, requires `user:manage`) to:

- **New User**: create an already-approved account directly (skips the registration/approval flow) — set username, email, password, full name, role, and optional group.
- **Edit**: change full name, role, group, or active flag.
- **Deactivate**: soft-deletes the account (sets inactive; login is blocked immediately, since every request re-fetches the user from the database).
- Filter by status, role, or search text; results are paginated.

---

## Reservation Workflow

1. Go to **Setups** (nav) → optionally pick a **Product** first from the card grid, or browse all setups directly.
2. Use the **search box**, **dropdown filters** (Product / Group / Status / Location), and **column filters** (instant, per-column text filters under the sticky header) to find the setup(s) you want.
3. Tick the checkbox next to one or more setups. A checkbox is only enabled if the setup is **AVAILABLE**, or it's currently reserved **by you**.
4. Click **Reserve** (enabled once at least one AVAILABLE setup is checked). This opens the Reserve dialog:
   - **Step 1 (form)**: confirm the setup list, set **From**/**Until**, optional **Remarks**, and optionally check one or more **Announce via** channels (Wall Message / Mail Leads / Groups / All Users) with an optional custom message.
   - Click **Preview** to review everything on one screen; use **Back** to return and edit, or **Confirm Reservation** to submit.
5. On success the table refreshes and a toast confirms the reservation (or lists any per-setup errors, e.g. a time-window conflict).
6. Reservations expire automatically at `reserved_until` (checked every `RESERVATION_SWEEP_INTERVAL_MINUTES`), freeing the setup back to AVAILABLE without any manual action.

### Unreserve

Select your own reserved setup(s) and click **Unreserve** → confirm. **If a swap request on that reservation is still PENDING**, the dialog shows a warning and disables the Confirm button — resolve (approve/reject/cancel) the swap first.

---

## Swap Workflow

### Simple 1:1 swap
1. Select exactly one setup **reserved by you**, click **Swap**.
2. Pick a replacement setup (must be AVAILABLE, and — by default — belong to the same Product) and an optional reason. Submitting creates a **PENDING** swap request; it does not move anything yet.
3. A user holding `swap:approve` (LEAD+) reviews it under **Swaps** and clicks **Approve** or **Reject**. On approval, your reservation moves to the new setup (same time window), the old setup is freed, and both reservations get a remark appended: `you@company.com swapped drive from OLD-HOSTNAME to NEW-HOSTNAME at HH:MM DD/MM/YYYY` — this is your permanent swap history trail.

### Multi-node Swap Mapping (A→B, B→A, C→D)

For coordinated swaps across several users at once (e.g. three teams rotating hardware), a LEAD+ uses **Swap Mapping** (nav, requires `swap:approve`):

1. For each row, pick a reservation (its current setup) and the target setup it should move to. Click **Add Row** for more pairs.
2. Submit — the system validates that **every reservation and every target setup appears at most once**, and that any target *not* itself a source within the same mapping is currently AVAILABLE. Invalid mappings are rejected with a specific error (e.g. "Target setup 12 is not part of the swap cycle and is not currently AVAILABLE").
3. Valid mappings appear under **Pending Mapping Batches**. Click **Approve Mapping** to apply every swap in the batch atomically — all reservations move together, each with its own swap-history remark appended.

---

## Announcements

Go to **Announcements** (nav). Anyone can view active announcements on the Dashboard and here; users holding `announcement:manage` (DEVELOPER_LEAD/OWNER) can:

- **New Announcement**: title, message, priority (LOW/NORMAL/HIGH/CRITICAL), start date, optional end date.
- **Edit** / **Delete**.
- Toggle **Show active only** to filter to currently-live announcements (`is_active` and within the start/end window).

Announcements can also be created directly from the **Reserve dialog** (see [Reservation Workflow](#reservation-workflow)) as a side effect of reserving a setup, via the **Announce via** checkboxes:
- **Wall Message** — posts to this Announcements list / dashboard.
- **Mail Leads** — emails every LEAD/DEVELOPER_LEAD/OWNER in the setup's Group.
- **Groups** — emails every member of the setup's Group.
- **All Users** — emails every approved, active user in the system.

(Email delivery requires `SMTP_ENABLED=true` and valid `SMTP_*` settings — see INSTALLATION.md. Otherwise messages are logged, not sent.)

---

## Logs (Audit Log)

Go to **Logs** (nav, requires `audit:view` — DEVELOPER_LEAD/OWNER). Every state-changing action in the system (create/update/delete/approve/reject/login/cancel/swap/import/export) is recorded here, filterable by entity type, entity ID, user ID, and action, with pagination. This is an **append-only** trail — nothing here can be edited or deleted through the UI.

---

## Excel Logs (Developer Logs)

Go to **Developer Logs** (nav, requires `logs:view` — LEAD/DEVELOPER_LEAD/OWNER). This shows a **tree view** of the raw Excel transaction log files generated for every Import/Export operation, organized as:

```
Logs/
  August_2026/
    20260804_090000_00001.xlsx
    20260804_153000_00002.xlsx
  September_2026/
    ...
```

A new file is automatically started once the current one reaches **40MB**. Click the download icon next to any file to retrieve it directly. This is distinct from the database-backed Audit Log above — it's the raw, portable Excel record of every import/export row processed, intended for offline analysis or compliance handoff.

---

## FAQ

**Q: I can't see the "Products" or "Users" management screens — why?**
A: Those require `product:manage` / `user:manage` (DEVELOPER_LEAD/OWNER). Regular USER/DEVELOPER/LEAD accounts only see the read-only "Setups" browse screen and, for LEAD, the Approval Dashboard scoped to their Group.

**Q: Why is my checkbox disabled on a setup I want to reserve?**
A: Checkboxes are only enabled for setups that are AVAILABLE, or already reserved by you. A setup RESERVED by someone else, or under MAINTENANCE/RETIRED, cannot be selected.

**Q: My swap request has been pending for a while — can I cancel it?**
A: Yes, if you're the requester: open the swap and use Cancel (also available via the API `PATCH /api/v1/swaps/{id}/cancel`). Cancelling restores your ability to unreserve that reservation directly.

**Q: I unreserved a setup by mistake — can I get it back?**
A: Not automatically. Re-reserve it via the normal Reservation Workflow if it's still AVAILABLE; if someone else has since reserved it, you'll need to coordinate a swap.

**Q: Why did my export come back with just headers and no data?**
A: If your filter (e.g. a specific Product) matches zero Setups, the export automatically becomes a blank **import template** instead of an empty file, so you can fill it in and re-upload immediately.

**Q: Who can see the Audit Log vs. Developer Logs?**
A: Audit Log requires `audit:view` (DEVELOPER_LEAD/OWNER) — human-readable, DB-backed, covers every entity. Developer Logs requires `logs:view` (LEAD/DEVELOPER_LEAD/OWNER) — raw rotating Excel files specifically for import/export transactions.

For anything not covered here, see DEVELOPER_GUIDE.md, or ask an administrator.
