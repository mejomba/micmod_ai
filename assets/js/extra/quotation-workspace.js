/* Compact quotation workspace. All Django forms stay mounted and submit together. */
(function (global) {
    'use strict';

    function normalize(value) {
        return String(value == null ? '' : value)
            .replace(/[۰-۹]/g, digit => String(digit.charCodeAt(0) - 1776))
            .replace(/[٠-٩]/g, digit => String(digit.charCodeAt(0) - 1632))
            .replace(/ي/g, 'ی').replace(/ك/g, 'ک')
            .replace(/[\u200c\u200d\u0640]/g, '')
            .toLocaleLowerCase().trim();
    }

    function toNumber(value) {
        return Number(normalize(value).replace(/[,،٬\s]/g, '').replace(/٫/g, '.')) || 0;
    }

    function pageWindow(length, size, requestedPage) {
        const pages = size > 0 ? Math.max(1, Math.ceil(length / size)) : 1;
        const page = Math.min(pages, Math.max(1, requestedPage || 1));
        const start = size > 0 ? (page - 1) * size : 0;
        return { page, pages, start, end: size > 0 ? Math.min(start + size, length) : length };
    }

    function init(root) {
        root = root || document.getElementById('quotation-workspace');
        if (!root || root.quotationWorkspace) return root && root.quotationWorkspace;
        const container = root.querySelector('#id_formset_container');
        const sortable = root.querySelector('#sortable-container');
        if (!container || !sortable) return null;
        const form = root.closest('form') || document.getElementById('main-form');
        const control = name => root.querySelector('#qw-' + name);
        const controls = {};
        ['search', 'filter', 'page-size', 'prev', 'next', 'page-info', 'empty',
            'visible-count', 'total-count', 'pending-count', 'error-count',
            'open-page', 'close-page', 'jump', 'jump-button', 'save-status'].forEach(name => {
            controls[name] = control(name) || document.getElementById('qw-' + name);
        });
        let rows = [];
        let matches = [];
        let visibleRows = [];
        let page = 1;
        let pageSize = controls['page-size'] ? (controls['page-size'].value === 'all' ? 0 : Number(controls['page-size'].value)) : 25;
        if (!Number.isFinite(pageSize) || pageSize < 0) pageSize = 25;
        let dirty = false;
        let submitting = false;
        let initialized = false;
        let refreshTimer;
        let firstInvalid;
        let lastOrder = [];
        const knownRows = new WeakSet();
        const stateByRow = new WeakMap();
        const digitFormatter = new Intl.NumberFormat('fa-IR');
        const count = value => digitFormatter.format(value);
        const text = (element, value) => {
            if (element && element.textContent !== String(value)) element.textContent = value;
        };
        const field = (row, suffix) => row.querySelector('[name$="-' + suffix + '"]');
        const value = element => !element ? '' : ('value' in element ? element.value : element.textContent);
        const checked = (row, suffix) => {
            const element = field(row, suffix);
            return !!(element && (element.type === 'checkbox' ? element.checked : /^(true|1|on)$/i.test(value(element))));
        };
        const observerOptions = { childList: true, subtree: true, characterData: true,
            attributes: true, attributeFilter: ['disabled', 'readonly'] };
        const observer = new MutationObserver(records => {
            if (records.some(record => !record.target.parentElement?.closest('.qw-row-summary'))) scheduleRefresh();
        });

        function markDirty() {
            if (submitting) return;
            dirty = true;
            text(controls['save-status'], 'تغییرات ذخیره نشده');
            controls['save-status']?.classList.add('qw-unsaved', 'qw-dirty');
        }

        function setOpen(row, open) {
            const header = row.querySelector('.question-btn');
            const answer = row.querySelector('.answer');
            if (!header || !answer) return;
            answer.classList.toggle('close', !open);
            header.classList.toggle('active-form', open);
            row.classList.toggle('qw-row-open', open);
            const toggle = header.querySelector('[data-qw-toggle]');
            if (toggle) {
                toggle.setAttribute('aria-expanded', String(open));
                toggle.setAttribute('aria-label', (open ? 'بستن جزئیات ردیف ' : 'باز کردن جزئیات ردیف ') +
                    (row.querySelector('[data-qw-position]')?.textContent || ''));
                text(toggle, open ? 'بستن' : 'جزئیات');
            }
        }

        function syncRow(row, index) {
            const header = row.querySelector('.qw-row-summary') || row.querySelector('.question-btn');
            const answer = row.querySelector('.answer') || row;
            const quantity = field(row, 'quantity');
            const price = field(row, 'final_price');
            const total = answer.querySelector('[name="-total_price"]');
            const goodsCode = value(field(row, 'goods_code')) || row.dataset.qwGoodsCode ||
                answer.querySelector('.goods_code .select2-selection__rendered')?.textContent || '';
            const goodsName = value(answer.querySelector('[name="-goods_name_lbl"]')) ||
                value(field(row, 'goods_name')) || row.dataset.qwGoodsName || '';
            // Legacy price builders use .counter to reconstruct the stable Django prefix.
            // Keep it independent from the displayed position after drag and drop.
            const counter = row.querySelector('.counter');
            const formIndex = quantity?.name?.match(/-(\d+)-quantity$/)?.[1];
            if (counter) {
                text(counter, formIndex == null ? index + 1 : Number(formIndex) + 1);
                counter.hidden = true;
                counter.setAttribute('aria-hidden', 'true');
                let position = header?.querySelector('[data-qw-position]');
                if (!position) {
                    position = document.createElement('span');
                    position.setAttribute('data-qw-position', '');
                    counter.after(position);
                }
                text(position, count(index + 1));
            }
            if (header) {
                text(header.querySelector('[name="code_h"]'), goodsCode || '—');
                text(header.querySelector('[name="name_h"]'), goodsName || 'کالای جدید');
                text(header.querySelector('[name="quantity_h"]'), value(quantity) || '—');
                text(header.querySelector('[name="unit-price_h"]'), value(price) || '—');
                text(header.querySelector('[name="total-price_h"]'), value(total) || '—');
            }
            const proxy = row.querySelector('[data-qw-quantity]');
            if (proxy) {
                proxy.disabled = root.dataset.editable === '0' || !quantity || quantity.disabled || quantity.readOnly ||
                    !!quantity.closest('fieldset[disabled]');
                proxy.setAttribute('aria-label', 'تعداد ردیف ' + count(index + 1));
                if (document.activeElement !== proxy && proxy.value !== value(quantity)) proxy.value = value(quantity);
            }
            const deleted = checked(row, 'DELETE');
            const pendingLocal = checked(row, 'need_local_price_inquiry') && !checked(row, 'local_price_inquiry_done');
            const pendingForeign = checked(row, 'need_foreign_price_inquiry') && !checked(row, 'foreign_price_inquiry_done');
            const errors = row.hasAttribute('data-qw-row-error') || !!row.querySelector('[data-qw-row-error]') ||
                !!row.querySelector('.errorlist, .invalid-feedback:not(:empty), .is-invalid, [aria-invalid="true"]');
            const unpriced = !!goodsCode && toNumber(value(price)) <= 0;
            const status = row.querySelector('[data-qw-status]');
            text(status, deleted ? 'در انتظار حذف' : errors ? 'نیاز به اصلاح' :
                pendingLocal && pendingForeign ? 'استعلام داخلی و خارجی' :
                    pendingLocal ? 'استعلام داخلی' : pendingForeign ? 'استعلام خارجی' : unpriced ? 'بدون قیمت' : goodsCode ? 'دارای قیمت' : 'ردیف جدید');
            row.classList.toggle('qw-row-deleted', deleted);
            row.classList.toggle('qw-deleted', deleted);
            row.classList.toggle('qw-row-error', errors);
            row.classList.toggle('qw-has-error', errors);
            if (status) status.dataset.status = deleted ? 'deleted' : errors ? 'error' :
                pendingLocal || pendingForeign ? 'pending' : unpriced ? 'unpriced' : 'ready';
            const search = normalize([goodsCode, goodsName,
                value(field(row, 'customer_goods_code')), value(field(row, 'customer_goods_name'))].join(' '));
            const state = { pendingLocal, pendingForeign, errors, unpriced, deleted, search };
            stateByRow.set(row, state);
            return state;
        }

        function refresh() {
            clearTimeout(refreshTimer);
            observer.disconnect();
            try {
                // Legacy addForm appends to the outer container; keep sortable order unified.
                Array.from(container.children).filter(element => element.classList.contains('item')).forEach(row => {
                    sortable.appendChild(row);
                });
                rows = Array.from(sortable.children).filter(element => element.classList.contains('item'));
                const added = rows.filter(row => !knownRows.has(row));
                const reordered = initialized && rows.length === lastOrder.length && rows.some((row, index) => row !== lastOrder[index]);
                if (initialized && (reordered || added.length)) {
                    rows.forEach((row, index) => { const order = field(row, 'index'); if (order) order.value = index; });
                    markDirty();
                }
                const states = rows.map((row, index) => {
                    const state = syncRow(row, index);
                    if (!knownRows.has(row)) {
                        knownRows.add(row);
                        setOpen(row, state.errors);
                    }
                    return state;
                });
                if (initialized && added.length) {
                    if (controls.search) controls.search.value = '';
                    if (controls.filter) controls.filter.value = 'all';
                    page = pageWindow(rows.length, pageSize, Math.floor(rows.indexOf(added[0]) / (pageSize || rows.length || 1)) + 1).page;
                    added.forEach(row => setOpen(row, true));
                    requestAnimationFrame(() => {
                        const first = added[0];
                        first.querySelector('[data-qw-toggle]')?.focus({ preventScroll: true });
                        first.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    });
                    markDirty();
                }
                const search = normalize(controls.search?.value);
                const filter = controls.filter?.value || 'all';
                matches = rows.filter(row => {
                    const state = stateByRow.get(row);
                    if (search && !search.split(/\s+/).every(term => state.search.includes(term))) return false;
                    if (filter === 'pending-local') return !state.deleted && state.pendingLocal;
                    if (filter === 'pending-foreign') return !state.deleted && state.pendingForeign;
                    if (filter === 'errors') return state.errors;
                    if (filter === 'unpriced') return !state.deleted && state.unpriced;
                    return true;
                });
                if (!initialized) {
                    const errorIndex = matches.findIndex(row => stateByRow.get(row).errors);
                    if (errorIndex >= 0 && pageSize) page = Math.floor(errorIndex / pageSize) + 1;
                }
                const window = pageWindow(matches.length, pageSize, page);
                page = window.page;
                visibleRows = matches.slice(window.start, window.end);
                const visible = new Set(visibleRows);
                rows.forEach(row => {
                    row.hidden = !visible.has(row);
                    row.classList.toggle('qw-page-hidden', !visible.has(row));
                });
                text(controls['total-count'], count(rows.length));
                text(controls['visible-count'], count(matches.length));
                text(controls['pending-count'], count(states.filter(state => !state.deleted && (state.pendingLocal || state.pendingForeign)).length));
                text(controls['error-count'], count(states.filter(state => state.errors).length));
                text(controls['page-info'], matches.length ?
                    count(window.start + 1) + ' تا ' + count(window.end) + ' از ' + count(matches.length) + ' ردیف · صفحه ' + count(page) + ' از ' + count(window.pages) : 'هیچ ردیفی یافت نشد');
                if (controls.empty) controls.empty.hidden = matches.length > 0;
                if (controls.prev) controls.prev.disabled = page <= 1;
                if (controls.next) controls.next.disabled = page >= window.pages;
                if (controls.jump) controls.jump.max = rows.length;
                root.classList.add('qw-ready');
                document.body.classList.add('qw-page-active');
                lastOrder = rows.slice();
                initialized = true;
            } finally {
                observer.observe(container, observerOptions);
            }
        }

        function scheduleRefresh() {
            clearTimeout(refreshTimer);
            refreshTimer = setTimeout(refresh, 60);
        }

        function revealRow(row, focus) {
            if (!row) return;
            if (controls.search) controls.search.value = '';
            if (controls.filter) controls.filter.value = 'all';
            const index = rows.indexOf(row);
            page = pageSize > 0 ? Math.floor(Math.max(0, index) / pageSize) + 1 : 1;
            setOpen(row, true);
            refresh();
            if (focus) {
                requestAnimationFrame(() => {
                    const target = typeof focus === 'object' ? focus : row.querySelector('[data-qw-toggle]');
                    target?.focus({ preventScroll: true });
                    row.scrollIntoView({ behavior: 'smooth', block: 'center' });
                });
            }
        }

        function commitQuantity(proxy, commit) {
            const row = proxy.closest('.item');
            const actual = row && field(row, 'quantity');
            if (!actual || proxy.disabled || actual.disabled || actual.readOnly || root.dataset.editable === '0') return;
            actual.value = normalize(proxy.value).replace(/[,،٬\s]/g, '').replace(/٫/g, '.');
            actual.dispatchEvent(new Event('input', { bubbles: true }));
            if (commit) {
                actual.dispatchEvent(new Event('change', { bubbles: true }));
                // Existing quantity price lookup listens to keyup, including quantity discounts.
                actual.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'Unidentified' }));
            }
            markDirty();
            scheduleRefresh();
        }

        controls.search?.addEventListener('input', () => { page = 1; scheduleRefresh(); });
        controls.filter?.addEventListener('change', () => { page = 1; refresh(); });
        controls['page-size']?.addEventListener('change', event => {
            const size = event.target.value === 'all' ? 0 : Number(event.target.value);
            pageSize = Number.isFinite(size) && size >= 0 ? size : 25;
            page = 1;
            refresh();
        });
        controls.prev?.addEventListener('click', () => { page -= 1; refresh(); });
        controls.next?.addEventListener('click', () => { page += 1; refresh(); });
        controls['open-page']?.addEventListener('click', () => visibleRows.forEach(row => setOpen(row, true)));
        controls['close-page']?.addEventListener('click', () => visibleRows.forEach(row => setOpen(row, false)));
        function jump() {
            const position = Math.trunc(toNumber(controls.jump?.value));
            if (position >= 1 && position <= rows.length) revealRow(rows[position - 1], true);
        }
        controls['jump-button']?.addEventListener('click', jump);

        root.addEventListener('click', event => {
            const header = event.target.closest('.question-btn');
            if (!header || !root.contains(header)) return;
            event.stopImmediatePropagation();
            if (event.target.closest('input, select, textarea, a, .handel-drop')) return;
            const row = header.closest('.item');
            if (row) setOpen(row, row.querySelector('.answer')?.classList.contains('close'));
        }, true);
        root.addEventListener('input', event => {
            if (event.target.matches('[data-qw-quantity]')) commitQuantity(event.target, false);
        });
        root.addEventListener('change', event => {
            if (event.target.matches('[data-qw-quantity]')) commitQuantity(event.target, true);
        });
        root.addEventListener('keydown', event => {
            if (event.key !== 'Enter' || !event.target.matches('[data-qw-quantity], #qw-search, #qw-jump')) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            if (event.target === controls.jump) jump();
            else if (event.target.matches('[data-qw-quantity]')) event.target.blur();
            else refresh();
        }, true);
        if (form) {
            const onEdit = event => {
                if (!event.target.matches('[name], [data-qw-quantity]') ||
                    event.target.id?.startsWith('qw-')) return;
                markDirty();
                scheduleRefresh();
            };
            form.addEventListener('input', onEdit);
            form.addEventListener('change', onEdit);
            form.addEventListener('invalid', event => {
                if (firstInvalid) return;
                firstInvalid = event.target;
                let details = event.target.closest('details');
                while (details) {
                    details.open = true;
                    details = details.parentElement?.closest('details');
                }
                const row = event.target.closest('.item');
                if (row) revealRow(row, event.target);
                setTimeout(() => { firstInvalid = null; }, 0);
            }, true);
            form.addEventListener('submit', () => {
                // Visibility does not affect successful controls or Django TOTAL_FORMS.
                submitting = true;
                dirty = false;
            });
        }
        // Select2 emits jQuery events; they do not necessarily become native change events.
        if (global.jQuery && form) {
            global.jQuery(form).on('select2:select.quotationWorkspace select2:clear.quotationWorkspace', () => {
                markDirty();
                scheduleRefresh();
            });
            global.jQuery(document).ajaxComplete(scheduleRefresh);
        }
        global.addEventListener('beforeunload', event => {
            if (!dirty || submitting) return;
            event.preventDefault();
            event.returnValue = '';
        });
        document.addEventListener('keydown', event => {
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k' && controls.search) {
                event.preventDefault();
                controls.search.focus();
            }
        });
        const footer = document.getElementById('form-footer-container');
        if (footer && global.ResizeObserver) {
            const footerObserver = new ResizeObserver(() => {
                document.documentElement.style.setProperty('--qw-footer-height', footer.offsetHeight + 'px');
            });
            footerObserver.observe(footer);
        }
        root.quotationWorkspace = {
            refresh,
            revealRow,
            getState: () => ({ page, pageSize, filteredCount: matches.length, totalCount: rows.length,
                visibleRows: visibleRows.slice(), dirty })
        };
        refresh();
        return root.quotationWorkspace;
    }

    global.QuotationWorkspace = { normalize, toNumber, pageWindow, init };
    if (typeof document !== 'undefined') {
        if (document.readyState === 'complete') init();
        else global.addEventListener('load', () => init(), { once: true });
    }
}(typeof window !== 'undefined' ? window : globalThis));
