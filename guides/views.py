from ajax_datatable import AjaxDatatableView
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import ListView

from guides.forms import GuidesForm
from translator import get_text as _

from core.views import BaseView, Base
from guides.models import Guides


# Create your views here.

class GuidesList(LoginRequiredMixin, BaseView):
    model = Guides
    template_name = 'guides/view.html'
    success_message = 'ذخیره شد'
    form_struct = {
        'form': GuidesForm,
        'childes': [
            {
                'form': '',
                'childes': [{}]
            },
        ]
    }

    def get_success_url(self):
        return reverse_lazy('guides:guides.view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class GuidesDatatableView(AjaxDatatableView):
    model = Guides
    title = 'guides'
    initial_order = [["id", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    def get_columns(self, fields):
        res = [AjaxDatatableView.render_row_tools_column_def()]
        for field in fields:
            col = dict()
            col['className'] = 'py-3'
            col['lookup_field'] = '__icontains'
            col['defaultContent'] = ''
            col['orderable'] = True
            col['searchable'] = True
            col['name'] = field if isinstance(field, str) else None
            col['visible'] = True
            if isinstance(field, dict):
                for key in field.keys():
                    col[key] = field[key]
            if not col.get('title'):
                col['title'] = _(col.get('name'))
            res.append(col)
        return res

    def get_column_defs(self, request):
        cols = [
            {'name': 'id', 'title': "<div class='px-3' style='max-width:20px;'>شناسه</div>", 'className': 'mxw-50px'},
            {'name': 'title', },
            {'name': 'description', 'title': "<div class='px-3' style='width:40px;'>توضیحات</div>",},
            {'name': 'file_1', 'title': "<div class='px-3' style='width:40px;'>فایل</div>", "searchable": False},
        ]

        return self.get_columns(cols)

    def customize_row(self, row, obj):
        x = super().customize_row(row, obj)
        row['title'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('guides:guides.update', args=(obj.id,)),
            obj.title if obj.title else '_'
        )
        row['file_1'] = ''
        for file in obj.files.all():
            row['file_1'] += '<a  target="_blank" href="%s" class ="me-1" ><i class ="fas fa-file-upload fs-2" ></i></a>' % (
                file.path.url,
            )

