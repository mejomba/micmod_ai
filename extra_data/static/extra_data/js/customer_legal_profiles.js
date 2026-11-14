/* Compact accordion editor for Customer.legal_profiles.
   One hidden JSON field is posted with the customer form. */
(function () {
    'use strict';

    const section = document.getElementById('customer-legal-profiles');
    if (!section) return;

    const hidden = section.querySelector('#id_legal_profiles');
    const list = section.querySelector('#customer-legal-profiles-list');
    const empty = section.querySelector('#customer-legal-profiles-empty');
    const addButton = section.querySelector('#customer-legal-profile-add');
    const template = document.getElementById('customer-legal-profile-template');
    const toggle = section.querySelector('#customer-legal-profiles-toggle');
    const body = section.querySelector('#customer-legal-profiles-body');
    const count = section.querySelector('#customer-legal-profiles-count');
    const summary = section.querySelector('#customer-legal-profiles-summary');
    if (!hidden || !list || !empty || !addButton || !template ||
        !toggle || !body || !count || !summary) return;

    const keys = ['name', 'national_id', 'type', 'postal_code', 'address'];

    function readRow(row) {
        const data = {};
        row.querySelectorAll('[data-legal-field]').forEach(function (field) {
            data[field.dataset.legalField] = field.value.trim();
        });
        return data;
    }

    function setExpanded(open) {
        toggle.setAttribute('aria-expanded', String(open));
        body.hidden = !open;
        section.classList.toggle('is-open', open);
    }

    function profilePreview(profile) {
        const name = profile.name || 'پروفایل بدون نام';
        const details = [];
        if (profile.type) details.push(profile.type);
        if (profile.national_id) details.push('شناسه ملی: ' + profile.national_id);
        return name + (details.length ? ' (' + details.join('، ') + ')' : ' (تکمیل نشده)');
    }

    function refresh() {
        const rows = Array.from(list.querySelectorAll('[data-legal-profile-row]'));
        const profiles = rows.map(readRow);
        rows.forEach(function (row, index) {
            const profile = profiles[index];
            row.querySelector('[data-legal-profile-title]').textContent =
                profile.name || 'پروفایل ' + (index + 1);
            row.querySelector('[data-legal-remove]').setAttribute(
                'aria-label', 'حذف پروفایل ' + (index + 1)
            );
            row.querySelector('[data-legal-row-summary]').textContent =
                [profile.type, profile.national_id].filter(Boolean).join(' · ') || 'در حال تکمیل';
        });
        empty.classList.toggle('d-none', rows.length > 0);
        count.textContent = rows.length + ' پروفایل';
        if (!rows.length) {
            summary.textContent = 'هنوز پروفایلی ثبت نشده است؛ برای افزودن کلیک کنید';
        } else {
            const previews = profiles.slice(0, 2).map(profilePreview);
            const remaining = profiles.length - previews.length;
            summary.textContent = previews.join('  •  ') +
                (remaining > 0 ? '  •  +' + remaining + ' پروفایل دیگر' : '');
        }
    }

    function sync() {
        const profiles = Array.from(list.querySelectorAll('[data-legal-profile-row]'))
            .map(readRow)
            .filter(function (profile) {
                return keys.some(function (key) { return Boolean(profile[key]); });
            });
        hidden.value = JSON.stringify(profiles);
        refresh();
    }

    function appendProfile(data, focus) {
        const fragment = template.content.cloneNode(true);
        const row = fragment.querySelector('[data-legal-profile-row]');
        row.querySelectorAll('[data-legal-field]').forEach(function (field) {
            const value = data && data[field.dataset.legalField];
            field.value = typeof value === 'string' ? value : '';
        });
        list.appendChild(fragment);
        refresh();
        if (focus) row.querySelector('[data-legal-field="name"]').focus();
    }

    let initial = [];
    try {
        const parsed = JSON.parse(hidden.value || '[]');
        if (Array.isArray(parsed)) initial = parsed;
    } catch (error) {
        // Server-side validation error is displayed and accordion opens automatically.
    }
    initial.forEach(function (profile) {
        if (profile && typeof profile === 'object' && !Array.isArray(profile)) {
            appendProfile(profile, false);
        }
    });

    // Invalid form submissions open the editor; valid forms start compact.
    setExpanded(toggle.getAttribute('aria-expanded') === 'true');
    refresh();

    toggle.addEventListener('click', function () {
        setExpanded(toggle.getAttribute('aria-expanded') !== 'true');
    });
    addButton.addEventListener('click', function () {
        setExpanded(true);
        appendProfile({}, true);
    });
    list.addEventListener('input', function (event) {
        if (event.target.matches('[data-legal-field]')) sync();
    });
    list.addEventListener('click', function (event) {
        const removeButton = event.target.closest('[data-legal-remove]');
        if (!removeButton) return;
        removeButton.closest('[data-legal-profile-row]').remove();
        sync();
    });
    const form = hidden.closest('form');
    if (form) form.addEventListener('submit', sync);
})();
