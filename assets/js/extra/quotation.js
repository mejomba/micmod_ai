

$(document).ready(function () {
    //addPageNumbers();
    String.prototype.insert = function(index, string) {
        if (index > 0) {
            return this.substring(0, index) + string + this.substring(index, this.length);
        }
        return string + this;
    };
    String.prototype.reverse_string=function() {return this.split("").reverse().join("");}

    addCommaSeperator()

    const elem = document.querySelector('.goods_code')
    if (elem) {
        $('#customer_code').select2({
            ajax: {
                url: '/sepidar/customers_list',
                dataType: "json",
                type: "GET",
                data: function (data) {
                    return {q: data.term, page: data.page}
                },
                processResults: function (data, params) {
                    params.page = params.page || 1;
                    return {
                        results: data.items,
                        pagination: {
                            more: (params.page * 30) < data.total_count
                        }
                    };
                },
                cache: true
            },
            minimumInputLength: 1,
            placeholder: {
                //id: document.getElementsByName("customer_code")[0].value.toString(),
                text: document.querySelector('[name="customer_code"]').value.toString(),
                //selected: 'selected'
            },
            allowClear: false,
            templateResult: formatRepoDL,
            templateSelection: formatRepoSelection
        });
    }
    // $('#customer_code').on('select2:open',function (e){
    //     //debugger
    //     const elem = $('.select2-results')[0]
    //     const ul = $('#select2-customer_code-results')[0]
    //     let ch = document.createTextNode("Hi there and greetings!");
    //     elem.insertBefore(ch,ul)
    // })
    //$('.goods_code').data('select2').dropdown.addClass('goods_select2')
    $('#customer_code').on("select2:select", function (e) {
        const data = e.params.data;
        document.querySelector('[name="customer_code"]').value = data.id
        document.querySelector('[id*="select2-customer_code"][id*="container"]').querySelector('span').innerHTML = data.id
        // $(document).find("#customer_card").attr("class", "alert-warning h-100 p-2");
        document.getElementById("customer_card").classList.remove('d-none');
        $(document).find("#customer_name").text(data.text);
        $(document).find("#customer_pid").text(data.pid);
    })
    document.getElementsByClassName('goods_name').ondblclick = function () {
        const item = findAncestor(this)
    }
    const items = $(document).find(".item")
    for (let i = 0; i < items.length; i++) {
        set_item_classes(items[i], i)
    }
    $('.replace-digits').replaceDigits();
    // scroll_down()
});

