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
        // A response can be shown only when the corresponding inquiry is requested.
        const approved = needed && done;
        const state = approved ? "is-approved" : (needed ? "is-pending" : "is-none");
        badge.classList.remove("is-approved", "is-pending", "is-none");
        badge.classList.add(state);
        badge.dataset.needed = needed ? "1" : "0";
        badge.dataset.done = done ? "1" : "0";
        badge.hidden = !needed;

        const symbol = first(badge, ".qv4-inquiry-symbol");
        if (symbol) symbol.textContent = approved ? "✓" : needed ? "◷" : "—";
        badge.title = approved
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
        const inquiryBlock = first(row, ".qv4-cell-inquiries");
        const anyNeeded = Array.from(row.querySelectorAll("[data-qv4-inquiry]"))
            .some((badge) => !badge.hidden);
        if (inquiryBlock) inquiryBlock.hidden = !anyNeeded;
        first(row, ".qv4-summary-grid")?.classList.toggle("qv4-no-inquiry", !anyNeeded);
    }

    function syncExpanded(row) {
        const header = first(row, ".qv3-row-header");
        if (!header) return;
        const isOpen = expanded(row);
        // Production formset.js toggles active-form opposite to the actual
        // body visibility. Normalize that state for consistent border radius.
        header.setAttribute("aria-expanded", isOpen ? "true" : "false");
        header.classList.toggle("active-form", isOpen);
        row.classList.toggle("qv3-is-expanded", isOpen);
        if (!isOpen) syncHeading(row);
    }

    function persistRowOrder() {
        // Match the established base.js Sortable onEnd index contract.
        // Do not renumber .counter: legacy price callbacks use it to locate
        // the formset index (which must not change when merely reordering).
        Array.from(list.querySelectorAll(":scope > .qv3-item")).forEach((item, index) => {
            const position = item.querySelector('input[id*="-index"]');
            if (position) position.value = String(index);
        });
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

        const handle = first(row, ".qv4-drag-handle");
        if (handle) {
            // Clicking the drag handle should never toggle the accordion.
            handle.addEventListener("click", (event) => event.stopPropagation());
            handle.addEventListener("keydown", (event) => {
                if (!["ArrowUp", "ArrowDown", "Enter", " "].includes(event.key)) return;
                event.stopPropagation();
                event.preventDefault();
                if (!["ArrowUp", "ArrowDown"].includes(event.key)) return;
                const sibling = event.key === "ArrowUp"
                    ? row.previousElementSibling : row.nextElementSibling;
                if (!sibling?.classList.contains("qv3-item")) return;
                if (event.key === "ArrowUp") list.insertBefore(row, sibling);
                else list.insertBefore(sibling, row);
                persistRowOrder();
                handle.focus();
            });
        }

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

        attachWideGoodsDropdown(row);

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



    function attachWideGoodsDropdown(row) {
        if (!window.jQuery) return;
        const $row = window.jQuery(row);
        const field = row.querySelector(".qv3-product-selector .goods_code");
        if (!field) return;
        let dropdown = null;
        let rafId = null;
        let observing = false;

        function positionDropdown() {
            if (!dropdown || !row.contains(dropdown)) return;
            const selection = field.querySelector(".select2-container") || field;
            const rect = selection.getBoundingClientRect();
            const viewportWidth = document.documentElement.clientWidth;
            const viewportHeight = window.innerHeight;
            const gap = 10;
            const right = Math.max(gap, viewportWidth - rect.right);
            const width = Math.max(0, Math.min(viewportWidth * 0.9, viewportWidth - right - gap));
            const panelHeight = Math.min(320, dropdown.getBoundingClientRect().height || 250);
            const below = Math.max(0, viewportHeight - rect.bottom - gap);
            const above = Math.max(0, rect.top - gap);
            const openAbove = below < Math.min(230, panelHeight) && above > below;
            const top = openAbove ? Math.max(gap, rect.top - panelHeight - 3) : rect.bottom + 3;

            dropdown.style.setProperty("--qv5-goods-top", Math.round(top) + "px");
            dropdown.style.setProperty("--qv5-goods-right", Math.round(right) + "px");
            dropdown.style.setProperty("--qv5-goods-width", Math.round(width) + "px");
            dropdown.style.setProperty("--qv5-goods-max-height",
                Math.round(Math.max(110, openAbove ? above : below)) + "px");
        }

        function schedulePosition() {
            if (rafId !== null) cancelAnimationFrame(rafId);
            rafId = requestAnimationFrame(() => {
                rafId = null;
                positionDropdown();
            });
        }

        function stop() {
            if (dropdown) {
                dropdown.classList.remove("qv5-wide-goods-dropdown");
            }
            dropdown = null;
            if (observing) {
                window.removeEventListener("resize", schedulePosition);
                document.removeEventListener("scroll", schedulePosition, true);
                observing = false;
            }
            if (rafId !== null) {
                cancelAnimationFrame(rafId);
                rafId = null;
            }
        }

        $row.on("select2:open", ".qv3-product-selector .goods_code", () => {
            // dropdownParent is the current row; Select2 creates an absolute
            // dropdown container inside it. The v2-only CSS switches that
            // container to viewport-fixed positioning using these variables.
            dropdown = Array.from(row.querySelectorAll(".select2-container--open"))
                .find(el => el.querySelector(".select2-dropdown")) || null;
            if (!dropdown) return;
            dropdown.classList.add("qv5-wide-goods-dropdown");
            positionDropdown();
            if (!observing) {
                window.addEventListener("resize", schedulePosition);
                document.addEventListener("scroll", schedulePosition, true);
                observing = true;
            }
        });
        $row.on("select2:close", ".qv3-product-selector .goods_code", stop);
    }

    function isEmptyExtraRow(row) {
        // Only exclude *unused* new items. Do not drop a partially completed
        // row: server validation must still report its missing requirements.
        if (row.querySelector('input[name$="-id"]')?.value?.trim()) return false;
        const meaningful = [
            "goods_code", "itemid", "quantity", "customer_goods_code",
            "customer_goods_name", "goods_code_alt", "description",
            "sales_description", "price_target", "pre_paid_amount",
            "assigned_trade_user", "assigned_trade_user2", "supply_date",
            "need_local_price_inquiry", "need_foreign_price_inquiry",
            "selected_price_code", "customer_request_item", "goods_name",
            "item_in_china", "task_start", "task_start2", "has_delay"
        ];
        const prefix = row.dataset.qv3Row + "-";
        for (const suffix of meaningful) {
            const field = Array.from(row.querySelectorAll("[name]"))
                .find(el => el.name === prefix + suffix);
            if (!field) continue;
            if (field.type === "checkbox") {
                if (field.checked) return false;
            } else if (String(field.value || "").trim() &&
                       !["false", "off"].includes(String(field.value).trim().toLowerCase())) {
                return false;
            }
        }
        const nestedPrefix = "qir-" + row.dataset.qv3Row + "-";
        for (const field of row.querySelectorAll("[name]")) {
            if (!field.name.startsWith(nestedPrefix)) continue;
            if (!/(?:-description|-supplier|-price|-quantity)$/.test(field.name)) continue;
            const value = String(field.value || "").trim();
            if (/(?:-price|-quantity)$/.test(field.name) && ["0", "0.0", "0.00"].includes(value)) {
                continue; // legacy initializer's numeric zero is not user data
            }
            if (field.type === "checkbox" ? field.checked : value) {
                return false;
            }
        }
        return true;
    }

    function trimUnusedExtraRowsBeforeSubmit() {
        const total = document.querySelector('input[name$="-TOTAL_FORMS"]');
        const initial = document.querySelector('input[name$="-INITIAL_FORMS"]');
        if (!total || !initial) return;

        const prefix = total.name.slice(0, -"-TOTAL_FORMS".length);
        let count = Number(total.value);
        const initialCount = Number(initial.value);
        if (!Number.isInteger(count) || !Number.isInteger(initialCount)) return;
        // Some workflow submit buttons are not handled by the legacy formset
        // button-click counter. Recompute the highest real prefix index so
        // dynamically added items are never lost, even after reordering.
        const indices = Array.from(list.querySelectorAll(".qv3-item"))
            .map(el => el.dataset.qv3Row || "")
            .filter(prefixValue => prefixValue.startsWith(prefix + "-"))
            .map(prefixValue => Number(prefixValue.slice(prefix.length + 1)))
            .filter(n => Number.isInteger(n) && n >= 0);
        count = Math.max(initialCount, 1, ...indices.map(n => n + 1));
        // Keep a single placeholder when there are no other forms: production
        // core/views.py still reads self.formset.forms[0] to detect nested forms.
        const minimum = Math.max(1, initialCount);
        while (count > minimum) {
            const row = Array.from(list.querySelectorAll(".qv3-item"))
                .find(el => el.dataset.qv3Row === prefix + "-" + (count - 1));
            if (!row || !isEmptyExtraRow(row)) break;
            row.remove();
            count -= 1;
        }
        total.value = String(count);
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

    // Preserve contiguous parent formset indices after trimming *only* the
    // unused trailing extra(s). Server still guards against empty placeholders.
    document.querySelector("#main-form")?.addEventListener("submit", () => {
        list.querySelectorAll(".qv3-item").forEach(syncHeading);
        trimUnusedExtraRowsBeforeSubmit();
    }, { capture: true });
})();
