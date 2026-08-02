async function get_translation_data(file_path){
    debugger
    try {
        const response = await fetch('/assets/lang/' + file_path + '.json');

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const data = await response.json();
        return data;

    } catch (error) {
        console.error('Error loading JSON:', error);
        return null; // در صورت خطا مقدار `null` برمی‌گردد
    }

}

function translate_handler(lang){
    debugger
    const elements_for_translate = document.querySelectorAll('[data-key]')
    get_translation_data(lang).then(data => {
        elements_for_translate && elements_for_translate.forEach(function (item){
            debugger
            if (item.dataset.key in data){
                item.innerText = data[item.dataset.key]
            } else {
                item.innerText = item.dataset.key
                console.log(item.dataset.key , 'not found in', lang, 'translation file')
            }
            // try {
            //     item.innerText = data[item.dataset.key]
            // } catch (e) {
            //     console.log(e)
            //     item.innerText = item.dataset.key
            // }
        })
    }).catch(error => console.error('Error:', error));
}

function get_translate(){
    const languages = document.querySelectorAll('[class$="language"]')
    languages && languages.forEach(function (item){
        item.addEventListener('click', () => translate_handler(item.dataset.lang))
        console.log(item.dataset.lang)
    })

    const current_lang = localStorage.getItem('Dason-language')
    current_lang && translate_handler(current_lang)
}
try {
!function (n) {
    "use strict";
    var e, t, a, o = localStorage.getItem("Dason-language"), r = "en";

    function d(t) {
        document.getElementById("header-lang-img") && ("fa" == t ? document.getElementById("header-lang-img").src = "/assets/media/flags/iran.jpg" : "en" == t ? document.getElementById("header-lang-img").src = "/assets/media/flags/us.jpg" : "sp" == t ? document.getElementById("header-lang-img").src = "/assets/media/flags/spain.jpg" : "gr" == t ? document.getElementById("header-lang-img").src = "/assets/media/flags/germany.jpg" : "it" == t ? document.getElementById("header-lang-img").src = "/assets/media/flags/italy.jpg" : "ru" == t && (document.getElementById("header-lang-img").src = "/assets/media/flags/russia.jpg"), localStorage.setItem("Dason-language", t), null == (o = localStorage.getItem("Dason-language")) && d(r), n.getJSON("/assets/lang/" + o + ".json", function (t) {
            n("html").attr("lang", o), n.each(t, function (t, e) {
                "head" === t && n(document).attr("title", e.title), n("[data-key='" + t + "']").text(e)
            })
        }))
    }

    function i() {
        var t = document.querySelectorAll(".counter-value");
        t.forEach(function (o) {
            !function t() {
                var e = +o.getAttribute("data-target"), a = +o.innerText, n = e / 250;
                n < 1 && (n = 1), a < e ? (o.innerText = (a + n).toFixed(0), setTimeout(t, 1)) : o.innerText = e
            }()
        })
    }

    function l() {
        for (var t = document.getElementById("topnav-menu-content").getElementsByTagName("a"), e = 0, a = t.length; e < a; e++) t[e] && t[e].parentElement && "nav-item dropdown active" === t[e].parentElement.getAttribute("class") && (t[e].parentElement.classList.remove("active"), t[e].nextElementSibling && t[e].nextElementSibling.classList.remove("show"))
    }

    function s(t) {
        null !== t && (document.getElementById(t).checked = !0)
    }

    function c() {
        document.webkitIsFullScreen || document.mozFullScreen || document.msFullscreenElement || n("body").removeClass("fullscreen-enable")
    }

    window.sessionStorage && ((t = sessionStorage.getItem("is_visited")) ? n("#" + t).prop("checked", !0) : sessionStorage.setItem("is_visited", "layout-ltr")), n("#password-addon").on("click", function () {
        0 < n(this).siblings("input").length && ("password" == n(this).siblings("input").attr("type") ? n(this).siblings("input").attr("type", "input") : n(this).siblings("input").attr("type", "password"))
    }), o && "null" != o && o !== r && d(o), n(".language").on("click", function (t) {
        d(n(this).attr("data-lang"))
    }), feather.replace(), n(window).on("load", function () {
        n("#status").fadeOut(), n("#preloader").delay(350).fadeOut("slow")
    }), a = document.getElementsByTagName("body")[0], n(".right-bar-toggle").on("click", function (t) {
        n("body").toggleClass("right-bar-enabled")
    }), n("#mode-setting-btn").on("click", function (t) {
        a.hasAttribute("data-layout-mode") && "dark" == a.getAttribute("data-layout-mode") ? ("dark" == localStorage.getItem("data-sidebar") && "horizontal" !== a.getAttribute("data-layout") && document.body.setAttribute("data-sidebar", "dark"), "dark" == localStorage.getItem("data-topbar") && "horizontal" !== a.getAttribute("data-layout") && (document.body.setAttribute("data-sidebar", "light"), document.body.setAttribute("data-topbar", "dark")), document.body.setAttribute("data-layout-mode", "light"), "dark" !== localStorage.getItem("data-topbar") && (document.body.setAttribute("data-topbar", "light"), s("topbar-color-light")), "brand" == localStorage.getItem("data-sidebar") && document.body.setAttribute("data-sidebar", "brand"), localStorage.getItem("data-sidebar") || localStorage.getItem("data-topbar") || document.body.removeAttribute("data-sidebar")) : ("dark" == localStorage.getItem("data-sidebar") && document.body.setAttribute("data-sidebar", "dark"), document.body.setAttribute("data-layout-mode", "dark"), document.body.setAttribute("data-topbar", "dark"), document.body.setAttribute("data-sidebar", "dark"))
    }), n(document).on("click", "body", function (t) {
        0 < n(t.target).closest(".right-bar-toggle, .right-bar").length || n("body").removeClass("right-bar-enabled")
    }), a.hasAttribute("data-layout") && "horizontal" == a.getAttribute("data-layout") ? (s("layout-horizontal"), n(".sidebar-setting").hide()) : s("layout-vertical"), a.hasAttribute("data-layout-mode") && "dark" == a.getAttribute("data-layout-mode") ? s("layout-mode-dark") : s("layout-mode-light"), a.hasAttribute("data-layout-size") && "boxed" == a.getAttribute("data-layout-size") ? s("layout-width-boxed") : s("layout-width-fuild"), a.hasAttribute("data-layout-scrollable") && "true" == a.getAttribute("data-layout-scrollable") ? s("layout-position-scrollable") : s("layout-position-fixed"), "light" != a.getAttribute("data-topbar") && "dark" == a.getAttribute("data-topbar") ? s("topbar-color-dark") : s("topbar-color-light"), a.hasAttribute("data-sidebar-size") && "sm" == a.getAttribute("data-sidebar-size") ? s("sidebar-size-small") : a.hasAttribute("data-sidebar-size") && "md" == a.getAttribute("data-sidebar-size") ? s("sidebar-size-compact") : s("sidebar-size-default"), a.hasAttribute("data-sidebar") && "brand" == a.getAttribute("data-sidebar") ? s("sidebar-color-brand") : a.hasAttribute("data-sidebar") && "dark" == a.getAttribute("data-sidebar") ? s("sidebar-color-dark") : s("sidebar-color-light"), document.getElementsByTagName("html")[0].hasAttribute("dir") && "rtl" == document.getElementsByTagName("html")[0].getAttribute("dir") ? s("layout-direction-rtl") : s("layout-direction-ltr"), n("input[name='layout']").on("change", function () {
        window.location.href = "vertical" == n(this).val() ? "/" : "/pages/layout/horizontal"
    }), n("input[name='layout-mode']").on("change", function () {
        "light" == n(this).val() ? (document.body.setAttribute("data-layout-mode", "light"), document.body.setAttribute("data-topbar", "light"), document.body.setAttribute("data-sidebar", "light"), a.hasAttribute("data-layout") && "horizontal" == a.getAttribute("data-layout") || document.body.setAttribute("data-sidebar", "light"), s("topbar-color-light"), s("sidebar-color-light")) : (document.body.setAttribute("data-layout-mode", "dark"), document.body.setAttribute("data-topbar", "dark"), document.body.setAttribute("data-sidebar", "dark"), a.hasAttribute("data-layout") && "horizontal" == a.getAttribute("data-layout") || document.body.setAttribute("data-sidebar", "dark"), s("sidebar-color-dark"))
    }), n("input[name='layout-direction']").on("change", function () {
        "ltr" == n(this).val() ? (document.getElementsByTagName("html")[0].removeAttribute("dir"), document.getElementById("bootstrap-style").setAttribute("href", "/assets/css/bootstrap.min.css"), document.getElementById("app-style").setAttribute("href", "/assets/css/app.min.css")) : (document.getElementById("bootstrap-style").setAttribute("href", "/assets/css/bootstrap-rtl.min.css"), document.getElementById("app-style").setAttribute("href", "/assets/css/app-rtl.min.css"), document.getElementsByTagName("html")[0].setAttribute("dir", "rtl"))
    }), Waves.init(), n("#checkAll").on("change", function () {
        n(".table-check .form-check-input").prop("checked", n(this).prop("checked"))
    }), n(".table-check .form-check-input").change(function () {
        n(".table-check .form-check-input:checked").length == n(".table-check .form-check-input").length ? n("#checkAll").prop("checked", !0) : n("#checkAll").prop("checked", !1)
    })
}(jQuery);
var user_login = document.getElementById("login-msg"), toastTrigger = document.getElementById("borderedToast1Btn"),
    toastLive = document.getElementById("borderedToast1");
user_login && (toastTrigger.addEventListener("click", function () {
    new bootstrap.Toast(toastLive).show()
}), toastTrigger.click());

} catch (e) {
    console.log(e)
}
document.addEventListener('DOMContentLoaded', function (e){
    get_translate()
})
