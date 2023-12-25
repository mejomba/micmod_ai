function getCookie(c_name)
{
    if (document.cookie.length > 0)
    {
        c_start = document.cookie.indexOf(c_name + "=");
        if (c_start != -1)
        {
            c_start = c_start + c_name.length + 1;
            c_end = document.cookie.indexOf(";", c_start);
            if (c_end == -1) c_end = document.cookie.length;
            return unescape(document.cookie.substring(c_start,c_end));
        }
    }
    return "";
 }

    const btn_send = (document).querySelector("[name='telegram_send_code']")
const btn_verify = (document).querySelector("[name='telegram_loging']")
const form = document.getElementById("session_form")
console.log(form)
btn_send.addEventListener('click',function(e) {
    e.preventDefault()
    let formData = new FormData(form);
    formData.set('id',btn_send.getAttribute("obj-id"))
    $.ajax({
        url: btn_send.getAttribute("url-data"),
        // data: {'phone_number':"989128900421","type":1,"id":1},
        data: formData,
        headers: { "X-CSRFToken": getCookie('csrftoken') },
        cache: false,
        processData: false,
        contentType: false,
        dataType: 'json',
        type: 'POST',
        success: function (resp) {
            console.log(resp);
            btn_verify.style.display = "block"
        },
        error: function (e) {
            alert('Error: ' + e);
        }
    });
})

btn_verify.addEventListener('click',function(e){
    e.preventDefault()
    let formData = new FormData(form)
    formData.set('id',btn_send.getAttribute("obj-id"))
    $.ajax({
        url: btn_verify.getAttribute("url-data"),
        data: formData,
        headers: { "X-CSRFToken": getCookie('csrftoken') },
        cache: false,
        processData: false,
        contentType: false,
        dataType: 'json',
        type: 'POST',
        success: function (resp) {
            console.log(resp);
            btn_verify.style.display = "none"
            btn_send.setAttribute("disabled","disabled")
        },
        error: function (e) {
            alert('Error: ' + e);
        }
    });
})
