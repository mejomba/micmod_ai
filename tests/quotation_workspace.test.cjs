/* Run: npm install --no-save playwright && node --test tests/quotation_workspace.test.cjs
 * Uses real Chromium and the production workspace controller, without Django or a DB.
 */
const { test, before, after, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const repo = path.resolve(__dirname, '..');
const controller = fs.readFileSync(path.join(repo, 'assets/js/extra/quotation-workspace.js'), 'utf8');
const view = fs.readFileSync(path.join(repo, 'micmod_base/templates/micmod-base/quotation/view.html'), 'utf8');
const itemTemplate = fs.readFileSync(path.join(repo, 'micmod_base/templates/micmod-base/quotation/workspace_item.html'), 'utf8');
let browser;
let page;
let pageErrors;

function row(index, options = {}) {
    const prefix = `quotation-${index}`;
    const local = index % 4 === 0;
    const foreign = index % 7 === 0;
    const price = index % 11 === 0 ? 0 : 12500;
    return `<div class="item sortable-item" data-row="${index}" data-qw-goods-code="SKU-${index}" data-qw-goods-name="کالای ${index}">
      <input type="hidden" id="id_${prefix}-id" name="${prefix}-id" value="${5000 + index}">
      <input type="hidden" id="id_${prefix}-index" name="${prefix}-index" value="${index}">
      <input type="hidden" name="${prefix}-goods_code" value="SKU-${index}">
      <input type="hidden" name="${prefix}-goods_name" value="کالای ${index}">
      <input type="hidden" name="qir-${prefix}-quotation_item_rel-TOTAL_FORMS" value="1">
      <input type="hidden" name="qir-${prefix}-quotation_item_rel-INITIAL_FORMS" value="1">
      <input type="hidden" name="qir-${prefix}-quotation_item_rel-0-id" value="${9000 + index}">
      <div class="row-counter question-btn active-form qw-row-summary">
        <div><span class="counter">${index + 1}</span><span class="handel-drop">⠿</span></div>
        <span class="code_h" name="code_h"></span><span name="name_h"></span>
        <span name="quantity_h"></span><input type="text" data-qw-quantity value="${index + 1}" disabled>
        <span name="unit-price_h"></span><span name="total-price_h"></span><span data-qw-status></span>
        <button type="button" data-qw-toggle aria-expanded="true">جزئیات</button>
      </div>
      <div class="answer">
        ${options.error ? '<div data-qw-row-error><ul class="errorlist"><li>تعداد نامعتبر است</li></ul></div>' : ''}
        <input type="text" id="id_${prefix}-quantity" name="${prefix}-quantity" value="${index + 1}" ${options.disabled ? 'disabled' : ''} ${options.readonly ? 'readonly' : ''}>
        <input type="text" name="${prefix}-final_price" value="${price}">
        <textarea name="-goods_name_lbl" disabled>کالای ${index}</textarea>
        <input name="${prefix}-customer_goods_code" value="CUSTOMER-${index}">
        <input name="${prefix}-customer_goods_name" value="کد مشتری ${index}">
        <input name="qir-${prefix}-quotation_item_rel-0-description" value="nested ${index}">
        <input type="checkbox" name="${prefix}-need_local_price_inquiry" ${local ? 'checked' : ''}>
        <input type="checkbox" name="${prefix}-local_price_inquiry_done">
        <input type="checkbox" name="${prefix}-need_foreign_price_inquiry" ${foreign ? 'checked' : ''}>
        <input type="checkbox" name="${prefix}-foreign_price_inquiry_done">
        <input type="checkbox" name="${prefix}-DELETE">
        <span name="-total_price">${price * (index + 1)}</span>
      </div>
    </div>`;
}

function fixture(options = {}) {
    const controls = ['prev', 'next', 'open-page', 'close-page', 'jump-button'];
    return `<!doctype html><html dir="rtl" lang="fa"><head><style>
      [hidden], .qw-page-hidden { display:none !important; } .answer.close { display:none; }
      .item {padding:4px;border:1px solid #ddd} input {max-width:130px}
    </style></head><body><form id="main-form">
      <input type="hidden" id="id_quotation-TOTAL_FORMS" name="quotation-TOTAL_FORMS" value="200">
      <input type="hidden" name="quotation-INITIAL_FORMS" value="200">
      <section id="quotation-workspace" data-editable="${options.editable === false ? 0 : 1}">
        <input type="search" id="qw-search">
        <select id="qw-filter"><option value="all">همه</option><option value="pending-local">داخلی</option><option value="pending-foreign">خارجی</option><option value="unpriced">بدون قیمت</option><option value="errors">خطا</option></select>
        <select id="qw-page-size"><option value="25">۲۵</option><option value="50">۵۰</option><option value="100">۱۰۰</option><option value="0">همه</option></select>
        ${controls.map(id => `<button type="button" id="qw-${id}">${id}</button>`).join('')}
        <input id="qw-jump"><span id="qw-page-info"></span><span id="qw-total-count"></span>
        <span id="qw-visible-count"></span><span id="qw-pending-count"></span><span id="qw-error-count"></span>
        <div id="qw-empty" hidden>خالی</div><span id="qw-save-status"></span>
        <div id="id_formset_container"><div id="sortable-container">
          ${Array.from({length: 200}, (_, i) => row(i, {disabled:i === 4, readonly:i === 5, error:i === options.errorAt})).join('')}
        </div></div>
      </section><input type="submit" id="save" value="ذخیره">
    </form></body></html>`;
}

async function mount(options = {}) {
    await page.setContent(fixture(options));
    await page.evaluate(() => {
        window.submitCount = 0;
        document.querySelector('form').addEventListener('submit', e => { e.preventDefault(); window.submitCount++; });
        window.baselinePayload = Array.from(new FormData(document.querySelector('form')).entries());
    });
    await page.addScriptTag({content: controller});
    await page.waitForFunction(() => document.querySelector('#quotation-workspace').quotationWorkspace);
}
async function state() {
    return page.evaluate(() => {
        const data = document.querySelector('#quotation-workspace').quotationWorkspace.getState();
        return {...data, visibleRows: data.visibleRows.map(row => Number(row.dataset.row))};
    });
}
async function refresh() {
    await page.evaluate(() => document.querySelector('#quotation-workspace').quotationWorkspace.refresh());
}
async function goTo(number) {
    await page.locator('#qw-jump').fill(String(number));
    await page.locator('#qw-jump-button').click();
}

before(async () => {
    const launch = {headless:true};
    if (process.env.CHROMIUM_PATH) launch.executablePath = process.env.CHROMIUM_PATH;
    else if (fs.existsSync('/usr/bin/chromium')) launch.executablePath = '/usr/bin/chromium';
    browser = await chromium.launch(launch);
});
after(async () => browser && browser.close());
beforeEach(async () => {
    page = await browser.newPage({viewport:{width:1440,height:1000}});
    pageErrors = [];
    page.on('pageerror', error => pageErrors.push(error.message));
    page.on('dialog', dialog => dialog.dismiss());
});
afterEach(async () => {
    assert.deepEqual(pageErrors, [], 'browser must not throw JavaScript errors');
    await page.close();
});

test('200 rows remain successful form controls while only one page is visible', async () => {
    await mount();
    const data = await state();
    assert.equal(data.totalCount, 200);
    assert.deepEqual(data.visibleRows, Array.from({length:25}, (_,i) => i));
    assert.equal(await page.locator('.item').count(), 200);
    assert.equal(await page.locator('.item:not([hidden])').count(), 25);
    assert.equal(await page.evaluate(() => JSON.stringify(Array.from(new FormData(document.querySelector('form')).entries())) === JSON.stringify(window.baselinePayload)), true);
    await page.locator('#qw-search').fill('CUSTOMER-173');
    await page.waitForFunction(() => document.querySelector('#quotation-workspace').quotationWorkspace.getState().filteredCount === 1);
    assert.deepEqual((await state()).visibleRows, [173]);
    assert.equal(await page.evaluate(() => new FormData(document.querySelector('form')).get('qir-quotation-199-quotation_item_rel-0-id')), '9199');
    assert.equal((await state()).dirty, false, 'changing navigation must not mark the document edited');
});

test('quick quantity edits normalize Persian digits and survive navigation and filtering', async () => {
    await mount();
    await goTo(175);
    await page.evaluate(() => {
        const actual = document.querySelector('[name="quotation-174-quantity"]');
        window.quantityEvents = [];
        for (const event of ['input','change','keyup']) actual.addEventListener(event, e => window.quantityEvents.push(e.type));
    });
    const proxy = page.locator('[data-row="174"] [data-qw-quantity]');
    await proxy.fill('۱٬۲۳۴٫۵');
    await proxy.blur();
    await page.waitForFunction(() => document.querySelector('[name="quotation-174-quantity"]').value === '1234.5');
    assert.equal((await state()).dirty, true);
    assert.ok((await page.evaluate(() => window.quantityEvents)).includes('keyup'), 'legacy price lookup must receive keyup on commit');
    await goTo(1);
    await page.locator('#qw-search').fill('SKU-174');
    await page.waitForFunction(() => document.querySelector('#quotation-workspace').quotationWorkspace.getState().filteredCount === 1);
    assert.equal(await proxy.inputValue(), '1234.5');
    assert.equal(await page.evaluate(() => new FormData(document.querySelector('form')).get('quotation-174-quantity')), '1234.5');
});

test('quick edits respect readonly, disabled and document access constraints', async () => {
    await mount();
    assert.equal(await page.locator('[data-row="4"] [data-qw-quantity]').isDisabled(), true);
    assert.equal(await page.locator('[data-row="5"] [data-qw-quantity]').isDisabled(), true);
    await page.evaluate(() => { document.querySelector('[name="quotation-6-quantity"]').disabled = true; });
    await page.waitForFunction(() => document.querySelector('[data-row="6"] [data-qw-quantity]').disabled);
    await page.evaluate(() => { document.querySelector('#quotation-workspace').dataset.editable = '0'; });
    await refresh();
    assert.equal(await page.locator('[data-qw-quantity]:enabled').count(), 0);
});

test('pending and unpriced filters search all rows, with Persian/Arabic normalization', async () => {
    await mount();
    await page.locator('#qw-filter').selectOption('pending-local');
    assert.equal((await state()).filteredCount, 50);
    await page.locator('#qw-filter').selectOption('pending-foreign');
    assert.equal((await state()).filteredCount, 29);
    await page.locator('#qw-filter').selectOption('unpriced');
    assert.equal((await state()).filteredCount, 19);
    await page.locator('#qw-filter').selectOption('all');
    await page.locator('#qw-search').fill('كالاي ۱۹۹');
    await page.waitForFunction(() => document.querySelector('#quotation-workspace').quotationWorkspace.getState().filteredCount === 1);
    assert.deepEqual((await state()).visibleRows, [199]);
    await page.locator('#qw-search').fill('no-match-xyz');
    await page.waitForFunction(() => document.querySelector('#qw-empty').hidden === false);
    assert.equal((await state()).visibleRows.length, 0);
});

test('page sizes, page bounds and Persian row jump work for 200 rows', async () => {
    await mount();
    await page.locator('#qw-page-size').selectOption('50');
    assert.equal((await state()).visibleRows.length, 50);
    await goTo('۱۹۹');
    assert.equal((await state()).page, 4);
    assert.equal(await page.locator('#qw-next').isDisabled(), true);
    await page.locator('#qw-page-size').selectOption('0');
    assert.equal((await state()).visibleRows.length, 200);
    assert.equal((await state()).page, 1);
    assert.equal(await page.locator('#qw-prev').isDisabled(), true);
});

test('native validation reveals the first invalid row from a hidden page', async () => {
    await mount();
    await page.evaluate(() => {
        const invalid = document.querySelector('[name="quotation-175-customer_goods_name"]');
        invalid.required = true; invalid.value = '';
        document.querySelector('form').reportValidity();
    });
    const data = await state();
    assert.equal(data.page, 8);
    assert.ok(data.visibleRows.includes(175));
    assert.equal(await page.locator('[data-row="175"] .answer').evaluate(e => e.classList.contains('close')), false);
    await page.waitForFunction(() => document.activeElement?.name === 'quotation-175-customer_goods_name');
    assert.equal(await page.evaluate(() => window.submitCount), 0);
});

test('initial server errors open their row and page, and remain filterable', async () => {
    await mount({errorAt:173});
    assert.equal((await state()).page, 7);
    assert.equal(await page.locator('[data-row="173"] .answer').evaluate(e => e.classList.contains('close')), false);
    await page.locator('#qw-filter').selectOption('errors');
    assert.deepEqual((await state()).visibleRows, [173]);
    assert.equal(await page.locator('#qw-error-count').textContent(), '۱');
});

test('legacy appended rows join sortable container, clear filters and retain nested controls', async () => {
    await mount();
    await page.locator('#qw-search').fill('SKU-173');
    await page.waitForFunction(() => document.querySelector('#quotation-workspace').quotationWorkspace.getState().filteredCount === 1);
    await page.evaluate(html => {
        document.querySelector('#id_formset_container').insertAdjacentHTML('beforeend', html);
        document.querySelector('[name="quotation-TOTAL_FORMS"]').value = '201';
    }, row(200));
    await page.waitForFunction(() => document.querySelector('#quotation-workspace').quotationWorkspace.getState().totalCount === 201);
    assert.equal((await state()).page, 9);
    assert.deepEqual((await state()).visibleRows, [200]);
    assert.equal(await page.locator('#qw-search').inputValue(), '');
    assert.equal(await page.locator('#sortable-container > [data-row="200"]').count(), 1);
    assert.equal(await page.locator('[data-row="200"] .answer').evaluate(e => e.classList.contains('close')), false);
    assert.equal(await page.evaluate(() => new FormData(document.querySelector('form')).get('qir-quotation-200-quotation_item_rel-0-description')), 'nested 200');
});

test('marking a row deleted is reversible and never removes its form or nested data', async () => {
    await mount();
    await page.evaluate(() => {
        const input = document.querySelector('[name="quotation-0-DELETE"]');
        input.checked = true; input.dispatchEvent(new Event('change', {bubbles:true}));
    });
    await refresh();
    assert.equal(await page.locator('[data-row="0"]').evaluate(e => e.classList.contains('qw-row-deleted')), true);
    await page.locator('#qw-filter').selectOption('pending-local');
    assert.equal((await state()).filteredCount, 49);
    assert.equal(await page.evaluate(() => new FormData(document.querySelector('form')).get('quotation-0-DELETE')), 'on');
    await page.evaluate(() => {
        const input = document.querySelector('[name="quotation-0-DELETE"]');
        input.checked = false; input.dispatchEvent(new Event('change', {bubbles:true}));
    });
    await refresh();
    assert.equal((await state()).filteredCount, 50);
    assert.equal(await page.locator('.item').count(), 200);
});

test('reordering persists order indexes while Django form identities stay stable', async () => {
    await mount();
    await page.evaluate(() => {
        const sortable = document.querySelector('#sortable-container');
        sortable.prepend(sortable.lastElementChild);
    });
    await page.waitForFunction(() => document.querySelector('[name="quotation-199-index"]').value === '0');
    assert.equal(await page.locator('[name="quotation-0-index"]').inputValue(), '1');
    assert.equal(await page.locator('[name="quotation-199-id"]').inputValue(), '5199');
    assert.equal(await page.locator('[data-row="199"] .counter').textContent(), '200', 'legacy pricing must retain the stable form prefix after a reorder');
    assert.equal(await page.locator('[data-row="199"] [data-qw-position]').textContent(), '۱');
    assert.equal(await page.evaluate(() => new FormData(document.querySelector('form')).get('qir-quotation-199-quotation_item_rel-0-id')), '9199');
    await page.addScriptTag({content: 'function set_price2() {}\n' +
        fs.readFileSync(path.join(repo, 'assets/js/extra/quotation1.js'), 'utf8')
            .split('function generate_price_method_select_option')[1].split('function display_price')[0]
            .replace(/^/, 'function generate_price_method_select_option')});
    const generatedName = await page.evaluate(() => {
        const row = document.querySelector('[data-row="199"]');
        row.insertAdjacentHTML('beforeend', '<textarea name="quotation-199-price_json">[]</textarea><div id="id_price_method_container"></div>');
        generate_price_method_select_option(row);
        return row.querySelector('#id_price_method_container select').name;
    });
    assert.equal(generatedName, 'quotation-199-price_method', 'legacy price regeneration must use the original prefix');
    assert.equal((await state()).dirty, true);
});

test('workspace buttons and Enter navigation do not submit the quotation', async () => {
    await mount();
    for (const id of ['qw-next','qw-prev','qw-open-page','qw-close-page']) await page.locator('#' + id).click();
    await page.locator('[data-row="0"] [data-qw-toggle]').click();
    await page.locator('#qw-search').press('Enter');
    await page.locator('#qw-jump').fill('25');
    await page.locator('#qw-jump').press('Enter');
    assert.equal(await page.evaluate(() => window.submitCount), 0);
    assert.equal(await page.locator('.item:not([hidden]) .answer:not(.close)').count(), 2, 'jump reveals the target while keeping the previously opened row');
    for (const id of ['qw-prev','qw-next','qw-open-page','qw-close-page','qw-jump-button']) {
        assert.match(view, new RegExp(`<button[^>]*type="button"[^>]*id="${id}"`), `${id} must be a non-submit production control`);
    }
    assert.match(itemTemplate, /<button[^>]*type="button"[^>]*data-qw-toggle/);
});


test('the legacy Add button and submit bookkeeping preserve prefixes for newly created rows', async () => {
    await mount();
    await page.addScriptTag({path:path.join(repo, 'assets/js/jquery-3.6.0.js')});
    const empty = row(200).replaceAll('quotation-200', 'quotation-__prefix__')
        .replace('data-row="200"', 'data-row="new"');
    await page.evaluate(html => {
        const template = document.createElement('template');
        template.id = 'id_formset_empty_form';
        template.innerHTML = html;
        document.querySelector('form').append(template);
        const add = document.createElement('button');
        add.type = 'button';
        add.name = 'id_formset_add_button';
        add.textContent = 'افزودن ردیف';
        document.querySelector('form').append(add);
        window.set_item_classes = () => {};
        window.addCommaSeperator = () => {};
        window.removeCommaSeperator = () => {};
    }, empty);
    await page.addScriptTag({path:path.join(repo, 'assets/js/extra/formset.js')});
    await page.evaluate(() => window.dispatchEvent(new Event('load')));
    await page.locator('[name="id_formset_add_button"]').click();
    await page.waitForFunction(() => document.querySelector('#quotation-workspace').quotationWorkspace.getState().totalCount === 201);
    assert.equal(await page.locator('[data-row="new"] [name="quotation-200-quantity"]').count(), 1);
    assert.equal(await page.locator('[data-row="new"] [name="qir-quotation-200-quotation_item_rel-0-description"]').count(), 1);
    assert.equal(await page.locator('[data-row="new"] .counter').textContent(), '201');
    assert.equal((await state()).page, 9);
    await page.locator('#save').click();
    assert.equal(await page.locator('[name="quotation-TOTAL_FORMS"]').inputValue(), '201');
    assert.equal(await page.evaluate(() => window.submitCount), 1);
});
