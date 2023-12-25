
$(document).ready(function () {
    console.log('start data table')
    let start = Date.now();
    $("#datatable").DataTable(), $("#datatable-buttons").DataTable({
        lengthChange: 100,
        buttons: ["copy", "excel", "pdf", "colvis"]
    }).buttons().container().appendTo("#datatable-buttons_wrapper .col-md-6:eq(0)"), $(".dataTables_length select").addClass("form-select form-select-sm")

    console.log('end data table')
 let timeTaken = Date.now() - start;
            console.log("Total time taken : " + timeTaken + " milliseconds");
});