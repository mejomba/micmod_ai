/* Legal-profile editor. Native <details> mirrors sale-conditions UI in invoice and quotation. */
(function () {
  'use strict';

  const root = document.getElementById('customer-legal-profiles');
  if (!root) return;
  const details = root.querySelector('#customer-legal-profiles-details');
  const hidden = root.querySelector('#id_legal_profiles');
  const rows = root.querySelector('#customer-legal-profiles-list');
  const empty = root.querySelector('#customer-legal-profiles-empty');
  const addButton = root.querySelector('#customer-legal-profile-add');
  const rowTemplate = root.querySelector('#customer-legal-profile-template');
  const cardTemplate = root.querySelector('#customer-legal-profile-card-template');
  const count = root.querySelector('#customer-legal-profiles-count');
  const cards = root.querySelector('#customer-legal-profiles-cards');
  const summaryEmpty = root.querySelector('#customer-legal-profiles-summary-empty');

  if (!details || !hidden || !rows || !empty || !addButton || !rowTemplate ||
      !cardTemplate || !count || !cards || !summaryEmpty) return;

  const fields = ['name', 'national_id', 'type', 'postal_code', 'address'];

  function readRow(row) {
    const result = {};
    row.querySelectorAll('[data-legal-field]').forEach(function (input) {
      result[input.dataset.legalField] = input.value.trim();
    });
    return result;
  }

  function activeProfiles() {
    return Array.from(rows.querySelectorAll('[data-legal-profile-row]'))
      .map(readRow)
      .filter(function (profile) {
        return fields.some(function (key) { return Boolean(profile[key]); });
      });
  }

  function renderSummary(profiles) {
    const fragment = document.createDocumentFragment();
    profiles.forEach(function (profile, index) {
      const card = cardTemplate.content.cloneNode(true);
      card.querySelector('[data-card-name]').textContent =
        profile.name || 'پروفایل ' + (index + 1);
      card.querySelector('[data-card-type]').textContent = profile.type || 'نوع مشخص نشده';
      card.querySelector('[data-card-national-id]').textContent = profile.national_id || '—';
      card.querySelector('[data-card-postal-code]').textContent = profile.postal_code || '—';
      card.querySelector('[data-card-address]').textContent = profile.address || 'آدرس ثبت نشده';
      fragment.appendChild(card);
    });
    cards.replaceChildren(fragment);
    summaryEmpty.hidden = profiles.length !== 0;
  }

  function refresh() {
    const elements = Array.from(rows.querySelectorAll('[data-legal-profile-row]'));
    elements.forEach(function (row, index) {
      const profile = readRow(row);
      row.querySelector('[data-legal-profile-title]').textContent =
        profile.name || 'پروفایل ' + (index + 1);
      row.querySelector('[data-legal-row-summary]').textContent =
        [profile.type, profile.national_id].filter(Boolean).join(' · ') || 'در حال تکمیل';
      row.querySelector('[data-legal-remove]').setAttribute(
        'aria-label', 'حذف پروفایل ' + (index + 1));
    });
    const nonEmpty = activeProfiles();
    count.textContent = nonEmpty.length + ' پروفایل';
    empty.hidden = elements.length > 0;
    renderSummary(nonEmpty);
  }

  function sync() {
    hidden.value = JSON.stringify(activeProfiles());
    refresh();
  }

  function addRow(profile, focus) {
    const fragment = rowTemplate.content.cloneNode(true);
    const row = fragment.querySelector('[data-legal-profile-row]');
    row.querySelectorAll('[data-legal-field]').forEach(function (input) {
      const value = profile && profile[input.dataset.legalField];
      input.value = typeof value === 'string' ? value : '';
    });
    rows.appendChild(fragment);
    refresh();
    if (focus) row.querySelector('[data-legal-field="name"]').focus();
  }

  let initial = [];
  try {
    const parsed = JSON.parse(hidden.value || '[]');
    if (Array.isArray(parsed)) initial = parsed;
  } catch (_) {
    // Server validation displays the error; <details open> exposes the editor.
  }
  initial.forEach(function (profile) {
    if (profile && typeof profile === 'object' && !Array.isArray(profile)) {
      addRow(profile, false);
    }
  });
  refresh();

  addButton.addEventListener('click', function () {
    details.open = true;
    addRow({}, true);
  });
  rows.addEventListener('input', function (event) {
    if (event.target.matches('[data-legal-field]')) sync();
  });
  rows.addEventListener('click', function (event) {
    const button = event.target.closest('[data-legal-remove]');
    if (!button) return;
    button.closest('[data-legal-profile-row]').remove();
    sync();
  });
  const form = hidden.closest('form');
  if (form) form.addEventListener('submit', sync);
})();
