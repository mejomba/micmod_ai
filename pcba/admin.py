from django.contrib import admin

from .models import Expert


@admin.register(Expert)
class ExpertAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'name')
    search_fields = ('name', 'user__username')
    list_filter = ('user',)
