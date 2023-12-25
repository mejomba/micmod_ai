from django.contrib import admin

from .forms import IMEIListRegFrm
from .models import (IMEIListReg,
                     IMEIListRegDetail,
                     IMEINTSWReg,
                     IMEINTSWRegDetail,
                     IMEISaleReg,
                     IMEISaleRegDetail,
                     IMEIErrReg
                     )
from django.db.utils import IntegrityError

from tools import utils


admin.site.register([
    IMEIListRegDetail, IMEINTSWReg,
                     IMEINTSWRegDetail,
                     IMEISaleReg,
                     IMEISaleRegDetail,
                     IMEIErrReg
])


class IMEIListRegAdmin(admin.ModelAdmin):
    form = IMEIListRegFrm

    # fieldsets = (
    #     (None, {
    #         'fields': ('name', 'description', 'extra_field',),
    #     }),
    # )
    # def save_model(self, request, obj, form, change):
    #     print('save model')
    #     action = request._post.get('action')
    #     file = request._files.get('source_file')
    #     IMEIListRegDetail.create_from_excel(file, action)
    #     super().save_model(request, obj, form, change)


admin.site.register(IMEIListReg, IMEIListRegAdmin)