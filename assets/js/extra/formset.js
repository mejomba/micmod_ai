window.addEventListener('load', (event) => {
    const textInput = document.querySelectorAll('.comma-seperator')
    textInput.forEach(function (item) {
        if (item.tagName === 'INPUT'){
            item.value = commaSeperator(item.value.toString().reverse_string()).reverse_string()
        } else {
            item.innerText = commaSeperator(item.innerText.toString().reverse_string()).reverse_string()
        }
    })
    // get form template and total number of forms from management form
    const templateForm = document.getElementById('id_formset_empty_form');
    const inputTotalForms = document.querySelector('input[id$="-TOTAL_FORMS"]');
    const inputInitialForms = document.querySelector('input[id$="-INITIAL_FORMS"]');

    // get our container (e.g. <table>, <ul>, or <div>) and "Add" button
    const containerFormSet = document.getElementById('id_formset_container');
    const buttonsAdd = document.querySelectorAll('[name="id_formset_add_button"]');
    // const buttonSubmit = document.querySelectorAll('[name="id_formset_submit_button"]');
    const buttonSubmit = document.querySelectorAll('input[type="submit"]');

    // event handlers
    for (let b in buttonsAdd) {
        buttonsAdd[b].onclick = addForm;
    }

    for (let b in buttonSubmit) {
        buttonSubmit[b].onclick = updateNameAttributes;
    }

    // form counters (note: proper form index bookkeeping is necessary
    // because django's formset will create empty forms for any missing
    // indices, and will discard forms with indices >= TOTAL_FORMS, which can
    // lead to funny behavior in some edge cases)
    let nextFormIndex
    if (inputTotalForms) {
        nextFormIndex = Number(inputTotalForms.value)
    }

    if (inputTotalForms){const initialForms = Number(inputTotalForms.value);}
    let extraFormIndices = [];

    function addForm(headerData) {
        // create DocumentFragment from template
        const formFragment = templateForm.content.cloneNode(true);
        // a django form is rendered as_table (default), as_ul, or as_p, so
        // the fragment will contain one or more <tr>, <li>, or <p> elements,
        // respectively.
        let elementInnerHtml
        for (let element of formFragment.children) {
            // replace the __prefix__ placeholders from the empty form by the
            // actual form index
            //  elementInnerHtml = element.innerHTML
            elementInnerHtml = element.innerHTML.replace(
                /(?<=\w+-)(0)(?=-\w+)/g,
                '__prefix__');
             elementInnerHtml = elementInnerHtml.replace(
                /(?<=\w+_)(rel-__prefix__)(?=-\w+)/g,
                'rel-0');
            elementInnerHtml = elementInnerHtml.replace(
                /(?<=\w+-)(__prefix__)(?=-\w+)/g,
                nextFormIndex.toString());
            element.innerHTML = elementInnerHtml
            // /(?<=\w+-)(__prefix__|\d+)(?=-\w+)/g,

            // qir-quotation-2-quotation_item_rel-0-quotation_item
            const qi = element.querySelector("[name$='-quotation_item']")
            const initialForms = element.querySelector("[name$='INITIAL_FORMS']")
            const totalForms = element.querySelector("[name$='TOTAL_FORMS']")
            if (qi){
                qi.value = null
            }
            if (totalForms){
                totalForms.value = 1
            }
            if (initialForms){
                initialForms.value = 0
            }
            element.dataset.formIndex = nextFormIndex.toString();
            // add a delete click handler (if formset can_delete)
            // setDeleteHandler(element);
        }
        // move the fragment's children onto the DOM
        // (the fragment is empty afterwards)
        containerFormSet.appendChild(formFragment);
        const items = $(containerFormSet).find(".item")
        set_item_classes(items[items.length - 1])
        // set_item_classes(formFragment)
        // keep track of form indices
        extraFormIndices.push(nextFormIndex++);
        // observer.disconnect();
        items[items.length - 1].querySelector('div.row-counter .counter').innerHTML = nextFormIndex;
        if (nextFormIndex % 2 === 0) {
            items[items.length - 1].parentElement.parentElement.classList.add('bg-soft-light')
        } else {
            items[items.length - 1].parentElement.parentElement.classList.add('bg-white')
        }
        // fix changelog for quotations =========
        const ch = items[items.length - 1].querySelector('.changelog-btn');
        const md = items[items.length - 1].querySelector('.modal');
        const cl = items[items.length - 1].querySelector('.close-modal');
        if (ch && md){
            ch.dataset.target = `#id_x${nextFormIndex}`;
            md.id = `id_x${nextFormIndex}`;
            cl.id = `id_x${nextFormIndex}`;
        }
        // ==================

        const newFormset = items[items.length - 1].querySelector('.question-btn');
        if (newFormset){
            newFormset.addEventListener('click', function(e) {
            const answer = items[items.length - 1].querySelector('.answer');
            answer.classList.toggle('close')
            if (answer && answer.offsetHeight > 0) {
                // answer.style.height = 0;
                // answer.style.overflow = 'hidden';
                answer.previousElementSibling.classList.remove('active-form')
                setFormsetHeader(e.currentTarget, answer, {
                    'code_h': ['class', 'select2-selection__rendered', 'lbl'],
                    'name_h': ['name', '-goods_name_lbl', 'lbl'],
                    'quantity_h': ['name', 'quotation-idx-quantity', 'input'],
                    'unit-price_h': ['name', 'quotation-idx-final_price', 'input'],
                    'total-price_h': ['name', '-total_price', 'lbl']
                }, parseInt(newFormset.querySelector('.counter').innerHTML)-1)
                showQuotationFormsetHeader(answer)
            } else if (answer){
                answer.previousElementSibling.classList.add('active-form')
                hideQuotationFormsetHeader(answer)
            }
           }) // end listener
        }// end if
        addCommaSeperator()
    }

    function removeForm(event) {
        // remove all elements with form-index matching that of the delete-input
        const formIndex = event.target.dataset.formIndex;
        for (let element of getFormElements(formIndex)) {
            element.remove();
        }
        // remove form index from array
        let indexIndex = extraFormIndices.indexOf(Number(formIndex));
        if (indexIndex > -1) {
            extraFormIndices.splice(indexIndex, 1);
        }
    }

    function setDeleteHandler(containerElement) {
        // modify DELETE checkbox in containerElement, if the checkbox exists
        // (these checboxes are added by formset if can_delete)
        const inputDelete = containerElement.querySelector('input[id$="-DELETE"]');
        if (inputDelete) {
            // duplicate the form index instead of relying on parentElement (more robust)
            inputDelete.dataset.formIndex = containerElement.dataset.formIndex;
            inputDelete.onclick = removeForm;
        }
    }

    function getFormElements(index) {
        // the data-form-index attribute is available as dataset.formIndex
        // https://developer.mozilla.org/en-US/docs/Learn/HTML/Howto/Use_data_attributes#javascript_access
        return containerFormSet.querySelectorAll('[data-form-index="' + index + '"]');
    }

    function updateNameAttributes(event) {
        // make sure the name indices are consecutive and smaller than
        // TOTAL_FORMS (the name attributes end up as dict keys on the server)
        // note we do not need to update the indices in the id attributes etc.
        // for (let [consecutiveIndex, formIndex] of extraFormIndices.entries()) {
        //     for (let formElement of getFormElements(formIndex)) {
        //         for (let element of formElement.querySelectorAll('input, select')) {
        //             if ('name' in element) {
        //                 element.name = element.name.replace(
        //                     /(?<=\w+-)(__prefix__|\d+)(?=-\w+)/g,
        //                     (initialForms + consecutiveIndex).toString());
        //             }
        //         }
        //     }
        // }
        updateTotalFormCount();
        removeCommaSeperator()
    }

    function updateTotalFormCount(event) {
        // note we could simply do initialForms + extraFormIndices.length
        // to get the total form count, but that does not work if we have
        // validation errors on forms that were added dynamically
        let firstElement;
        if (templateForm){
            firstElement = templateForm.content.querySelector('input, select');
        }
        // select the first input or select element, then count how many ids
        // with the same suffix occur in the formset container
        if (firstElement) {
            let suffix = firstElement.id.split('__prefix__')[1];
            let selector = firstElement.tagName.toLowerCase() + '[id$="' + suffix + '"]';
            let allElementsForId = containerFormSet.querySelectorAll(selector);
            // update total form count
            inputTotalForms.value = allElementsForId.length;
        }
    }
}, false);