function set_item_classes(item) {
    // debugger
    if(item.getElementsByClassName('goods_code')) {
        // const cc = item.getElementsByClassName('goods_code')
        $(item).find('.goods_code').on("select2:select", function (e) {
        const elem = findAncestor(e.target, "item")
        const data = e.params.data;
        set_price_data(data, elem, e.target)
    })
        $(item).find('.goods_code_alt').on("select2:select", function (e) {
            var elem = findAncestor(e.target, "item")
            var data = e.params.data;
            set_alt_price_data(data, elem)
        })
        $(item).find('.goods_code').select2({
            dir: 'ltr',
            ajax: {
                url: '/sepidar/items_list',
                dataType: "json",
                type: "GET",
                data: function (data) {
                    var p_id = document.getElementById('customer_pid').textContent || -1;
                    return {q: data.term, party_id: p_id, page: data.page}
                },
                processResults: function (data, params) {
                    params.page = params.page || 1;
                    return {
                        results: data.items,
                        pagination: {
                            more: (params.page * 30) < data.total_count
                        }
                    };
                },
                cache: true
            },
            dropdownAutoWidth: true,
            dropdownCssClass: 'goods_select2',
            minimumInputLength: 1,
            //placeholder: $(document).find("#customer_code").text(),
            templateResult: formatRepoItem,
            templateSelection: formatRepoSelection,
        });
        $(item).find('.goods_code_alt').select2({
            dir: 'ltr',
            ajax: {
                url: '/sepidar/items_list',
                dataType: "json",
                type: "GET",
                data: function (data) {
                    const p_id = document.getElementById('customer_pid').textContent;
                    return {q: data.term, party_id: p_id, page: data.page}
                },
                processResults: function (data, params) {
                    params.page = params.page || 1;
                    const items = [];
                    for (const item in data.items) {
                        if (data.items[item].f_fee_cust) {
                            items.push(data.items[item]);
                        }
                    }
                    return {
                        results: items,
                        pagination: {
                            more: (params.page * 30) < data.total_count
                        }
                    };
                },
                cache: true
            },
            dropdownAutoWidth: true,
            dropdownCssClass: 'goods_select2',
            minimumInputLength: 1,
            //placeholder: $(document).find("#hiden_customer_code").text(),
            templateResult: formatRepoItem,
            templateSelection: formatRepoSelection
        });
    }
    $(item).find('[id$="final_price"]').on('change keydown paste input', function (e) {
        calculate_price(e.target);
    });
    // $(item).find('.quantity').on('change keydown paste input', function (e) {
    $(item).find('input[id$="quantity"]').on('change keydown paste input', function (e) {
        // debugger
        calculate_price(e.target);
    });
    $(item).find('[id$="price_method"]').on('change', function (e) {
        set_price(e.target)
    })
    copy_values(item, '-goods_name')
    copy_values(item, 'stock_amount')
    copy_values(item, 'stock_amount_res')
    copy_values(item, 'max_price')
    copy_values(item, 'avg_price')
    copy_values(item, 'min_price')
    copy_values(item, 'avg_count')
    copy_values(item, 'goods_price_sheet1')
    copy_values(item, 'goods_price_sheet2')
    copy_values(item, 'goods_price_sheet3')
    copy_values(item, 'goods_sheet_date', true)
    copy_values(item, 'goods_price_market')
    copy_values(item, 'goods_market_date', true)
    copy_values(item, 'last_price')
    copy_values(item, 'total_sales')
    copy_values(item, 'last_sale', true)
    copy_values(item, 'q_last_price')
    copy_values(item, 'q_total_sales')
    copy_values(item, 'q_last_sale', true)
    const select01 = item.querySelector('[id*="select2-goods_code"][id*="container"]')
    if (select01) {
        select01.innerHTML = item.querySelector('[id*="-goods_code"]').value
        item.querySelector('[id*="select2-goods_code_alt"][id*="container"]').innerHTML = item.querySelector('[id*="-goods_code_alt"]').value
    }
    copy_values(item, '-goods_name_alt')
    const w = item.querySelector('[name*="-goods_code"]')
    const ww = item.querySelector('[name*="-goods_code_alt"]')
    const box = item.querySelector('[name="box-alt-goods"]')
    if (item.querySelector('[name*="-goods_code"]') && (item.querySelector('[name*="-goods_code"]').value != item.querySelector('[name*="-goods_code_alt"]').value)) {
        if (box) {
            box.classList.remove('d-none')
        }
    } else {
        if (box) {
            box.classList.add('d-none')
        }
    }
    // const item = item.querySelector('[class*="final_price"]')
    set_price(item)

}

$.fn.replaceDigits = function () {
    var map =
        [
            "&\#1632;", "&\#1633;", "&\#1634;", "&\#1635;", "&\#1636;",
            "&\#1637;", "&\#1638;", "&\#1639;", "&\#1640;", "&\#1641;"
        ];

    $(this).each(function (item) {
        $(this).html($(this).html().replace(
            /\d(?=[^<>]*(<|$))/g,
            function ($0) {
                return map[$0]
            }
        ));
    });
}
function replaceDigits(){
    let temp = '';
    var map =
        [
            "&\#1632;", "&\#1633;", "&\#1634;", "&\#1635;", "&\#1636;",
            "&\#1637;", "&\#1638;", "&\#1639;", "&\#1640;", "&\#1641;"
        ];
    const el = document.querySelectorAll('.persian-digit')
    el.forEach(function (item){
        if (item.nodeName !== 'INPUT' || item.nodeName !== 'TEXTAREA'){
            for (let i=0; i<=item.value.length; i++){
                console.log(map[item.value[i]])
            }
        } else if (item.nodeName === 'DIV') {
            item.innerHTML = 'akbar'
        }
    })
}
// replaceDigits()
function m_isInt(value) {
    var x;
    if (isNaN(value)) {
        return false;
    }
    x = parseFloat(value);
    return (x | 0) === x;
}

