/* The payment summary travels with the same server-side DataTable draw. */
const TradePaymentFilters = (() => {
    function setup(table, extraData, options, url) {
        const panel = $('#tradePaymentPanel');
        const modeButtons = panel.find('[data-payment-mode]');
        const summaryPanel = $('#tradePaymentSummary');
        let pendingMode = '';
        let latestSummary = null;
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

        const calendar = TradePaymentCalendar.setup(() => {
            updateInputs();
            if (latestSummary) renderSummary(latestSummary);
        });
        const isDated = value => ['date_range', 'due_until'].includes(value);
        function updateInputs() {
            const value = pendingMode;
            const dateChanged = isDated(value) && (
                (value === 'date_range' && start.val() !== extraData.payment_start) ||
                end.val() !== extraData.payment_end
            );
            const needsApply = isDated(value) && (value !== extraData.payment_filter || dateChanged);
            $('#tradePaymentDateControls').toggleClass('d-none', !isDated(value));
            $('#tradePaymentStartWrap').toggleClass('d-none', value !== 'date_range');
            $('#tradePaymentEndWrap').toggleClass('d-none', !isDated(value));
            modeButtons.each(function () {
                const applied = this.dataset.paymentMode === extraData.payment_filter;
                const pending = this.dataset.paymentMode === pendingMode && needsApply;
                $(this).toggleClass('active bg-primary', applied).toggleClass('tp-pending', pending)
                    .attr('aria-pressed', String(applied));
            });
            $('#tradePaymentClear').toggleClass('d-none', !value && !extraData.payment_filter);
            $('#tradePaymentFilterHelp').text((hints[value] || '') +
                (needsApply ? ' تاریخ هنوز اعمال نشده است؛ برای اعمال، تایید را بزنید.' : ''));
            error.text('');
        }

        function apply() {
            const value = pendingMode;
            const from = value === 'date_range' ? start.val() : '';
            const to = isDated(value) ? end.val() : '';
            if ((value === 'date_range' && (!from || !start[0].checkValidity())) ||
                (isDated(value) && (!to || !end[0].checkValidity()))) {
                error.text('تاریخ معتبر مورد نیاز را انتخاب کنید.');
                return;
            }
            if (from && to && from > to) {
                error.text('تاریخ شروع نباید بعد از تاریخ پایان باشد.');
                return;
            }
            extraData.payment_filter = value;
            extraData.payment_start = from;
            extraData.payment_end = to;
            calendar.close();
            updateInputs();
            table.DataTable().ajax.reload();
        }

        modeButtons.on('click', function () {
            pendingMode = this.dataset.paymentMode;
            calendar.close();
            updateInputs();
            if (!isDated(pendingMode)) apply();
        });
        $('#tradePaymentApply').on('click', apply);
        $('#tradePaymentClear').on('click', () => {
            pendingMode = ''; start.val(''); end.val('');
            calendar.sync();
            apply();
        });
        table.on('init.dt', () => modeButtons.add('#tradePaymentApply, #tradePaymentClear').prop('disabled', false));

        function resetSummary(message) {
            latestSummary = null;
            totals.addClass('d-none');
            orderCount.text('—');
            undated.addClass('d-none').text('');
            status.text(message);
        }

        function renderSummary(summary) {
            if (!summary || summary.error) {
                resetSummary(summary && summary.error ? summary.error : 'خلاصه پرداخت دریافت نشد.');
                if (summary && summary.error) error.text(summary.error);
                return;
            }
            latestSummary = summary;
            orderCount.text(summary.order_count.toLocaleString('fa-IR'));
            const dateLabel = value => {
                const jalali = TradePaymentCalendar.format(value);
                return calendar.mode() === 'jalali' && jalali ? jalali + ' شمسی' : value.replace(/-/g, '/') + ' میلادی';
            };
            const filterLabel = summary.filter_label.replace(/\d{4}-\d{2}-\d{2}/g, dateLabel);
            status.text('فیلتر اعمال‌شده: ' + filterLabel + ' | مبنای تاریخ: ' + dateLabel(summary.as_of));
            ['paid', 'overdue', 'today', 'scheduled'].forEach(key => {
                const target = summaryPanel.find('[data-payment-total="' + key + '"]').empty();
                const amounts = summary.totals[key];
                if (!amounts.length) {
                    target.text('—');
                    return;
                }
                amounts.forEach(row => {
                    const line = $('<div>').addClass('d-flex justify-content-between align-items-center gap-2 py-1 tp-total-line');
                    $('<span>').attr('dir', 'ltr').addClass('fw-bold text-nowrap tp-total-amount').text(row.amount + ' ' + row.currency).appendTo(line);
                    $('<small>').addClass('text-muted text-nowrap').text(row.count.toLocaleString('fa-IR') + ' ردیف').appendTo(line);
                    target.append(line);
                });
            });
            totals.removeClass('d-none');
            undated.addClass('d-none').text('');
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
