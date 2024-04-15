$(document).ready(function (){
    // const elem = document.querySelector('.goods_code')
    // if (elem) {
    //     applySelect2Ajax('#customer_code', 'customer_code','/sepidar/customers_list', 'json', 'GET', 'select', 1,
    //         {text: document.querySelector('[name="customer_code"]').value.toString(),},
    //         formatRepoDL, formatRepoSelection
    //     )
    // }

    const items = document.querySelectorAll(".item")
    items.forEach(function (item, idx){
        console.log(item.querySelectorAll('input[type=hidden]'))
        console.log('init data for: ', item)
        initDataFromHiddenForm(item, 'quotation', idx, ['delivery_time', 'goods_code', 'goods_name' ,
            'stock_amount' ,'stock_amount_res' ,'goods_max_price' ,'goods_avg_price' ,'goods_min_price' ,'goods_avg_count' ,
            'goods_price_sheet1' ,'goods_price_sheet2' ,'goods_price_sheet3' ,'goods_sheet_date' ,
            'goods_price_market' ,'goods_market_date' ,'goods_last_price' ,'goods_total_sales' ,'goods_last_sale' ,
            'goods_q_last_price' ,'goods_q_total_sales' ,'goods_q_last_sale'])
        // set_item_classes(items[i])
    })
    // for (let i = 0; i < items.length; i++) {
    //     initDataFromHiddenForm(items[i], 'quotation', i, ['delivery_time', 'goods_code', 'goods_name' ,
    //         'stock_amount' ,'stock_amount_res' ,'goods_max_price' ,'goods_avg_price' ,'goods_min_price' ,'goods_avg_count' ,
    //         'goods_price_sheet1' ,'goods_price_sheet2' ,'goods_price_sheet3' ,'goods_sheet_date' ,
    //         'goods_price_market' ,'goods_market_date' ,'goods_last_price' ,'goods_total_sales' ,'goods_last_sale' ,
    //         'goods_q_last_price' ,'goods_q_total_sales' ,'goods_q_last_sale'])
    //     set_item_classes(items[i])
        // console.log('init data for: ', items[i])
    // }
});

function initDataFromHiddenForm(item, model, idx, fields){
    let sourceElementAttributeName, sourceElementAttributeId, targetElementAttributeId,
        targetElementAttributeName, sourceElement, targetElement, ajaxData;

    const party_id = document.getElementById('customer_pid').textContent || -1;
    const code = item.querySelector('[id*="goods_code"]').value
    console.log(party_id)
    console.log(code)
    ajaxData = get_price_data(18620, party_id);
    set_price_data(ajaxData, item)
    console.log('ajaxData: ', ajaxData)
    for (let i = 0; i < fields.length; i++) {
        sourceElementAttributeName = `${model}-${idx}-${fields[i]}`
        sourceElementAttributeId = `id_${model}-${idx}-${fields[i]}`
        targetElementAttributeName = fields[i]
        targetElementAttributeId = `${fields[i]}_${idx+1}`

        sourceElement = item.querySelector(`#${sourceElementAttributeId}`);
        // '[name*="-goods_name_alt"]'
        targetElement = item.querySelector(`[name=${targetElementAttributeName}]`);

        if (targetElement && targetElement.tagName.toLowerCase() === 'input') {
            targetElement.value = sourceElement.value;
            console.log('input element')
        } else if (targetElement) {
            targetElement.innerHTML = sourceElement.value;
            console.log('div element')
        }
        console.log('fields=== ', fields[i])
        console.log("sourceElement ", sourceElement)
        console.log("targetElement ", targetElementAttributeId, targetElement)
    }
}

