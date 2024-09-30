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
                text: document.querySelector('[name="customer_code"]').value.toString(),
            },
            allowClear: false,
            templateResult: formatRepoDL,
            templateSelection: formatRepoSelection
        });

if (false){
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

$('#id_customer').on("select2:select", function (e) {
        const data = e.params.data;
        document.querySelector('[name="customer_code"]').value = data.id
        document.querySelector('[id*="select2-customer_code"][id*="container"]').querySelector('span').innerHTML = data.id
        // $(document).find("#customer_card").attr("class", "alert-warning h-100 p-2");
        document.getElementById("customer_card").classList.remove('d-none');
        $(document).find("#customer_name").text(data.text);
        $(document).find("#customer_pid").text(data.sepidar_party_id);
        $(document).find("#id_customer_party_id").val(data.sepidar_party_id);
    })
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