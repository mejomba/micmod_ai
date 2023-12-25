from django.contrib import admin

from .models import WorkFlow, FlowAdminGroup

admin.site.register(WorkFlow)
# admin.site.register(WorkFlowAction)


class FlowAdminGroupAdmin(admin.ModelAdmin):
    list_display = ['group_name', 'group_rel', 'groups_child']

    # @staticmethod
    # def this_group_admin(obj):
    #     return " | ".join([u.username for u in obj.user_rel.all()])

    @staticmethod
    def groups_child(obj):
        return " | ".join([g.name for g in obj.group_child.all()])


admin.site.register(FlowAdminGroup, FlowAdminGroupAdmin)
