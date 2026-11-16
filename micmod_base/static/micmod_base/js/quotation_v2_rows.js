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

    function currentMethodLabel(row) {
        const control = first(row, "#id_price_method_container select");
        const selected = control?.selectedOptions?.[0];
        const fallback = first(row, '[name="price-method_h"]')?.dataset.qv4Method || "";
        const method = control?.value || first(row, 'input[name$="-price_method"]')?.value || fallback;
        if (!method) return "—";
        if (method === "sales_admin") return "مصوب مدیر";

        // Prefer the human-readable price source from the *actual* form/price list.
        const label = selected?.textContent?.trim();
        if (selected?.value === method && label && !/^[-—]+$/.test(label)) {
            return label.split("|")[0].trim() || label;
        }
        let prices = [];
        try {
            prices = JSON.parse(first(row, 'textarea[name$="-price_json"]')?.value || "[]");
        } catch (_) {
            prices = [];
        }
        if (Array.isArray(prices)) {
            const match = prices.find((item) => item?.unique_title === method);
            if (match?.title) return String(match.title);
        }
        const known = {
            bazar: "قیمت بازار", price_market: "قیمت بازار",
            express: "اکسپرس", price_sheet1: "اکسپرس",
            air: "هوایی", price_sheet2: "هوایی",
            sea: "دریایی", price_sheet3: "دریایی",
        };
        return known[method] || method;
    }

    function syncInquiryBadge(row, type, title) {
        const badge = first(row, '[data-qv4-inquiry="' + type + '"]');
        if (!badge) return;

        function valueOf(suffix, fallback) {
            const field = first(row, 'input[name$="-' + suffix + '"]');
            if (!field) return fallback === "1";
            if (field.type === "checkbox") return field.checked;
            return /^(1|true|yes|on)$/i.test(String(field.value || "").trim());
        }

        const needed = valueOf("need_" + type + "_price_inquiry", badge.dataset.needed);
        const done = valueOf(type + "_price_inquiry_done", badge.dataset.done);
        const state = done ? "is-approved" : (needed ? "is-pending" : "is-none");
        badge.classList.remove("is-approved", "is-pending", "is-none");
        badge.classList.add(state);
        badge.dataset.needed = needed ? "1" : "0";
        badge.dataset.done = done ? "1" : "0";

        const symbol = first(badge, ".qv4-inquiry-symbol");
        if (symbol) symbol.textContent = done ? "✓" : needed ? "◷" : "—";
        badge.title = done
            ? "پاسخ استعلام " + title + " ثبت و تأیید شده"
            : needed
                ? "در انتظار تأیید پاسخ استعلام " + title
                : "استعلام " + title + " درخواست نشده";
        badge.setAttribute("aria-label", badge.title);
    }

    function syncHeading(row) {
        const sku = first(row, 'input[type="hidden"][name$="-goods_code"]');
        const skuLabel = first(row, ".qv3-sku");
        if (skuLabel && sku) {
            skuLabel.textContent = sku.value || "—";
            skuLabel.title = sku.value || "";
        }

        const name = first(row, 'textarea[name="-goods_name_lbl"]');
        const heading = first(row, ".qv3-product-title");
        if (name && heading && name.value.trim()) {
            heading.textContent = name.value.trim();
            heading.title = name.value.trim();
        }

        const qty = first(row, 'input[name$="-quantity"]');
        const qtyTarget = first(row, '[name="quantity_h"]');
        if (qty && qtyTarget) qtyTarget.textContent = fmt(number(qty.value), 0);

        const methodTarget = first(row, '[name="price-method_h"]');
        if (methodTarget) {
            methodTarget.textContent = currentMethodLabel(row);
            methodTarget.title = methodTarget.textContent;
        }

        const fee = first(row, 'input[name$="-final_price"]');
        const feeTarget = first(row, '[name="unit-price_h"]');
        if (fee && feeTarget) feeTarget.textContent = fmt(number(fee.value));

        for (const [source, target] of [
            ['[name="discount_value"]', '[name="discount_h"]'],
            ['[name="tax_value"]', '[name="tax_h"]'],
            ['[name="-total_price"]', '[name="total-price_h"]'],
        ]) {
            const from = first(row, source);
            const to = first(row, target);
            if (!from || !to) continue;
            const current = (from.textContent || "").trim();
            const parsed = number(current);
            to.textContent = Number.isFinite(parsed) ? fmt(parsed) : (current || "—");
        }

        syncInquiryBadge(row, "local", "داخلی");
        syncInquiryBadge(row, "foreign", "خارجی");
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
        const sections = Array.from(row.querySelectorAll(".qv3-detail-grid > details.qv3-panel"));
        const allOpen = sections.length > 0 && sections.every((item) => item.open);
        btn.textContent = allOpen ? "بستن همه" : "بازکردن همه";
        btn.setAttribute("aria-expanded", allOpen ? "true" : "false");
    }

    function syncCollapsedSummaries(row) {
        // These summaries intentionally read the user's current form values,
        // never write to the form or change any financial data.
        const caption = (selector, value) => {
            const node = first(row, selector);
            if (node) node.textContent = value;
        };
        const value = (selector) => {
            const field = first(row, selector);
            return field?.value?.trim() || "";
        };
        const checked = (suffix) => Boolean(first(row, 'input[name$="-'+suffix+'"]')?.checked);
        const inquiryCount = first(row, "#all_price_count")?.textContent?.trim() || "(0)";
        const internal = checked("local_price_inquiry_done") ? "تکمیل" : checked("need_local_price_inquiry") ? "در انتظار" : "—";
        const foreign = checked("foreign_price_inquiry_done") ? "تکمیل" : checked("need_foreign_price_inquiry") ? "در انتظار" : "—";
        caption('[data-qv3-summary="inquiry"]',
            inquiryCount + " قیمت · داخلی: " + internal + " · خارجی: " + foreign);

        const reserveStatus = first(row, ".qv3-row-chips .qv3-chip")?.textContent.trim() || "بدون تخصیص";
        const alt = value('input[name$="-goods_code_alt"]') || "—";
        caption('[data-qv3-summary="stock"]', reserveStatus + " · جایگزین: " + alt);

        const delivery = first(row, "#lead_time_text")?.textContent.trim() || "—";
        const supplyDate = value('input[name$="-supply_date"]') ||
            first(row, 'select[name$="-supply_date"]')?.selectedOptions?.[0]?.textContent || "—";
        const assigned = first(row, 'select[name$="-assigned_trade_user"]')?.selectedOptions?.[0]?.textContent ||
            first(row, ".qv3-panel-delivery .qv3-readonly-detail strong")?.textContent || "—";
        caption('[data-qv3-summary="delivery"]',
            "تحویل: " + delivery + " · تعهد: " + supplyDate + " · مسئول: " + assigned);

        const note = value('textarea[name$="-sales_description"]') ||
            value('textarea[name$="-description"]') || "بدون توضیح ثبت‌شده";
        caption('[data-qv3-summary="notes"]', note.slice(0, 90));

        const pack = first(row, "#moq")?.textContent.trim() || "—";
        const customerCode = value('input[name$="-customer_goods_code"]') || "—";
        caption(".qv3-product-extra>summary span",
            "بسته‌بندی: " + pack + " عدد · کد مشتری: " + customerCode);
    }

    function scheduleHeading(row) {
        // Legacy quotation1.js updates several fields through price AJAX.
        // Update after its synchronous changes without changing its handlers.
        requestAnimationFrame(() => {
            syncHeading(row);
            syncCollapsedSummaries(row);
        });
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

        // Several legacy price methods update financial spans programmatically
        // without dispatching input/change. Observe those changes so the
        // collapsed summary always reflects the current calculation.
        const totals = first(row, ".qv3-financial-breakdown");
        if (totals) {
            const totalsObserver = new MutationObserver(() => scheduleHeading(row));
            totalsObserver.observe(totals, {
                childList: true, characterData: true, subtree: true,
            });
        }
        // The price-method Select is dynamically created by quotation1.js.
        const methodContainer = first(row, "#id_price_method_container");
        if (methodContainer) {
            const methodObserver = new MutationObserver(() => scheduleHeading(row));
            methodObserver.observe(methodContainer, { childList: true });
        }

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
            const panels = Array.from(row.querySelectorAll(".qv3-detail-grid > details.qv3-panel"));
            const allOpen = panels.every((item) => item.open);
            panels.forEach((item) => {
                item.open = !allOpen;
            });
            syncDetailToggle(row);
        });
        row.querySelectorAll("details.qv3-panel").forEach((panel) => {
            panel.addEventListener("toggle", () => syncDetailToggle(row));
        });

        // The legacy Select2 AJAX/search handlers remain authoritative.
        // The dropdown has the row as its dropdownParent, so raise this row
        // above sticky bars and neighbouring cards only while it is open.
        if (window.jQuery) {
            const $row = window.jQuery(row);
            const select2Controls = ".goods_code, .goods_code_alt, .selected_price_code";
            $row.on("select2:select", select2Controls, () => scheduleHeading(row));
            $row.on("select2:open", select2Controls, () => {
                row.classList.add("qv3-select2-active");
                requestAnimationFrame(() => {
                    const search = row.querySelector(".select2-container--open .select2-search__field");
                    search?.focus();
                });
            });
            $row.on("select2:close", select2Controls, () => {
                row.classList.remove("qv3-select2-active");
            });
        }

        revealErrors(row);
        syncDelete(row);
        syncExpanded(row);
        syncDetailToggle(row);
        syncCollapsedSummaries(row);
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

    // In large quotations every valid row starts compact, so many rows
    // fit in a single viewport. Keep a lone row and validation errors open.
    window.addEventListener("load", () => {
        const rows = Array.from(list.querySelectorAll(".qv3-item"));
        rows.forEach((row) => {
            if (rows.length <= 1 || first(row, ".qv3-row-errors") || first(row, ".errorlist")) return;
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
