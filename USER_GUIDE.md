# Reservation Management System — User Guide

## 1. Overview

Web app for reserving lab/test hardware ("setups") grouped under Products. Users browse a product's setup table, reserve/swap/unreserve equipment, and see announcements. Admins manage products, dynamic setup templates, groups, users, and audit logs.

## 2. Getting Started

- Access via browser at the app URL. No public/anonymous pages besides Login, Register, Forgot/Reset Password.
- **Login** (`/login`): username + password. "Forgot password?" link available.
- **Register** (`/register`): username, email, full name, password (8+ chars, upper+lower+digit), optional multi-select Groups. New accounts start in **PENDING** status and cannot log in until an authorized user approves them.
- **Forgot/Reset Password** (`/forgot-password`, `/reset-password`): emails a single-use reset link (30 min expiry) if the address matches an approved, active account. The message shown is the same either way, so it won't confirm whether an email is registered.
- Password fields have a show/hide (eye) toggle.

## 3. User Roles

Roles: **User, Lead, Developer, Developer Lead, Owner** (Owner has every permission).

**Roles were renamed**: the old "User" role is now **Bot**, the old "Developer" role is now **User**, and "Developer Lead" is now **Manager**. Lead and Owner are unchanged in name. Permissions per role:

| Feature | Bot | User | Lead | Manager | Owner |
|---|---|---|---|---|---|
| View products / setup table / announcements | ✓ | ✓ | ✓ | ✓ | ✓ |
| Reserve / Swap-request setups; cancel own reservation | | ✓ | ✓ | ✓ | ✓ |
| Export Excel | | ✓ | ✓ | ✓ | ✓ |
| Approve/reject swaps; cancel any reservation | | | ✓ | ✓ | ✓ |
| Import Excel | | | ✓ | ✓ | ✓ |
| Approve/reject pending registrations | | | ✓ | ✓ | ✓ |
| Manage Groups | | | ✓ | ✓ | ✓ |
| Manage products & Design Template | | | | ✓ | ✓ |
| Manage users (create/edit/deactivate) | | | | ✓ | ✓ |
| Manage Announcements | | | | ✓ | ✓ |
| View Audit Logs | | | | ✓ | ✓ |
| View Developer (Excel transaction) Logs | | | | ✓ | ✓ |

The **Bot** role is view-only by default (no reserve/swap/import/export). **Lead no longer has access to Developer Logs** (Manager/Owner only now). Only permitted actions/nav items are shown to a given role.

## 4. Dashboard

Landing page after login: welcome message, active Announcements, and a product card grid (same as Product Selection).

Navbar: brand → Dashboard, Products, Groups, Announcements (if permitted); Admin dropdown (Products Admin, Users, Approvals, Logs, Developer Logs — each only if permitted); user menu (username, theme toggle, Logout).

## 5. Product Selection

`/products`: card per Product. Clicking a card opens that product's setup table (`/setups?product_id=...`). Products with no setups yet still open normally, showing an empty table.

## 6. Product-Specific Templates

Under **Admin → Products**, an authorized user (product:manage — Developer Lead/Owner) clicks the **Template** button on a product row to open **Design Template**.

- **Mandatory columns** (every product, always, cannot be renamed/reordered/deleted): IP, User, Owner, Reservation, Remark, Location, Group, Product.
- **Custom columns**: add/edit/delete/reorder (up/down arrows). Each has: Name (key), Label, Type (String, Integer, Float, Boolean, Date, DateTime, Dropdown), Required, Default Value, and — for Dropdown — a comma-separated list of Allowed Values.
- Custom columns appear in the setup table (when filtered to that one product), in Setup Edit, and in that product's Excel import/export.

## 7. Setup Table

| Column | Description |
|---|---|
| (checkbox) | Select row(s) for Reserve/Swap/Unreserve; disabled if reserved by someone else |
| Sr No | Row number |
| Status | AVAILABLE / RESERVED / MAINTENANCE / RETIRED |
| IP, Hostname | Setup identifiers |
| User | Current reserver's name (— if available) |
| Form Factor, Capacity, Aardvark, Quarch, APC, Remote Server, Hardware Info, Adapter | Hardware fields |
| Owner | Assigned owner |
| Location, Group, Product | Mandatory fields |
| *(custom columns)* | Only shown when filtered to a single Product |
| Reserved Time | Reservation window, if reserved |
| Remarks | Reservation remark, or the setup's own remark |
| Actions | Edit button (product:manage only) |

Filters: Product, Group, Status, Location dropdowns/search, plus a per-column text filter row (client-side). No server-side sort; filtering only. The page opens pre-filtered to the first Product and first Group (rather than "All"), and shows up to 200 rows per page.

## 8. Reserve

1. Select one or more AVAILABLE setups' checkboxes (requires `reservation:create` — User role or above).
2. Click **Reserve**.
3. Dialog shows the selected setups, a start/end time range, a Remarks field, and Announcement channel checkboxes (Wall, Mail to Leads, Mail to Group, Mail to All).
4. Submit. One reservation is created per selected setup over the same time window. Validation errors (e.g. overlapping window, setup not available) are shown per-setup; setups that succeeded are still reserved even if another in the batch failed.

