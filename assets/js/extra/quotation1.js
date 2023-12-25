$(document).ready(function () {
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
    $('#customer_code').on("select2:select", function (e) {
        const data = e.params.data;
        document.querySelector('[name="customer_code"]').value = data.id
        document.querySelector('[id*="select2-customer_code"][id*="container"]').querySelector('span').innerHTML = data.id
        $(document).find("#customer_card").attr("class", "alert-warning h-100 p-2");
        $(document).find("#customer_name").text(data.text);
        $(document).find("#customer_pid").text(data.pid);
    })
    $('.goods_code').on("select2:select", function (e) {
        const elem = findAncestor(e.target, "item")
        const data = e.params.data;
        elem.getElementsByClassName('goods_name')[0].value = data.text
        //$(elem).find('.goods_name').text(data.text);
        elem.getElementsByClassName("stock_amount")[0].value = parseFloat(data.stock_qty)
        //$(elem).find('.stock_amount').attr('value', data.stock_qty);
        elem.getElementsByClassName("goods_avg_price")[0].value = parseFloat(data.avg_price)
        // $(elem).find('.goods_avg_price').attr('value', data.avg_price);
        $(elem).find('.goods_price_sheet').text("");
        $(elem).find('.goods_sheet_date').text("");
        elem.getElementsByClassName("goods_total_sales")[0].value = parseFloat(data.f_qty_all)
        //$(elem).find('.goods_total_sales').attr('value', data.f_qty_all);
        //debugger
        //const qt = (elem).querySelector('[id*="goods_code_alt-container"][class*="select2"]');
        //qt.innerHtml = 'ss'
        if (data.f_fee_cust != '') {
            //(elem).getElementsByClassName('goods_code_alt')[0].placeholder = data.id
            $(elem).find('.goods_name_alt').text(data.text)
            const mm = elem.querySelector('[id*="goods_last_sale"]').querySelector('[id*="goods_last_sale"]')
            mm.value = data.f_date_cust
            elem.getElementsByClassName("goods_last_price")[0].value = parseFloat(data.f_fee_cust)
            //$(elem).find('.goods_last_price').attr('value', data.f_fee_cust)
        }
        set_price(e.target)
    })
    $('.goods_code_alt').on("select2:select", function (e) {
        var elem = findAncestor(e.target, "item")
        var data = e.params.data;
        if (data.f_fee_cust != '') {
            (elem).getElementsByClassName('goods_code_alt').value = data.id
            $(elem).find('.goods_name_alt').text(data.text)
            $(elem).find('.goods_last_sale').attr('value', data.f_date_cust)
            $(elem).find('.goods_last_price').attr('value', data.f_fee_cust)
        }
        set_price(e.target)
    })
    $('input[type=radio][m-data="price_method"]').on('change', function (e) {
        set_price(e.target)
    })
    $('.goods_code').select2({
        ajax: {
            url: '/sepidar/itemss_list',
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
        headers: ['test1', 'teste'],
        dropdownAutoWidth: true,
        minimumInputLength: 1,
        //placeholder: $(document).find("#customer_code").text(),
        templateResult: formatRepoItem,
        templateSelection: formatRepoSelection
    });
    $('.goods_code_alt').select2({
        ajax: {
            url: '/sepidar/itemss_list',
            dataType: "json",
            type: "GET",
            data: function (data) {
                var p_id = document.getElementById('customer_pid').textContent;
                return {q: data.term, party_id: p_id, page: data.page}
            },
            processResults: function (data, params) {
                params.page = params.page || 1;
                var items = [];
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
        minimumInputLength: 1,
        //placeholder: $(document).find("#hiden_customer_code").text(),
        templateResult: formatRepoItem,
        templateSelection: formatRepoSelection
    });
    $(".final_price").on('change keydown paste input', function (e) {
        calculate_price(e.target);
    });
    $(".quantity").on('change keydown paste input', function (e) {
        calculate_price(e.target);
    });

    const items = $(document).find(".item")
    const c = document.getElementById('select2-customer_code-container')
    //alert(document.getElementsByName("customer_code")[0].value)
    //c.innerText = '100';
    //c.value = 100;

    for (const i in items) {
        const item = items[i].getElementsByClassName('final_price')[0]
        set_price(item)
    }
});


function set_price(target) {
    const elem = findAncestor(target, "item")
    const final_price = (elem).getElementsByClassName('final_price')[0]
    const quantity = (elem).getElementsByClassName('quantity')[0]
    final_price.disabled = true;
    switch ($(elem).find('[m-data="price_method"]:checked')[0].value) {
        case 'last_sale':
            final_price.value = elem.getElementsByClassName("goods_last_price")[0].value;
            break;
        case 'price_sheet':
            final_price.value = elem.getElementsByClassName("goods_price_sheet")[0].value;
            break;
        case 'price_avg':
            final_price.value = elem.getElementsByClassName("goods_avg_price")[0].value;
            break;
        case 'sales_admin':
            final_price.disabled = false;
            break;
    }
    calculate_price(target)
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
        "<div class='select2-result-repository clearfix w-100'>" +
        "<div class='row'>" +
        "<div class='col-lg-2' >" +
        "<div>" + repo.id + "</div>" +
        "<div> (" + numberWithCommas(repo.stock_qty, 0) + ") </div>" +
        "</div>" +
        "<div class='col-lg-2'>" +
        "<div >" + repo.text + "</div>" +
        "</div>" +
        "<div class='col-lg-3 alert-warning'>" +
        "<div class='row'>" +
        "<div class='col-lg-6'>" + numberWithCommas(repo.f_fee_cust, 1) + "</div>" +
        "<div class='col-lg-6 ms-lg-auto'>" + numberWithCommas(repo.f_qty_cust, 0) + "</div>" +
        "<div class=''>" + repo.f_date_cust + "</div>" +
        "</div> </div> " +
        "<div class='col-lg-3 ms-lg-auto'>" +
        "<div class='row c-3-color'>" +
        "<div class='col-lg-5'>" +
        "<div>" + add_discounts(repo.week1, repo.yuan_rate) + "</div>" +
        "<div>" + add_discounts(repo.week2, repo.yuan_rate) + "</div>" +
        "</div>" +
        "<div class='col-lg-7 ms-lg-auto'>" +
        "<div>" + add_discounts(repo.week3, repo.yuan_rate) + "</div>" +
        "<div>" + repo.date + "</div>" +
        "</div>" +
        "</div>" +
        "<div class='d-flex'> " +
        "<div class='w-50'>" + add_discounts(repo.m_price, repo.yuan_rate, 2) + "</div>" +
        "<div class='w-50'>" + repo.m_date + "</div>" +
        "</div> " +
        "</div> " +
        "<div class='col-lg-2'>" +
        "<div class='row'>" +
        "<div class='col-lg-6'>" + numberWithCommas(repo.avg_price, 1) + "</div>" +
        "<div class='col-lg-6 ms-lg-auto'>" + numberWithCommas(repo.f_qty_all, 0) + "</div>" +
        "</div></div>" +
        "</div></div>"
    );
    return $container;
}

function findAncestor(el, cls) {
    while ((el = el.parentElement) && !el.classList.contains(cls)) ;
    return el;
}

function numberWithCommas(x, digits = 2) {
    if (x == '' || x == null) return '-'
    x = parseFloat(x)
    return x.toLocaleString('en-US', {maximumFractionDigits: digits})
}

function calculate_price(target) {
    const elem = findAncestor(target, "item")
    const final_price = (elem).getElementsByClassName('final_price')[0]
    const quantity = (elem).getElementsByClassName('quantity')[0]
    $(elem).find('.total_price')[0].innerHTML = numberWithCommas(parseFloat(final_price.value) * parseFloat(quantity.value))
}

function add_discounts(value, yuan_rate, type = 1, target = null, QTYDis = null) {
    debugger
    const currency_ref = parseInt(document.getElementById('id_currency_ref').value)
    if (type == 1) {
        var payment_method = parseFloat((document.getElementById('id_payment_method').value).split(','))
        if (currency_ref == 1) {
            payment_method *= (5 / 3)
        }
        var customer_grade = parseFloat((document.getElementById('id_customer_grade').value).split(','))
        if (target) {
            var quantity = findAncestor(target, "item").querySelector('[id*="quantity"]').value
            quantity = Math.floor(Math.pow(quantity, 0.1))
            quantity = QTYDis[quantity]
        } else {
            var quantity = 0
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

