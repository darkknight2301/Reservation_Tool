/**
 * Core application script: dark mode, toast notifications, confirmation
 * dialogs, and global HTMX event wiring (loading indicator + error toasts).
 * Loaded on every page via base.html.
 */
(function () {
    "use strict";

    // ---------------------------------------------------------------
    // Dark mode
    // ---------------------------------------------------------------
    const THEME_STORAGE_KEY = "rms-theme";
    const rootEl = document.documentElement;
    const themeToggleBtn = document.getElementById("themeToggleBtn");

    function applyTheme(theme) {
        rootEl.setAttribute("data-bs-theme", theme);
        if (themeToggleBtn) {
            const icon = themeToggleBtn.querySelector("i");
            if (icon) {
                icon.className = theme === "dark" ? "bi bi-sun" : "bi bi-moon-stars";
            }
        }
    }

    const storedTheme = localStorage.getItem(THEME_STORAGE_KEY);
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    applyTheme(storedTheme || (prefersDark ? "dark" : "light"));

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener("click", function () {
            const current = rootEl.getAttribute("data-bs-theme");
            const next = current === "dark" ? "light" : "dark";
            applyTheme(next);
            localStorage.setItem(THEME_STORAGE_KEY, next);
        });
    }

    // ---------------------------------------------------------------
    // Toast notifications
    // ---------------------------------------------------------------
    const TOAST_ICONS = {
        success: "bi-check-circle-fill text-success",
        error: "bi-x-circle-fill text-danger",
        warning: "bi-exclamation-triangle-fill text-warning",
        info: "bi-info-circle-fill text-info",
    };

    /**
     * Show a Bootstrap toast.
     * @param {string} message
     * @param {"success"|"error"|"warning"|"info"} type
     */
    window.showToast = function (message, type) {
        type = type || "info";
        const container = document.getElementById("toastContainer");
        if (!container) return;

        const toastEl = document.createElement("div");
        toastEl.className = "toast align-items-center border-0";
        toastEl.setAttribute("role", "alert");
        toastEl.innerHTML =
            '<div class="d-flex">' +
            '<div class="toast-body"><i class="bi ' + (TOAST_ICONS[type] || TOAST_ICONS.info) + ' me-2"></i>' +
            escapeHtml(message) +
            "</div>" +
            '<button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast"></button>' +
            "</div>";
        container.appendChild(toastEl);

        const toast = new bootstrap.Toast(toastEl, { delay: 5000 });
        toastEl.addEventListener("hidden.bs.toast", function () {
            toastEl.remove();
        });
        toast.show();
    };

    function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value;
        return div.innerHTML;
    }

    // ---------------------------------------------------------------
    // Confirmation dialog
    // ---------------------------------------------------------------
    const confirmModalEl = document.getElementById("confirmModal");
    const confirmModal = confirmModalEl ? new bootstrap.Modal(confirmModalEl) : null;
    const confirmTitleEl = document.getElementById("confirmModalTitle");
    const confirmBodyEl = document.getElementById("confirmModalBody");
    const confirmAcceptBtn = document.getElementById("confirmModalAcceptBtn");
    let pendingConfirmCallback = null;

    /**
     * Prompt the user to confirm a destructive/important action.
     * @param {string} title
     * @param {string} body
     * @param {Function} onConfirm - called if the user accepts
     */
    window.confirmAction = function (title, body, onConfirm) {
        if (!confirmModal) return;
        confirmTitleEl.textContent = title;
        confirmBodyEl.textContent = body;
        pendingConfirmCallback = onConfirm;
        confirmModal.show();
    };

    if (confirmAcceptBtn) {
        confirmAcceptBtn.addEventListener("click", function () {
            if (typeof pendingConfirmCallback === "function") {
                pendingConfirmCallback();
            }
            pendingConfirmCallback = null;
            confirmModal.hide();
        });
    }

    // Declarative confirmation: any element with data-confirm-title /
    // data-confirm-body triggers the modal before htmx proceeds.
    document.body.addEventListener("htmx:confirm", function (evt) {
        const el = evt.detail.elt;
        if (el && el.hasAttribute("data-confirm-title")) {
            evt.preventDefault();
            window.confirmAction(
                el.getAttribute("data-confirm-title"),
                el.getAttribute("data-confirm-body") || "Are you sure?",
                function () {
                    evt.detail.issueRequest(true);
                }
            );
        }
    });

    // ---------------------------------------------------------------
    // Global HTMX wiring: loading overlay + error toasts
    // ---------------------------------------------------------------
    document.body.addEventListener("htmx:beforeRequest", function () {
        document.body.classList.add("rms-loading");
    });
    document.body.addEventListener("htmx:afterRequest", function () {
        document.body.classList.remove("rms-loading");
    });

    document.body.addEventListener("htmx:responseError", function (evt) {
        let message = "Something went wrong. Please try again.";
        try {
            const parsed = JSON.parse(evt.detail.xhr.responseText);
            if (parsed && parsed.error && parsed.error.message) {
                message = parsed.error.message;
            }
        } catch (err) {
            /* response was not JSON; fall back to the default message */
        }
        window.showToast(message, "error");
    });

    document.body.addEventListener("htmx:sendError", function () {
        window.showToast("Network error: could not reach the server.", "error");
    });

    // Server-triggered toasts: responses may set
    // HX-Trigger: {"showToast": {"message": "...", "type": "success"}}
    document.body.addEventListener("showToast", function (evt) {
        window.showToast(evt.detail.message, evt.detail.type || "info");
    });

    // Server-triggered modal close: responses may set
    // HX-Trigger: {"closeDialog": {}}
    document.body.addEventListener("closeDialog", function () {
        document.querySelectorAll(".modal.show").forEach(function (modalEl) {
            const instance = bootstrap.Modal.getInstance(modalEl);
            if (instance) instance.hide();
        });
    });

    // Redirect helper: server responses may set
    // HX-Trigger: {"redirect": {"url": "/somewhere"}}
    document.body.addEventListener("redirect", function (evt) {
        window.location.href = evt.detail.url;
    });
})();