function get_price_data(code, party_id) {
    $.ajax({
        url: '/sepidar/item_list2',
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




// ===================================
function refresh_prices() {
    const items = $(document).find(".item")
    const party_id = document.getElementById('customer_pid').textContent || -1;
    for (let i = 0; i < items.length; i++) {
        const code = items[i].querySelector('[id*="-goods_code"]').value
        console.log('goods_code_data....', code)
        const data = get_price_data(code, party_id)
        console.log(data)
        if (data) {
            set_price_data(data, items[i], items[i])
            const select = items[i].querySelector('[id*="select2-goods_code"][id*="container"]')
            if (select) {
                select.innerHTML = data['goods_code']
                console.log('select item ', data['goods_code'])
            }

            if (!data['last_price']) {
                items[i].querySelector('[name="box-alt-goods"]').classList.remove('d-none')
                set_values(items[i].querySelectorAll('[name*="-goods_name_alt"]'), '',)
                set_values(items[i].querySelectorAll('[name*="-goods_code_alt"]'), '',)
            } else {
                items[i].querySelector('[name="box-alt-goods"]').classList.add('d-none')
            }
            set_price(items[i].querySelector('[name*="-goods_name"]'))
        } // end if

        const alt_code = items[i].querySelector('[id*="-goods_code_alt"]').value
        console.log('goods_code_alt data....', alt_code[0])
        if (alt_code != "") {
            const alt_data = get_price_data(alt_code.replaceAll(',', ''), party_id)
            set_alt_price_data(alt_data, items[i])
        }
    }
}

function set_price_data(dataJson, elem, target, mapDict) {
    // data = {'field_name': 'value'}
    let d = JSON.stringify(dataJson)
    d = JSON.parse(d)
    console.log(d)
    for(let key in d){
        set_values(elem.querySelectorAll(`[name*="${key}"]`), d[key], d[key])
    }
    console.log('****************')



    // set_values(elem.querySelectorAll('[name*="-goods_name"]'), data.text)
    // set_values(elem.querySelectorAll('[name*="stock_amount"]'), data.stock_qty)
    // set_values(elem.querySelectorAll('[name*="stock_amount_res"]'), data.stock_qty_res)
    // set_values(elem.querySelectorAll('[name*="max_price"]'), data.max_price)
    // set_values(elem.querySelectorAll('[name*="avg_price"]'), data.avg_price)
    // set_values(elem.querySelectorAll('[name*="min_price"]'), data.min_price)
    // set_values(elem.querySelectorAll('[name*="avg_count"]'), data.f_qty_all)
    // set_values(elem.querySelectorAll('[name*="goods_price_sheet1"]'), add_discounts(data.week1, data.yuan_rate, 1, target, data.QTYDis, data.PMDisY, data.PMDisR))
    // set_values(elem.querySelectorAll('[name*="goods_price_sheet2"]'), add_discounts(data.week2, data.yuan_rate, 1, target, data.QTYDis, data.PMDisY, data.PMDisR))
    // set_values(elem.querySelectorAll('[name*="goods_price_sheet3"]'), add_discounts(data.week3, data.yuan_rate, 1, target, data.QTYDis, data.PMDisY, data.PMDisR))
    // set_values(elem.querySelectorAll('[name*="goods_sheet_date"]'), data.date, true)
    // set_values(elem.querySelectorAll('[name*="goods_price_market"]'), add_discounts(data.m_price, data.yuan_rate, 2, target, data.QTYDis))
    // set_values(elem.querySelectorAll('[name*="goods_market_date"]'), data.m_date, true)
    // set_values(elem.querySelectorAll('[name*="last_price"]'), data.f_fee_cust)
    // set_values(elem.querySelectorAll('[name*="total_sales"]'), data.f_qty_cust)
    // set_values(elem.querySelectorAll('[name*="last_sale"]'), data.f_date_cust, true)
    // set_values(elem.querySelectorAll('[name*="q_last_price"]'), data.q_fee_cust)
    // set_values(elem.querySelectorAll('[name*="q_total_sales"]'), data.q_qty_cust)
    // set_values(elem.querySelectorAll('[name*="q_last_sale"]'), data.q_date_cust, true)
    // set_values(elem.querySelectorAll('[name*="-goods_code"]'), data.id,)


    // const select = elem.querySelector('[id*="select2-goods_code"][id*="container"]')
    // if (select) {
    //     select.innerHTML = d['goods_code']
    //     console.log('select item ', d['goods_code'])
    // }
    //
    // if (!dataJson['last_price']) {
    //     elem.querySelector('[name="box-alt-goods"]').classList.remove('d-none')
    //     set_values(elem.querySelectorAll('[name*="-goods_name_alt"]'), '',)
    //     set_values(elem.querySelectorAll('[name*="-goods_code_alt"]'), '',)
    // } else {
    //     elem.querySelector('[name="box-alt-goods"]').classList.add('d-none')
    // }
    // set_price(elem.querySelector('[name*="-goods_name"]'))
}

function set_alt_price_data(data, elem) {
    if (data['last_price'] != '') {
        console.log('================= goods name alt', data.text)
        // data = {'field_name': 'value'}
        let d = JSON.stringify(data)
        d = JSON.parse(d)
        for(let key in d){
            set_values(elem.querySelectorAll(`[name*="${key}"]`), d[key])
        }
        elem.querySelector('[id*="select2-goods_code_alt"][id*="container"]').innerHTML = data['goods_code']
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
        "<div class='w-100 replace-digits text-center' dir='rtl' style='font-family: BYekan'>" +
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

    const elem = findAncestor(target, "item")
    const final_price = elem.querySelector('[name*="-final_price"]')
    const total_price = elem.querySelector('[name*="-total_price"]')
    const quantity = elem.querySelector('[name*="quantity"]')

    let qty = parseFloat(quantity.innerHTML.replaceAll(',', ''))
    if (isNaN(qty)) {
        qty = quantity.value
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
        console.log('value ', value)
        console.log('value str', value_str)
    }
    for (let i = 0; i < items.length; i++) {
        if (items[i].tagName && items[i].tagName.toLowerCase() == "input") {
            if (value == '-') {
                value = null
            }
            items[i].value = value_str;
            //items[i].text = value;
            // console.log(`${items[i].getAttribute('name')} - set value ${i} of ${items.length - 1} INPUT : `, value_str)
        } else {
            items[i].innerHTML = value_str;
            // console.log(`${items[i].getAttribute('name')} - set value ${i} of ${items.length - 1} inner html: `, value_str)
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
            // items[i].value = value_str;
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




// ===================================
function applySelect2Ajax(selectorString, name, ajaxUrl, requestDataType,
                      requestMethod, select2Event, minimumInputLength=1,
                      placeholder, templateResult, templateSelection) {
    // ajax GET for select2
    const E = document.querySelector(selectorString)
    $(selectorString).select2({
        ajax: {
            url: ajaxUrl,
            dataType: requestDataType,
            type: requestMethod,
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
        minimumInputLength: minimumInputLength,
        // placeholder: {text: document.querySelector('[name="customer_code"]').value.toString(), },
        placeholder: placeholder,
        allowClear: false,
        // templateResult: formatRepoDL,
        // templateSelection: formatRepoSelection
        templateResult: templateResult,
        templateSelection: templateSelection
    });

    // select2 manage data
    $(selectorString).on(`select2:${select2Event}`, function (e) {
        const data = e.params.data;
        document.querySelector(`[name=${name}]`).value = data.id; // fill hidden input
        document.querySelector('[id*="select2-customer_code"][id*="container"]').querySelector('span').innerHTML = data.id; // fill select2 span
        // extra action for fill visible data
        $(document).find("#customer_card").attr("class", "bg-soft-success h-100 p-2");
        $(document).find("#customer_name").text(data.text);
        $(document).find("#customer_pid").text(data.pid);
    })
}

function copyValue(targetElement, names) {
    let e = undefined;
    let items = undefined;
    let value_str = undefined;
    names.forEach(function (name){
        e = targetElement.querySelector('input[name*="' + name[0] + '"]')
        items = targetElement.querySelectorAll('[name*="' + name[0] + '"]')
        if (!isNaN(parseInt(e.value)) && !e.classList.contains('jalali_date-date')) {
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
    })
}

function setValues(elem_items) {
    let item, value, is_date, value_str;
    elem_items.forEach(function (item_list){
        // item_list = ['item', 'value', 'is_date']
        item = item_list[0]
        value = item_list[1]
        is_date = item_list[2]
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
            } else {
                items[i].innerHTML = value_str;
            }
        }
    })
}

function setValues2(elem){

}
// ===================================
function HiddenFieldsetValue(inputData) {
    const items = document.querySelectorAll('.item')
}
function ajaxCallByForm(form) {
    $.ajax({ // create an AJAX call...
        data: $(form).serialize(), // get the form data
        type: $(form).attr('method'), // GET or POST
        url: $(form).attr('action'), // the file to call
    });
}

function ajaxCallByData(url, data={}, method='GET') {
    $.ajax({ // create an AJAX call...
        data: $(form).serialize(), // get the form data
        type: $(form).attr('method'), // GET or POST
        url: $(form).attr('action'), // the file to call
    });
}