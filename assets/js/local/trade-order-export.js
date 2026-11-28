/* Capture the accepted server-side draw, without changing standard DT export buttons. */
const TradeOrderExport = (() => {
    function setup(table) {
        const root = $('#tradeOrderExport');
        if (!root.length) return;
        const toggle = $('#tradeOrderExportToggle');
        const panel = $('#tradeOrderExportOptions');
        const download = $('#tradeOrderExportDownload');
        const fields = root.find('[data-export-field]');
        const count = $('#tradeOrderExportCount');
        const status = $('#tradeOrderExportStatus');
        let snapshot = null, orderCount = 0, busy = false;
        function selected() { return fields.filter(':checked').map(function () { return this.value; }).get(); }
        function sync() {
            toggle.prop('disabled', !snapshot && panel.hasClass('d-none'));
            download.prop('disabled', busy || !snapshot || !selected().length);
            count.text(selected().length + ' ستون انتخاب شده' + (snapshot ? ' | ' + orderCount.toLocaleString('fa-IR') + ' سفارش در همه صفحات' : ''));
        }
        function open(show) {
            panel.toggleClass('d-none', !show);
            toggle.attr('aria-expanded', String(show));
            sync();
        }
        toggle.on('click', () => open(panel.hasClass('d-none')));
        $('#tradeOrderExportClose').on('click', () => open(false));
        fields.on('change', sync);
        root.find('[data-export-select]').on('click', function () {
            const mode = this.dataset.exportSelect;
            fields.each(function () { this.checked = mode === 'all' || (mode === 'default' && this.dataset.default === '1'); });
            sync();
        });
        table.on('tradeExportPending', () => { snapshot = null; sync(); });
        table.on('tradeExportReady', (event, data, total) => {
            snapshot = data; orderCount = total; sync();
        });
        download.on('click', async () => {
            if (!snapshot || busy || !selected().length) return;
            const payload = $.extend(true, {}, snapshot);
            payload.export_fields = selected();
            payload.export_payment_details = $('#tradeExportDetails').prop('checked') ? '1' : '0';
            busy = true; status.removeClass('text-danger').text('در حال تهیه فایل…'); sync();
            try {
                const response = await fetch(root.data('url'), {
                    method: 'POST', credentials: 'same-origin',
                    headers: {'X-CSRFToken': root.find('input[name="csrfmiddlewaretoken"]').val(),
                              'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'},
                    body: $.param(payload)
                });
                if (!response.ok || !response.headers.get('content-type')?.includes('spreadsheetml')) {
                    let message = 'دریافت فایل انجام نشد؛ دوباره تلاش کنید.';
                    try { const error = await response.json(); if (error.error) message = error.error; } catch (_) {}
                    throw new Error(message);
                }
                const blob = await response.blob();
                const href = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = href;
                const name = /filename="([^"]+)"/.exec(response.headers.get('content-disposition') || '');
                link.download = name ? name[1] : 'trade-orders.xlsx';
                document.body.appendChild(link); link.click(); link.remove();
                setTimeout(() => URL.revokeObjectURL(href), 1000);
                status.text('فایل آماده شد.');
            } catch (error) {
                status.addClass('text-danger').text(error.message || 'خطا در دریافت فایل.');
            } finally {
                busy = false; sync();
            }
        });
        sync();
    }
    return {setup};
})();
