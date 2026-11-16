/**
 * New quotation row workspace: UI behavior only.
 * Do not replace price calculation, formset, inquiry, or workflow functions.
 */
(function () {
    "use strict";
    if (!document.querySelector(".quotation-v2-full")) return;

    const list = document.getElementById("sortable-container");
    if (!list) return;

    const number = (value) => {
        if (value === null || value === undefined || String(value).trim() === "") return NaN;
        const n = Number(String(value).replace(/,/g, "").trim());
        return Number.isFinite(n) ? n : NaN;
    };
    const fmt = (value, decimals = 4) => (
        Number.isFinite(value)
            ? new Intl.NumberFormat("en-US", { maximumFractionDigits: decimals }).format(value)
            : "—"
    );
    const first = (row, selector) => row.querySelector(selector);
    const expanded = (row) => {
        const content = first(row, ".qv3-row-content");
        return !!content && !content.classList.contains("close");
    };

    function syncHeading(row) {
        const sku = first(row, 'input[type="hidden"][name$="-goods_code"]');
        const skuLabel = first(row, ".qv3-sku");
        if (skuLabel && sku) skuLabel.textContent = sku.value || "کد انتخاب نشده";

        const name = first(row, 'textarea[name="-goods_name_lbl"]');
        const heading = first(row, ".qv3-product-title");
        if (name && heading && name.value.trim()) heading.textContent = name.value.trim();

        const qty = first(row, 'input[name$="-quantity"]');
        const qtyTarget = first(row, '[name="quantity_h"]');
        if (qty && qtyTarget) qtyTarget.textContent = fmt(number(qty.value), 0);

        const fee = first(row, 'input[name$="-final_price"]');
        const feeTarget = first(row, '[name="unit-price_h"]');
        if (fee && feeTarget) feeTarget.textContent = fmt(number(fee.value));

        const amount = first(row, '[name="-total_price"]');
        const amountTarget = first(row, '[name="total-price_h"]');
        if (amount && amountTarget) {
            const n = number(amount.textContent);
            amountTarget.textContent = Number.isFinite(n) ? fmt(n) : amount.textContent.trim() || "—";
        }
    }

    function syncExpanded(row) {
        const header = first(row, ".qv3-row-header");
        if (!header) return;
        header.setAttribute("aria-expanded", expanded(row) ? "true" : "false");
        if (!expanded(row)) syncHeading(row);
    }

    function syncDelete(row) {
        const input = first(row, 'input[name$="-DELETE"]');
        row.classList.toggle("qv3-marked-delete", !!input?.checked);
    }

    function syncDetailToggle(row) {
        const btn = first(row, "[data-qv3-toggle-all]");
        if (!btn) return;
        const sections = Array.from(row.querySelectorAll("details.qv3-panel"));
        const allOpen = sections.length > 0 && sections.every((item) => item.open);
        btn.textContent = allOpen ? "بستن همه" : "بازکردن همه";
        btn.setAttribute("aria-expanded", allOpen ? "true" : "false");
    }

    function scheduleHeading(row) {
        // Legacy quotation1.js updates several fields through price AJAX.
        // Update after its synchronous changes without changing its handlers.
        requestAnimationFrame(() => syncHeading(row));
    }

    function revealErrors(row) {
        if (!first(row, ".qv3-row-errors") && !first(row, ".errorlist")) return;
        const header = first(row, ".qv3-row-header");
        const answer = first(row, ".qv3-row-content");
        if (answer?.classList.contains("close")) {
            answer.classList.remove("close");
            header?.classList.add("active-form");
        }
        row.querySelectorAll("details.qv3-panel").forEach((section) => {
            if (section.querySelector(".errorlist,[aria-invalid='true']")) section.open = true;
        });
        syncExpanded(row);
    }

    function attachRow(row) {
        if (row.dataset.qv3Ready) return;
        row.dataset.qv3Ready = "1";

        const header = first(row, ".qv3-row-header");
        const content = first(row, ".qv3-row-content");
        if (!header || !content) return;

        header.addEventListener("keydown", (event) => {
            if (event.target !== header) return;
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                header.click(); // Use production formset collapse handler.
            }
        });
        header.addEventListener("click", () => {
            // The production formset handler is registered before this UI handler.
            requestAnimationFrame(() => syncExpanded(row));
        });

        const observer = new MutationObserver(() => syncExpanded(row));
        observer.observe(content, { attributes: true, attributeFilter: ["class"] });

        row.addEventListener("input", (event) => {
            if (event.target.matches(
                'input[name$="-quantity"], input[name$="-final_price"], input[name$="-discount_per_item"], input[name$="-v2_manager_price"]'
            )) scheduleHeading(row);
        });
        row.addEventListener("change", (event) => {
            if (event.target.matches('input[name$="-DELETE"]')) syncDelete(row);
            scheduleHeading(row);
        });

        const toggle = first(row, "[data-qv3-toggle-all]");
        if (toggle) toggle.addEventListener("click", () => {
            const panels = Array.from(row.querySelectorAll("details.qv3-panel"));
            const allOpen = panels.every((item) => item.open);
            panels.forEach((item) => {
                item.open = !allOpen;
            });
            syncDetailToggle(row);
        });
        row.querySelectorAll("details.qv3-panel").forEach((panel) => {
            panel.addEventListener("toggle", () => syncDetailToggle(row));
        });

        // The legacy Select2 integration remains the source of truth.
        // React only after its existing handlers have updated the row fields.
        if (window.jQuery) {
            window.jQuery(row).on(
                "select2:select",
                ".goods_code, .goods_code_alt, .selected_price_code",
                () => scheduleHeading(row)
            );
        }

        revealErrors(row);
        syncDelete(row);
        syncExpanded(row);
        syncDetailToggle(row);
        scheduleHeading(row);
    }

    const attachAll = () => {
        list.querySelectorAll(".qv3-item").forEach(attachRow);
    };

    // The production formset.js appends cloned rows to #id_formset_container,
    // whereas the original rows sit inside #sortable-container. Normalize
    // that DOM location after its synchronous initialization has completed;
    // this also keeps drag-and-drop, overview totals and v2 bindings working.
    const host = document.getElementById("id_formset_container");
    function normalizeAddedRows() {
        if (!host) return;
        Array.from(host.children).forEach((child) => {
            if (child.classList.contains("qv3-item")) {
                list.appendChild(child);
            }
        });
        attachAll();
    }
    if (host) {
        const hostObserver = new MutationObserver(normalizeAddedRows);
        hostObserver.observe(host, { childList: true });
    }
    const rowsObserver = new MutationObserver(() => attachAll());
    rowsObserver.observe(list, { childList: true });
    normalizeAddedRows();

    // Let the legacy Select2 controls initialize while visible, then present a
    // useful compact overview instead of dozens of expanded historical rows.
    // Keep the first row and all rows with validation errors open.
    window.addEventListener("load", () => {
        const rows = Array.from(list.querySelectorAll(".qv3-item"));
        rows.forEach((row, index) => {
            if (index === 0 || first(row, ".qv3-row-errors") || first(row, ".errorlist")) return;
            const content = first(row, ".qv3-row-content");
            const header = first(row, ".qv3-row-header");
            if (!content || !header) return;
            content.classList.add("close");
            header.classList.remove("active-form");
            syncExpanded(row);
        });
    });

    // Standard formset submit does the actual save. Never intercept form POST.
    document.querySelector("#main-form")?.addEventListener("submit", () => {
        list.querySelectorAll(".qv3-item").forEach(syncHeading);
    }, { capture: true });
})();
