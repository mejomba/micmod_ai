function get_translation_data(file_path){
    fetch("/assets/lang/" + file_path)
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log(data);
    })
    .catch(error => console.error('Error loading JSON:', error));

}

function translate_handler(){
    const translation_data = get_translation_data()
    const elements_for_translate = document.querySelectorAll('[data-key]')
    elements_for_translate && elements_for_translate.forEach(function (item){

    })
}

function get_translate(){
    const languages = document.querySelectorAll('[class="language"]')
    languages && languages.forEach(function (item){
        item.addEventListener('click', translate_handler, item.dataset.lang)
    })
}
document.addEventListener('DOMContentLoaded', function (e){
    get_translate()
})