from ajax_datatable import AjaxDatatableView
from django.template import loader
from django.template.exceptions import TemplateDoesNotExist


class CustomAjaxDatatableView(AjaxDatatableView):

    def render_row_details(self, pk, request=None):

        # we do some optimization on the request
        relateds = []
        if not self.disable_queryset_optimization_only and not self.disable_queryset_optimization_select_related:
            relateds = [f.name for f in self.model._meta.get_fields() if f.many_to_one and f.concrete]

        prefetchs = []
        if not self.disable_queryset_optimization_only and not self.disable_queryset_optimization_prefetch_related:
            prefetchs = [f.name for f in self.model._meta.get_fields() if f.many_to_many and f.concrete]

        obj = self.model.objects.filter(pk=pk).select_related(*relateds).prefetch_related(*prefetchs).first()

        # Extract "extra_data" from request
        extra_data = {k: v for k, v in request.GET.items() if k not in ['action', 'pk', ]}

        # Search a custom template for rendering, if available
        try:
            template = loader.select_template([
                'ajax_datatable/%s/%s/%s' % (self.model._meta.app_label,
                                             self.model._meta.model_name, self.get_render_row_details_template_name(request)),
                'ajax_datatable/%s/%s' % (self.model._meta.app_label, self.get_render_row_details_template_name(request)),
                'ajax_datatable/%s' % (self.get_render_row_details_template_name(request), ),
            ])
            html = template.render({
                'model': self.model,
                'model_admin': self.get_model_admin(),
                'object': obj,
                'extra_data': extra_data,
            }, request)

        # Failing that, display a simple table with field values
        except TemplateDoesNotExist:
            fields = [f.name for f in self.model._meta.get_fields() if f.concrete]
            html = '<table class="row-details">'
            for field in fields:
                if field in prefetchs:
                    value = ', '.join([str(x) for x in eval(f'obj.{field}').all()])
                else:
                    try:
                        value = getattr(obj, field)
                    except AttributeError:
                        continue
                html += '<tr><td>%s</td><td>%s</td></tr>' % (field, value)
            html += '</table>'
        return html

    def get_render_row_details_template_name(self, request, *args, **kwargs):
        return self.render_row_details_template_name
