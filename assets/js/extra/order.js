
// const customer_select2_placeholder = document.querySelector('[name="customer"]').value.toString() || "مشتری"
const item_select2_placeholder = document.querySelector('[name="item"]').value.toString() || "کد کالا"
// select2_generate('#id_customer_select2', '#id_customer', '/sepidar/customers_list', customer_select2_placeholder, 'sepidar_party_id')
select2_generate('#id_item_select2', '#id_item', '/inquiry/items_list', item_select2_placeholder)

if (!$('#id_trade_commitment_date').data("datepicker")){
    $('#id_trade_commitment_date').datepicker({
        dateFormat: 'yy-mm-dd',
        changeMonth: true,
        changeYear: true,
    });
}
if (!$('#id_commitment_date_to_customer').data("datepicker")){
    $('#id_commitment_date_to_customer').datepicker({
        dateFormat: 'yy-mm-dd',
        changeMonth: true,
        changeYear: true,
    });
}
if (false){

    $('#id_customer_select2').select2({
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
        text: document.querySelector('[name="customer"]').value.toString() || "مشتری",
    },
    allowClear: false,
    templateResult: formatRepoDL,
    templateSelection: formatRepoSelection
});

$('#id_customer_select2').on("select2:select", function (e) {
    debugger
    const data = e.params.data;
    document.querySelector('[name="customer"]').value = data.id
    document.querySelector('[id*="select2-id_customer_select2-container"]').querySelector('span').innerHTML = data.id + " " + data.text
    // $(document).find("#customer_card").attr("class", "alert-warning h-100 p-2");
    // document.getElementById("customer_card").classList.remove('d-none');
    // $(document).find("#customer_name").text(data.text);
    // $(document).find("#customer_pid").text(data.sepidar_party_id);
    // $(document).find("#id_customer_party_id").val(data.sepidar_party_id);
})


$(item).find('.goods_code').select2({
    dir: 'ltr',
    ajax: {
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

$('#id_item').select2({
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


$('#id_item').on("select2:select", function (e) {
        const data = e.params.data;
        document.querySelector('[name="customer_code"]').value = data.id
        document.querySelector('[id*="select2-customer_code"][id*="container"]').querySelector('span').innerHTML = data.id
        // $(document).find("#customer_card").attr("class", "alert-warning h-100 p-2");
        document.getElementById("customer_card").classList.remove('d-none');
        $(document).find("#customer_name").text(data.text);
        $(document).find("#customer_pid").text(data.sepidar_party_id);
        $(document).find("#id_customer_party_id").val(data.sepidar_party_id);
    })
}