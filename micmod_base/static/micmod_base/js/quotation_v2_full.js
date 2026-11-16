/* Full quotation v2: enhance legacy behavior without replacing inquiry/workflow. */
(function () {
    "use strict";
    if (!document.querySelector(".quotation-v2-full")) return;

    const oldCalculate = window.calculate_price;
    const oldSetPrice2 = window.set_price2;
    const oldInitPriceMethod = window.init_price_method;
    const oldSetPriceData = window.set_price_data;

    const parse = (raw) => {
        if (raw === null || raw === undefined || String(raw).trim() === "") return NaN;
        const value = Number(String(raw).replace(/,/g, ""));
        return Number.isFinite(value) ? value : NaN;
    };
    const format = (num) => Number.isFinite(num)
        ? new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 }).format(num)
        : "—";
    const rowFrom = (target) => {
        if (!target) return null;
        if (target instanceof Event) target = target.currentTarget || target.target;
        if (!target?.closest) return null;
        return target.closest(".item");
    };
    const validOption = (entry) => {
        if (!entry || ["sales_admin", "goods_last_price", "goods_q_last_price", "----------"].includes(entry.unique_title)) return false;
        if (!entry.unique_title) return false;
        const price = typeof entry.value === "object" ? parse(entry.value?.price) : parse(entry.value);
        return Number.isFinite(price) && price > 0;
    };
    function methods(row) {
        const el = row.querySelector("textarea[name$='-price_json']");
        if (!el?.value) return [];
        try {
            const items = JSON.parse(el.value);
            return Array.isArray(items) ? items : [];
        } catch (_) { return []; }
    }
    function priceMethod(row) {
        return row.querySelector("#id_price_method_container select")?.value
            || row.querySelector("input[name$='-price_method']")?.value
            || "";
    }
    function isV2(row) {
        return row && row.dataset.qv2Version === "2";
    }
    function selectedReference(row) {
        const select = row.querySelector("[data-qv2-source-select]");
        const option = select?.selectedOptions?.[0];
        return {
            value: parse(option?.dataset.price),
            method: option?.dataset.method || "",
            index: option?.value || "",
        };
    }
    function updateSourceInputs(row) {
        const ref = selectedReference(row);
        const target = row.querySelector("input[name$='-v2_system_method']");
        const index = row.querySelector("input[name$='-v2_system_index']");
        if (target) target.value = ref.method;
        if (index) index.value = ref.index === "keep" ? "" : ref.index;
        const note = row.querySelector("[data-qv2-reference-value]");
        if (note) note.textContent = Number.isFinite(ref.value) && ref.value > 0
            ? "قیمت مرجع سیستم: " + format(ref.value)
            : "انتخاب قیمت مرجع برای ذخیره قیمت نسخه ۲ ضروری است.";
    }
    function syncSourceOptions(row) {
        if (!isV2(row)) return;
        const select = row.querySelector("[data-qv2-source-select]");
        if (!select) return;
        const prior = select.value;
        const previousMethod = selectedReference(row).method;
        const savedMethod = row.dataset.qv2SystemMethod || "";
        const savedPrice = parse(row.dataset.qv2SystemPrice);
        const optionRows = methods(row);
        const signature = JSON.stringify(optionRows.map((item) => [
            item.unique_title, item.value, item.iqref, item.ref
        ]));
        if (select.dataset.signature !== signature) {
            select.innerHTML = "";
            const empty = document.createElement("option");
            empty.value = "";
            empty.textContent = "انتخاب قیمت مرجع از استعلام";
            select.appendChild(empty);
            if (Number.isFinite(savedPrice) && savedPrice > 0 && savedMethod) {
                const keep = document.createElement("option");
                keep.value = "keep";
                keep.dataset.price = String(savedPrice);
                keep.dataset.method = savedMethod;
                keep.textContent = "قیمت مرجع ثبت‌شده: " + format(savedPrice) + " (" + savedMethod + ")";
                select.appendChild(keep);
            }
            optionRows.forEach((entry, index) => {
                if (!validOption(entry)) return;
                const opt = document.createElement("option");
                opt.value = String(index);
                opt.dataset.method = entry.unique_title;
                opt.dataset.price = String(
                    typeof entry.value === "object" ? parse(entry.value.price) : parse(entry.value)
                );
                opt.textContent = (entry.title || entry.unique_title) + " — " + format(parse(opt.dataset.price));
                select.appendChild(opt);
            });
            select.dataset.signature = signature;
        }
        const currentMethod = priceMethod(row);
        if (Array.from(select.options).some((option) => option.value === prior && prior)) {
            select.value = prior;
        } else if (Array.from(select.options).some((o) => o.value === "keep") && savedMethod) {
            select.value = "keep";
        } else if (currentMethod && currentMethod !== "sales_admin") {
            const match = Array.from(select.options).find((o) => o.dataset.method === currentMethod);
            select.value = match?.value || "";
        } else if (previousMethod) {
            const match = Array.from(select.options).find((o) => o.dataset.method === previousMethod);
            select.value = match?.value || "";
        }
        updateSourceInputs(row);
        showMode(row);
    }
    function showMode(row) {
        if (!isV2(row)) return;
        const manager = priceMethod(row) === "sales_admin";
        const box = row.querySelector("[data-qv2-manager-wrap]");
        if (box) box.classList.toggle("is-hidden", !manager);
        const discount = row.querySelector("input[name$='-discount_per_item']");
        const discountHolder = discount?.closest(".on-border") || discount?.parentElement;
        if (discountHolder) discountHolder.classList.toggle("qv2-discount-inactive", manager);
        const managerPrice = row.querySelector("input[name$='-v2_manager_price']");
        if (managerPrice) managerPrice.required = manager;
    }

    function recalculateV2(row) {
        if (!isV2(row)) return oldCalculate?.call(window, row);
        const source = selectedReference(row);
        const qtyField = row.querySelector("input[id$='-quantity']");
        const qty = parse(qtyField?.value);
        const manager = priceMethod(row) === "sales_admin";
        const approved = parse(row.querySelector("input[name$='-v2_manager_price']")?.value);
        const unitDiscount = parse(row.querySelector("input[name$='-discount_per_item']")?.value) || 0;
        const selfDiscount = parse(document.querySelector("input[name='self_discount']")?.value) || 0;
        const finalPrice = row.querySelector("input[name$='-final_price']");
        const summary = row.querySelector("[name='-total_price']");
        const finalAmount = row.querySelector("input[name$='-final_amount']");
        const total = (number, selector) => {
            const element = row.querySelector(selector);
            if (element) element.textContent = format(number);
        };
        showMode(row);
        if (!Number.isFinite(source.value) || source.value <= 0 ||
            !Number.isFinite(qty) || qty <= 0 ||
            (manager && (!Number.isFinite(approved) || approved < 0))) {
            if (summary) summary.textContent = "—";
            if (finalAmount) finalAmount.value = "0";
            return updateGrandTotal();
        }
        const system = source.value;
        const sale = manager ? approved : system;
        const customerBase = manager ? Math.max(system, sale) : system;
        const manual = manager ? Math.max(0, system - sale) : unitDiscount;
        const documentDiscount = manager ? 0 : system * selfDiscount / 100;
        if (manual < 0 || documentDiscount < 0 || manual + documentDiscount > customerBase) {
            if (summary) summary.textContent = "تخفیف نامعتبر";
            if (finalAmount) finalAmount.value = "0";
            return updateGrandTotal();
        }
        if (finalPrice) {
            finalPrice.disabled = false;
            finalPrice.readOnly = true;
            finalPrice.value = format(sale);
        }
        const gross = customerBase * qty;
        const commercial = (manual + documentDiscount) * qty;
        const official = document.querySelector("#id_is_official")?.checked;
        const officialValue = parse(document.querySelector("#id_official_value")?.value) || 0;
        const configuredTaxRate = parse(document.querySelector(".quotation-v2-full")?.dataset.taxRate);
        const taxRate = Number.isFinite(configuredTaxRate) ? configuredTaxRate : 10;
        const officialAdj = official ? (gross - commercial) * officialValue / (100 + taxRate) : 0;
        const discount = commercial + officialAdj;
        const tax = official ? (gross - discount) * taxRate / 100 : 0;
        const rial = document.querySelector("#id_currency_ref")?.value === "1";
        const shownDiscount = rial ? Math.trunc(discount) : discount;
        const shownTax = rial ? Math.trunc(tax) : tax;
        const totalValue = gross - shownDiscount + shownTax;
        total(gross, "[name='MAC']");
        total(shownTax, "[name='tax_value']");
        total(shownDiscount, "[name='discount_value']");
        if (summary) summary.textContent = format(totalValue);
        if (finalAmount) finalAmount.value = String(totalValue);
        updateGrandTotal();
    }

    function updateGrandTotal() {
        let sum = 0;
        document.querySelectorAll("#sortable-container .item [name='-total_price']").forEach((item) => {
            const n = parse(item.textContent);
            if (Number.isFinite(n)) sum += n;
        });
        sum += (parse(document.querySelector("#id_addition")?.value) || 0);
        sum += (parse(document.querySelector("#id_tax")?.value) || 0);
        document.querySelectorAll(".quotation_total_price").forEach((node) => {
            node.textContent = format(sum);
        });
    }

    if (typeof oldCalculate === "function") {
        window.calculate_price = function (target) {
            const row = rowFrom(target);
            if (!isV2(row)) return oldCalculate.apply(this, arguments);
            recalculateV2(row);
        };
    }
    if (typeof oldSetPrice2 === "function") {
        window.set_price2 = function (target) {
            const result = oldSetPrice2.apply(this, arguments);
            const row = rowFrom(target);
            if (isV2(row)) {
                syncSourceOptions(row);
                recalculateV2(row);
            }
            return result;
        };
    }
    if (typeof oldInitPriceMethod === "function") {
        window.init_price_method = function (row) {
            const result = oldInitPriceMethod.apply(this, arguments);
            syncSourceOptions(row);
            recalculateV2(row);
            return result;
        };
    }
    if (typeof oldSetPriceData === "function") {
        window.set_price_data = function (data, row) {
            const result = oldSetPriceData.apply(this, arguments);
            if (isV2(row)) {
                syncSourceOptions(row);
                recalculateV2(row);
            }
            return result;
        };
    }

    function attachRow(row) {
        if (!isV2(row) || row.dataset.qv2Bound) return;
        row.dataset.qv2Bound = "1";
        syncSourceOptions(row);
        row.addEventListener("input", (event) => {
            if (event.target.matches(
                "input[name$='-v2_manager_price'],input[name$='-quantity'],input[name$='-discount_per_item']"
            )) recalculateV2(row);
        });
        row.addEventListener("change", (event) => {
            if (event.target.matches("[data-qv2-source-select]")) {
                updateSourceInputs(row);
                const methodSelect = row.querySelector("#id_price_method_container select");
                if (methodSelect && methodSelect.value !== "sales_admin") {
                    const newMethod = selectedReference(row).method;
                    if (newMethod && methodSelect.value !== newMethod) {
                        methodSelect.value = newMethod;
                        methodSelect.dispatchEvent(new Event("change", {bubbles:true}));
                    }
                }
            } else if (event.target.matches("select[name$='-price_method']")) {
                syncSourceOptions(row);
            }
            recalculateV2(row);
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll("#sortable-container .item").forEach(attachRow);
        updateGrandTotal();
        const container = document.querySelector("#sortable-container");
        if (container && typeof MutationObserver !== "undefined") {
            const observer = new MutationObserver(() => {
                container.querySelectorAll(".item").forEach(attachRow);
                updateGrandTotal();
            });
            observer.observe(container, {childList:true, subtree:false});
        }
        document.querySelector("#main-form")?.addEventListener("submit", () => {
            // Hidden formset v2 source values are always updated before submit.
            document.querySelectorAll("#sortable-container .item[data-qv2-version='2']")
                .forEach(updateSourceInputs);
        });
    });
})();
