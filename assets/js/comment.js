    const submitCommentBtns = document.querySelectorAll('[id*="id_comment__"]')
    submitCommentBtns.forEach(function (item){
        item.addEventListener('click', function (e){
            e.preventDefault()
            let comment_url = item.dataset.form_url;
            const pk = item.dataset.pk;
            const comment_type = item.dataset.comment_type
            const comment_input_id = comment_url.replace('/', '_')
            const comment_form = document.getElementById(comment_input_id);
            const comment_element = $('#id-empty-modal-body')
            const commentFormForCopy = document.getElementById(`id_comment_form_for_copy__${pk}`)
            const commentFormGroup = document.querySelector(`[id*="comment-form-group__${pk}"]`)
            const title = commentFormGroup.querySelector('[id*="title"]')
            const content = commentFormGroup.querySelector('[id*="content"]')
            const father = findAncestor(item, "symbol-group")
            const commentCounter = item.nextElementSibling
            if (father){
                const images = father.querySelectorAll('img')
                images.forEach(function (img){
                    img.classList.remove('border')
                    commentCounter.innerHTML = '0'
                })
            }
            if (title && content) {comment_url += `?comment_title=${title.options[title.selectedIndex].value}&comment_content=${content.value}&comment_type=${comment_type}`} else {comment_url += `?comment_type=${comment_type}`}
            custom_ajax_get(comment_form, comment_url, comment_element)
        }) // end eventListener
    }) // end forEach

    function addCommentInput(){
        const pkElement = document.querySelector('[id*="object_id__"]')
        const pk = pkElement.dataset.pk
        const ctt_id = pkElement.dataset.ctt_id

        const commentFormGroup = document.querySelector(`[id*="comment-form-group__${pk}"]`)
        const commentFormForCopy = document.getElementById(`id_comment_form_for_copy__${pk}`)
        commentFormGroup.innerHTML = ''
        commentFormGroup.appendChild(commentFormForCopy)
        alert('addCommentInput')
    }