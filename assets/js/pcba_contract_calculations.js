/* Live PCBA contract calculations. The server-side Contract properties remain
   authoritative when the form is saved. */
(function () {
    'use strict';

    function readInteger(id) {
        var field = document.getElementById(id);
        if (!field) return 0n;

        var persian = '۰۱۲۳۴۵۶۷۸۹';
        var arabic = '٠١٢٣٤٥٦٧٨٩';
        var value = String(field.value || '').replace(/[۰-۹٠-٩]/g, function (digit) {
            var index = persian.indexOf(digit);
            return String(index >= 0 ? index : arabic.indexOf(digit));
        }).replace(/[\s,٬،]/g, '');

        if (!/^\d+$/.test(value)) return 0n;
        try {
            return BigInt(value);
        } catch (error) {
            return 0n;
        }
    }

    function displayInteger(element, value) {
        if (element) element.textContent = value.toLocaleString('en-US');
    }

    function refresh() {
        var normal = readInteger('id_pad_count');
        var ic = readInteger('id_ic_pad_count');
        var paste = readInteger('id_not_assembly_pad_count');
        var boards = readInteger('id_customer_total_board_count');
        var normalRate = readInteger('id_pad_cost');
        var icRate = readInteger('id_ic_pad_cost');
        var firstSetup = readInteger('id_first_setup_cost');
        var secondSetup = readInteger('id_second_setup_cost');
        var extra = readInteger('id_extra_total_cost');

        displayInteger(document.getElementById('pcba-total-pads-per-board'),
                       normal + ic + paste);

        var total = ((normal + paste) * normalRate + ic * icRate) * boards
                    + firstSetup + secondSetup + extra;
        displayInteger(document.getElementById('pcba-calculated-contract-cost'), total);
    }

    var inputs = [
        'id_pad_count', 'id_ic_pad_count', 'id_not_assembly_pad_count',
        'id_customer_total_board_count', 'id_pad_cost', 'id_ic_pad_cost',
        'id_first_setup_cost', 'id_second_setup_cost', 'id_extra_total_cost'
    ];

    inputs.forEach(function (id) {
        var field = document.getElementById(id);
        if (!field) return;
        field.addEventListener('input', refresh);
        field.addEventListener('change', refresh);
    });

    refresh();
})();
