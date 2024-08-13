function copy_values(elem, name, is_date = false) {
    const e = elem.querySelector('input[name*="' + name + '"]')
    const items = elem.querySelectorAll('[name*="' + name + '"]')
    if (!e) {
        return
    }
    var value_str = e.value.toString()
    if (!isNaN(e.value) && !is_date) {
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

function set_values(items, value, is_date = false) {
    debugger
    let value_str = value
    if (!isNaN(parseInt(value)) && !is_date) {
        value = parseFloat(value.toString().replaceAll(',', ''))
        value_str = numberWithCommas(value)
    }
    for (let i = 0; i < items.length; i++) {
        items[i].classList.remove('d-none')
        if (items[i].tagName && items[i].tagName.toLowerCase() == "input") {
            if (value == '-') {
                value = null
            }
            if (value == undefined || value == '-'){value=''}
            items[i].value = value;
            //items[i].text = value;
        } else {
            if (value_str == undefined || value_str == '-'){value_str=''}
            items[i].innerHTML = value_str;
        }
    }
}

$(document).ready(function () {
    $('#id_select_quotation_for_factor').select2({
        dir: 'ltr',
        ajax: {
            delay: 150,
            // url: '/sepidar/items_list',
            url: '/factor/search',
            dataType: "json",
            type: "GET",
            data: function (data) {
                console.log('inside data', data)
                return {
                    q: data.term, page: data.page, // party_id: p_id,
                }
            },
            processResults: function (data, params) {
                params.page = params.page || 1;
                const div = document.createElement('div')
                const s = document.createTextNode(`<div class="row bg-light-info sticky-top">
            <div class="col-3">
                <span>شرکت</span>
            </div>
            <div class="col-2">
                <span>پیش فاکتور</span>
            </div>
            <div class="col-1">
                <span>تعداد ردیف</span>
            </div>
            <div class="col-2">
                <span>کارشناس</span>
            </div>
            <div class="col-2">
                <span>تاریخ انقضا</span>
            </div>
            <div class="col-2">
                <span>نوع فروش</span>
            </div>
        </div>`)
                div.innerHTML = s
                document.querySelector('.select2-results').appendChild(div)
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
        dropdownCssClass: 'quotation_to_factor_select2',
        minimumInputLength: 3,
        placeholder: 'جستجوی پیش فاکتور با [نام مشتری ...]',
        templateResult: selectQuotationForFactorRepoItem,
        templateSelection: formatRepoSelection,
    });
})

function selectQuotationForFactorRepoItem(repo) {
    console.log(repo)
    if (repo.loading) {
        return "repo.text";
    }
    // debugger
    var $container = $(
        `<div class="quotation_search_result">
        <div class="row">
            <div class="col-3">
                <span>${repo.customer_name}</span>
                <span>(${repo.customer_party_id})</span>
            </div>
            <div class="col-2">
                <span>${repo.quotation_id}</span>
            </div>
            <div class="col-1">
                <span>${repo.row_count}</span>
                <span>ردیف</span>
            </div>
            <div class="col-2">
                <span>${repo.last_work_flow_user}</span>
            </div>
            <div class="col-2">
                <span>${repo.expiration_date}</span>
            </div>
            <div class="col-2">
                <span>${repo.sale_type}</span>
            </div>
        </div>
    </div>`
    );
    return ($container);
}

function formatRepoSelection(repo) {
    return repo.id || repo.text
}