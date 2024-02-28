const baseUrl = window.origin
const footerToggle = document.querySelector('.footer-toggle');
const formFooterContainer = document.getElementById('form-footer-container')
let footerOpen = true;

if (footerToggle) {
    footerToggle.addEventListener('click', function (e) {
        if (footerOpen) {
            footerToggle.style.rotate = '-90deg';
            formFooterContainer.style.bottom = "-40px";
            footerOpen = !footerOpen
        } else {
            footerToggle.style.rotate = '90deg';
            formFooterContainer.style.bottom = "0";
            footerOpen = !footerOpen;
        }
    })
}

const m = document.querySelectorAll('.modal');
const closeModal = document.querySelectorAll('.close-modal');
const changeLogBtn = document.querySelectorAll('.changelog-btn');

changeLogBtn.forEach(function (item) {
    item.addEventListener('click', function (e) {
        if (formFooterContainer) {
            formFooterContainer.classList.remove('position-fixed')
        }
    })
})
closeModal.forEach(function (item) {
    item.addEventListener('click', function (e) {
        if (formFooterContainer) {
            formFooterContainer.classList.add('position-fixed')
        }
    })
})

function getCookie(c_name) {
    if (document.cookie.length > 0) {
        c_start = document.cookie.indexOf(c_name + "=");
        if (c_start != -1) {
            c_start = c_start + c_name.length + 1;
            c_end = document.cookie.indexOf(";", c_start);
            if (c_end == -1) c_end = document.cookie.length;
            return unescape(document.cookie.substring(c_start, c_end));
        }
    }
    return "";
}

$.fn.replaceDigits = function () {
    var map =
        [
            "&\#1632;", "&\#1633;", "&\#1634;", "&\#1635;", "&\#1636;",
            "&\#1637;", "&\#1638;", "&\#1639;", "&\#1640;", "&\#1641;"
        ];

    $(this).each(function () {
        $(this).html($(this).html().replace(
            /\d(?=[^<>]*(<|$))/g,
            function ($0) {
                return map[$0]
            }
        ));
    });

}

function convertToInt() {
    const convertToInt = document.querySelectorAll('.convert-to-int')
    convertToInt.forEach(function (item) {
        item.value = parseInt(item.value.replaceAll(',', '').toString())
    })
}

// convertToInt()
function commaSeperator(n) {
    let c = 0;
    let nwc = n;
    for (let i = 0; i <= n.length; i++) {
        if (i % 3 === 0 && i !== 0 && i !== n.length) {
            nwc = nwc.insert(i + c, ',')
            c++;
        }
    }
    return nwc
}

function addCommaSeperator() {
    let inputNumberValue;
    let numberWithComma;

    const textInput = document.querySelectorAll('.comma-seperator')
    textInput.forEach(function (item) {
        item.addEventListener('keyup', function (e) {
            inputNumberValue = e.currentTarget.value.replaceAll(',', '').reverse_string();
            numberWithComma = inputNumberValue;
            numberWithComma = commaSeperator(inputNumberValue)
            e.currentTarget.value = numberWithComma.reverse_string()
        })
    })
}

function removeCommaSeperator() {
    const textInput = document.querySelectorAll('.comma-seperator')
    textInput.forEach(function (item) {
        item.value = item.value.replaceAll(',', '')
    })
}

const main_container = new KTBlockUI(document.querySelector('#main-content'), {
    overlayClass: "bg-primary bg-opacity-25",
});

function get_main_container() {
    let block_container = document.querySelector('#block_container')
    if (!block_container) {
        block_container = document.querySelector('#main-content')
    }
    main_container.element = block_container
    return main_container
}

function block_main_container() {
    get_main_container().block(

    );
}

function release_main_container() {
    get_main_container().release();
}

function custom_ajax_post(form, url, element) {
    let formData = new FormData(form);
    $.ajax({
        type: 'POST',
        url: url,
        dataType: 'json',
        data: formData,
        headers: {
            "X-CSRFToken": getCookie("csrftoken")
        },
        cache: false,
        processData: false,
        contentType: false,
        beforeSend: block_main_container,
        success: function (data) {
            html = data['res'];
            element.html(html);
            run_scripts(html);
        },
        error: function () {

        },
        complete: release_main_container
    }); // end ajax
}

function run_scripts(elem) {
    const scripts = elem.match(/<script (.*?)<\/script>/g)
    const u_scripts = Array.from(new Set(scripts))
    u_scripts.map((script) => {
        script = script.replace('"><\/script>', '').replace('<script src="/', '');
        loadJS(script);
    })
    loadJS('/assets/js/refresh_after_ajax.js')
    loadJS('/assets/lang/translate.js')
}

function loadJS(file) {
    const content = document.querySelector('body');
    const jsElm = document.createElement("script");
    jsElm.src = file;
    content.appendChild(jsElm);
}

function custom_ajax_get(form, url, element) {
    let new_url = url
    if (form) {
        const formSerialize = form.serialize();
        new_url = `${url}?${formSerialize}`
    }
    $.ajax({
        type: 'GET',
        url: new_url,
        dataType: 'json',
        cache: false,
        processData: false,
        contentType: false,
        beforeSend: block_main_container,
        success: function (data) {
            html = data['res'];
            element.html(html);
            run_scripts(html);
        },
        error: function () {

        },
        complete: release_main_container
    });
}


function setCookie(cname, cvalue, exdays = null) {
    const d = new Date();
    if (exdays == null) {
        exdays = 365
    }
    d.setTime(d.getTime() + (exdays * 24 * 60 * 60 * 1000));
    let expires = "expires=" + d.toUTCString();
    document.cookie = cname + "=" + cvalue + ";" + expires + ";path=/";
}

function getCookie(cname) {
    let name = cname + "=";
    let ca = document.cookie.split(';');
    for (let i = 0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) == ' ') {
            c = c.substring(1);
        }
        if (c.indexOf(name) == 0) {
            return c.substring(name.length, c.length);
        }
    }
    return "";
}

function checkCookie() {
    let user = getCookie("username");
    if (user != "") {
        alert("Welcome again " + user);
    } else {
        user = prompt("Please enter your name:", "");
        if (user != "" && user != null) {
            setCookie("username", user, 365);
        }
    }
}

function copyToClipboard(elem) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).catch(function () {
        });
    } else {
        // let copyText = elem;
        elem.focus();
        document.execCommand("copy");
    }
}

