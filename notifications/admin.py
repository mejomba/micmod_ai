from django.contrib import admin

from .models import Messages, Groups
from django.utils.html import mark_safe

admin.site.register([Messages,])


class AdminGroups(admin.ModelAdmin):
    list_display = ('group_id', "members_",)

    def members_(self, obj):
        return mark_safe(" - ".join([f'''<span style="background-color:#dfffff">{u.username}</span>''' for u in obj.members.all()]))


admin.site.register(Groups, AdminGroups)