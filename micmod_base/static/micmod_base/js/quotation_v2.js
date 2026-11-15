/* Standalone quotation v2 editor: no globals or legacy quotation1.js hooks. */
(() => {
    "use strict";
    const root = document.querySelector(".v2-shell");
    if (!root) return;

    const asNumber = (value) => {
        if (value === null || String(value).trim() === "") return NaN;
        return Number(String(value).replace(/,/g, "").trim());
    };
    const format = (value) => new Intl.NumberFormat("en-US", {
        maximumFractionDigits: 4
    }).format(value);

    const pct = asNumber(root.dataset.selfDiscount) || 0;
    const taxRate = asNumber(root.dataset.taxRate) || 0;
    const officialValue = asNumber(root.dataset.officialValue) || 0;
    const isOfficial = root.dataset.official === "1";

    document.querySelectorAll("[data-pricing-form]").forEach((form) => {
        const dropdown = form.querySelector("[data-system-select]");
        const approved = form.querySelector("[data-manager-toggle]");
        const managerField = form.querySelector("[data-manager-field]");
        const managerPrice = managerField.querySelector("input");
        const discountField = form.querySelector("[data-discount-field]");
        const discountPrice = discountField.querySelector("input");
        const priceDisplay = form.querySelector("[data-preview-price]");
        const hint = form.querySelector("[data-preview-hint]");
        const row = form.closest("[data-v2-row]");
        const rawQty = row?.querySelector(".v2-row-name p bdi:last-child")?.textContent ?? "1";
        const qty = asNumber(rawQty);

        function recalculate() {
            const selected = dropdown.selectedOptions[0];
            const system = asNumber(selected?.dataset.price);
            const isManager = approved.checked;
            managerField.classList.toggle("is-hidden", !isManager);
            discountField.classList.toggle("is-hidden", isManager);
            managerPrice.disabled = !isManager;
            managerPrice.required = isManager;
            discountPrice.disabled = isManager;

            if (!Number.isFinite(system) || system <= 0 || !Number.isFinite(qty) || qty <= 0) {
                priceDisplay.textContent = "—";
                hint.textContent = "برای محاسبه، ابتدا یک قیمت مرجع معتبر انتخاب کنید.";
                return;
            }
            let visibleBase;
            let unitDiscount;
            let effective;
            if (isManager) {
                const manager = asNumber(managerPrice.value);
                if (!Number.isFinite(manager) || manager < 0) {
                    priceDisplay.textContent = "—";
                    hint.textContent = "قیمت مصوب مدیر را وارد کنید؛ تخفیف کلی اعمال نمی‌شود.";
                    return;
                }
                visibleBase = Math.max(system, manager);
                unitDiscount = visibleBase - manager;
                effective = manager;
            } else {
                const rowDiscount = asNumber(discountPrice.value) || 0;
                if (rowDiscount < 0 || rowDiscount > system || pct < 0 || pct > 100) {
                    priceDisplay.textContent = "—";
                    hint.textContent = "مجموع تخفیف‌ها نامعتبر است.";
                    return;
                }
                visibleBase = system;
                unitDiscount = rowDiscount;
                effective = system - unitDiscount - system * pct / 100;
                if (effective < 0) {
                    priceDisplay.textContent = "—";
                    hint.textContent = "جمع تخفیف‌ها بیشتر از قیمت مرجع است.";
                    return;
                }
            }
            const adjustedTaxBase = isOfficial
                ? effective * (1 - officialValue / (100 + taxRate))
                : effective;
            const finalWithTax = adjustedTaxBase * (1 + (isOfficial ? taxRate : 0) / 100);

            priceDisplay.textContent = format(effective);
            hint.textContent = isManager
                ? ("مصوب مدیر · بدون تخفیف کلی یا دستی · مبلغ تقریبی ردیف با مالیات: " + format(finalWithTax * qty))
                : ("قیمت نمایشی: " + format(visibleBase) + " · تخفیف واحد: " + format(unitDiscount) + " · تخفیف کلی: " + pct + "% · مبلغ تقریبی ردیف با مالیات: " + format(finalWithTax * qty));
        }

        for (const field of [dropdown, approved, managerPrice, discountPrice]) {
            field.addEventListener("input", recalculate);
            field.addEventListener("change", recalculate);
        }
        form.addEventListener("submit", (event) => {
            if (approved.checked && !managerPrice.value.trim()) {
                event.preventDefault();
                managerPrice.focus();
            }
        });
        recalculate();
    });
})();
