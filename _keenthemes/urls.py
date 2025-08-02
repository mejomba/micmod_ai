"""_keenthemes URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path, re_path
from django.conf import settings
from _keenthemes.views import SystemView
from . import views
from django.conf.urls.static import static

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path('admin/jsi18n/', admin.site.i18n_javascript, name='admin:jsi18n'),
    # YOUR PATTERNS
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Optional UI:
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    path('admin/', admin.site.urls),

    # Dashboard urls
    path('', include('dashboards.urls')),

    # Auth urls
    path('', include('auth.urls')),

    path("settings", views.Settings.as_view(), name="settings"),
    # Custum change password done page redirect
    path(
        "account/password/change/",
        login_required(views.MyPasswordChangeView.as_view()),
        name="account_change_password",
    ),
    # Custum set password done page redirect
    path(
        "account/password/set/",
        login_required(views.MyPasswordSetView.as_view()),
        name="account_set_password",
    ),
    # Apps
    path("apps/", include("apps.urls")),
    path("tlg/", include("tlg.urls")),
    # Apps
    path("dw/", include("dw.urls"), name="dw"),
    path("core/", include("core.urls"), name="core"),
    path("micmod_base/", include("micmod_base.urls"), name="micmod_base"),
    path("sepidar/", include("sepidar.urls"), name="sepidar"),
    path("imei/", include("IMEI.urls"), name="IMEI"),
    path("inquiry/", include("inquiry.urls"), name="inquiry"),
    path("inventory/", include("inventory.urls"), name='inventory'),
    path("files/", include("files.urls"), name='fiels'),
    path("extra_data/", include("extra_data.urls"), name='extra_data'),
    path("changelog/", include("changelog.urls"), name='changelog'),
    path("notifications/", include("notifications.urls"), name='notifications'),
    # Components
    #path("components/", include("components.urls")),
    # Pages
    # path("pages/", include("pages.urls")),
    # Include the allauth and 2FA urls from their respective packages.
    path("/", include("allauth_2fa.urls")),
    path("account/", include("allauth.urls")),

    # select 2
    path("select2/", include("django_select2.urls")),
    path('accounts/', include('accounts.urls')),
    path('comments/', include('comments.urls')),

    path('api/', include('api.urls')),
    path('dashboards/', include('dashboards.urls')),
    path('payment/', include('payment.urls')),
    path('factor/', include('factor.urls')),
    path('pcba/', include('pcba.urls')),
    path('order/', include('order.urls')),
    path('transportation/', include('transportation.urls')),
    path('guides/', include('guides.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler404 = SystemView.as_view(template_name = 'pages/system/not-found.html', status=404)
handler500 = SystemView.as_view(template_name = 'pages/system/error.html', status=500)