function m_replaceDigits(m_html) {
    return m_html
    let m_text = m_html[0].innerHTML
    var map =
        [
            "&\#1632;", "&\#1633;", "&\#1634;", "&\#1635;", "&\#1636;",
            "&\#1637;", "&\#1638;", "&\#1639;", "&\#1640;", "&\#1641;"
        ];
    for (var i = 0; i < m_text.length; i++) {
        let s = m_text[i]
        if (m_isInt(s)) {
            s = map[s]
            m_text[i] = s
        }
    }
    m_html[0].innerHTML = m_text
    return m_html
}

function t_replaceDigits(m_text) {
    var map =
        [
            "&\#1632;", "&\#1633;", "&\#1634;", "&\#1635;", "&\#1636;",
            "&\#1637;", "&\#1638;", "&\#1639;", "&\#1640;", "&\#1641;"
        ];
    for (var i = 0; i < m_text.length; i++) {
        let s = m_text[i]
        if (m_isInt(s)) {
            s = map[s]
            m_text[i] = s
        }
    }
    return m_text
}

function refresh_prices() {
    const items = $(document).find(".item")
    const party_id = document.getElementById('customer_pid').textContent || -1;
    for (let i = 0; i < items.length; i++) {
        const code = items[i].querySelector('[id*="-goods_code"]').value
        const data = get_price_data(code, party_id)
        set_price_data(data, items[i], items[i])
        const alt_code = items[i].querySelector('[id*="-goods_code_alt"]').value
        if (alt_code != "") {
            const alt_data = get_price_data(alt_code, party_id)
            set_alt_price_data(alt_data, items[i])
        }
    }
}

function get_price_data(code, party_id) {
    $.ajax({
        url: '/sepidar/item_list',
        dataType: "json",
        type: "GET",
        async: false,
        data: {q: code, party_id: party_id, page: 1},
        cache: true,
        success: function (data) {
            result = data;
        }
    });
    if (result.total_count > 0) {
        return result.items[0];
    }
}

function set_price_data(data, elem, target) {
    if (data){
        set_values(elem.querySelectorAll('[name*="-goods_name"]'), data.text)
        set_values(elem.querySelectorAll('[name*="stock_amount"]'), data.stock_qty)
        set_values(elem.querySelectorAll('[name*="stock_amount_res"]'), data.stock_qty_res)
        set_values(elem.querySelectorAll('[name*="max_price"]'), data.max_price)
        set_values(elem.querySelectorAll('[name*="avg_price"]'), data.avg_price)
        set_values(elem.querySelectorAll('[name*="min_price"]'), data.min_price)
        set_values(elem.querySelectorAll('[name*="avg_count"]'), data.f_qty_all)
        set_values(elem.querySelectorAll('[name*="goods_price_sheet1"]'), add_discounts(data.week1, data.yuan_rate, 1, target, data.QTYDis, data.PMDisY, data.PMDisR))
        set_values(elem.querySelectorAll('[name*="goods_price_sheet2"]'), add_discounts(data.week2, data.yuan_rate, 1, target, data.QTYDis, data.PMDisY, data.PMDisR))
        set_values(elem.querySelectorAll('[name*="goods_price_sheet3"]'), add_discounts(data.week3, data.yuan_rate, 1, target, data.QTYDis, data.PMDisY, data.PMDisR))
        set_values(elem.querySelectorAll('[name*="goods_sheet_date"]'), data.date, true)
        set_values(elem.querySelectorAll('[name*="goods_price_market"]'), add_discounts(data.m_price, data.yuan_rate, 2, target, data.QTYDis))
        set_values(elem.querySelectorAll('[name*="goods_market_date"]'), data.m_date, true)
        set_values(elem.querySelectorAll('[name*="last_price"]'), data.f_fee_cust)
        set_values(elem.querySelectorAll('[name*="total_sales"]'), data.f_qty_cust)
        set_values(elem.querySelectorAll('[name*="last_sale"]'), data.f_date_cust, true)
        set_values(elem.querySelectorAll('[name*="q_last_price"]'), data.q_fee_cust)
        set_values(elem.querySelectorAll('[name*="q_total_sales"]'), data.q_qty_cust)
        set_values(elem.querySelectorAll('[name*="q_last_sale"]'), data.q_date_cust, true)
        set_values(elem.querySelectorAll('[name*="-goods_code"]'), data.id,)
        const select = elem.querySelector('[id*="select2-goods_code"][id*="container"]')
        if (select) {
            select.innerHTML = data.id
        }
        if (!data.f_fee_cust) {
            elem.querySelector('[name="box-alt-goods"]').classList.remove('d-none')
            set_values(elem.querySelectorAll('[name*="-goods_name_alt"]'), '',)
            set_values(elem.querySelectorAll('[name*="-goods_code_alt"]'), '',)
        } else {
            elem.querySelector('[name="box-alt-goods"]').classList.add('d-none')
        }
        set_price(elem.querySelector('[name*="-goods_name"]'))
    }
}

