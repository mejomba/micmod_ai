function initSelect2(scope) {
    $(scope).find("select.select2").each(function () {
        var $el = $(this);
        if ($el.hasClass("select2-hidden-accessible")) return;   // قبلاً init شده

        var isMulti = $el.prop("multiple");
        var placeholder = $el.data("placeholder") || "";
        var opts = {
            width: $el.data("width") || "100%",
            dir: "rtl",
            placeholder: placeholder,
            // allowClear فقط برای تک‌انتخابی و فقط وقتی placeholder داریم
            allowClear: !isMulti && !!$el.data("allow-clear") && !!placeholder,
            closeOnSelect: !isMulti,
            // ⭐ مهم: جلوگیری از اسکیپ شدن HTML
            escapeMarkup: function(markup) {
                return markup;  // برگرداندن HTML بدون تغییر
            },
        };

        var url = $el.data("ajax-url");
        if (url) {
            var mi = $el.data("min-input");
            opts.minimumInputLength = (mi === undefined || mi === "") ? 1 : mi;
            opts.ajax = {
                url: url,
                dataType: "json",
                delay: 250,
                cache: true,
                data: function (p) {
                    var d = { q: p.term, page: p.page || 1 };
                    var extra = $el.data("ajax-extra");
                    if (extra && typeof extra === "object") $.extend(d, extra);
                    return d;
                },
                processResults: function (d, p) {
                    // ⭐ اضافه کردن templateResult برای هر آیتم
                    p.page = p.page || 1;
                    var results = d.results || [];

                    // اگر داده‌ها شامل text با HTML هستند، همینجا پردازش می‌شوند
                    return {
                        results: results,
                        pagination: { more: d.pagination && d.pagination.more || false }
                    };
                },
            };
        }

        // ⭐ اضافه کردن templateResult برای نمایش HTML
        opts.templateResult = function(item) {
            if (item.loading) {
                return item.text;
            }

            // اگر آیتم دارای text است و شامل تگ HTML می‌باشد
            if (item.text) {
                // استفاده از jQuery برای تبدیل HTML به DOM
                return $('<span>').html(item.text);
            }

            // اگر آیتم دارای children است (برای گروه‌ها)
            if (item.children) {
                return $('<span>').html(item.text || item.id);
            }

            // حالت عادی
            return item.text || item.id;
        };

        // ⭐ اضافه کردن templateSelection برای نمایش در بخش انتخاب شده
        opts.templateSelection = function(item) {
            if (!item || !item.text) {
                return item.text || item.id;
            }

            // نمایش HTML در بخش انتخاب شده
            return $('<span>').html(item.text);
        };

        try {
            $el.select2(opts);

            // وقتی dropdown باز می‌شود
            $el.on('select2:open', function() {
                setTimeout(function (){
                    document.querySelector('.select2-search__field')?.focus()
                }, 50)
            });

            // ⭐ برای حفظ وضعیت فعلی و نمایش درست HTML
            // اگر آیتمی از قبل انتخاب شده، دوباره رندر کن
            var selectedValue = $el.val();
            if (selectedValue) {
                setTimeout(function() {
                    // به‌روزرسانی نمایش برای انتخاب‌های فعلی
                    var selection = $el.select2('data');
                    if (selection && selection.length > 0) {
                        // Select2 خودش نمایش را به‌روز می‌کند
                        $el.trigger('change');
                    }
                }, 100);
            }

            var onSelect = $el.data("on-select");
            if (onSelect) {
                $el.on("select2:select", function (e) {
                    var fn = window.select2Handlers && window.select2Handlers[onSelect];
                    if (typeof fn === "function") fn(e.params.data, $el, e);
                });
            }
        } catch (e) {
            console.error("Select2 init failed:", $el.attr("name"), e);
        }
    });
}


$(function () { initSelect2(document); });
