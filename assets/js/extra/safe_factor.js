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

function get_quotation_items(quotation_pk){
    const ajax_quotation_items = $('#ajax_quotation_items')
    debugger
    if (ajax_quotation_items){
        custom_ajax_get(null, `/factor/ajax/get_quotation_items_for_factor/${quotation_pk}/safe/`, ajax_quotation_items)
    }
}

$(document).ready(function () {
    $('#id_select_quotation_for_factor').select2({
        dir: 'rtl',
        pageLength: 5,
        ajax: {
            delay: 150,
            url: '/factor/search',
            dataType: "json",
            type: "GET",
            data: function (data) {
                const search_by = document.querySelectorAll('.limit_query input[type="checkbox"]')
                const search_by_list = []
                if (search_by){
                    search_by.forEach(function (item){
                        if (item.checked){
                            search_by_list.push(item.name)
                        }
                    })
                }
                return {
                    q: data.term, page: data.page, // party_id: p_id,
                    search_by: JSON.stringify(search_by_list)
                }
            },
            processResults: function (data, params) {
                params.page = params.page || 1;
                return {
                    results: data.items,
                    pagination: {
                        more: (params.page * 10) < data.total_count
                    }
                };
            },
            success: function (){
                const s = `<div class="d-flex  bg-light-info sticky-top  py-2 bold">
                                    <div class="col-3 ">
                                        <span class="ms-1">مشتری</span>
                                    </div>
                                    <div class="col-2 ">
                                        <span class="ms-1">پیش فاکتور</span>
                                    </div>
                                    <div class="col-1 ">
                                        <span class="ms-1">تعداد ردیف</span>
                                    </div>
                                    <div class="col-2 ">
                                        <span class="ms-1">کارشناس</span>
                                    </div>
                                    <div class="col-1 ">
                                        <span class="ms-1">تاریخ انقضا</span>
                                    </div>
                                    <div class="col-1 ">
                                        <span class="ms-1">نوع فروش</span>
                                    </div>
                                    <div class="col-1 ">
                                        <span class="ms-1">روش پرداخت</span>
                                    </div>
                                    <div class="col-1 ">
                                        <span class="ms-1">نوع1</span>
                                    </div>
                                  </div>`
                const div = document.createElement('div')
                div.classList.add('singleton')
                div.innerHTML = s
                const s2el = document.querySelector('.select2-results')
                if (!s2el.firstElementChild.classList.contains('singleton')){
                    s2el.insertBefore(div, s2el.firstElementChild)
                }

            },
            cache: true
        },
        dropdownAutoWidth: true,
        dropdownCssClass: 'quotation_to_factor_select2',
        minimumInputLength: 2,
        placeholder: 'جستجوی پیش فاکتور با [شناسه پیش فاکتور، شماره سپیدار پیش فاکتور، نام مشتری، شناسه مشتری، کد کالا، پارت نامبر، ...]',
        templateResult: selectQuotationForFactorRepoItem,
        templateSelection: formatRepoSelection,
    });
    $('#id_select_quotation_for_factor').on("select2:select", function (e){
        const data = e.params.data;
        document.querySelector('input[name="q"]').value = data.id
        document.querySelector('[id*="select2-id_select_quotation_for_factor-container"]')
            .querySelector('span').innerHTML = `${data.customer_title}(${data.customer_party_id}) - ${data.sale_type} - ${data.expiration_date} - پیش فاکتور ${data.quotation_id}`
        get_quotation_items(data.id)

    })
    $('#id_select_quotation_for_factor').on("select2:open", function (e){
        document.querySelector('.select2-search__field')?.focus();
    })
})

function selectQuotationForFactorRepoItem(repo) {
    if (repo.loading) {
        return repo.text;
    }
    var $container = $(
        `<div class="quotation_search_result">
        <div class="row">
            <div class="col-3">
                <span>${repo.customer_title}</span>
                <span>(${repo.customer_party_id})</span>
            </div>
            <div class="col-2">
                <span>${repo.quotation_id}</span>
                <span>(${repo.last_work_flow_state})</span>
            </div>
            <div class="col-1">
                <span>${repo.row_count}</span>
            </div>
            <div class="col-2">
                <span>${repo.last_work_flow_user}</span>
            </div>
            <div class="col-1">
                <span>${repo.expiration_date}</span>
            </div>
            <div class="col-1">
                <span>${repo.sale_type}</span>
            </div>
            <div class="col-1">
                <span>${repo.payment_method}</span>
            </div>
            <div class="col-1">
                <span>${repo.is_official}</span>
            </div>
        </div>
    </div>`
    );
    return ($container);
}

function formatRepoSelection(repo) {
    return repo.id || repo.text
}

function getUrlParameter(name) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(name);
    }

    function removeUrlParam(paramName) {
        const url = new URL(window.location);
        url.searchParams.delete(paramName);
        window.history.replaceState({}, document.title, url.toString());
    }

    function createFactorFromQuotationList(){
     const paramName = 'q_id';
        const paramValue = getUrlParameter(paramName);
        // document.getElementById('quotation_id_for_factor').value = paramValue
        document.querySelector("input[name='q']").value = paramValue

        if (paramValue) {
            console.log('Found q_id param:', paramValue);
            setTimeout(() => {
                get_quotation_items(paramValue);
                removeUrlParam(paramName);
            }, 200); // delay can be adjusted or removed
        }
    }

createFactorFromQuotationList()