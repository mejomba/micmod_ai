/* The payment summary travels with the same server-side DataTable draw. */
const TradePaymentFilters = (() => {
    function setup(table, extraData, options, url) {
        const panel = $('#tradePaymentPanel');
        const mode = $('#tradePaymentFilter');
        const start = $('#tradePaymentStart');
        const end = $('#tradePaymentEnd');
        const error = $('#tradePaymentFilterError');
        const status = $('#tradePaymentStatus');
        const totals = $('#tradePaymentTotals');
        const orderCount = $('#tradePaymentOrderCount');
        const undated = $('#tradePaymentUndated');
        let latestDraw = 0;

        const hints = {
            scheduled: 'حداقل یک ردیف با تاریخ آینده، با هر وضعیت پرداخت.',
            overdue: 'حداقل یک ردیف پرداخت‌نشده با تاریخ قبل از امروز.',
            today: 'حداقل یک ردیف با سررسید امروز، با هر وضعیت پرداخت.',
            due_until: 'همه سررسیدهای پرداخت‌نشده تا تاریخ انتخابی (شامل معوقات و خود تاریخ).',
            date_range: 'سررسید بین دو تاریخ انتخابی (شامل ابتدا و انتها)، با هر وضعیت پرداخت.'
        };

        function updateInputs() {
            const value = mode.val();
            $('#tradePaymentStartWrap').toggleClass('d-none', value !== 'date_range');
            $('#tradePaymentEndWrap').toggleClass('d-none', value !== 'date_range' && value !== 'due_until');
            $('#tradePaymentFilterHelp').text(hints[value] || '');
            error.text('');
        }

        function apply() {
            const value = mode.val();
            const from = value === 'date_range' ? start.val() : '';
            const to = ['date_range', 'due_until'].includes(value) ? end.val() : '';
            if ((value === 'date_range' && !from) ||
                (['date_range', 'due_until'].includes(value) && !to)) {
                error.text('تاریخ مورد نیاز را انتخاب کنید.');
                return;
            }
            if (from && to && from > to) {
                error.text('تاریخ شروع نباید بعد از تاریخ پایان باشد.');
                return;
            }
            error.text('');
            extraData.payment_filter = value;
            extraData.payment_start = from;
            extraData.payment_end = to;
            table.DataTable().ajax.reload();
        }

        mode.on('change', updateInputs);
        $('#tradePaymentApply').on('click', apply);
        $('#tradePaymentClear').on('click', () => {
            mode.val(''); start.val(''); end.val('');
            updateInputs();
            apply();
        });
        table.on('init.dt', () => $('#tradePaymentApply, #tradePaymentClear').prop('disabled', false));

        function resetSummary(message) {
            totals.addClass('d-none');
            orderCount.text('');
            undated.addClass('d-none').text('');
            status.text(message);
        }

        function renderSummary(summary) {
            if (!summary || summary.error) {
                resetSummary(summary && summary.error ? summary.error : 'خلاصه پرداخت دریافت نشد.');
                if (summary && summary.error) error.text(summary.error);
                return;
            }
            orderCount.text('(' + summary.order_count.toLocaleString('fa-IR') + ' سفارش در تمام صفحات)');
            status.text('فیلتر اعمال‌شده: ' + summary.filter_label + ' | مبنای تاریخ: ' + summary.as_of);
            ['paid', 'overdue', 'today', 'scheduled'].forEach(key => {
                const target = panel.find('[data-payment-total="' + key + '"]').empty();
                const amounts = summary.totals[key];
                if (!amounts.length) {
                    target.text('—');
                    return;
                }
                amounts.forEach(row => {
                    const line = $('<div>').addClass('d-flex justify-content-between align-items-center gap-2 py-1');
                    $('<span>').attr('dir', 'ltr').addClass('fw-bold text-nowrap').text(row.amount + ' ' + row.currency).appendTo(line);
                    $('<small>').addClass('text-muted text-nowrap').text(row.count.toLocaleString('fa-IR') + ' ردیف').appendTo(line);
                    target.append(line);
                });
            });
            totals.removeClass('d-none');
            if (summary.totals.undated.length) {
                const detail = summary.totals.undated.map(row => row.amount + ' ' + row.currency + ' (' + row.count + ' ردیف)').join(' | ');
                undated.text('پرداخت‌های پرداخت‌نشده بدون تاریخ، خارج از چهار جمع بالا: ' + detail).removeClass('d-none');
            }
        }

        // Preserve the existing ajax_datatable parameters, CSRF and extra filter object.
        // Only the trade page overrides the request to handle stale/failing draws safely.
        options.ajax = function(data, callback, settings) {
            const draw = Number(data.draw);
            latestDraw = draw;
            resetSummary('در حال محاسبه خلاصه تمام نتایج…');
            data.date_from = $(this).data('date_from');
            data.date_to = $(this).data('date_to');
            Object.assign(data, extraData);
            return $.ajax({
                type: 'POST', url: url, data: data, dataType: 'json', cache: false,
                headers: {'X-CSRFToken': panel.find('input[name="csrfmiddlewaretoken"]').val()}
            }).done(response => {
                if (draw !== latestDraw) return;
                if (Number(response.draw) !== draw) {
                    resetSummary('پاسخ جدول معتبر نیست؛ دوباره تلاش کنید.');
                    callback({draw: draw, recordsTotal: 0, recordsFiltered: 0, data: []});
                    return;
                }
                callback(response);
                renderSummary(response.payment_summary);
            }).fail((xhr, reason) => {
                if (draw !== latestDraw || reason === 'abort') return;
                resetSummary('خطا در دریافت نتایج و خلاصه پرداخت؛ دوباره تلاش کنید.');
                callback({draw: draw, recordsTotal: 0, recordsFiltered: 0, data: []});
            });
        };
        updateInputs();
    }
    return {setup};
})();
