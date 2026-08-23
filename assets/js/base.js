// document.querySelectorAll('.replace-digits').forEach()
function formatNumber(event) {
    debugger
    let value = event.currentTarget.value
  if (!value) return "";

  // حذف هر چیزی به جز عدد و نقطه
  value = value.toString().replace(/[^\d.]/g, "");

  // جلوگیری از چند نقطه
  const parts = value.split(".");
  const integerPart = parts[0];
  const decimalPart = parts[1] !== undefined ? parts[1] : null;

  // فرمت سه‌رقمی بخش صحیح
  const formattedInt = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");

  // برگرداندن نتیجه
  const final = decimalPart !== null
    ? `${formattedInt}.${decimalPart}`
    : formattedInt;
  event.currentTarget.value = final

}
function findAncestor(el, cls) {
    if (el.classList.contains(cls)) {
        return el
    }
    while ((el = el.parentElement) && !el.classList.contains(cls)) ;
    return el;
}
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
function commaSeperator(value, step=3, sep=',') {
    debugger
    if (!value) return "";

  // حذف هر چیزی به جز عدد و نقطه
  value = value.toString().replace(/[^\d.]/g, "");

  // جلوگیری از چند نقطه
  const parts = value.split(".");
  const integerPart = parts[0];
  const decimalPart = parts[1] !== undefined ? parts[1] : null;

  // فرمت سه‌رقمی بخش صحیح+
    const regex = new RegExp(`\\B(?=(\\d{${step}})+(?!\\d))`, 'g');
  const formattedInt = integerPart.replace(regex, sep);

  if (decimalPart !== null && decimalPart !== "0"){
      return `${formattedInt}.${decimalPart}`
  } else {
      return formattedInt
  }

    // let c = 0;
    // let nwc = n;
    // if (!step){step = 3}
    // for (let i = 0; i <= n.length; i++) {
    //     if (i % step === 0 && i !== 0 && i !== n.length) {
    //         if (sep){
    //             nwc = nwc.insert(i + c, sep)
    //         }else {
    //             nwc = nwc.insert(i + c, ',')
    //         }
    //         c++;
    //     }
    // }
    // return nwc
}

function numberWithCommas(x, digits = 2) {
    if (x == '' || x == null || isNaN(x)) return ''
    x = parseFloat(x)
    let res = (x.toLocaleString('en-US', {maximumFractionDigits: digits}))//t_replaceDigits
    return res
}

