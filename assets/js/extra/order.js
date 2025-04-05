// const price_element = document.querySelector("input[name='price']")
// const price_trade_element = document.querySelector("input[name='price_trade']")
// const price_mac_element = document.querySelector("input[name='price_mac']")


// const customer_select2_placeholder = document.querySelector('[name="customer"]').value.toString() || "مشتری"

const item_select2_placeholder = document.querySelector('[name="item_placeholder"]').innerText.toString() || "کد کالا"
// select2_generate('#id_customer_select2', '#id_customer', '/sepidar/customers_list', customer_select2_placeholder, 'sepidar_party_id')
select2_generate('#id_item_select2', '#id_item', '/inquiry/items_list', item_select2_placeholder)
select2_generate('#id_item_trade_select2', '#id_item_trade', '/inquiry/items_list', item_select2_placeholder)

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