## 9. Swap

A swap exchanges one field's recorded value (e.g. an SSD) between two setups **you already have reserved** — it does not relocate either reservation.

- **Rules**: both the current setup and the target setup must currently be reserved by you. You pick which column to exchange — one of the fixed hardware fields (SSD, HDD, Hardware Info, Capacity, Form Factor, Adapter, Aardvark, Quarch, APC, Remote Server), or, if the two setups belong to different products, a custom column that exists on **both** products' templates.
- **Request** (`swap:request` — User role or above): open Swap from your reservation, pick the other setup and the column, optionally add a reason. Starts **PENDING**; a notification is sent for approval.
- **Approve / reject** (`swap:approve` — Lead role or above): review pending requests; approving exchanges the column's value between the two setups (neither reservation changes).
- **Cancel**: the requester can cancel their own still-pending swap request.
- **Coordinated multi-setup swap mapping** (`swap:approve` — Lead role or above, via the swap-mapping screen): a separate, unrelated workflow for relocating several reservations across setups at once — build a set of moves (e.g. reservation A → setup B, reservation B → setup A) where every reservation and every target setup appears exactly once, submitted and approved as one batch.

## 10. Unreserve

1. Select your reserved setup(s) (`reservation:cancel_own`) — or, with `reservation:cancel_any` (Lead role or above), any user's reservation — and open **Unreserve**.
2. Preview shows what will be released.
3. Confirm to cancel the reservation; the setup returns to AVAILABLE.

If a reservation's end time passes and it is **not** manually unreserved, the system automatically completes it and posts a **CRITICAL** announcement plus a direct email to the setup's owner and the reserving user.

## 11. Announcements

Options when reserving: **Wall** (dashboard banner), **Mail to Leads** (Lead/Manager/Owner in the setup's Group), **Mail to Group** (all approved members of the Group), **Mail to All** (every active, approved user). Everyone with `announcement:view` (every role) can see active announcements; standalone create/edit/delete (`announcement:manage`) is Manager/Owner only — Lead can view but not manage them.

The Announcements screen lists announcements sorted **Critical → High → Normal → Low**, grouped into a collapsible section per priority (Critical and High expanded by default).

**Automatic critical announcements**: if a reservation's time window elapses without the setup being unreserved, the system itself posts a CRITICAL announcement and emails the setup owner and the reserving user directly (see §10).

## 12. Groups

Lead, Developer Lead, and Owner can create, edit, and delete Groups (name + description) under **Groups**. Groups are used for setup ownership/filtering, user membership (multi-group per user), and announcement targeting (Mail to Group/Leads).

## 13. Product Administration

**Admin → Products** (Developer Lead/Owner): Add/Edit product (name, description); Design Template; Import Excel; Export Excel. A product cannot be deleted while it still has setups (returns an error).

## 14. Excel Import

From a product's Template page → **Import Excel**: upload `.xlsx`. Headers are validated against that product's current template (mandatory columns + existing custom columns). If the file has columns not yet in the template, you get **"New columns detected"** with a choice: **Add to Template & Import** (adds them as String columns, then imports) or **Reject Import** (nothing is committed). Row-level errors (missing required fields, bad types, invalid dropdown values) are listed and block the import until fixed.

## 15. Excel Export

From a product's Template page → **Export**: downloads an `.xlsx` with that product's mandatory + custom columns, in template order, containing current data (or an empty header-only template if the product has no setups yet).

## 16. Logs

- **Audit Logs** (`/admin/logs`, `audit:view` — Manager/Owner only): filterable, paginated table of create/update/delete/approve/reject/login/logout/swap/import/export events with user, entity, timestamp.
- **Developer Logs** (`/admin/developer-logs`, `logs:view` — Manager, Owner): tree view of rotated Excel import/export transaction log files, each downloadable. Lead no longer has access to this screen.

## 17. Common Errors

| Problem | Possible Cause | Solution |
|---|---|---|
| "Account is pending approval" at login | Registration not yet approved | Ask a Lead/Developer Lead/Owner to approve via Approvals |
| Can't delete a Product | Setups still assigned to it | Remove/reassign setups first |
| Import rejected with row errors | Missing required field, wrong type, invalid dropdown value | Fix the Excel file and re-upload |
| "New columns detected" | Excel has headers not in the product's template | Choose Add to Template & Import, or fix the file |
| Swap request rejected as invalid | The two setups aren't both currently reserved by you, or the chosen column isn't common to both products | Pick two setups you have reserved and a shared column |
| Reset link says invalid/expired | Link older than 30 minutes or already used | Request a new one via Forgot Password |

## 18. FAQ

**Q: Why don't I see Admin/Groups/Logs in the nav?** Your role lacks that permission.
**Q: Can I belong to more than one group?** Yes — select multiple at registration or have an admin edit your groups.
**Q: Do custom columns show for every product?** No — a product's custom columns only appear in the setup table when it's filtered to that single product.
**Q: What happens to a setup's data if a custom column is deleted from a template?** The column definition is removed from the template; its recorded values are no longer shown/editable through the template UI.