function set_alt_price_data(data, elem) {
    if (data.f_fee_cust != '') {
        set_values(elem.querySelectorAll('[name*="-goods_name_alt"]'), data.text)
        set_values(elem.querySelectorAll('[name*="last_price"]'), data.f_fee_cust)
        set_values(elem.querySelectorAll('[name*="total_sales"]'), data.f_qty_cust)
        set_values(elem.querySelectorAll('[name*="last_sale"]'), data.f_date_cust, true)
        set_values(elem.querySelectorAll('[name*="q_last_price"]'), data.q_fee_cust)
        set_values(elem.querySelectorAll('[name*="q_total_sales"]'), data.q_qty_cust)
        set_values(elem.querySelectorAll('[name*="q_last_sale"]'), data.q_date_cust, true)
        set_values(elem.querySelectorAll('[name*="-goods_code_alt"]'), data.id,)
        elem.querySelector('[id*="select2-goods_code_alt"][id*="container"]').innerHTML = data.id
    }
    set_price(elem.querySelector('[name*="-goods_name"]'))
}

function set_price(target) {
    const elem = findAncestor(target, "item")
    const price_method = elem.querySelector('[name*="price_method"]')
    const final_price = elem.querySelector('[name*="-final_price"]')
    final_price.disabled = true;

    let p_m = price_method.getAttribute('value')
    if (!p_m) {
        p_m = price_method.value
    }
    switch (p_m) {
        case 'last_sale':
            final_price.value = elem.querySelector('[name*="goods_last_price"]').value;
            final_price.innerHTML = numberWithCommas(elem.querySelector('[name*="goods_last_price"]').value);
            break;
        case 'last_sale_q':
            final_price.value = elem.querySelector('[name*="goods_q_last_price"]').value;
            final_price.innerHTML = numberWithCommas(elem.querySelector('[name*="goods_q_last_price"]').value);
            break;
        case 'price_avg':
            final_price.value = elem.querySelector('[name*="goods_avg_price"]').value;
            final_price.innerHTML = numberWithCommas(elem.querySelector('[name*="goods_avg_price"]').value);
            break;
        case 'sales_admin':
            final_price.disabled = false;
            break;
        case 'price_sheet1':
            final_price.value = elem.querySelector('[name*="goods_price_sheet1"]').value;
            final_price.innerHTML = numberWithCommas(elem.querySelector('[name*="goods_price_sheet1"]').value);
            break;
        case 'price_sheet2':
            final_price.value = elem.querySelector('[name*="goods_price_sheet2"]').value;
            final_price.innerHTML = numberWithCommas(elem.querySelector('[name*="goods_price_sheet2"]').value);
            break;
        case 'price_sheet3':
            final_price.value = elem.querySelector('[name*="goods_price_sheet3"]').value;
            final_price.innerHTML = numberWithCommas(elem.querySelector('[name*="goods_price_sheet3"]').value);
            break;
        case 'price_market':
            final_price.value = elem.querySelector('[name*="goods_price_market"]').value;
            final_price.innerHTML = numberWithCommas(elem.querySelector('[name*="goods_price_market"]').value);
            break;
    }
    calculate_price(target)
}

function hide_show_goods_alt(el) {

    const elem = findAncestor(el, 'item')
    const box = elem.querySelector('[name="box-alt-goods"]')
    if (box.classList.contains('d-none')) {
        box.classList.remove('d-none')
        set_values(elem.querySelectorAll('[name*="-goods_name_alt"]'), '',)
        set_values(elem.querySelectorAll('[name*="-goods_code_alt"]'), '',)
    } else {
        box.classList.add('d-none')
    }
    elem.querySelector('.answer').style.height = 'fit-content'
}

