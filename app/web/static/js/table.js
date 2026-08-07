/**
 * Reservation table behavior: checkbox eligibility rules, Reserve/Swap/
 * Unreserve button enable-state, and client-side per-column text filters.
 * Re-initialized after every HTMX swap of the table body (see the
 * htmx:afterSwap listener at the bottom).
 */
(function () {
    "use strict";

    function getSelectedRows() {
        return Array.from(document.querySelectorAll(".rms-setup-checkbox:checked"))
            .map(function (checkbox) {
                return checkbox.closest("tr");
            });
    }

    function updateActionButtons() {
        const selectedRows = getSelectedRows();
        const reserveBtn = document.getElementById("reserveActionBtn");
        const swapBtn = document.getElementById("swapActionBtn");
        const unreserveBtn = document.getElementById("unreserveActionBtn");
        if (!reserveBtn || !swapBtn || !unreserveBtn) return;

        const allAvailable = selectedRows.length > 0 && selectedRows.every(function (row) {
            return row.dataset.status === "AVAILABLE";
        });
        const allMine = selectedRows.length > 0 && selectedRows.every(function (row) {
            return row.dataset.mine === "true";
        });

        reserveBtn.disabled = !allAvailable;
        unreserveBtn.disabled = !allMine;
        swapBtn.disabled = !(selectedRows.length === 1 && allMine);

        const selectedSetupIds = selectedRows.map(function (row) { return row.dataset.setupId; }).join(",");
        const selectedReservationIds = selectedRows
            .map(function (row) { return row.dataset.reservationId; })
            .filter(Boolean)
            .join(",");

        reserveBtn.setAttribute("data-setup-ids", selectedSetupIds);
        unreserveBtn.setAttribute("data-reservation-ids", selectedReservationIds);
        swapBtn.setAttribute("data-reservation-ids", selectedReservationIds);
        swapBtn.setAttribute("data-current-setup-id", selectedRows.length ? selectedRows[0].dataset.setupId : "");
    }

    function initCheckboxes() {
        document.querySelectorAll(".rms-setup-checkbox").forEach(function (checkbox) {
            checkbox.addEventListener("change", updateActionButtons);
        });
        updateActionButtons();
    }

    function initColumnFilters() {
        const filterInputs = document.querySelectorAll(".rms-column-filter");
        filterInputs.forEach(function (input) {
            input.addEventListener("input", applyColumnFilters);
            input.addEventListener("change", applyColumnFilters);
        });
    }

    function applyColumnFilters() {
        const filters = Array.from(document.querySelectorAll(".rms-column-filter"))
            .map(function (input) {
                return { column: parseInt(input.dataset.column, 10), value: input.value.trim().toLowerCase() };
            })
            .filter(function (f) { return f.value.length > 0; });

        const rows = document.querySelectorAll("#setupsTableBody tr");
        rows.forEach(function (row) {
            const cells = row.querySelectorAll("td");
            const matches = filters.every(function (filter) {
                const cell = cells[filter.column];
                if (!cell) return true;
                return cell.textContent.trim().toLowerCase().indexOf(filter.value) !== -1;
            });
            row.style.display = matches ? "" : "none";
        });
    }

    function initTable() {
        initCheckboxes();
        initColumnFilters();
    }

    document.addEventListener("DOMContentLoaded", initTable);
    document.body.addEventListener("htmx:afterSwap", function (evt) {
        if (evt.detail.target && evt.detail.target.id === "setupsTableContainer") {
            initTable();
        }
    });
})();