function addCommaSeperator(on_load=null, step=3, sep=',') {
    let inputNumberValue;
    let numberWithComma;

    const textInput = document.querySelectorAll('.comma-seperator')
    textInput.forEach(function (item) {
        item.addEventListener('keyup', function (e) {
            debugger
            inputNumberValue = e.currentTarget.value.replaceAll(sep, '') //.reverse_string();
            numberWithComma = inputNumberValue;
            numberWithComma = commaSeperator(inputNumberValue, step, sep)
            e.currentTarget.value = numberWithComma //numberWithComma.reverse_string()
        })
        if (on_load){
            debugger
            inputNumberValue = item.value.replaceAll(sep, '') //.reverse_string();
            numberWithComma = inputNumberValue;
            numberWithComma = commaSeperator(inputNumberValue, step, sep)
            item.value = numberWithComma //numberWithComma.reverse_string()
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

function removeCommaSeperator(str=null) {
    debugger
    if (str !== null){
        try {
            return str.replaceAll(',', '')
        } catch (e) {
            return ''
        }
    } else {
        const textInput = document.querySelectorAll('.comma-seperator')
        textInput.forEach(function (item) {
            item.value = item.value.replaceAll(',', '')
        })
    }
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

function custom_ajax_post(form, url, element, reload_=null) {
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
            if (element){
                element.html(html);
            }
            if (reload_){
                console.log('reload...')
                setTimeout(function (){
                    var loc = window.location;
                    window.location = loc.protocol + '//' + loc.host + loc.pathname + loc.search;
                    // location.reload()
                }, 500)
            }
            run_scripts(html);
        },
        error: function () {

        },
        complete: release_main_container
    }); // end ajax
}

function custom_ajax_post_data(post_data, url, element=null, reload_page=null) {
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
            debugger
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
        error: function (data) {
            debugger
            // createAccordion(data.responseJSON['res'], jsonContainer)
            initJsonAccordion(data.responseJSON['res'])
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
            emptyModal.addEventListener('shown.bs.modal', function (e) {
                setTimeout(get_translate, 1500)
            })
        }

        const emptyModalLG = document.getElementById('id_kt_empty_modal_lg')
        if (emptyModalLG){
            emptyModalLG.addEventListener('hidden.bs.modal', function (e) {
                document.querySelector('#id-empty-modal-body-lg').innerHTML = ''
            })
            emptyModalLG.addEventListener('shown.bs.modal', function (e) {
                setTimeout(get_translate, 1500)
            })
        }

        const emptyModalSM = document.getElementById('id_kt_empty_modal_sm')
        if (emptyModalSM) {
            emptyModalSM.addEventListener('hidden.bs.modal', function (e) {
                document.querySelector('#id-empty-modal-body-sm').innerHTML = ''
            })
            emptyModalSM.addEventListener('shown.bs.modal', function (e) {
                setTimeout(get_translate, 1500)
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
    $.ajax({ // create an AJAX call...
        beforeSend: function (xhr){
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
            if (reload_){
                window.location.reload()
            }
        }
    });
}

function ajax_submit_with_file(form, reload_=null, elem_for_load=null) {
    $.ajax({
        beforeSend: function (xhr) {
            if (elem_for_load) {
                console.log('load...');
            }
            if (!$(form).find('input[name="csrfmiddlewaretoken"]').length) {
                const csrfToken = getCookie('csrftoken');
                xhr.setRequestHeader('X-CSRFToken', csrfToken);
            }
        },
        data: new FormData(form), // استفاده از FormData
        type: $(form).attr('method'), // GET یا POST
        url: $(form).attr('action'), // آدرس سرور
        processData: false, // غیرفعال کردن پردازش داده‌ها
        contentType: false, // تنظیم خودکار content type
        success: function (data) {
            if (reload_) {
                window.location.reload();
            }
        },
        error: function (error) {
            console.error("Error:", error);
        }
    });
}

function initializeDatepickers(elem_id=null) {
    console.log("======  initialize Datepickers  =====", elem_id)
    if(elem_id){
        elem_id.forEach(function (id){
            console.log(elem_id, $(`#${id}`))
            try {
                $(`#${id}`).datepicker({
                dateFormat: 'yy-mm-dd',
                changeMonth: true,
                changeYear: true,
                });
            } catch (e) {
                console.log(e)
            }
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
                          formatRepoDL=null, formatRepoSelection=null, afterSelect=null) {
    console.log('formatRepoDL', formatRepoDL)
    let select2_container_width;
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
            text: '' || placeholder
        },
        allowClear: false,
        templateResult: formatRepoDL || defaultFormatRepoDL,
        templateSelection: formatRepoSelection || defaultFormatRepoSelection
    });
    if (afterSelect){
        afterSelect(select2_element, target_element, id_field)
    } else {
        $(select2_element).on("select2:select", function (e) {
            debugger
            const data = e.params.data;
            const element_to_show = "select2-" + target_element.substring(1) + "_select2-container"
            $(document).find(target_element).val(data[id_field])
            document.querySelector(`[id*=${element_to_show}]`).querySelector('span').innerHTML = data.id + " " + data.text
        })
    }

    $(select2_element).on("select2:open", function (e){
         $('#id_kt_empty_modal_lg').css({
                'visibility': 'hidden',
                'pointer-events': 'none',
         });
        document.querySelector('.select2-search__field')?.focus();
        document.querySelector(`${select2_element}`).parentElement.classList.remove('col')
        const select2_container = document.querySelector('.select2-container--below')
        select2_container_width = select2_container.style.width
        select2_container.style.width = '100%'
    })

    $(select2_element).on("select2:close", function () {
        // Restore modal settings after closing select2
        $('#id_kt_empty_modal_lg').css({
            'opacity': '1',
            'visibility': 'visible',
            'pointer-events': 'auto'
        });
        document.querySelector('.select2-container--below').style.width = select2_container_width
        document.querySelector(`${select2_element}`).parentElement.classList.add('col')
    })
}

function defaultFormatRepoDL(repo) {
    if (repo.loading) {
        return repo.text;
    }
    var $container = $(`
        <div class='d-flex'>
        <span class="bg-light-success rounded px-1 me-3 text-primary">${repo.id}</span>
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
            debugger
            items.forEach(function(item, index) {
                item.querySelector(`[id*=${index_field_id_selector}]`).value = index
            });
            removeWindowHighlightSections()
        },
        onUpdate: function (evt) {
            debugger
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

        const submitGenericPaymentBtns = document.querySelectorAll('[id*="id_payment__"]')
    submitGenericPaymentBtns.forEach(function (item){
        item.addEventListener('click', function (e){
            e.preventDefault()
            let generic_payment_url = item.dataset.form_url;
            const pk = item.dataset.pk;
            const comment_type = item.dataset.comment_type
            const comment_input_id = generic_payment_url.replace('/', '_')
            const comment_form = document.getElementById(comment_input_id);
            const generic_payment_element = $('#id-empty-modal-body')
            // const commentFormForCopy = document.getElementById(`id_generic_payment_form_for_copy__${pk}`)
            const GenericPaymentFormGroup = document.querySelector(`[id*="generic-payment-form-group__${pk}"]`)
            const g_from_date = GenericPaymentFormGroup.querySelector('[id*="g_from_date"]')
            const g_to_date = GenericPaymentFormGroup.querySelector('[id*="g_to_date"]')
            const total_amount = GenericPaymentFormGroup.querySelector('[id*="total_amount"]')
            const description = GenericPaymentFormGroup.querySelector('[id*="description"]')
            const father = findAncestor(item, "symbol-group")
            const commentCounter = item.nextElementSibling
            if (father){
                const images = father.querySelectorAll('img')
                images.forEach(function (img){
                    img.classList.remove('border')
                    commentCounter.innerHTML = '0'
                })
            }

            if (g_from_date && g_to_date && total_amount) {generic_payment_url += `?g_from_date=${g_from_date.value}&g_to_date=${g_to_date.value}&total_amount=${total_amount.value}&description=${description.value}`}
            custom_ajax_get(comment_form, generic_payment_url, generic_payment_element)
        }) // end eventListener
    }) // end forEach
    function addGenericPaymentInput(){
        const pkElement = document.querySelector('[id*="payment_object_id__"]')
        const pk = pkElement.dataset.pk
        const ctt_id = pkElement.dataset.ctt_id

        const GenericPaymentFormGroup = document.querySelector(`[id*="generic-payment-form-group__${pk}"]`)
        const commentFormForCopy = document.getElementById(`id_generic_payment_form_for_copy__${pk}`)
        GenericPaymentFormGroup.innerHTML = ''
        GenericPaymentFormGroup.appendChild(commentFormForCopy)
    }

    function delete_with_modal(elem){
        const modal_sm_body = $('#id-empty-modal-body-sm')
        custom_ajax_get('', elem.dataset.url, modal_sm_body)
    }

    function edit_with_modal(elem){
        const modal_lg_body = $('#id-empty-modal-body-lg')
            $.ajax({
            type: 'GET',
            url: elem.dataset.url,
            dataType: 'json',
            cache: false,
            processData: false,
            contentType: false,
            beforeSend: block_main_container,
            success: function (data) {
                html = data['res'];
                modal_lg_body.html(html);
                initializeDatepickers(['id_g_from_date', 'id_g_to_date']);
            },
            error: function () {

            },
            complete: release_main_container
        }); //end ajax
    }

    function change_log_with_modal(elem){
        const modelName = elem.dataset.model_name
        const objectId = elem.dataset.object_id
        const appName = elem.dataset.app_name
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
                html = data['res'];
                document.querySelector('#id-empty-modal-body-lg').innerHTML = html
            },
            error: function () {

            },
            complete: release_main_container

        });
    }
    function diffTime(time_iso){
        let t1 = new Date();
        let t2 = new Date(time_iso);
        const isDateOnly = t2.getHours() === 0 && t2.getMinutes() === 0 && t2.getSeconds() === 0;
        if (isDateOnly){
            t1.setHours(0);
            t1.setMinutes(0);
            t1.setSeconds(0);
            t1.setMilliseconds(0);
        }
        let diffMilliseconds = t2 - t1;
        let diffDays = Math.floor(diffMilliseconds / (1000 * 60 * 60 * 24));
        let diffHours = Math.floor(diffMilliseconds / (1000 * 60 * 60));
        let diffMinuets = Math.floor(diffMilliseconds / (1000 * 60));

        return [diffDays, diffHours, diffMinuets]
    }

    function diffTimeInQuotation(time_iso){
        const [days, hours, minuets] = diffTime(time_iso)
        if (days < 0 || hours < 0 || minuets < 0){
            return {
                status: true,
                message: "اعتبار استعلام به پایان رسیده، این قیمت روی پیش فاکتور ذخیره نمیشود",
                css: "text-danger"
            }
        }
        else if(days >= 1){
            return {
                status: false,
                message: `معتبر تا ${ days } روز و ${ hours - (days*24) } ساعت دیگر`,
                css: ""
            }
        } else if (hours >= 1) {
            return {
                status: false,
                message: `معتبر تا ${hours} ساعت دیگر`,
                css: ""
            }
        } else {
            return {
                status: false,
                message: `معتبر تا ${minuets} دقیقه دیگر`,
                css: ""
            }
        }
    }



//========= حالت ذخیره اطلاعات وقتی روی دکمه های ذخیره کننده فرم میزنن برای جلوگیری از تکرار درخواست و حذف جداکننده هزارگان ===========
const global_action_btn = document.querySelector('#global-action-button')
const pleas_wait = document.querySelector('#id_pleas_wait')


const draft_btn = document.querySelector('#submit_draft')
const next_btn = document.querySelector('#submit_next')
const back_btn = document.querySelector('#submit_back')
const save_btn = document.querySelector('#submit_save')
const send_factor_to_sepidar_btn = document.querySelector('#send_factor_to_sepidar')

const main_form = document.querySelector('#main-form')

function show_global_action_btn(){
    global_action_btn.classList.remove('d-none')
    pleas_wait.classList.add('d-none')
}

send_factor_to_sepidar_btn && send_factor_to_sepidar_btn.addEventListener('click', function (){
    removeCommaSeperator()
    global_action_btn.classList.add('d-none')
    pleas_wait.classList.remove('d-none')
    pleas_wait.innerHTML = 'در حال ذخیره اطلاعات....'
    setTimeout(show_global_action_btn, 18000)
})

draft_btn && draft_btn.addEventListener('click', function (){
    if (main_form){
        if (main_form.checkValidity()){
            removeCommaSeperator()
            global_action_btn.classList.add('d-none')
            pleas_wait.classList.remove('d-none')
            pleas_wait.innerHTML = 'در حال ذخیره اطلاعات....'
            setTimeout(show_global_action_btn, 18000)
        } else {
            try {
                form.reportValidity()
            } catch (e) {
                main_form.reportValidity()
            }
        }
    } else {
        removeCommaSeperator()
        global_action_btn.classList.add('d-none')
        pleas_wait.classList.remove('d-none')
        pleas_wait.innerHTML = 'در حال ذخیره اطلاعات....'
        setTimeout(show_global_action_btn, 18000)
    }
})

next_btn && next_btn.addEventListener('click', function (){
    if (main_form){
        if (main_form.checkValidity()) {
            removeCommaSeperator()
            global_action_btn.classList.add('d-none')
            pleas_wait.classList.remove('d-none')
            pleas_wait.innerHTML = 'در حال ذخیره اطلاعات....'
            setTimeout(show_global_action_btn, 18000)
        } else {
            try {
                form.reportValidity()
            } catch (e) {
                main_form.reportValidity()
            }
        }
    } else {
        removeCommaSeperator()
        global_action_btn.classList.add('d-none')
        pleas_wait.classList.remove('d-none')
        pleas_wait.innerHTML = 'در حال ذخیره اطلاعات....'
        setTimeout(show_global_action_btn, 18000)
    }
})

save_btn && save_btn.addEventListener('click', function (){
    removeCommaSeperator()
    global_action_btn.classList.add('d-none')
    pleas_wait.classList.remove('d-none')
    pleas_wait.innerHTML = 'در حال ذخیره اطلاعات....'
    setTimeout(show_global_action_btn, 18000)
})

back_btn && back_btn.addEventListener('click', function (){
    if (main_form){
        if (main_form.checkValidity()) {
            removeCommaSeperator()
            global_action_btn.classList.add('d-none')
            pleas_wait.classList.remove('d-none')
            pleas_wait.innerHTML = 'در حال ذخیره اطلاعات....'
            setTimeout(show_global_action_btn, 18000)
        } else {
            try {
                form.reportValidity()
            } catch (e) {
                main_form.reportValidity()
            }
        }
    } else {
        removeCommaSeperator()
        global_action_btn.classList.add('d-none')
        pleas_wait.classList.remove('d-none')
        pleas_wait.innerHTML = 'در حال ذخیره اطلاعات....'
        setTimeout(show_global_action_btn, 18000)
    }
})

//=====================