from django.contrib import admin
from .models import PaymentOrder, PaymentSource

admin.site.register([PaymentOrder, PaymentSource])
