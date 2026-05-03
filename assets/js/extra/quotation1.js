
const global_info = document.querySelector('#global-info')
let ids = ["#submit_draft", "#submit_next", "#submit_copy", "#submit_save"];
let submit_buttons = ids.map(id => document.querySelector(id)).filter(el => el !== null);
let check_price_expire_date_array = []

function hideShowQuotationItemTransportationCost(nodeList, action) {
    nodeList.forEach(function (item){
        if (action == 'show'){
            item.classList.remove('d-none')
        } else if (action == 'hide') {
            item.classList.add('d-none')
        }
    })
}

function setPriceWithAjax(e, elem=null, price_code=''){
        elem = elem ? elem : findAncestor(e.target, "item")
        let party_id = document.getElementById('customer_pid').textContent || elem.querySelector('#customer_pid') || -1
        if (party_id == 'None'){
            party_id = -1
        }
        const reserve_count = elem.querySelector('[id*="-reserve_count"]')
        if (reserve_count) {reserve_count.value = parseInt(removeCommaSeperator(elem.querySelector('[id*="-quantity"]').value))}
        const tradePriceCode = elem.querySelector('[id*="-trade_price_code"]')
        const bazarPriceCode = elem.querySelector('[id*="-bazar_price_code"]')
        let tradePriceCodeValue;
        let bazarPriceCodeValue;
        if (tradePriceCode && tradePriceCode.options[tradePriceCode.selectedIndex]){
            tradePriceCodeValue = tradePriceCode.options[tradePriceCode.selectedIndex].value
        }
        if (bazarPriceCode && bazarPriceCode.options[bazarPriceCode.selectedIndex]){
            bazarPriceCodeValue = bazarPriceCode.options[bazarPriceCode.selectedIndex].value
        }

        $.ajax({
                url: '/inquiry/item_list/',
                data: {
                    'q': elem.querySelector('input[name*="goods_code"]').value,
                    'party_id': party_id,
                    'id_currency_ref': document.getElementById('id_currency_ref').value,
                    'id_payment_method': document.getElementById('id_payment_method').value,
                    'id_market_grade': document.getElementById('id_market_grade').value,
                    'id_customer_grade': document.getElementById('id_customer_grade').value,
                    'price_setting': document.querySelector('#id_q_price_setting').value,
                    'quantity': elem.querySelector('[id*="quantity"]').value.replaceAll(',', ''),
                    'trade_price_code': tradePriceCodeValue,
                    'bazar_price_code': bazarPriceCodeValue,
                },
                cache: false,
                type: 'GET',
                success: function (response){
                    if (response.items){
                        // console.log('kdsjfkdsj fkldsjfkdsjf klsdjf')

                        set_price_data(response.items[0], elem, e.target, true)
                        display_price(elem)
                        generate_price_method_select_option(elem)
                        check_price_expire_date_array = []
                        document.querySelectorAll('.item').forEach(function (item){
                            check_quotation_price_market_before_save_permission2(item).every(Boolean) ? toggle_submit_buttons(true): toggle_submit_buttons(false)
                        })
                        setTimeout(show_expire_message_popup, 600)
                    }
                },
                error: function (xhr) {
                    console.log(xhr)
                }
            }); // end ajax
    }

$(document).ready(function () {
    const quantityInput = document.querySelectorAll('input[name*="-quantity"]')
    const newInquiryResult = document.querySelectorAll('[id*="new-inquiry-result"]')
    const tradePriceCodeElem = document.querySelectorAll('[id*="trade_price_code"]')
    const bazarPriceCodeElem = document.querySelectorAll('[id*="bazar_price_code"]')
    const newInquiryResultDoneLocal = document.querySelectorAll('[id*="local_price_inquiry_done"]')
    const newInquiryResultDoneForeign = document.querySelectorAll('[id*="foreign_price_inquiry_done"]')
    const currencyRef = document.getElementById('id_currency_ref')
    let currencyRefValue = ''
    if (currencyRef){currencyRefValue = currencyRef.value}
    const paymentMethod = document.getElementById('id_payment_method')
    const customerGrade = document.getElementById('id_customer_grade')
    const all_prices = document.querySelectorAll('.all_prices')


    function setPriceWithAjaxForAllPrices(e, elem, price_code=''){

        let party_id = document.getElementById('customer_pid').textContent || elem.querySelector('#customer_pid') || -1
        if (party_id == 'None'){
            party_id = -1
        }
        setTimeout(function (){
            const all_prices_form = findAncestor(e.target, "all_prices_form")
            const params = new URLSearchParams(new FormData(all_prices_form)).toString()
            $.ajax({
                url: `/inquiry/item_list/?${params}`,
                data: {
                    'q': elem.querySelector('input[name*="goods_code"]').value,
                    'party_id': party_id,
                    'id_currency_ref': document.getElementById('id_currency_ref').value,
                    'id_payment_method': document.getElementById('id_payment_method').value,
                    'id_market_grade': document.getElementById('id_market_grade').value,
                    'id_customer_grade': document.getElementById('id_customer_grade').value,
                    'price_setting': document.querySelector('#id_q_price_setting').value,
                    'quantity': elem.querySelector('[id*="quantity"]').value.replaceAll(',', ''),
                    // 'trade_price_code': tradePriceCode,
                    // 'bazar_price_code': bazarPriceCode,
                },
                cache: false,
                type: 'GET',
                success: function (response){
                    if (response.items){
                        //set_price_data(response.items[0], elem, e.target)
                        set_price_data(response.items[0], elem, e.target, true)
                        display_price(elem)
                        generate_price_method_select_option(elem)
                        check_price_expire_date_array = []
                        document.querySelectorAll('.item').forEach(function (item){
                            check_quotation_price_market_before_save_permission2(item).every(Boolean) ? toggle_submit_buttons(true): toggle_submit_buttons(false)
                        })
                        setTimeout(show_expire_message_popup, 600)
                    }
                },
                error: function (xhr) {
                    console.log(xhr)
                }
            }); // end ajax
        }, 200)
    }

    if (currencyRefValue == '1'){
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="express_transportation_cost_1"]'), 'show')
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="air_transportation_cost_1"]'), 'show')
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="sea_transportation_cost_1"]'), 'show')
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="express_transportation_cost_2"]'), 'show')
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="air_transportation_cost_2"]'), 'show')
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="sea_transportation_cost_2"]'), 'show')
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="express_transportation_cost_3"]'), 'hide')
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="air_transportation_cost_3"]'), 'hide')
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="sea_transportation_cost_3"]'), 'hide')
    }
    else if (currencyRefValue == '2') {
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="express_transportation_cost_1"]'), 'hide')
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="air_transportation_cost_1"]'), 'hide')
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="sea_transportation_cost_1"]'), 'hide')
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="express_transportation_cost_2"]'), 'hide')
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="air_transportation_cost_2"]'), 'hide')
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="sea_transportation_cost_2"]'), 'hide')
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="express_transportation_cost_3"]'), 'show')
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="air_transportation_cost_3"]'), 'show')
        hideShowQuotationItemTransportationCost(document.querySelectorAll('[name*="sea_transportation_cost_3"]'), 'show')
    }

    if (all_prices){
        all_prices.forEach(function (item){
            item.addEventListener('click', function (e){
                // e.preventDefault()
                const elem = findAncestor(e.target, "item")
                setPriceWithAjaxForAllPrices(e, elem)
            })
        })
    }
    newInquiryResult.forEach(function (item){
        item.addEventListener('click', function (e){
            e.preventDefault();
            const elem = findAncestor(e.target, "item")
                setPriceWithAjax(e, elem)
        })
    })

    newInquiryResultDoneLocal.forEach(function (item){
        item.addEventListener('change', function (e){
            e.preventDefault();
            if (item.checked){
                const elem = findAncestor(e.target, "item")
                setPriceWithAjax(e, elem)
                }
        })
    })

    newInquiryResultDoneForeign.forEach(function (item){
        item.addEventListener('change', function (e){
            e.preventDefault();
            if (item.checked){
                const elem = findAncestor(e.target, "item")
                setPriceWithAjax(e, elem)
                }
        })
    })

    tradePriceCodeElem.forEach(function (item){
        item.addEventListener('change', function (e){
            e.preventDefault();
            const elem = findAncestor(e.target, "item")
            setPriceWithAjax(e, elem)
        })
    })

    bazarPriceCodeElem.forEach(function (item){
        item.addEventListener('change', function (e){
            e.preventDefault();
            const elem = findAncestor(e.target, "item")
            setPriceWithAjax(e, elem)
        })
    })

    quantityInput.forEach(function (item){
        const draftBtn = document.querySelector('input[name*="draft"]')
        const backBtn = document.querySelector('input[name*="back"]')
        const nextBtn = document.querySelector('input[name*="next"]')
        // item.addEventListener('focus', function (e) {
        //     draftBtn ? draftBtn.disabled=true : ''
        //     backBtn ? backBtn.disabled=true : ''
        //     nextBtn ? nextBtn.disabled=true : ''
        // })
        // item.addEventListener('focusout', function (e) {
        //     draftBtn ? draftBtn.disabled=false : ''
        //     backBtn ? backBtn.disabled=false : ''
        //     nextBtn ? nextBtn.disabled=false : ''
        // })
        item.addEventListener('keyup', function (e) {
            e.preventDefault();
            const elem = findAncestor(e.target, "item")
            setPriceWithAjax(e, elem)
        })
    })

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
    $('#customer_code').on("select2:select", function (e) {
        const data = e.params.data;
        document.querySelector('[name="customer_code"]').value = data.id
        document.querySelector('[id*="select2-customer_code"][id*="container"]').querySelector('span').innerHTML = data.id
        // $(document).find("#customer_card").attr("class", "alert-warning h-100 p-2");
        document.getElementById("customer_card").classList.remove('d-none');
        $(document).find("#customer_name").text(data.text);
        $(document).find("#customer_pid").text(data.sepidar_party_id);
        $(document).find("#id_customer_party_id").val(data.sepidar_party_id);
        get_customer_accounting_info()
    })
    document.getElementsByClassName('goods_name').ondblclick = function () {
        const item = findAncestor(this)
    }
    const items = $(document).find(".item")
    for (let i = 0; i < items.length; i++) {
        set_item_classes(items[i], i)
        init_front_prices(items[i])

        try{
            init_price_method(items[i], i)
        } catch(e) {
            console.log(e)
        }

        try {
            const foreign_price_inquiry_done = items[i].querySelector('[id*="foreign_price_inquiry_done"]')
            const local_price_inquiry_done = items[i].querySelector('[id*="local_price_inquiry_done"]')
            if (foreign_price_inquiry_done.checked){
                items[i].querySelector('[id*="need_foreign_price_inquiry"]').style.pointerEvents = 'none'
            }
            if (local_price_inquiry_done.checked){
                items[i].querySelector('[id*="need_local_price_inquiry"]').style.pointerEvents = 'none'
            }
        } catch (e) {
            console.log(e)
        }


    }
});

