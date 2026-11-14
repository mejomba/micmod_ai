/* Editor for Customer.legal_profiles: the JSON hidden field is the only posted value. */
(function () {
    'use strict';

    const section = document.getElementById('customer-legal-profiles');
    if (!section) return;

    const hidden = section.querySelector('#id_legal_profiles');
    const list = section.querySelector('#customer-legal-profiles-list');
    const empty = section.querySelector('#customer-legal-profiles-empty');
    const addButton = section.querySelector('#customer-legal-profile-add');
    const template = document.getElementById('customer-legal-profile-template');
    if (!hidden || !list || !empty || !addButton || !template) return;

    const keys = ['name', 'national_id', 'type', 'postal_code', 'address'];

    function readRow(row) {
        const data = {};
        row.querySelectorAll('[data-legal-field]').forEach(function (field) {
            data[field.dataset.legalField] = field.value.trim();
        });
        return data;
    }

    function refresh() {
        const rows = Array.from(list.querySelectorAll('[data-legal-profile-row]'));
        rows.forEach(function (row, index) {
            row.querySelector('[data-legal-profile-title]').textContent = 'پروفایل ' + (index + 1);
            row.querySelector('[data-legal-remove]').setAttribute('aria-label', 'حذف پروفایل ' + (index + 1));
        });
        empty.classList.toggle('d-none', rows.length > 0);
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
        // The form will show the server-side invalid JSON error near the section.
    }
    initial.forEach(function (profile) {
        if (profile && typeof profile === 'object' && !Array.isArray(profile)) {
            appendProfile(profile, false);
        }
    });
    // Do not replace the submitted JSON on a failed form before the user edits.
    // Normal form submissions always serialize the visible rows.
    refresh();

    addButton.addEventListener('click', function () {
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
