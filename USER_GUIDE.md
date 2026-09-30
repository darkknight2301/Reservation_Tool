# Reservation Management System — User Guide

This guide describes what the web application does today, using the labels you see on screen. Buttons and menu items appear only if your role allows them.

## 1. Overview

The system lets teams reserve shared hardware **setups**, exchange hardware between setups (**Swap**), and temporarily lend a setup to another group (**Borrow**). Reserve, Swap and Borrow are three independent workflows: none of them requires another.

- **Original vs Current hardware** — every setup remembers the hardware it was first recorded with (Original). Swaps change what is Current; changed cells are highlighted.
- **Approvals** — Swap and Borrow requests are routed to the leads configured for the relevant group; any one of them can approve.

## 2. Login and registration

- **Login** (`/login`): enter **Username** and **Password**, then **Login**. After login you land on the **Dashboard**.
- **Register** (`/register`, link "Register here"): fill **Full name**, **Username**, **Email**, **Password**, choose **Groups**, then **Register**. The page states *"Your account will require approval from a Lead or above."* Until approved, login shows *"Your account is pending approval by a Lead or above."*
- **Forgot password?** on the login page emails a reset link (see §14 for when email is only logged).
- Disabled or rejected accounts see *"Your account is disabled. Contact an administrator."*
- **Logout** is at the right end of the top bar.

## 3. Roles and permissions

| Role | What it can do |
|---|---|
| **BOT** | View only: products, groups, reservations, swaps, announcements. |
| **USER** | Everything BOT can, plus reserve/unreserve own reservations, raise Swap requests, Export. |
| **LEAD** | USER abilities plus: unreserve anyone's reservation, approve/reject Swaps, request/approve/return **Borrow**, approve new users, manage groups, Excel Import, view **Developer Logs**. |
| **MANAGER** | LEAD abilities plus manage users, products/templates and announcements, and view **Logs** (audit). |
| **OWNER** | All permissions. |

Additional rules:

- Approving a specific Swap or Borrow is further limited to the **routed approvers** for that request (§9, §11); Owner can always act; nobody can approve their own Borrow request.
- **Swap** access is by group: you can only swap setups belonging to your group (or a group holding it through an active Borrow). A setup with no group is open to everyone with Swap permission.
- Only LEAD, MANAGER and OWNER may use **Borrow**, and the requester must belong to a group.

## 4. Top bar and dashboard

Top-bar items (shown per permission): **Dashboard**, **Setups**, **Announcements**, **Swap Approvals**, **Approvals**, **Borrow**, **User Approvals** (new user registrations), **Products**, **Groups**, **Users**, **Logs**, **Developer Logs**, and a **Documentation** menu (**User Guide**, **API Guide**; available once the Sphinx site has been built).

> **Approvals** lists **Swap and Borrow** approvals (everyone). **User Approvals** (leads and managers) is for approving new user registrations.

The **Dashboard** shows *Welcome, <name>*, cards for **Total Setups**, **Available Now**, **My Active Reservations** and **Pending User Approvals** (pending user registrations, for users who can approve them), plus shortcuts **Browse Setups & Reserve** and **View Announcements**.

## 5. Product selection

**Setups** opens **Select a Product**: one card per product (with the number of setups and how many are available) and **View All Setups**. Choose a product to open its table.

## 6. The setups table ("Reservation Table")

Columns: Sr No, Status, IP, Hostname, User, Form Factor, Capacity, SSD, HDD, Aardvark, Quarch, APC, Remote Server, Hardware Info, Adapter, Owner, Location, any **product-specific columns**, Reserved Time, Remarks, Actions.

- **Status** badge: AVAILABLE, RESERVED, MAINTENANCE or RETIRED. A **Borrowed by <group>** badge next to the hostname means the setup is currently lent to that group.
- **User** and **Reserved Time** show who reserved it and the window.
- Toolbar: **Export**, **Reserve**, **Swap**, **Unreserve**, **Borrow / Return** (leads), **Approvals**. Reserve/Swap/Unreserve stay disabled until valid rows are ticked.
- A row's checkbox is enabled only when the setup is AVAILABLE or reserved by you.

### Search and filter
- Drop-downs **All Products**, **All Groups**, **All Statuses**, a **Location** box and the search box (*Search IP, hostname, hardware...*) reload the table.
- Each column header has a **Filter** box that filters the rows on the page.
- Pagination appears below the table.

### Setup details
- The **columns icon** in **Actions** opens **Original vs Current — <hostname>** (§10).
- Managers/Owners also see a **pencil** (Edit setup) opening **Edit Setup**: Product, Status, Group, IP Address, Hostname, Owner, Location, Form Factor, Capacity, Adapter, SSD, HDD, Aardvark, Quarch, APC, Remote Server, Hardware Info, Remarks and any **Custom Fields**. Saving an edit makes the values you changed the new **Original** values (fields you did not touch keep theirs).

## 7. Reserve