function set_item_classes(item, idx=null) {
    if (idx === null) {idx = parseInt(item.dataset.formIndex)}
    if(item.getElementsByClassName('goods_code')) {
        $(item).find('.goods_code').on("select2:select", function (e) {
            const elem = findAncestor(e.target, "item")
            const data = e.params.data;
            item.querySelector('#moq').innerHTML = data.moq || '-'
            item.querySelector('#moq_box').innerHTML = data.moq_box || '-'
            item.querySelector('#moq_main_box').innerHTML = data.moq_main_box || '-'
            set_price_data(data, elem, e.target, true, idx)
            display_price(elem)
            generate_price_method_select_option(elem)
            check_price_expire_date_array = []
            document.querySelectorAll('.item').forEach(function (item){
                check_quotation_price_market_before_save_permission2(item).every(Boolean) ? toggle_submit_buttons(true): toggle_submit_buttons(false)
            })
            setTimeout(show_expire_message_popup, 600)
            calculate_price(elem)

            $(item).find('input[id*="goods_code_fk"]').val(data['id'])
            let m_url = "/inquiry/ajax/count/?sku=" + data['id']
            $.ajax({
                type: 'GET',
                url: m_url,
                dataType: 'json',
                cache: false,
                processData: false,
                contentType: false,
                success: function (data) {
                    $(item).find('#all_price_count').html(`(${data['res']})`)
                },
                error: function () {
                    alert('خطا در دریافت استعلام قیمت')
                }
            });
    })
        $(item).find('.goods_code_alt').on("select2:select", function (e) {
            var elem = findAncestor(e.target, "item")
            var data = e.params.data;
            set_alt_price_data(data, elem)
        })
        $(item).find('.goods_code').select2({
            dir: 'ltr',
            ajax: {
                // url: '/sepidar/items_list',
                url: '/inquiry/items_list/',
                dataType: "json",
                type: "GET",
                data: function (data) {
                    let p_id = document.getElementById('customer_pid').textContent || -1;
                    if (!p_id){
                        p_id = item.getElementById('customer_pid')
                    }
                    return {
                        q: data.term, party_id: p_id, page: data.page,
                        id_currency_ref: document.getElementById('id_currency_ref').value,
                        id_payment_method: document.getElementById('id_payment_method').value,
                        id_market_grade: document.getElementById('id_market_grade').value,
                        id_customer_grade: document.getElementById('id_customer_grade').value,
                        'price_setting': document.querySelector('#id_q_price_setting').value,
                        quantity: item.querySelector('[id*="quantity"]').value.replaceAll(',', ''),
                    }
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
            templateResult: newFormatRepoItem,
            templateSelection: formatRepoSelection,
        });
        $(item).find('.goods_code_alt').select2({
            dir: 'ltr',
            ajax: {
                // url: '/sepidar/items_list',
                url: '/inquiry/items_list',
                dataType: "json",
                type: "GET",
                data: function (data) {
                    const p_id = document.getElementById('customer_pid').textContent;
                    return {
                        q: data.term, party_id: p_id, page: data.page,
                        id_currency_ref: document.getElementById('id_currency_ref').value,
                        id_payment_method: document.getElementById('id_payment_method').value,
                        id_market_grade: document.getElementById('id_market_grade').value,
                        id_customer_grade: document.getElementById('id_customer_grade').value,
                        'price_setting': document.querySelector('#id_q_price_setting').value,
                        quantity: item.querySelector('[id*="quantity"]').value.replaceAll(',', ''),
                    }
                },
                processResults: function (data, params){
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
            templateResult: newFormatRepoItem,
            templateSelection: formatRepoSelection
        });
        $(item).find('.selected_price_code').select2({
            dir: 'ltr',
            ajax: {
                url: '/inquiry/all_prices/',
                dataType: "json",
                type: "GET",
                data: function (data) {
                    let sku = item.querySelector('input[class*="-goods_code"]')
                    if (!sku){
                        sku = item.querySelector('.select2-selection__rendered').innerText
                    }
                    return {
                        q: data.term,
                        sku: sku,
                        page: data.page,
                    }
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
                success: function (){
                    const header_ = `
                    <div class="d-flex flex-row-reverse bg-light-success sticky-top text-center">
                        <div class="col-2">
                            <span class="bold">کد کالا</span>
                        </div>
                        <div class="col-5">
                            <span class="bold">نوع استعلام</span>
                        </div>
                        <div class="col-2">
                            <span class="bold">تاریخ</span>
                        </div>
                        <div class="col-3">
                            <span class="bold">توسط</span>
                        </div>
                    </div>`

                    const div = document.createElement('div')
                    div.classList.add('singleton')
                    div.innerHTML = header_
                    const el = document.querySelector('.select2-results')
                    if (!el.firstElementChild.classList.contains('singleton')){
                        el.insertBefore(div, el.firstElementChild)
                    }
                },
                cache: true
            },
            dropdownAutoWidth: true,
            dropdownCssClass: 'all_price_select2',
            minimumInputLength: 0,
            placeholder: 'برای مشاهده قیمت ها کلیک کنید',
            templateResult: AllPriceFormatRepoItem,
            templateSelection: formatRepoSelection,
        });
        $(item).find('.selected_price_code').on("select2:select", function (e) {
            var elem = findAncestor(e.target, "item")
            const data = e.params.data;
            const p_id = document.getElementById('customer_pid').textContent || -1
            const price_selected_code = item.querySelector('input[name*="-selected_price_code"]').value
            const d = get_all_price_data(data.sku, p_id,  elem, data.id, data.inquiry_type_detector)
            const select2_price = elem.querySelector('[id*="select2-selected_price_code"][id*="container"]')
            elem.querySelector('input[name*="selected_price_code"]').value = data.id
            if (select2_price) {
                select2_price.innerHTML = `<span class="d-flex flex-row-reverse gap-2"><span class="font-size-12">${data.sku}</span> <span class="me-3">&#8592;</span> <span class="font-size-12 me-2">${data.inquiry_type}</span> <span class="font-size-11 text-danger">${data.last_update_date}</span> <span class="font-size-11">${data.editor_user}</span></span>`
            }
            set_price_data(d, elem, e.target, true, idx)
            // set_price_data(response.items[0], elem, e.target, true)
            display_price(elem)
            generate_price_method_select_option(elem)
            check_price_expire_date_array = []
            document.querySelectorAll('.item').forEach(function (item){
                check_quotation_price_market_before_save_permission2(item).every(Boolean) ? toggle_submit_buttons(true): toggle_submit_buttons(false)
            })
            setTimeout(show_expire_message_popup, 600)
        })
        $(item).find('.bazar_selected_price_code').on("select2:select", function (e) {
            var elem = findAncestor(e.target, "item")
            const data = e.params.data;
            const p_id = document.getElementById('customer_pid').textContent || -1
            const trade_selected_code = item.querySelector('input[name*="-trade_selected_price_code"]').value
            const d = get_all_price_data(data.sku, p_id,  elem, trade_selected_code, data.id)
            const select2_bazar_price = elem.querySelector('[id*="select2-bazar_selected_price_code"][id*="container"]')
            elem.querySelector('input[name*="bazar_selected_price_code"]').value = data.id
            if (select2_bazar_price) {
                // select2_bazar_price.innerHTML = `<span class="font-size-8">id_${data.id}</span> <span class="font-size-10">${data.inquiry_type}</span> <span class="font-size-9 text-danger">${data.last_update_date}</span>`
                select2_bazar_price.innerHTML = `<span class="font-size-12 me-2">${data.inquiry_type}</span> <span class="font-size-10 text-danger">${data.last_update_date}</span>`
            }
            set_price_data(d, elem, e.target, true, idx)

        })
        $(item).find('.goods_code').on("select2:open", function (e){
            document.querySelector('.select2-search__field')?.focus();
        })
    }
    $(item).find('[id$="final_price"]').on('change keydown paste input', function (e) {
        calculate_price(e.target);
    });
    // $(item).find('.quantity').on('change keydown paste input', function (e) {
    $(item).find('input[id$="quantity"]').on('change keydown paste input', function (e) {
        calculate_price(e.target);
    });
    $(item).find('[id$="price_method"]').on('change', function (e) {
        const expire_inquiry_error = document.querySelector('#expire_inquiry_error')
        expire_inquiry_error && expire_inquiry_error.classList.add('d-none')
        calculate_price(e.target)
        check_price_expire_date_array = []
        document.querySelectorAll('.item').forEach(function (item){
            check_quotation_price_market_before_save_permission2(item).every(Boolean) ? toggle_submit_buttons(true): toggle_submit_buttons(false)
        })
        setTimeout(show_expire_message_popup, 600)
    })
    // copy_values(item, '-goods_name')
    copy_values(item, 'stock_amount')
    copy_values(item, 'stock_amount_res')
    copy_values(item, 'goods_max_price')
    copy_values(item, 'goods_avg_price')
    copy_values(item, 'goods_min_price')
    copy_values(item, 'goods_avg_count')
    copy_values(item, 'goods_price_sheet1')
    copy_values(item, 'goods_price_sheet2')
    copy_values(item, 'goods_price_sheet3')
    copy_values(item, 'goods_sheet_date', true)
    copy_values(item, 'goods_price_market')
    copy_values(item, 'goods_market_date', true)
    copy_values(item, 'goods_last_price')
    copy_values(item, 'goods_total_sales')
    copy_values(item, 'goods_last_sale', true)
    copy_values(item, 'goods_q_last_price')
    copy_values(item, 'goods_q_total_sales')
    copy_values(item, 'goods_q_last_sale', true)
    copy_values(item, 'price_update_date', true)

    copy_values(item, 'express_transportation_cost_1')
    copy_values(item, 'air_transportation_cost_1')
    copy_values(item, 'sea_transportation_cost_1')
    copy_values(item, 'express_transportation_cost_2')
    copy_values(item, 'air_transportation_cost_2')
    copy_values(item, 'sea_transportation_cost_2')
    copy_values(item, 'express_transportation_cost_3')
    copy_values(item, 'air_transportation_cost_3')
    copy_values(item, 'sea_transportation_cost_3')
    copy_values(item, 'inquiry_price_json')

    const select01 = item.querySelector('[id*="select2-goods_code"][id*="container"]')
    if (select01) {
        select01.innerHTML = item.querySelector('[id*="-goods_code"]').value
        item.querySelector('[id*="select2-goods_code_alt"][id*="container"]').innerHTML = item.querySelector('[id*="-goods_code_alt"]').value
    }
    const select2_price = item.querySelector('[id*="select2-selected_price_code"][id*="container"]')
    if (select2_price){
        let t = item.querySelector('[id*="selected_price_code_data"]')
        select2_price.innerHTML = `${t.dataset.selected_price_code_inquiry_type}`
    }
    // const select2_bazar_price = item.querySelector('[id*="select2-bazar_selected_price_code"][id*="container"]')
    // if (select2_bazar_price){
    //     let b = item.querySelector('[id*="bazar_selected_price_code_data"]')
    //     select2_bazar_price.innerHTML = `${b.dataset.bazar_selected_price_code_inquiry_type}`
    // }
    copy_values(item, '-goods_name_alt')
    // const box = item.querySelector('[name="box-alt-goods"]')

    // set_price(item, null, true)
    // set_price2(item)
    // init_price_method(item, idx)
    // set_price_method(item)
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

function refresh_front_prices(elem){
    const items = document.querySelectorAll('.item')
    items.forEach(function (item){
      calculate_price(item)
    })
}

function init_front_prices(elem){
    calculate_price(elem)
}


function refresh_prices() {
    const items = $(document).find(".item")
    const party_id = document.getElementById('customer_pid').textContent || -1;
    const price_updating = document.querySelector('#price-updating')
    const price_updated = document.querySelector('#price-updated')
    for (let i = 0; i < items.length; i++) {
        if (i === items.length - 1){
            // price_updating.classList.add('d-none')
            // price_updated.classList.remove('d-none')
        } else if (i === 0){
            // price_updating.classList.remove('d-none')
            // price_updated.classList.add('d-none')
        }
        setTimeout(function (){
            const code = items[i].querySelector('[id*="-goods_code"]').value
            const data = get_price_data(code, party_id, items[i]) // 1
            set_price_data(data, items[i], items[i]) // 2
            display_price(items[i]) // 3
            generate_price_method_select_option(items[i], null, i) // 4
            check_price_expire_date_array = []
            document.querySelectorAll('.item').forEach(function (item){
                check_quotation_price_market_before_save_permission2(item).every(Boolean) ? toggle_submit_buttons(true): toggle_submit_buttons(false)
            })
            setTimeout(show_expire_message_popup, 600)
            const alt_code = items[i].querySelector('[id*="-goods_code_alt"]').value
            if (alt_code != "") {
                // const alt_data = get_price_data(alt_code, party_id, items[i])
                // set_alt_price_data(alt_data, items[i])
            }
        }, 150)
        setTimeout(calculate_price, 500, items[i])
    }
}

function get_price_data(code, party_id, item) {
        const tradePriceCode = item.querySelector('[id*="-trade_price_code"]')
        const bazarPriceCode = item.querySelector('[id*="-bazar_price_code"]')
        let tradePriceCodeValue;
        let bazarPriceCodeValue;
        if (tradePriceCode && tradePriceCode.options[tradePriceCode.selectedIndex]){
            tradePriceCodeValue = tradePriceCode.options[tradePriceCode.selectedIndex].value
        }
        if (bazarPriceCode && bazarPriceCode.options[bazarPriceCode.selectedIndex]){
            bazarPriceCodeValue = bazarPriceCode.options[bazarPriceCode.selectedIndex].value
        }
    $.ajax({
        url: '/inquiry/item_list',
        dataType: "json",
        type: "GET",
        async: false,
        data: {
                q: code, party_id: party_id, page: 1,
                id_currency_ref: document.getElementById('id_currency_ref').value,
                id_payment_method: document.getElementById('id_payment_method').value,
                id_market_grade: document.getElementById('id_market_grade').value,
                id_customer_grade: document.getElementById('id_customer_grade').value,
                price_setting: document.querySelector('#id_q_price_setting').value,
                quantity: item.querySelector('[id*="quantity"]').value.replaceAll(',', ''),
                'trade_price_code': tradePriceCodeValue,
                'bazar_price_code': bazarPriceCodeValue,
            },
        cache: true,
        success: function (data) {
            result = data;
        }
    });
    if (result.total_count > 0) {
        return result.items[0];
    }
}

function get_all_price_data(code, party_id, item, selected_price_code=null, price_type=null) {
    let trade_price_code;
    let bazar_price_code;
    if (price_type == 1){
        trade_price_code = selected_price_code
        bazar_price_code = -1
    } else if (price_type == 2){
        bazar_price_code = selected_price_code
        trade_price_code = -1
    }
    $.ajax({
        url: '/inquiry/item_list',
        dataType: "json",
        type: "GET",
        async: false,
        data: {
                q: code, party_id: party_id, page: 1,
                trade_price_code: trade_price_code,
                bazar_price_code: bazar_price_code,
                id_currency_ref: document.getElementById('id_currency_ref').value,
                id_payment_method: document.getElementById('id_payment_method').value,
                id_market_grade: document.getElementById('id_market_grade').value,
                id_customer_grade: document.getElementById('id_customer_grade').value,
                price_setting: document.querySelector('#id_q_price_setting').value,
                quantity: item.querySelector('[id*="quantity"]').value.replaceAll(',', ''),
            },
        cache: true,
        success: function (data) {
            result = data;
        }
    });
    if (result.total_count > 0) {
        return result.items[0];
    }
}

function init_price_method(row, idx){
    const price_json = row.querySelector('textarea[name$="-price_json"]')
    const price_json_value = JSON.parse(price_json?.value || 0) || []
    display_price(row)
    generate_price_method_select_option(row, price_json_value, idx)
    set_price2(row)
    // calculate_price(row)
    check_price_expire_date_array = []
    check_quotation_price_market_before_save_permission2(row).every(Boolean) ? toggle_submit_buttons(true): toggle_submit_buttons(false)
    setTimeout(show_expire_message_popup, 600)
}

function generate_price_method_select_option(row, price_json=null, idx=null){
    idx = idx ? idx : parseInt(row.querySelector('.counter').innerText) - 1
    const previous_price_method = row.querySelector('[data-previous_price_method]')?.dataset.previous_price_method
    const select = document.createElement('select');
    select.className = 'w-100 form-control'
    select.id = 'id_select_price_method'
    select.name = `quotation-${idx}-price_method`
    select.onchange = set_price2
    price_json = JSON.parse(row.querySelector('textarea[name$="-price_json"]')?.value || 0) || []
    price_json.push({type: "sales_admin",
                            ref: null,
                            value: "",
                            title: "مصوب مدیر",
                            access_type: null,
                            unique_title: "sales_admin",
                            date: null,
                            seen: null
                        })
    price_json.push({type: "",
                            ref: null,
                            value: "",
                            title: "----------",
                            access_type: null,
                            unique_title: "----------",
                            date: null,
                            seen: null
                        })
    price_json.reverse()
    for (let item of price_json){
        if (item.unique_title === 'goods_q_last_price' || item.unique_title === 'goods_last_price'){
            continue
        } else {
            const option = document.createElement('option');
            option.value = item.unique_title === '----------' ? '' : item.unique_title
            option.textContent = item.unique_title === 'sales_admin' ? `${item.title}` : `${item.title} | ${item.unique_title}`;
            if (option.value === previous_price_method){
                option.selected = true
                if (previous_price_method !== 'sales_admin' && previous_price_method !== '----------'){
                    row.querySelector('[name*="-final_price"]').value = round_rial(item.value)
                } //else if (previous_price_method !== '----------'){
                    //row.querySelector('[name*="-final_price"]').value = ''
                //}
            }
            select.appendChild(option);
        }
    }

    const price_method_container = row.querySelector('#id_price_method_container')
    price_method_container.innerHTML = ''
    price_method_container.appendChild(select)
}

function display_price(row){
    const final_price = row.querySelector('input[name*="-final_price"]')
    const display_price_container = row.querySelector('#id_display_price_container')
    const display_last_sale_price_container = row.querySelector('#customer-last-sales')
    const price_json = JSON.parse(row.querySelector('textarea[name$="-price_json"]')?.value || 0) || []
    let last_sale_price_list = []
    let iqr_price_list = []
    let access_type = '';

    if (display_price_container) {
        price_json.forEach(function (item){
            if(item.lead_time){
                row.querySelector('#lead_time_text').innerText = item.lead_time
                try {
                    row.querySelector('input[name$="lead_time"]').value = item.lead_time
                } catch (err){
                    console.log('error at: row.querySelector("input[name^=lead_time]").value = item.lead_time', err)
                }
            }
            if (item.unique_title === 'goods_last_price' || item.unique_title === 'goods_q_last_price'){
                last_sale_price_list.push(`<div class="row row-cols-4 mx-1 hover-link" id=id_${item.unique_title}>
                    <span class="col-3 p-0">
                    آخرین
                    ${item.title}</span>
                    <span class="col-3">${item.jdate}</span>
                    <span class="col-2 p-0">${numberWithCommas(item.quantity)}</span>
                    <span class="col-4">
                         💵
                        ${numberWithCommas(item.value)}
                    </span>
                </div>`)
            } else {
                console.log(item)
                if (item.access_type === 'QUESTION'){
                    access_type = '(باهماهنگی بازرگانی)'
                } else {
                    access_type = ''
                }
                iqr_price_list.push(`<div class="row row-cols-4 mx-1 mb-1 hover-link">
                    <span class="col-12 p-0 font-size-11" name="price_expire_date"></span>
                    <span class="col-5 px-1">${item.unique_title} ${access_type} ${item?.variant_show || ''}</span>
                    <span class="col-3 p-0">${numberWithCommas(item.value)}</span>
                    <span class="col-2 p-0" name="price_update_date">${item.jdate}</span>
                    <span class="col-2 p-0">${item.title}</span>
                </div>`)
            }
        })
        debugger
        checkPrice(row)
        final_price.addEventListener('keyup', () => checkPrice(row));

        // const html = price_json.map(function (item){
        // return `<div class="row row-cols-4 mx-1 hover-link">
        //             <span class="col-4">${item.unique_title}</span>
        //             <span class="col-3">${numberWithCommas(item.value)}</span>
        //             <span class="col-2">${item.date.slice(10, item.date.length)}</span>
        //             <span class="col-3">${item.title}</span>
        //         </div>`
        //
        // })

        display_price_container.innerHTML = iqr_price_list.join(" ")

        // if (!row.querySelector('input[name*="-goods_code_alt"]').value) {
            display_last_sale_price_container.innerHTML = last_sale_price_list.join(" ")
        // }
    }
}

function set_price_data(data, elem, target, single=null, idx=null) {
    let items_count;
    let row_number;
    try {
        if (single){
            row_number = 1
            items_count = 1
        } else {
            row_number = elem.querySelector('.counter').innerText
            items_count = document.querySelectorAll('.item').length
        }
    }
    catch (e) {
        row_number = null
        items_count = 1
    }
    if (data){
        console.log(data)
        let options = [
                            {type: "",
                            ref: null,
                            value: "",
                            title: "----------",
                            access_type: null,
                            unique_title: "----------",
                            date: null,
                            seen: null
                            },
                            {type: "sales_admin",
                            ref: null,
                            value: "",
                            title: "مصوب مدیر",
                            access_type: null,
                            unique_title: "sales_admin",
                            date: null,
                            seen: null
                        }]
        data.price_list?.forEach(function(item){
            options.push({type: item.type,
                            ref: item.ref,
                            value: item.value,
                            title: item.title,
                            access_type: item.access_type,
                            unique_title: item.unique_title,
                            date: item.date,
                            jdate: item.jdate,
                            seen: item.seen,
                            lead_time: item.lead_time,
                            variant_show: item.variant_show,
                        })
        })

        elem.querySelector('textarea[name$="-price_json"]').value = JSON.stringify(data.price_list || null)


        // set_values(elem.querySelectorAll('[name$="last__sale__goods__name"]'), data.text)
        set_values(elem.querySelectorAll('[name$="-goods_name"]'), data.text)
        set_values(elem.querySelectorAll('[name$="-goods_name_lbl"]'), data.text)
        set_values(elem.querySelectorAll('[name*="stock_amount"]'), data.stock_qty)
        set_values(elem.querySelectorAll('[name*="stock_amount_res"]'), data.stock_qty_res)

        set_values(elem.querySelectorAll('[name*="itemid"]'), data.itemid)
        set_values(elem.querySelectorAll('[name$="-goods_code"]'), data.id,)
        const select = elem.querySelector('[id*="select2-goods_code"][id*="container"]')
        if (select) {
            select.innerHTML = data.id
        }
        if (!data.f_fee_cust) {
            elem.querySelector('[name="box-alt-goods"]').classList.remove('d-none')
            set_values(elem.querySelectorAll('[name*="-goods_name_alt"]'), '',)
            set_values(elem.querySelectorAll('[name*="-goods_code_alt"]'), '',)
        } else {
            elem.querySelector('[name="box-alt-goods"]').classList.remove('d-none')
        }
    }

    set_loading(items_count, row_number)
}

function set_loading(items_count, row_number){
    let inquiry_loading_value = (row_number/items_count)*100
    const vertical_loading_text = document.querySelector('.vertical-loading-inner')
    const vertical_loading_value =document.querySelector('#vertical-loading-value')

    vertical_loading_text.style.opacity = "1";

    vertical_loading_value.innerText = `${Math.round(inquiry_loading_value)}`
    vertical_loading_text.style.height = `${Math.round(inquiry_loading_value)}%`
}

function set_alt_price_data(data, elem) {

    if (data.f_fee_cust != '') {
        const price_json = elem.querySelector('textarea[name$="-price_json"]')
        const price_json_value = JSON.parse(price_json?.value || 0) || []

        for (let d of price_json_value){
            if (d.unique_title === "goods_last_price"){
                const [jy, jm, jd] = data.f_date_cust.split('-').map(Number);
                const gregorianDate = toGregorian(jy, jm, jd);
                d['date'] = `${gregorianDate.gy}-${gregorianDate.gm}-${gregorianDate.gd}`
                d['jdate'] = data.f_date_cust
                d['value'] = data.f_fee_cust
                d['quantity'] = data.f_qty_cust
            }
            if (d.unique_title === "goods_q_last_price"){
                const [jy, jm, jd] = data.f_date_cust.split('-').map(Number);
                const gregorianDate = toGregorian(jy, jm, jd);
                d['date'] = `${gregorianDate.gy}-${gregorianDate.gm}-${gregorianDate.gd}`
                d['jdate'] = data.q_date_cust
                d['value'] = data.q_fee_cust
                d['quantity'] = data.q_qty_cust
            }
        }

        price_json.value = JSON.stringify(price_json_value)
        // set_values(elem.querySelectorAll('[name$="last__sale__goods__name"]'), data.text)
        const last_factor = elem.querySelector('#id_goods_last_price')
        const last_quotation = elem.querySelector('#id_goods_q_last_price')
        last_factor.innerHTML = `<span class="col-3 p-0">آخرین فاکتور</span>
                    <span class="col-3">${data.f_date_cust}</span>
                    <span class="col-2">${numberWithCommas(data.f_qty_cust)}</span>
                    <span class="col-4">
                         💵
                        ${numberWithCommas(data.f_fee_cust)}
                    </span>`

        last_quotation.innerHTML = `<span class="col-3 p-0">آخرین پیش فاکتور</span>
                    <span class="col-3">${data.q_date_cust}</span>
                    <span class="col-2">${numberWithCommas(data.q_qty_cust)}</span>
                    <span class="col-4">
                         💵
                        ${numberWithCommas(data.q_fee_cust)}
                    </span>`

        set_values(elem.querySelectorAll('[name*="-goods_name_alt"]'), data.text)
        // set_values(elem.querySelectorAll('[name*="last_price"]'), data.f_fee_cust)
        // set_values(elem.querySelectorAll('[name*="total_sales"]'), data.f_qty_cust)
        // set_values(elem.querySelectorAll('[name*="last_sale"]'), data.f_date_cust, true)
        // set_values(elem.querySelectorAll('[name*="q_last_price"]'), data.q_fee_cust)
        // set_values(elem.querySelectorAll('[name*="q_total_sales"]'), data.q_qty_cust)
        // set_values(elem.querySelectorAll('[name*="q_last_sale"]'), data.q_date_cust, true)
        set_values(elem.querySelectorAll('[name*="-goods_code_alt"]'), data.id,)
        try{
            elem.querySelector('[id*="select2-goods_code_alt"][id*="container"]').innerHTML = data.id
        } catch (err){
            console.log('catch error: ', err)
        }
    }
    set_price2(elem.querySelector('[name*="-goods_name"]'))
    calculate_price(elem)
}

function set_price2(target, data=null) {
    // تنظیم فیلد قیمت نهایی بر اساس روش تعین قیمت از جیسون موجود
    // alert('set_price')
    let elem;
    let found;

    if (target instanceof Event){
        elem = findAncestor(target.currentTarget, "item")
    } else {
        try {
            elem = findAncestor(target, "item")
        } catch (e) {
            elem = target
        }
    }

    // let p_m = elem.querySelector('[name*="price_method"]')?.value
    let selected_method;
    if (this.constructor.name === 'Window'){
        selected_method = elem.querySelector('[data-previous_price_method]')?.dataset.previous_price_method
    } else {
        selected_method = this.value
    }

    const price_json = JSON.parse(elem.querySelector('textarea[name$="-price_json"]')?.value || 0) || []
    const final_price = elem.querySelector('input[name$="-final_price"]')



    if (selected_method === 'sales_admin') {
        final_price.disabled = false
        final_price.readOnly = false;
        final_price.style.backgroundColor = "#fff";   // ظاهر غیرقابل ویرایش
        final_price.style.cursor = "auto";
        elem.querySelector('[data-previous_price_method]').setAttribute('data-previous_price_method', 'sales_admin')
        final_price.value = round_rial(numberWithCommas(final_price.value).replaceAll(',', ''))
    } else {
        price_json && price_json.forEach(function (item){
            if (item.unique_title === selected_method){
                final_price.disabled = false
                final_price.readOnly = true;
                final_price.style.backgroundColor = "#fafafa";   // ظاهر غیرقابل ویرایش
                final_price.style.cursor = "not-allowed";
                if (Number.isFinite(item.value)){
                    final_price.value = round_rial(numberWithCommas(item.value).replaceAll(',', ''))
                }else{
                    final_price.value = round_rial(numberWithCommas(item.value?.price).replaceAll(',', ''))
                }

                elem.querySelector('[data-previous_price_method]').setAttribute('data-previous_price_method', item.unique_title)
                found = true
            }
        })

        if (!found){
            final_price.value = '';
            final_price.readOnly = true;
            final_price.style.cursor = "not-allowed";
            final_price.style.backgroundColor = "#fafafa";
            elem.querySelector('[data-previous_price_method]').setAttribute('data-previous_price_method', '----------')
        }
    }
    checkPrice(elem)
    // calculate_price(elem)
}

function date_str_to_iso_date(date_str, sep='-'){
    const [year, month, day] = date_str.split(sep).map(Number);
    const miladiDate = toGregorian(year, month, day);
    return new Date(miladiDate.gy, miladiDate.gm - 1, miladiDate.gd);
}

function add_n_hour(currentDate ,n){
    return new Date(currentDate.getTime() + (n * 60 * 60 * 1000));
}

function show_expire_message_popup(){
    const trueIndexes = check_price_expire_date_array.map((val, idx) => !val ? idx + 1 : null).filter(idx => idx !== null).join(', ');
    if (trueIndexes) {
        document.querySelector('#expire_inquiry_error').classList.remove('d-none')
        document.querySelector('#expire_inquiry_row_number').innerHTML = trueIndexes
    }
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
    let goods_market_date;
    if (repo.loading) {
        return repo.text;
    }
    if (repo.goods_market_date){goods_market_date=repo.goods_market_date} else {goods_market_date='-'}
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
        "<div class='w-40'>" + (add_discounts(repo.goods_price_market, repo.yuan_rate, 2)) + "</div>" +
        "<div class='w-60'>" + goods_market_date + "</div>" +
        "</div> " +
        "</div> " +
        "</div></div>"
    );
    return ($container);
}

function newFormatRepoItem(repo) {
    if (repo.loading) {
        return repo.text;
    }

    let repo_express;
    let repo_air;
    let repo_sea;
    let goods_market_date;
    let goods_price_market;

    if (repo.rial_final_price){repo_express = repo.rial_final_price.express?.price; repo_air = repo.rial_final_price.air?.price; repo_sea = repo.rial_final_price.sea?.price}
    if (repo.rmb_final_price){repo_express = repo.rmb_final_price.express?.price; repo_air = repo.rmb_final_price.air?.price; repo_sea = repo.rmb_final_price.sea?.price}


    if (repo_express == undefined){
        repo_express = '-'
    }
    if (repo_air == undefined){
        repo_air = '-'
    }
    if (repo_sea == undefined){
        repo_sea = '-'
    }

    if (repo.goods_market_date){goods_market_date=repo.goods_market_date} else {goods_market_date='-'}
    if (repo.goods_price_market){goods_price_market=repo.goods_price_market} else {goods_price_market='-'}
    let parent_code = '';
    if (repo.parent_sku){
        parent_code = "<div class='bold text-info d-flex align-items-center'>کد مادر " + repo.parent_sku + "<span class='font-size-12 mx-1'>(" +repo.parent_part_number +")</span>" + "</div>"
    }

    var $container = $(
        "<div class='w-100 replace-digits' dir='rtl' style='font-family: BYekan'>" +
        "<div class='d-flex border'>" +
        "<div class='border-end w-15 pe-1' >" +
        "<div>" + repo.id + "</div>" +
        "<div> " + numberWithCommas(repo.stock_qty, 0) + " </div>" +
        "<div> " + numberWithCommas(repo.stock_qty_res, 0) + " </div>" +
        "<div> " + "MOQ: " + repo.moq + " </div>" +
        "</div>" +
        "<div class='w-30 border-end pe-1'>" +
        "<div >" + repo.text + "</div>" +
        "</div>" +
        "<div class='bg-soft-warning w-20 border-end pe-1'>" +
        "<div class=''>" +
        "<div class=''>" + repo.f_date_cust + "</div>" +
        "<div class=''>" + numberWithCommas(repo.f_qty_cust, 0) + "</div>" +
        "<div class=''>" + numberWithCommas(repo.f_fee_cust, 1) + "</div>" +
        "</div> </div> " +
        "<div class='bg-soft-pink w-20 border-end pe-1'>" +
        "<div class=''>" +
        "<div class=''>" + repo.q_date_cust + "</div>" +
        "<div class=''>" + numberWithCommas(repo.q_qty_cust, 0) + "</div>" +
        "<div class=''>" + numberWithCommas(repo.q_fee_cust, 1) + "</div>" +
        "</div> </div> " +
        "<div class='w-15 border-end pe-1'>" +
        "<div class=''>" +
        "<div class=''>" + numberWithCommas(repo.max_price, 1) + "</div>" +
        "<div class=''>" + numberWithCommas(repo.avg_price, 1) + "</div>" +
        // "<div class=''>" + numberWithCommas(repo.min_price, 1) + "</div>" +
        "</div></div>" +
        "<div class='w-40 border-end'>" +
        "<div class='d-flex c-3-color pe-1'>" +
        "<div class=' w-40'>" +
        "<div>." + repo_express + "</div>" +
        "<div>." + repo_air + "</div>" +
        "</div>" +
        "<div class='w-60'>" +
        "<div>." + repo_sea + "</div>" +
        "<div class='c-3-color'>" + repo.price_update_date + "</div>" +
        "</div>" +
        "</div>" +
        "<div class='d-flex pe-1'> " +
        "<div class='w-40'>" + goods_price_market + "</div>" +
        "<div class='w-60'>" + goods_market_date + "</div>" +
        "</div> " +
        "</div> " +

        "</div>" +
        parent_code +
        "</div>"

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

function round_rial(x){
    debugger
    const currency = parseInt(document.getElementById('id_currency_ref').value)
    if (currency != 1){
        return x
    }
    // return x
    if (x >= 1000000) {
        // more than 6 digit, round 3 digit
        x = parseInt(x)
        if (x % 100 === 0){
            return x
        }else {
            x = x / 1000
            x = (parseInt(x) + 1) * 1000
        }
    }
    else if (x <= 999999 || x > 10000){
        // 5 or 6 digit, round 2 digit
        x = parseInt(x)
        if (x % 10 === 0){
            return x
        }else {
            x = x / 10
            x = (parseInt(x) + 1) * 10
        }
    } else if (x <= 9999 || x > 100){
        // 3 or 4 digit, round 2 digit (always to up)
        x = parseInt(x)
        if (x % 10 === 0) {
            return x
        }else {
            x = x / 10
            x = (parseInt(x) + 1) * 10
        }
    } else if (x / 10 > 1) {
        // remove decimal placement
        x = parseInt(x)
    }
    return x
}
function numberWithCommas(x, digits = 2) {
    const currency_ref = parseInt(document.getElementById('id_currency_ref').value)
    if (currency_ref != 1) {
        digits = 4
    }
    if (x == '' || x == null || isNaN(x)) return ''
    x = parseFloat(x)
    if (x >= 100){digits=2}
    let res = (x.toLocaleString('en-US', {maximumFractionDigits: digits}))//t_replaceDigits
    return res
}

function calculate_price(target) {
    const elem = findAncestor(target, "item")
    const final_price = elem.querySelector('[name*="-final_price"]')
    const total_price = elem.querySelector('[name*="-total_price"]')
    const final_amount = elem.querySelector('[name*="-final_amount"]')
    const quantity = elem.querySelector('input[id$="quantity"]')
    const selfDiscount = document.querySelector('input[name*="self_discount"]')
    const isOfficial =  document.querySelector('#id_is_official')
    const isOfficialValue = document.querySelector('#id_official_value')
    let isOfficialValue_number = 0
    let tax = 0;
    let taxValue = 0
    let row_discount = 0
    let row_discount_amount = 0
    let tax_discount = 0
    let row_discount_base_percentage = 0
    let totalDiscount = 0
    let net_price = 0
    let net_price_after_tax_discount = 0
    let calculated_price = 0
    // qty
    let qty = parseFloat(quantity.innerHTML.replaceAll(',', ''))
    if (isNaN(qty)) {
        qty = quantity.value.replaceAll(',', '')
    }
debugger
    // price
    let price = parseFloat(final_price.innerHTML.replaceAll(',', ''))
    if (isNaN(price)) {
        price = removeCommaSeperator(final_price.value)
    }
    row_discount_amount = parseFloat(elem.querySelector('[name*="-discount_per_item"]').value.replaceAll(',', ''))
    row_discount = row_discount_amount * qty
    // net_price = (price - row_discount_amount) * qty
    net_price = price * qty
    net_price_after_tax_discount = net_price

    let selfDiscountValue = parseFloat(selfDiscount.value.replaceAll(',', ''))
    row_discount_base_percentage = net_price_after_tax_discount * (selfDiscountValue/100)

    if (isOfficial && isOfficial.checked){
        tax = 12
        if (isOfficialValue){
            isOfficialValue_number = parseFloat(isOfficialValue.value);
            tax_discount = (net_price - row_discount - row_discount_base_percentage) * (
                        1 - ((100 + tax - isOfficialValue_number) / (100 + tax)))
            // tax_discount = net_price * (isOfficialValue_number / 100)
        }
        net_price_after_tax_discount = net_price - tax_discount
    }


    totalDiscount = row_discount + tax_discount + row_discount_base_percentage //((price * qty) * selfDiscountValue/100)
    if (tax){
        // const final_tax_value = Math.max(tax - isOfficialValue_number, 0)
        taxValue = (net_price - totalDiscount) * (tax/100)
    } else {
        taxValue = 0
    }

    const currency_ref = parseInt(document.getElementById('id_currency_ref').value)
    if (currency_ref == 1){
        taxValue = parseInt(taxValue)
        totalDiscount = parseInt(totalDiscount)
        elem.querySelector('[name*="MAC"]').innerHTML = numberWithCommas(net_price)
        elem.querySelector('[name*="tax_value"]').innerHTML = numberWithCommas(taxValue)
        elem.querySelector('[name*="discount_value"]').innerHTML = numberWithCommas(totalDiscount)
        total_price.innerHTML = numberWithCommas(net_price - totalDiscount + taxValue) || numberWithCommas(price * qty)
        final_amount.value = Number(String(total_price.innerHTML).replace(/,/g, '')) || 0
    } else {
        elem.querySelector('[name*="MAC"]').innerHTML = numberWithCommas(net_price)
        elem.querySelector('[name*="tax_value"]').innerHTML = numberWithCommas(taxValue)
        elem.querySelector('[name*="discount_value"]').innerHTML = numberWithCommas(totalDiscount)
        total_price.innerHTML = numberWithCommas((price * qty) - totalDiscount + taxValue) || numberWithCommas(price * qty)
        final_amount.value = Number(String(total_price.innerHTML).replace(/,/g, '')) || 0
    }
    //calculated_price = net_price - totalDiscount + tax

    var items = document.querySelectorAll('[name="-total_price"]')
    let m_sum = 0
    for (let i = 0; i < items.length; i++) {
        val = parseFloat(items[i].innerHTML.replaceAll(',', ''))
        // console.log(`${i}=== ${val}`)
        if (!isNaN(val)) {
            m_sum += val
        }
    }
    console.log(`===========================\n============================`)
    if (!m_sum) {
        m_sum = 0
    }
    const t_prices = $(document).find('.quotation_total_price')
    const additionElm = document.querySelector('#id_addition')
    const taxElm = document.querySelector('#id_tax')
    const additionValue = additionElm.value ? parseFloat(additionElm.value) : 0
    const topTaxValue = taxElm.value ? parseFloat(taxElm.value) : 0
    for (let i = 0; i < t_prices.length; i++) {
        t_prices[i].innerHTML = numberWithCommas(m_sum + additionValue + topTaxValue, 0).toString()
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

function set_values_if(items, value, is_date = false, field_name=null, row_number=null) {

    if (!value) {
        if (global_info){
            global_info.classList.remove('d-none')
            global_info.querySelector('#global-info-text').innerHTML = `<span>${field_name}</span> <span>یافت نشد</span> <span>ردیف</span> <span>${row_number}</span>`
        }
        return false
    }

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

function AllPriceFormatRepoItem(repo) {
    if (repo.loading) {
        return repo.text;
    }

    let variant = ''
    for (let key in repo.variants_json){
        variant += `<span class="badge" style="text-align: right">${key} ${repo.variants_json[key]}</span>`
    }
    var $container = $(
        `<div class="row flex-row-reverse text-center">
            <div class="col-2">
                <span class="me-3">${repo.sku}</span>
            </div>
            <div class="col-5" style="text-align: right; direction: rtl">
                <span class="me-1">${repo.inquiry_type}</span>
                <span class="me-2">${variant}</span>
            </div>
            <div class="col-2">
                <span>${repo.last_update_date}</span>
            </div>
            <div class="col-3">
                <span>${repo.editor_user}</span>
            </div>
        </div>`
    );
    return ($container);
}

function read_price_json(elem){
    let price_json = elem.querySelector('textarea[name$="-price_json"]')
    price_json = JSON.parse(price_json?.value || 0) || []
    return price_json
}
function check_quotation_price_market_before_save_permission2(elem){
    // check_price_expire_date_array = []

    let p_m = elem.querySelector('select[name*="-price_method"]')?.value || null
    let price_json = read_price_json(elem)

    if (p_m === 'bazar'){

        for (let item of price_json){
            if (item.unique_title === 'bazar'){
                const market_diff_time = diffTimeInQuotation(item.price_expire_date || 10000)
                if (market_diff_time.status) { // invalid price - expire
                    check_price_expire_date_array.push(false)
                    // submit_buttons.forEach(function (submit_button){
                    //     submit_button.classList.add('disabled')
                    // })
                    show_price_expire_message(elem, market_diff_time.message, market_diff_time.css)
                } else { // valid price
                    check_price_expire_date_array.push(true)
                    // submit_buttons.forEach(function (submit_button){
                    //     submit_button.classList.remove('disabled')
                    // })
                    show_price_expire_message(elem, market_diff_time.message, market_diff_time.css)
                }
            }
        }
    } else if (p_m === 'sales_admin') {
        check_price_expire_date_array.push(true)
        elem.querySelector('input[name$="-final_price"]').classList.remove('disable')
        show_price_expire_message(elem, '')
    } else {
        check_price_expire_date_array.push(true)
        show_price_expire_message(elem, '')
    }

    return check_price_expire_date_array
}

function show_price_expire_message(elem, message, css=null){

    const price_expire_message_container = elem.querySelector('[name*="price_expire_date"]')
    if (price_expire_message_container){
        price_expire_message_container.innerText = message
        if (css){
            price_expire_message_container.classList.add(css)
        }
    }
}

function toggle_submit_buttons(status){
    if (status){ // enable submit buttons
        submit_buttons.forEach(function (submit_button){
            submit_button.classList.remove('disabled')
        })
    } else { // disable submit buttons
        submit_buttons.forEach(function (submit_button){
            submit_button.classList.add('disabled')
        })
    }
}


function checkPrice(row=null) {
    debugger;
    let prices = []
    const diff_price_alert = row.querySelector('.diff_price_alert')
    const final_price = row.querySelector('input[name*="-final_price"]')
    const price_json = JSON.parse(row.querySelector('textarea[name$="-price_json"]')?.value || 0) || []
    price_json.forEach(function (item){
            console.log(item)
            if (item.unique_title !== 'goods_last_price' && item.unique_title !== 'goods_q_last_price'){
                prices.push(item.value)
            }
        })

    // اگر هیچ قیمت دیگری وجود ندارد یا مقدار عددی نیست
    if (prices.length === 0 || isNaN(final_price.value)) {
        final_price.classList.remove('border-danger');
        // diff_price_alert.classList.remove('badge-danger');
        diff_price_alert.textContent = ''
        return;
    }

    const numericFinalPrice = parseFloat(final_price.value);
    const numericPrices = prices.map(p => parseFloat(p)).filter(p => !isNaN(p));

    numericPrices.push(numericFinalPrice);
    numericPrices.sort((a, b) => a - b);

    const idx = numericPrices.indexOf(numericFinalPrice);
    let diff = 0;

    if (idx === 0 && numericPrices.length > 1) {
        diff = ((numericPrices[1] - numericPrices[0]) / numericPrices[0]) * 100;
    } else if (idx === numericPrices.length - 1 && numericPrices.length > 1) {
        diff = ((numericPrices[idx] - numericPrices[idx - 1]) / numericPrices[idx - 1]) * 100;
    }

    // ✅ حالا بررسی اختلاف
    if (Math.abs(diff) > 50) {
        final_price.classList.add('border-danger');
        diff_price_alert.classList.remove('d-none');
        // diff_price_alert.classList.add('badge');
        // diff_price_alert.classList.add('badge-danger');
        // diff_price_alert.classList.add('rounded');
        diff_price_alert.textContent = '⚠️ اختلاف قیمت بیش از ۵۰٪ است. ذخیره پیش فاکتور ممکن نیست.';
        //document.querySelector('#global-action-button').classList.add('d-none')

    } else if (Math.abs(diff) > 10){
        final_price.classList.add('border-danger');
        diff_price_alert.classList.remove('d-none');
        // diff_price_alert.classList.add('badge');
        // diff_price_alert.classList.add('badge-danger');
        // diff_price_alert.classList.add('rounded');
        diff_price_alert.textContent = '⚠️ اختلاف قیمت بیش از ۱۰٪ است.';
        //document.querySelector('#global-action-button').classList.remove('d-none')
    }
    else {
        final_price.classList.remove('border-danger');
        // diff_price_alert.classList.remove('badge');
        // diff_price_alert.classList.remove('badge-danger');
        // diff_price_alert.classList.remove('rounded');
        diff_price_alert.classList.add('d-none');
        diff_price_alert.textContent = ''
        //document.querySelector('#global-action-button').classList.remove('d-none')
    }
}
