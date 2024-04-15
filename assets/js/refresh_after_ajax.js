function replaceDigits() {
    const elements = document.querySelectorAll('.persian-digit')
    elements.forEach(function (item) {
        item.innerHTML = item.innerHTML.replaceAll("0", "۰").replaceAll('1', "۱").replaceAll('2', "۲").replaceAll('3', "۳").replaceAll('4', "۴").replaceAll('5', "۵").replaceAll('6', "۶").replaceAll('7', "۷").replaceAll('8', "۸").replaceAll('9', "۹");
    })
}

replaceDigits()

// for image galery

// Gallery image hover
$(".img-wrapper").hover(
    function () {
        $(this).find(".img-overlay").animate({opacity: 1}, 600);
    }, function () {
        $(this).find(".img-overlay").animate({opacity: 0}, 600);
    }
);

// Lightbox
var $overlay = $('<div id="overlay"></div>');
var $image = $("<img>");
var $prevButton = $('<div id="prevButton"><i class="fa fa-chevron-left fs-4x"></i></div>');
var $nextButton = $('<div id="nextButton"><i class="fa fa-chevron-right fs-4x"></i></div>');
var $exitButton = $('<div id="exitButton"><i class="fa fa-times fs-3x"></i></div>');

// Add overlay
$overlay.append($image).prepend($prevButton).append($nextButton).append($exitButton);
$("#gallery").append($overlay);

// Hide overlay on default
$overlay.hide();

// When an image is clicked
$(".img-overlay").click(function (event) {
    // Prevents default behavior
    event.preventDefault();
    // Adds href attribute to variable
    var imageLocation = $(this).prev().attr("href");
    // Add the image src to $image
    $image.attr("src", imageLocation);
    // Fade in the overlay
    $overlay.fadeIn("slow");
});

// When the overlay is clicked
$overlay.click(function () {
    // Fade out the overlay
    $(this).fadeOut("slow");
});

// When next button is clicked
$nextButton.click(function (event) {
    // Hide the current image
    $("#overlay img").hide();
    // Overlay image location
    const $currentImgSrc = $("#overlay img").attr("src");
    // Image with matching location of the overlay image
    const $currentImg = $('#image-gallery img[src="' + $currentImgSrc + '"]');
    // Finds the next image
    const $nextImg = $($currentImg.closest(".image").next().find("img"));
    // If there is a next image
    if ($nextImg.length > 0) {
        // Fade in the next image
        $("#overlay img").attr("src", $nextImg.attr("src")).fadeIn(400);
    } else {
        // All of the images in the gallery
        const $images = $currentImg.closest('#image-gallery').find("img") //$("#image-gallery img");
        // Otherwise fade in the first image
        $("#overlay img").attr("src", $($images[0]).attr("src")).fadeIn(400);
    }
    // Prevents overlay from being hidden
    event.stopPropagation();
});

// When previous button is clicked
$prevButton.click(function (event) {
    // Hide the current image
    $("#overlay img").hide();
    // Overlay image location
    const $currentImgSrc = $("#overlay img").attr("src");
    // Image with matching location of the overlay image
    const $currentImg = $('#image-gallery img[src="' + $currentImgSrc + '"]');
    // Finds the next image
    const $nextImg = $($currentImg.closest(".image").prev().find("img"));
    // Fade in the next image
    // If there is a next image
    if ($nextImg.length > 0) {
        // Fade in the next image
        $("#overlay img").attr("src", $nextImg.attr("src")).fadeIn(400);
    } else {
        // All of the images in the gallery
        const $images = $currentImg.closest('#image-gallery').find("img") //$("#image-gallery img");
        // Otherwise fade in the last image
        $("#overlay img").attr("src", $($images[$images.length - 1]).attr("src")).fadeIn(400);
    }
    // Prevents overlay from being hidden
    event.stopPropagation();
});

// When the exit button is clicked
$exitButton.click(function () {
    // Fade out the overlay
    $("#overlay").fadeOut("slow");
});