1. Tick one or more **AVAILABLE** rows and click **Reserve**.
2. Fill **From** / **Until** (until must be after from), **Reason / remarks** (stored as Remarks), and optionally **Announce this reservation via** options (§13).
3. Submit. The setup becomes RESERVED and shows you in **User** and the window in **Reserved Time**.

Errors: *"Reservations must start at least N minute(s) from now."* (only if the administrator set a minimum lead time); *"Setup is already reserved for an overlapping time window."*; *"Setup is currently maintenance/retired and cannot be reserved."*. When several setups are reserved together, each is processed separately and the result reports any that failed.

## 8. Unreserve

Tick your reserved rows (Leads and Managers can also unreserve others') and click **Unreserve**, confirm **Unreserve**. The setup returns to AVAILABLE. Reservations whose window ends are completed automatically by a background job. Unreserving is never blocked by a pending Swap or Borrow.

## 9. Swap

A Swap exchanges the value of one or more hardware fields between two setups, after approval.

1. Tick **exactly one** setup and click **Swap** (**Swap Column(s) Between Setups**). No reservation is needed.
2. **Swap with**: pick another setup you have access to. Only setups that share at least one swappable column are listed. By default only setups of the **same product** are offered (an administrator setting can allow cross-product swaps).
3. **Column(s) to exchange**: columns present on **both** setups are selectable; others are greyed out with "not on both setups". Select none to swap every common column. Ctrl/Cmd-click to select several.
4. Optionally fill **Reason (optional)**, **Start time (optional)**, **End time (optional)** and the announcement options (**Announce this swap request via**). The routed approving leads are always emailed.
5. Submit. The request is **PENDING**.

Swappable columns are the fixed hardware fields (SSD, HDD, hardware info, capacity, form factor, adapter, Aardvark, Quarch, APC, remote server) plus product custom columns that exist on both setups.

### Swap approval and status
- Open **Approvals** (check-square icon). **Pending Approvals** lists requests you can decide (**Approve** / **Reject**, optional rejection reason) or that are yours (**Cancel my request**). Others see *"You are not one of the routed approvers…"*.
- Routing: for a swap, approval goes to the Lead/Manager of the **requester's setup group** and of every group above it in the configured hierarchy. Any **one** may approve. If nothing is configured, any Lead/Manager/Owner can approve.
- On approval the values are exchanged and the **Current** hardware changes; **Original** never changes. Reject/cancel change nothing.
- **Approval History** shows Approved (COMPLETED), REJECTED, CANCELLED and EXPIRED requests with the decider. The older **Swap Approvals** page lists pending swaps with the same actions.
- **Show only my requests** (toggle, top right of the page) narrows either tab to your own requests.

Errors: *"These two setups have no swappable columns in common."*; *"Requested setup must differ from the current setup."*; *"You may only request a swap for setups belonging to your group…"*; *"Setup … cannot be part of a swap"* (maintenance/retired).

## 10. Original vs Current hardware and changed cells

- In the table, a cell whose Current value differs from its Original value is **highlighted** (amber). One changed field highlights one cell; several changed fields highlight each cell. Hover a highlighted cell for *Changed from original*.
- The **columns icon** (amber when the setup has changes) opens **Original vs Current**: *Field / Original / Current*, a **N field(s) changed** badge, a **Borrowed by** badge if applicable, and **Change history** (when, field, from, to, source such as SWAP #id, by whom).

## 11. Borrow

Borrow temporarily gives your group access to a setup owned by another group. The owning group and the hardware values never change. (LEAD, MANAGER, OWNER only.)

1. Open **Borrow** (or **Borrow / Return** on the Setups page) and click **New Borrow Request**.
2. **Source lead (whose setup you need)**: pick the lead of the other group.
3. **Setup needed**: the setups of that lead's group that are free to borrow. **Hardware required**: *Entire setup* or one hardware field (informational — access is granted per setup).
4. Fill **Reason**, **Start time**, **End time** (must be in the future) and announcement options. Routed leads are always emailed.
5. Submit. The request appears under **Pending approval** with *Borrower*, *Source* and *Approval status: awaiting any ONE of <leads>*.

### Borrow approval and status
- Approval goes to the source group's Lead/Manager, its parent's lead and the sibling groups under that parent (configured Borrow hierarchy). Any **one** may **Approve** or **Reject**; you cannot decide your own request. Owner can always decide.
- Approve, Reject and Cancel are available on the **Borrow** page cards and under **Approvals**.
- After approval the request moves to **Currently borrowed** (Borrower, Source, Approved by, Window, **Overdue** badge if the end time has passed) and the borrowing group gains access; the setup shows **Borrowed by <group>** and is listed under the borrowing group. While lent out, the owning group cannot raise Swaps on it.
- Other states: REJECTED, CANCELLED, EXPIRED (a pending request whose end time passed), RETURNED. The **History** table lists them.
- Conflicts: *"Setup … already has a pending or active borrow request."*, *"Setup … is already borrowed by another group."*, *"Your group already holds this setup…"*.

### Return / Get back
In **Currently borrowed**, click **Return / Get back** and confirm. Allowed for the requester, another lead of the borrowing group, a routed approver of the source group, or an Owner. The borrowing group's access ends, the owner's access is restored, the status becomes RETURNED, and the requester and source leads are emailed (plus any announcement channels chosen on the request). Borrowed access does **not** end automatically at the end time; overdue borrows are only flagged.

## 12. Products and templates (Managers/Owners)

- **Products** → **Product Management**: **New Product** (Name, Description), edit, delete (blocked while setups use it), **Import Setups**, **Blank Template**.
- **Design Template** (per product): **Add Custom Column** with *Column Name (key, used in Excel header)*, *Display Label*, *Type* (String, Integer, Float, Boolean, Date, DateTime, Dropdown), *Required*, *Default Value*, *Allowed Values* (Dropdown). Columns can be reordered, deleted, imported (**Import Excel**) and exported (**Export**). Custom columns appear in the setups table and in the Edit Setup dialog.

## 13. Announcements and email notifications

- **Announcements** lists active announcements; Managers/Owners use **New Announcement** (*Title, Message, Priority LOW/NORMAL/HIGH/CRITICAL, Start, End*) and **Show active only**.
- On Reserve, Swap and Borrow you may tick **Wall Message** (posts an announcement for 7 days), **Mail Leads**, **Groups** (group members) or **All Users**, and add a custom message.
- Swap and Borrow requests **always** email the routed approvers; approval/rejection emails the requester (Borrow); Return emails the requester and source leads.
- Reservations only email leads if you tick **Mail Leads**.

## 14. Excel import and export

- **Export** (Setups toolbar, and Product template page) downloads an `.xlsx` of the current filter/product (includes custom columns for a product export). Requires export permission (USER and above).
- **Import**: on the **Products** page (Managers and Owners) use **Import Setups**, or a product's **Design Template → Import Excel**, then upload an `.xlsx` and click **Upload & Import**. (Leads hold the import permission but the Products page itself is Manager/Owner only.) Required headers: `ip_address`, `hostname`, `location`; use **Blank Template** for the exact layout. Rows are matched to existing setups by IP or hostname (existing setups are updated, others created). If any row has an error the **whole import is rejected** and errors are listed by row.
- Unknown columns in a product import raise **New columns detected**: choose **Add to Template & Import** or **Reject Import**.
- Imports and exports are recorded in Excel log files and the audit log. Importing does **not** reset Original hardware (only Edit Setup does).
- If SMTP is not enabled on the server, emails are written to the server log instead of being sent.

## 15. History and audit

- **Logs** (**Audit Logs**, Managers and Owners): filter by **All Actions**, **Entity type**, **Entity ID**, **User ID**. Reservations, swaps, borrows, logins, imports/exports and admin changes are recorded.
- **Developer Logs** (Leads and above): browse/download server log files.
- Swap and Borrow history: **Approvals → Approval History**, the Borrow **History** table, and **Change history** in Original vs Current.

## 16. Common workflows

- **Reserve a lab setup:** Setups → product → tick AVAILABLE row → Reserve → dates + reason → submit.
- **Fix a hardware part between two of your group's setups:** tick one → Swap → pick partner → pick column → reason → submit; a routed lead approves in Approvals.
- **Borrow another group's setup:** Borrow → New Borrow Request → source lead → setup → dates → submit; wait for any routed lead; when done click Return / Get back.
- **Approve a request:** Approvals → Pending Approvals → Approve/Reject.
- **See what changed on a setup:** highlighted cells, or the columns icon.

## 17. Common errors and troubleshooting

| Message / symptom | Cause / fix |
|---|---|
| Invalid username or password. | Check credentials; use **Forgot password?**. |
| Your account is pending approval… | A Lead or above must approve you in **User Approvals**. |
| Setup is already reserved for an overlapping time window. | Choose another window or setup. |
| reserved_until must be after reserved_from. | Set **Until** later than **From**. |
| You are not one of the routed approvers… | Only routed leads (or Owner) may decide; ask one of them. |
| Swap button disabled | Tick exactly one row (only AVAILABLE rows or your own reservations can be ticked). |
| No other setup you have access to shares a swappable column | Partner must be in your group and share a column. |
| Borrow menu missing / 403 | Borrow is for Lead, Manager, Owner. |
| Cell not highlighted after Edit Setup | Edit Setup resets Original for fields you changed. |
| No email received | SMTP may be disabled; the message is only logged. |
| 403 / "You do not have permission" | Your role lacks the permission. |

## 18. FAQ

- **Does Swap need a reservation?** No. **Does Borrow?** No.
- **Can the hierarchy give me access to other groups' setups?** No. It only decides who may approve.
- **Does approving a Swap change Original hardware?** No, only Current.
- **Why is a Borrow still active after its end time?** Return is manual; it shows **Overdue**.
- **Can I swap between different products?** Not by default: swaps are limited to setups of the same product. If the administrator turns that rule off, cross-product swaps work for columns present on both setups.