function formatRepoDL(repo) {
    if (repo.loading) {
        return repo.text;
    }

    var $container = $(
        "<div class='select2-result-repository clearfix'>" +
        "<td class='select2-result-repository__meta' >" + repo.id + "</td>" +
        "<td class='select2-result-repository__title' >(" + repo.text + ")</td>" +
        "</div>"
    );
    return $container;
}

function formatRepoSelection(repo) {
    return repo.id || repo.text
}

function formatRepoItem(repo) {
    if (repo.loading) {
        return repo.text;
    }
    var $container = $(
        "<div class='w-100 replace-digits' dir='rtl' style='font-family: BYekan'>" +
        "<div class='d-flex border'>" +
        "<div class='border w-15' >" +
        "<div>" + repo.id + "</div>" +
        "<div> " + numberWithCommas(repo.stock_qty, 0) + " </div>" +
        "<div> " + numberWithCommas(repo.stock_qty_res, 0) + " </div>" +
        "</div>" +
        "<div class='w-30 border'>" +
        "<div >" + repo.text + "</div>" +
        "</div>" +
        "<div class='alert-warning w-20 border'>" +
        "<div class=''>" +
        "<div class=''>" + repo.f_date_cust + "</div>" +
        "<div class=''>" + numberWithCommas(repo.f_qty_cust, 0) + "</div>" +
        "<div class=''>" + numberWithCommas(repo.f_fee_cust, 1) + "</div>" +
        "</div> </div> " +
        "<div class='bg-soft-pink w-20 border'>" +
        "<div class=''>" +
        "<div class=''>" + repo.q_date_cust + "</div>" +
        "<div class=''>" + numberWithCommas(repo.q_qty_cust, 0) + "</div>" +
        "<div class=''>" + numberWithCommas(repo.q_fee_cust, 1) + "</div>" +
        "</div> </div> " +
        "<div class='w-15'>" +
        "<div class=''>" +
        "<div class=''>" + numberWithCommas(repo.max_price, 1) + "</div>" +
        "<div class=''>" + numberWithCommas(repo.avg_price, 1) + "</div>" +
        "<div class=''>" + numberWithCommas(repo.min_price, 1) + "</div>" +
        "</div></div>" +
        "<div class='w-40 border'>" +
        "<div class='d-flex c-3-color'>" +
        "<div class=' w-40'>" +
        "<div>." + (add_discounts(repo.week1, repo.yuan_rate, 1, null, repo.QTYDis, repo.PMDisY, repo.PMDisR)) + "</div>" +
        "<div>." + (add_discounts(repo.week2, repo.yuan_rate, 1, null, repo.QTYDis, repo.PMDisY, repo.PMDisR)) + "</div>" +
        "</div>" +
        "<div class='w-60'>" +
        "<div>." + (add_discounts(repo.week3, repo.yuan_rate, 1, null, repo.QTYDis, repo.PMDisY, repo.PMDisR)) + "</div>" +
        "<div class='c-3-color'>" + repo.date + "</div>" +
        "</div>" +
        "</div>" +
        "<div class='d-flex'> " +
        "<div class='w-40'>" + (add_discounts(repo.m_price, repo.yuan_rate, 2)) + "</div>" +
        "<div class='w-60'>" + repo.m_date + "</div>" +
        "</div> " +
        "</div> " +
        "</div></div>"
    );
    return ($container);
}

function findAncestor(el, cls) {
    if (el.classList.contains(cls)) {
        return el
    }
    while ((el = el.parentElement) && !el.classList.contains(cls)) ;
    return el;
}

function numberWithCommas(x, digits = 2) {
    if (x == '' || x == null || isNaN(x)) return ''
    x = parseFloat(x)
    let res = (x.toLocaleString('en-US', {maximumFractionDigits: digits}))//t_replaceDigits
    return res
}

