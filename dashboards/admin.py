from django.contrib import admin
from .models import BIReport


class BiReport(admin.ModelAdmin):
    filter_horizontal = ('user_list', )

# admin.site.register([BIReport])
admin.site.register(BIReport, BiReport)