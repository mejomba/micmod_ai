const leftArrow = document.querySelectorAll(".left");
const rightArrow = document.querySelectorAll(".right");

const sliderCardContainer = document.querySelectorAll('.slider-card-container');
const mobileSlider = document.querySelectorAll('.mobile-slider');

const diff = 250;

let moving = false;
let transform = 0;
let transformValue = 0;


sliderCardContainer.forEach(function (item, idx){
    rightArrow[idx].addEventListener('click', function () {
    transform = window.getComputedStyle(item)
   .getPropertyValue('transform') !== 'none'
   ? window.getComputedStyle(item)
   .getPropertyValue('transform').split(',')[4].trim() : 0;

        if (transformValue < -(sliderCardContainer[idx].offsetWidth - mobileSlider[idx].offsetWidth)){
            transformValue = -(sliderCardContainer[idx].offsetWidth - mobileSlider[idx].offsetWidth);
        }else if (transformValue > 0){
            transformValue = 0;
        }else {
            transformValue -= diff;
        }
        item.style.transform = `translateX(${transformValue}px)`;
    })

    leftArrow[idx].addEventListener('click', function (e) {
        transform = window.getComputedStyle(item)
       .getPropertyValue('transform') !== 'none'
       ? window.getComputedStyle(item)
       .getPropertyValue('transform').split(',')[4].trim() : 0;

        if (transformValue < 0){
            transformValue += diff;
        }else {
            transformValue = 0;
        }

        item.style.transform = `translateX(${transformValue}px)`;
        // console.log('click right: ', item.style.transform)
    })
}) // end forEach

// remove single image process
const removeBtns = document.querySelectorAll('.content-remove-btn')
removeBtns.forEach(function (removeBtn){
    removeBtn.addEventListener('click', function (e){
        e.preventDefault();
        let imageId = removeBtn.getAttribute('data-id')
        let imageArea = document.getElementById(`slider-card-inner-${imageId}`)
        let imageAreaWidth = imageArea.getBoundingClientRect().width
        let imageAreaHeight = imageArea.getBoundingClientRect().height
        console.log(imageArea.getBoundingClientRect())
        let url = ''
        if (removeBtn.className.includes('image')){
            url = `/files/image/delete/single/${imageId}/`;
        } else if (removeBtn.className.includes('file')){
            url = `/files/file/delete/single/${imageId}/`;
        }

        $.ajax({
            url: url,
            type: 'POST',
            dataType: 'json',
            headers: { "X-CSRFToken": getCookie('csrftoken') },
            cache: false,
            processData: false,
            contentType: false,
            success: function (data) {
                imageArea.style.width = `${imageAreaWidth}px`;
                imageArea.style.height = `${imageAreaHeight}px`;
                imageArea.classList.add('d-flex', 'justify-content-center', 'align-items-center')
                imageArea.innerText = 'حذف شد'
                imageArea.classList.add('badge')
                imageArea.classList.add('badge-soft-danger')
            },
            error: function (rs, e){
                console.log('error.... ', rs)
            }
        })// end ajax
    }) // end addEventListener
}) // end forEach


var modal = document.getElementById("myModal");
var img = document.querySelectorAll(".gallery_image");
var modalImg = document.getElementById("img01");
var closeImage = document.getElementById("close-image");
img.forEach(function (item){
    item.onclick = function(){
        modal.style.display = "block";
        modalImg.src = this.src;
    }
})

closeImage.onclick = function() {
  modal.style.display = "none";
}