function calculate_price(target) {
    // debugger
    const elem = findAncestor(target, "item")
    const final_price = elem.querySelector('[name*="-final_price"]')
    const total_price = elem.querySelector('[name*="-total_price"]')
    const quantity = elem.querySelector('input[id$="quantity"]')

    let qty = parseFloat(quantity.innerHTML.replaceAll(',', ''))
    if (isNaN(qty)) {
        qty = quantity.value.replaceAll(',', '')
    }
    let price = parseFloat(final_price.innerHTML.replaceAll(',', ''))
    if (isNaN(price)) {
        price = final_price.value
    }
    total_price.innerHTML = numberWithCommas(price * qty)

    var items = document.querySelectorAll('[name="-total_price"]')
    let m_sum = 0
    for (let i = 0; i < items.length; i++) {
        val = parseFloat(items[i].innerHTML.replaceAll(',', ''))
        if (!isNaN(val)) {
            m_sum += val
        }
    }
    if (!m_sum) {
        m_sum = 0
    }
    const t_prices = $(document).find('.quotation_total_price')
    for (let i = 0; i < t_prices.length; i++) {
        t_prices[i].innerHTML = numberWithCommas(m_sum, 0).toString()
    }
}

function add_discounts(value, yuan_rate, type = 1, target = null, QTYDis = null, PMDisY = null, PMDisR = null) {
    const currency_ref = parseInt(document.getElementById('id_currency_ref').value)
    if (type == 1) {
        var payment_method = parseFloat((document.getElementById('id_payment_method').value).split(','))
        payment_method = Math.floor(payment_method / 3)
        if (currency_ref == 1) {
            payment_method = PMDisR[payment_method]
        } else {
            payment_method = PMDisY[payment_method]
        }
        var customer_grade = parseFloat((document.getElementById('id_customer_grade').value).split(','))
        if (target) {
            var quantity = parseFloat(findAncestor(target, "item").querySelector('input[id*="quantity"]').value)
            quantity = Math.floor(Math.log10(quantity))
            quantity = QTYDis[quantity]
            if (isNaN(quantity)) {
                quantity = 0;
            }
        } else {
            var quantity = 0;
        }
        const discount = payment_method + customer_grade + quantity
        if (currency_ref == 1) {
            return numberWithCommas(value * yuan_rate * (100 + discount) / 100, 0)
        } else {
            return numberWithCommas(value * (100 + discount) / 100, 4)
        }
    } else {
        const discount = parseFloat((document.getElementById('id_market_grade').value).split(','))
        return numberWithCommas(value * (100 + discount) / 100, 0)
    }

}

function set_values(items, value, is_date = false) {
    let value_str = value
    if (!isNaN(parseInt(value)) && !is_date) {
        value = parseFloat(value.toString().replaceAll(',', ''))
        value_str = numberWithCommas(value)
    }
    for (let i = 0; i < items.length; i++) {
        if (items[i].tagName && items[i].tagName.toLowerCase() == "input") {
            if (value == '-') {
                value = null
            }
            items[i].value = value;
            //items[i].text = value;
        } else {
            items[i].innerHTML = value_str;
        }
    }
}

function copy_values(elem, name, is_date = false) {
    const e = elem.querySelector('input[name*="' + name + '"]')
    const items = elem.querySelectorAll('[name*="' + name + '"]')
    if (!e) {
        return
    }
    var value_str = e.value.toString()
    if (!isNaN(parseInt(e.value)) && !is_date) {
        value_str = numberWithCommas(e.value)
    }
    if (!value_str) {
        value_str = '-'
    }
    for (let i = 0; i < items.length; i++) {
        if (items[i].tagName && items[i].tagName.toLowerCase() == "input") {
            //items[i].value = value;
            //items[i].text = value;
        } else {
            items[i].innerHTML = value_str;
        }
    }
}

function do_print(data) {
    const d = "{{greeting}}"
    const form = document.forms['main_form'];
    ajax_submit(form)
    const target = document.querySelector('[name="do_print"]');
    const href = target.getAttribute('m-href');
    printJS({
        printable: ['https://cdn.shopify.com/s/files/1/0284/4946/products/IMG_8999_720x.jpg?v=1580507812', 'https://bloomex.ca/components/com_virtuemart/shop_image/product/Make-a-Wish-LF102-53.png', 'https://s3.amazonaws.com/cdn.brecksbulbs.ca/images/500/60053.jpg'],
        type: 'image',
        header: 'Multiple Images',
        imageStyle: 'width:50%;margin-bottom:20px;'
    })
    // window.location.href = href;
    let w = window.open('', '_blank');
    w.location.href = href
    w.print()
    //w.close()
}