let items, openAll, closeAll;
items = document.querySelectorAll('.question-btn');
openAll = document.querySelector('button[name="open-all"]');
closeAll = document.querySelector('button[name="close-all"]');

items.forEach(function(item, idx) {
    // item.onclick = collapseFormset
  item.addEventListener('click', function(e) {
  const answer = e.currentTarget.nextElementSibling;
  answer.classList.toggle('close')
  if (answer.offsetHeight > 0) {
      answer.previousElementSibling.classList.remove('active-form')
      setFormsetHeader(e.currentTarget, answer, {
                    'code_h': ['class', 'select2-selection__rendered', 'lbl'],
                    'name_h': ['name', '-goods_name_lbl', 'lbl'],
                    'quantity_h': ['name', 'quotation-idx-quantity', 'input'],
                    'unit-price_h': ['name', 'quotation-idx-final_price', 'input'],
                    'total-price_h': ['name', '-total_price', 'lbl']
                }, idx)
      showQuotationFormsetHeader(answer)
  } else {
      answer.previousElementSibling.classList.add('active-form')
      hideQuotationFormsetHeader(answer)
  }
 })
}) // forEach

if (openAll) {
    openAll.addEventListener('click', function (e) {
        items = document.querySelectorAll('.question-btn');
        items.forEach(function (j) {
            j.classList.add('active-form')
            const answer = j.nextElementSibling;
            answer.classList.remove('close')
            hideQuotationFormsetHeader(answer)
        })
    }) // addEventListener
}
function closeAllFormset(headerData){
    if (closeAll) {
        closeAll.addEventListener('click', function (e) {
            items = document.querySelectorAll('.question-btn');
            items.forEach(function (k, idx) {
                k.classList.remove('active-form')
                const answer = k.nextElementSibling;
                answer.classList.add('close')
                setFormsetHeader(k, answer, headerData, idx)
                showQuotationFormsetHeader(answer)
            })
        }) // addEventListener
    }
}
function setFormsetHeader(header, body, headerData, idx){
    for(const [x, y] of Object.entries(headerData)){
        if (y[0] === 'class' && y[2] === 'lbl') {
            header.querySelector(`[class*=${x}]`).innerHTML = body.querySelector(`[class*=${y[1].replace('idx', idx.toString())}]`).innerHTML;
        }else if (y[0] === 'class' && y[2] === 'input'){
            header.querySelector(`[class=${x}]`).innerHTML = body.querySelector(`[class*=${y[1].replace('idx', idx.toString())}]`).value;
        }else if (y[0] === 'name' && y[2] === 'lbl'){
            header.querySelector(`[name=${x}]`).innerHTML = body.querySelector(`[name*=${y[1].replace('idx', idx.toString())}]`).innerHTML;
        }else if (y[0] === 'name' && y[2] === 'input'){
            header.querySelector(`[name=${x}]`).innerHTML = body.querySelector(`[name*=${y[1].replace('idx', idx.toString())}]`).value;
        }
    }
}
function hideQuotationFormsetHeader(el){
    el.previousElementSibling.classList.remove('py-2');
    el.previousElementSibling.querySelectorAll('.col').forEach(function (item){
        item.classList.add('d-none')
    })
}
function showQuotationFormsetHeader(el){
    el.previousElementSibling.classList.add('py-2');
    el.previousElementSibling.querySelectorAll('.col').forEach(function (item){
        item.classList.remove('d-none')
        item.style.display = 'block'
    })
}