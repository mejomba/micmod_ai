/* Quick Packing calendar. Conversion functions from the project's bundled jalaali-js v1.1.0 (MIT). */
(function () {
function toJalaali(a,i,d){return"[object Date]"===Object.prototype.toString.call(a)&&(d=a.getDate(),i=a.getMonth()+1,a=a.getFullYear()),d2j(g2d(a,i,d))}function toGregorian(a,i,d){return d2g(j2d(a,i,d))}function isValidJalaaliDate(a,i,d){return a>=-61&&a<=3177&&i>=1&&i<=12&&d>=1&&d<=jalaaliMonthLength(a,i)}function isLeapJalaaliYear(a){return 0===jalCal(a).leap}function jalaaliMonthLength(a,i){return i<=6?31:i<=11||isLeapJalaaliYear(a)?30:29}function jalCal(a){var i,d,t,l,r,n,e=[-61,9,38,199,426,686,756,818,1111,1181,1210,1635,2060,2097,2192,2262,2324,2394,2456,3178],o=e.length,v=a+621,g=-14,u=e[0];if(a<u||a>=e[o-1])throw new Error("Invalid Jalaali year "+a);for(n=1;n<o&&(d=(i=e[n])-u,!(a<i));n+=1)g=g+8*div(d,33)+div(mod(d,33),4),u=i;return g=g+8*div(r=a-u,33)+div(mod(r,33)+3,4),4===mod(d,33)&&d-r==4&&(g+=1),l=20+g-(div(v,4)-div(3*(div(v,100)+1),4)-150),d-r<6&&(r=r-d+33*div(d+4,33)),-1===(t=mod(mod(r+1,33)-1,4))&&(t=4),{leap:t,gy:v,march:l}}function j2d(a,i,d){var t=jalCal(a);return g2d(t.gy,3,t.march)+31*(i-1)-div(i,7)*(i-7)+d-1}function d2j(a){var i,d=d2g(a).gy,t=d-621,l=jalCal(t);if((i=a-g2d(d,3,l.march))>=0){if(i<=185)return{jy:t,jm:1+div(i,31),jd:mod(i,31)+1};i-=186}else t-=1,i+=179,1===l.leap&&(i+=1);return{jy:t,jm:7+div(i,30),jd:mod(i,30)+1}}function g2d(a,i,d){var t=div(1461*(a+div(i-8,6)+100100),4)+div(153*mod(i+9,12)+2,5)+d-34840408;return t=t-div(3*div(a+100100+div(i-8,6),100),4)+752}function d2g(a){var i,d,t,l;return i=(i=4*a+139361631)+4*div(3*div(4*a+183187720,146097),4)-3908,d=5*div(mod(i,1461),4)+308,t=div(mod(d,153),5)+1,l=mod(div(d,153),12)+1,{gy:div(i,1461)-100100+div(8-l,6),gm:l,gd:t}}function div(a,i){return~~(a/i)}function mod(a,i){return a-~~(a/i)*i}

/* Quick Packing dual-calendar editor. The form's real input is always ISO Gregorian.
 * Jalali view is display-only: no Jalali year can reach Django's DateField. */
(function () {
    'use strict';
    const header = document.getElementById('packing-header');
    if (!header) return;
    const inputs = Array.from(header.querySelectorAll('input[data-packing-gregorian-date]'))
        .filter(input => input.type === 'date' && !input.disabled);
    if (!inputs.length) return;

    const months = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
                    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
    const weekdays = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج'];
    const storeKey = 'quickPackingDateCalendar';
    const isEnglish = () => /^en/i.test(localStorage.getItem('Dason-language') || document.documentElement.lang || 'fa');
    const labels = () => isEnglish()
        ? { choose: 'Date input calendar', greg: 'Gregorian', jalali: 'Jalali',
            empty: 'Select a Persian date', today: 'Today', clear: 'Clear',
            previous: 'Previous month', next: 'Next month',
            prevYear: 'Previous year', nextYear: 'Next year' }
        : { choose: 'تقویم ورود تاریخ', greg: 'میلادی', jalali: 'شمسی',
            empty: 'انتخاب تاریخ شمسی', today: 'امروز', clear: 'پاک کردن',
            previous: 'ماه قبل', next: 'ماه بعد',
            prevYear: 'سال قبل', nextYear: 'سال بعد' };
    const pad = n => String(n).padStart(2, '0');
    const isoFromGregorian = (y, m, d) => [y, pad(m), pad(d)].join('-');
    function toPersian(iso) {
        const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
        if (!match) return null;
        const y = Number(match[1]), m = Number(match[2]), d = Number(match[3]);
        if (y < 1800 || y > 2200) return null;
        try {
            return toJalaali(y, m, d);
        } catch (_) { return null; }
    }
    const toolbar = document.createElement('div');
    toolbar.className = 'pk-date-calendar-toolbar';
    const label = document.createElement('label');
    const select = document.createElement('select');
    select.className = 'form-select form-select-sm pk-date-calendar-switch';
    select.id = 'pk-date-calendar-mode';
    label.setAttribute('for', select.id);
    const opts = [{ value: 'gregorian', key: 'greg' }, { value: 'jalali', key: 'jalali' }];
    opts.forEach(option => {
        const o = document.createElement('option');
        o.value = option.value;
        o.dataset.key = option.key;
        select.appendChild(o);
    });
    function refreshLanguage() {
        const words = labels();
        label.textContent = words.choose;
        select.querySelectorAll('option').forEach(el => { el.textContent = words[el.dataset.key]; });
        wrappers.forEach(({ display }) => {
            display.placeholder = words.empty;
            display.setAttribute('aria-label', words.empty);
        });
    }
    toolbar.append(label, select);
    const headerHistory = header.querySelector('.pk-header-history-tools');
    if (headerHistory) headerHistory.insertAdjacentElement('afterend', toolbar);
    else header.prepend(toolbar);

    const popup = document.createElement('div');
    popup.className = 'pk-persian-date-popup';
    popup.setAttribute('role', 'dialog');
    popup.setAttribute('aria-label', 'Jalali date picker');
    popup.hidden = true;
    document.body.appendChild(popup);
    let active = null, shown = null;
    const wrappers = [];

    function close() { popup.hidden = true; active = null; }
    function formatJalali(j) { return j ? [j.jy, pad(j.jm), pad(j.jd)].join('/') : ''; }
    function sync() {
        wrappers.forEach(({ input, display }) => {
            const jalali = toPersian(input.value);
            display.value = formatJalali(jalali);
            if (input.value && !jalali) {
                display.placeholder = isEnglish()
                    ? 'Incorrect previous date — select a new date'
                    : 'تاریخ قبلی نامعتبر است؛ تاریخ جدید انتخاب کنید';
            } else {
                display.placeholder = labels().empty;
            }
        });
    }
    function placePopup() {
        if (!active) return;
        const rect = active.display.getBoundingClientRect();
        const w = popup.offsetWidth || 315;
        popup.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, rect.right - w)) + 'px';
        popup.style.top = (rect.bottom + 5) + 'px';
        const popRect = popup.getBoundingClientRect();
        if (popRect.bottom > window.innerHeight && rect.top > popRect.height) {
            popup.style.top = Math.max(8, rect.top - popRect.height - 5) + 'px';
        }
    }
    function addButton(container, value, aria, handler, extraClass='') {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = value;
        button.setAttribute('aria-label', aria);
        button.className = extraClass;
        button.addEventListener('click', handler);
        container.appendChild(button);
        return button;
    }
    function shiftMonth(delta) {
        let year = shown.jy;
        let month = shown.jm + delta;
        while (month > 12) { month -= 12; year++; }
        while (month < 1) { month += 12; year--; }
        if (year < 1200 || year > 1600) return;
        shown = { jy: year, jm: month };
        renderCalendar();
    }
    function chooseDate(jy, jm, jd) {
        if (!active || !isValidJalaaliDate(jy, jm, jd)) return;
        const g = toGregorian(jy, jm, jd);
        active.input.value = isoFromGregorian(g.gy, g.gm, g.gd);
        active.input.dispatchEvent(new Event('change', { bubbles: true }));
        sync();
        close();
    }
    function renderCalendar() {
        if (!shown) return;
        popup.textContent = '';
        const word = labels();
        const top = document.createElement('div');
        top.className = 'pk-persian-calendar-head';
        addButton(top, '«', word.prevYear, () => shiftMonth(-12));
        addButton(top, '‹', word.previous, () => shiftMonth(-1));
        const heading = document.createElement('strong');
        heading.textContent = months[shown.jm-1] + ' ' + shown.jy;
        top.appendChild(heading);
        addButton(top, '›', word.next, () => shiftMonth(1));
        addButton(top, '»', word.nextYear, () => shiftMonth(12));
        popup.appendChild(top);
        const grid = document.createElement('div');
        grid.className = 'pk-persian-calendar-grid';
        weekdays.forEach(weekday => {
            const el = document.createElement('span');
            el.className = 'pk-persian-calendar-weekday';
            el.textContent = weekday;
            grid.appendChild(el);
        });
        const first = toGregorian(shown.jy, shown.jm, 1);
        const offset = (new Date(first.gy, first.gm - 1, first.gd).getDay() + 1) % 7;
        for (let i=0; i<offset; i++) {
            grid.appendChild(document.createElement('span'));
        }
        const selected = active ? toPersian(active.input.value) : null;
        const now = new Date();
        const today = toJalaali(now.getFullYear(), now.getMonth()+1, now.getDate());
        for (let day=1; day<=jalaaliMonthLength(shown.jy, shown.jm); day++) {
            const d = day;
            const btn = addButton(grid, String(day), formatJalali({jy:shown.jy,jm:shown.jm,jd:day}),
                () => chooseDate(shown.jy, shown.jm, d), 'pk-persian-calendar-day');
            if (selected && selected.jy===shown.jy && selected.jm===shown.jm && selected.jd===day)
                btn.classList.add('is-selected');
            if (today.jy===shown.jy && today.jm===shown.jm && today.jd===day)
                btn.classList.add('is-today');
        }
        popup.appendChild(grid);
        const foot = document.createElement('div');
        foot.className = 'pk-persian-calendar-foot';
        addButton(foot, word.clear, word.clear, () => {
            if (active) {
                active.input.value = '';
                active.input.dispatchEvent(new Event('change', { bubbles: true }));
            }
            sync(); close();
        });
        addButton(foot, word.today, word.today, () => {
            const date = new Date();
            const today = toJalaali(date.getFullYear(), date.getMonth()+1, date.getDate());
            chooseDate(today.jy, today.jm, today.jd);
        });
        popup.appendChild(foot);
        popup.hidden = false;
        placePopup();
    }
    function openCalendar(wrapper) {
        if (wrapper.input.disabled) return;
        active = wrapper;
        const now = new Date();
        const j = toPersian(wrapper.input.value) ||
            toJalaali(now.getFullYear(), now.getMonth()+1, now.getDate());
        shown = { jy: j.jy, jm: j.jm };
        renderCalendar();
    }

    inputs.forEach(input => {
        const wrap = document.createElement('span');
        wrap.className = 'pk-date-input-wrap';
        input.parentNode.insertBefore(wrap, input);
        wrap.appendChild(input);
        const display = document.createElement('input');
        display.type = 'text';
        display.readOnly = true;
        display.className = 'form-control pk-jalali-date-display';
        display.autocomplete = 'off';
        display.setAttribute('aria-haspopup', 'dialog');
        display.hidden = true;
        wrap.appendChild(display);
        const picker = document.createElement('button');
        picker.type = 'button';
        picker.className = 'pk-jalali-calendar-open';
        picker.setAttribute('aria-label', 'Open Jalali calendar');
        picker.textContent = '▦';
        picker.hidden = true;
        wrap.appendChild(picker);
        const row = { input, display, picker };
        display.addEventListener('click', () => openCalendar(row));
        picker.addEventListener('click', () => openCalendar(row));
        input.addEventListener('change', sync);
        wrappers.push(row);
    });
    const applyMode = () => {
        const jalali = select.value === 'jalali';
        close();
        wrappers.forEach(({ input, display, picker }) => {
            input.hidden = jalali;
            display.hidden = !jalali;
            picker.hidden = !jalali;
        });
        sync();
    };
    let savedMode = 'gregorian';
    try { savedMode = localStorage.getItem(storeKey) || 'gregorian'; } catch (_) {}
    select.value = savedMode === 'jalali' ? 'jalali' : 'gregorian';
    select.addEventListener('change', () => {
        try { localStorage.setItem(storeKey, select.value); } catch (_) {}
        applyMode();
    });
    document.addEventListener('pointerdown', event => {
        if (!popup.hidden && !popup.contains(event.target) &&
            !wrappers.some(({ display, picker }) => display===event.target || picker===event.target)) close();
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') close();
    });
    window.addEventListener('resize', () => { if (!popup.hidden) placePopup(); });
    window.addEventListener('scroll', () => { if (!popup.hidden) placePopup(); }, true);
    refreshLanguage();
    applyMode();
})();

})();
