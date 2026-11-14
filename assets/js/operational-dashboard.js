/* Progressive enhancement for the operational performance dashboard.
   No external libraries and no global listeners outside its own root. */
(function () {
  'use strict';

  var root = document.getElementById('op-dashboard');
  if (!root) return;

  var tabs = Array.prototype.slice.call(root.querySelectorAll('[data-op-tab]'));
  var panels = Array.prototype.slice.call(root.querySelectorAll('[data-op-panel]'));

  function activate(tab, focus) {
    if (!tab) return;
    var selectedId = tab.getAttribute('data-op-target');

    tabs.forEach(function (button) {
      var selected = button === tab;
      button.classList.toggle('is-active', selected);
      button.setAttribute('aria-selected', selected ? 'true' : 'false');
      button.tabIndex = selected ? 0 : -1;
    });

    panels.forEach(function (panel) {
      panel.hidden = panel.id !== selectedId;
    });

    if (focus) tab.focus();
  }

  tabs.forEach(function (tab, index) {
    tab.addEventListener('click', function () {
      activate(tab, false);
    });
    tab.addEventListener('keydown', function (event) {
      var next;
      // In RTL, left moves to the next visual tab and right to the previous.
      if (event.key === 'ArrowLeft') next = (index + 1) % tabs.length;
      else if (event.key === 'ArrowRight') next = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = tabs.length - 1;
      else return;
      event.preventDefault();
      activate(tabs[next], true);
    });
  });

  if (tabs.length) {
    activate(tabs[0], false);
  }

  function normalizeText(value) {
    return (value || '')
      .normalize('NFKC')
      .replace(/\u064a/g, '\u06cc')
      .replace(/\u0643/g, '\u06a9')
      .replace(/[\u064b-\u065f]/g, '')
      .toLocaleLowerCase();
  }

  panels.forEach(function (panel) {
    var search = panel.querySelector('[data-op-search]');
    if (!search) return;
    var cards = Array.prototype.slice.call(panel.querySelectorAll('[data-op-person]'));
    var empty = panel.querySelector('[data-op-no-results]');

    search.addEventListener('input', function () {
      var query = normalizeText(search.value).trim();
      var visible = 0;
      cards.forEach(function (card) {
        var name = normalizeText(card.getAttribute('data-op-name'));
        var matches = !query || name.indexOf(query) !== -1;
        card.hidden = !matches;
        if (matches) visible += 1;
      });
      if (empty) empty.hidden = visible !== 0;
    });
  });
})();