function ajax_submit(form) {
    $.ajax({ // create an AJAX call...
        data: $(form).serialize(), // get the form data
        type: $(form).attr('method'), // GET or POST
        url: $(form).attr('action'), // the file to call
    });
}

function addPageNumbers() {
    var totalPages = Math.ceil(document.body.scrollHeight / 1123);  //842px A4 pageheight for 72dpi, 1123px A4 pageheight for 96dpi,
    for (var i = 1; i <= totalPages; i++) {
        var pageNumberDiv = document.createElement("div");
        var pageNumber = document.createTextNode("صفحه " + i + " از " + totalPages);
        pageNumberDiv.style.position = "absolute";
        pageNumberDiv.style.top = "calc((" + i + " * (297mm - 0.5px)) - 40px)"; //297mm A4 pageheight; 0,5px unknown needed necessary correction value; additional wanted 40px margin from bottom(own element height included)
        pageNumberDiv.style.height = "16px";
        pageNumberDiv.appendChild(pageNumber);
        document.body.insertBefore(pageNumberDiv, document.getElementById("content"));
        pageNumberDiv.style.left = "calc(100% - (" + pageNumberDiv.offsetWidth + "px + 20px))";
    }
}

function scroll_down() {
    window.scrollTo(0, document.body.scrollHeight);
}


// function setQuotationHeaderInfo(data){
//     const items = document.querySelectorAll('.item')
//     items.forEach(function (item){
//         const code = item.querySelector('[name*="-goods_code"]')
//         const name = item.querySelector('[name*="-goods_name_lbl"]')
//         const count = item.querySelector('[name*="-quantity"]')
//         const unitPrice = item.querySelector('[name*="-final_price"]')
//         const totalPrice = item.querySelector('[name*="-total_price"]')
//     })
// }
// ==================================================



// Select the node that will be observed for mutations
// const targetNode = document.getElementById("id_formset_container");

// Options for the observer (which mutations to observe)
// const config = {childList: true, subtree: false };

// Callback function to execute when mutations are observed
// const callback = (mutationList, observer) => {
//   for (const mutation of mutationList) {
//     if (mutation.type === "childList") {
//         items = document.querySelectorAll('.question-btn');
//         items.forEach(function(item) {
//             if (item.classList.contains('question-btn')){
//                  item.addEventListener('click', function(e) {
//                   const answer = e.currentTarget.nextElementSibling;
//                   if (answer.offsetHeight > 0) {
//                       answer.style.height = 0;
//                       answer.style.overflow = 'hidden';
//                       answer.previousElementSibling.classList.remove('active-form')
//                       // debugger
//                       showQuotationFormsetHeader(answer)
//                   } else {
//                       answer.style.height = answer.scrollHeight + 'px';
//                       answer.previousElementSibling.classList.add('active-form')
//                       hideQuotationFormsetHeader(answer)
//                   }
//                  })
//             }
//         }) // forEach
//     } // end if
//   } // for
// };
// Create an observer instance linked to the callback function
// const observer = new MutationObserver(callback);

// Start observing the target node for configured mutations
// observer.observe(targetNode, config);

// observer.disconnect();



// const hiddenInput = document.querySelectorAll('input[class="form-control"]');
// const formsetItem = document.querySelectorAll('.item');
// formsetItem.forEach(function (item){
//     const hiddenInputs = item.querySelectorAll(`input[type='hidden']`)
//     const quotationFormsetHeader = item.querySelector('.question-btn')
//     console.log(quotationFormsetHeader)
//     if (quotationFormsetHeader) {
//         hiddenInputs.forEach(function (item){
//             console.log(`span[name*="${item.name}"]`)
//             const c = quotationFormsetHeader.querySelectorAll(`span[name*="${item.name}"]`)
//             console.log(c)
//         })
//     }
// })

// hiddenInput.forEach(function (item) {
    // const t = document.querySelectorAll(`[name*="${item.name}"]`)
    // const b = document.querySelectorAll(`[name*="${item.name}"]`)
    // console.log(t)
// })

