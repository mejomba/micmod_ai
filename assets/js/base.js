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
function commaSeperator(n, step=null, sep=null) {
    let c = 0;
    let nwc = n;
    if (!step){step = 3}
    for (let i = 0; i <= n.length; i++) {
        if (i % step === 0 && i !== 0 && i !== n.length) {
            if (sep){
                nwc = nwc.insert(i + c, sep)
            }else {
                nwc = nwc.insert(i + c, ',')
            }
            c++;
        }
    }
    return nwc
}

function numberWithCommas(x, digits = 2) {
    if (x == '' || x == null || isNaN(x)) return ''
    x = parseFloat(x)
    let res = (x.toLocaleString('en-US', {maximumFractionDigits: digits}))//t_replaceDigits
    return res
}

function addCommaSeperator(on_load=null) {
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
        if (on_load){
            inputNumberValue = item.value.replaceAll(',', '').reverse_string();
            numberWithComma = inputNumberValue;
            numberWithComma = commaSeperator(inputNumberValue)
            item.value = numberWithComma.reverse_string()
        }
    })
}

function shomare_kart(on_load=null) {
    let inputNumberValue;
    let numberWithComma;

    const textInput = document.querySelectorAll('.shomare-kart')
    textInput.forEach(function (item) {
        item.addEventListener('keyup', function (e) {
            inputNumberValue = e.currentTarget.value.replaceAll('-', '').reverse_string();
            numberWithComma = inputNumberValue;
            numberWithComma = commaSeperator(inputNumberValue, 4, '-')
            e.currentTarget.value = numberWithComma.reverse_string()
        })
        if (on_load){
            inputNumberValue = item.value.replaceAll('-', '').reverse_string();
            numberWithComma = inputNumberValue;
            numberWithComma = commaSeperator(inputNumberValue, 4, '-')
            item.value = numberWithComma.reverse_string()
        }
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
    debugger
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

function custom_ajax_post_data(post_data, url, element=null, reload_page=null) {
    debugger
    $.ajax({
        type: 'POST',
        url: url,
        dataType: 'json',
        data: post_data,
        headers: {
            "X-CSRFToken": getCookie("csrftoken")
        },
        cache: false,
        processData: false,
        contentType: false,
        beforeSend: block_main_container,
        success: function (data) {
            if(element) {
                html = data['res'];
                try {
                    element.html(html);
                } catch (e) {
                    element.innerHTML = html
                }
                run_scripts(html);
            }
            if(reload_page){
                setTimeout(function (){
                    var loc = window.location;
                    window.location = loc.protocol + '//' + loc.host + loc.pathname + loc.search;
                    // location.reload()
                }, 500)
            }
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

function custom_ajax_get(form_, url, element) {
    removeCommaSeperator()
    let new_url = url
    if (form_) {
        const formSerialize = form_.serialize();
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
    // debugger
    // if (navigator.clipboard) {
    //     navigator.clipboard.writeText(text).catch(function () {
    //     });
    // } else {
    // let copyText = elem;
    // elem.focus();
    // elem.select();
    // document.execCommand("copy");
    // }
    const str = elem.outerText
    const el = document.createElement('textarea');
    el.value = str;
    el.setAttribute('readonly', '');
    el.style.position = 'absolute';
    el.style.left = '-9999px';
    document.body.appendChild(el);
    const selected =
        document.getSelection().rangeCount > 0
            ? document.getSelection().getRangeAt(0)
            : false;
    el.select();
    document.execCommand('copy');
    document.body.removeChild(el);
    if (selected) {
        document.getSelection().removeAllRanges();
        document.getSelection().addRange(selected);
        const div = document.createElement('div')
        div.classList.add('message-bottom-middle')
        div.classList.add('bg-light-success')
        div.classList.add('rounded')
        const message = document.createTextNode(`${str} کپی شد`)
        div.appendChild(message)
        document.body.appendChild(div)
        setTimeout(function (){div.classList.add('d-none')}, 2500)
    }
}


    const changeLogBtnAjax = document.querySelectorAll('[name="name_change_log"]')
    if (changeLogBtnAjax){
    changeLogBtnAjax.forEach(function (item) {
        item.addEventListener('click',function (e){
            const modelName = item.dataset.model_name
            const objectId = item.dataset.object_id
            const appName = item.dataset.app_name
            debugger
        let new_url = `/core/ajax/changelog/${appName}/${modelName}/${objectId}/`
        $.ajax({
            type: 'GET',
            url: new_url,
            dataType: 'json',
            cache: false,
            processData: false,
            contentType: false,
            beforeSend: block_main_container,
            success: function (data) {
                debugger
                html = data['res'];
                document.querySelector('#id-empty-modal-body-lg').innerHTML = html
            },
            error: function () {

            },
            complete: release_main_container

        });
     })
    })


        const emptyModal = document.getElementById('id_kt_empty_modal')
        if (emptyModal){
            emptyModal.addEventListener('hidden.bs.modal', function (e) {
            document.querySelector('#id-empty-modal-body').innerHTML = ''
            })
        }

        const emptyModalLG = document.getElementById('id_kt_empty_modal_lg')
        if (emptyModalLG){
            emptyModalLG.addEventListener('hidden.bs.modal', function (e) {
            document.querySelector('#id-empty-modal-body-lg').innerHTML = ''
        })
        }

        const emptyModalSM = document.getElementById('id_kt_empty_modal_sm')
        if (emptyModalSM) {
            emptyModalSM.addEventListener('hidden.bs.modal', function (e) {
            document.querySelector('#id-empty-modal-body-sm').innerHTML = ''
        })
        }

        const modalLG = document.querySelector('#id_kt_empty_modal_lg');
        if (modalLG){
            modalLG.addEventListener('click', function (e){
                if (formFooterContainer) {
                    console.log('hide')
                      formFooterContainer.classList.add('position-fixed')
                  }
            })
        }

    }

function ajax_submit
(form, reload_=null, elem_for_load=null) {
        debugger
    $.ajax({ // create an AJAX call...
        beforeSend: function (xhr){
            debugger
            if (elem_for_load){
                console.log('load...')
            }
            if (!$(form).find('input[name="csrfmiddlewaretoken"]').length) {
                const csrfToken = getCookie('csrftoken');
                xhr.setRequestHeader('X-CSRFToken', csrfToken);
            }
        },
        data: $(form).serialize(), // get the form data
        type: $(form).attr('method'), // GET or POST
        url: $(form).attr('action'), // the file to call
        success: function (data){
            debugger
            if (reload_){
                window.location.reload()
            }
        }
    });
}

function initializeDatepickers(elem_id=null) {
    console.log(elem_id)
    if(elem_id){
        elem_id.forEach(function (id){
            console.log(elem_id, $(`#${id}`))
            $(`#${id}`).datepicker({
                dateFormat: 'yy-mm-dd',
                changeMonth: true,
                changeYear: true,
            });
        })
    }
}

function ajax_delete(elms) {
    if (elms) {
        elms.forEach((element) => {
            element.addEventListener('click', function (e) {
                e.preventDefault()
                const modal_sm_body = $('#id-empty-modal-body-sm')
                custom_ajax_get('', this.dataset.url, modal_sm_body)
            })
        })
    }
}

function select2_generate(select2_element, target_element, url, placeholder, id_field='id', minimumInputLength=null,
                          formatRepoDL=null, formatRepoSelection=null){
    // target_element => '#target_element'
    $(select2_element).select2({
        ajax: {
            url: url,
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
        minimumInputLength: minimumInputLength || 1,
        placeholder: {
            text: placeholder
        },
        allowClear: false,
        templateResult: formatRepoDL || defaultFormatRepoDL,
        templateSelection: formatRepoSelection || defaultFormatRepoSelection
    });

    $(select2_element).on("select2:select", function (e) {
        const data = e.params.data;
        const element_to_show = "select2-" + target_element.substring(1) + "_select2-container"
        $(document).find(target_element).val(data[id_field])
        document.querySelector(`[id*=${element_to_show}]`).querySelector('span').innerHTML = data.id + " " + data.text
    })
}

function defaultFormatRepoDL(repo) {
    if (repo.loading) {
        return repo.text;
    }
    var $container = $(`
        <div class='d-flex'>
        <span class="bg-light-success rounded px-1 me-3">${repo.id}</span>
        <span>${repo.text}</span>
        </div>
    `);
    return ($container)
}

function defaultFormatRepoSelection(repo) {
    return repo.id || repo.text
}

function addWindowHighlightSections(color = 'rgba(0, 128, 255, 0.3)') {
    const topHighlight = document.createElement('div');
    const  help_text = 'برای اسکرول خودکار ابتدا همه ردیف ها را بسته و ردیف مورد نظر را به اینجا بکشید'
    topHighlight.innerText = help_text
    topHighlight.id = 'topHighlight'
    Object.assign(topHighlight.style, {
        position: 'fixed',
        top: '100px',
        left: '0',
        width: '90%',
        height: '100px',
        textAlign: 'center',
        color: 'blue',
        fontSize: '18px',
        backgroundColor: color,
        zIndex: '9999',
        pointerEvents: 'none',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
    });
    document.body.appendChild(topHighlight);

    const bottomHighlight = document.createElement('div');
    bottomHighlight.innerText = help_text
    bottomHighlight.id = 'bottomHighlight'
    Object.assign(bottomHighlight.style, {
        position: 'fixed',
        bottom: '100px',
        left: '0',
        width: '90%',
        height: '100px',
        textAlign: 'center',
        color: 'blue',
        fontSize: '18px',
        backgroundColor: color,
        zIndex: '9999',
        pointerEvents: 'none',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
    });
    document.body.appendChild(bottomHighlight);
}
    function removeWindowHighlightSections(){
        const a = document.querySelector('#bottomHighlight');
        const b = document.querySelector('#topHighlight');
        if (a){a.remove()}
        if (b){b.remove()}
    }

function generate_drag_drop(container_id='sortable-container', draggable_items_selector='#sortable-container .sortable-item', index_field_id_selector='-index'){
    var sortable = new Sortable(document.getElementById(container_id), {
        animation: 200,
        handle: '.handel-drop',
        ghostClass: 'drag-drop',
        onStart: function (evt){
            addWindowHighlightSections('rgba(255, 0, 0, 0.2)');
        },
        onEnd: function (evt) {
            var items = document.querySelectorAll(draggable_items_selector);
            items.forEach(function(item, index) {
                item.querySelector(`[id*=${index_field_id_selector}]`).value = index
            });
            removeWindowHighlightSections()
        },
        onUpdate: function (evt) {
            evt.item.querySelector(`[id*=${index_field_id_selector}]`).value = evt.newIndex
        },
        onChange: function (evt) {
            const threshold = 200; // فاصله از لبه صفحه برای شروع اسکرول
            const scrollSpeed = 100; // سرعت اسکرول
            const topHighlight = document.createElement('div');

            // چک کردن موقعیت موس
            const mouseY = evt.originalEvent.clientY;
            console.log('mouseY= ', mouseY)

            // اگر موس به بالای صفحه نزدیک شد، اسکرول به سمت بالا
            if (mouseY < threshold) {
                window.scrollBy(0, -scrollSpeed);
            }
            // اگر موس به پایین صفحه نزدیک شد، اسکرول به سمت پایین
            else if ((window.innerHeight - mouseY) < threshold) {
                window.scrollBy(0, scrollSpeed);
            }
        }
    });
}