from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from jalali_date import datetime2jalali

from comments.forms import CommentsForm
from core.views import BaseView, Base
from extra_data.models import Customer
from factor.forms import FactorModelForm, FactorItemFormset
from factor.models import Factor
from micmod_base.models import Quotation
from tools.import_data import import_customers_from_sepidar


class FactorView(LoginRequiredMixin, BaseView):
    template_name = 'factor/factor.html'
    form_class = FactorModelForm
    model = Factor
    wf_last_step_is_open = True
    has_flow = True
    form_struct = {
        'form': FactorModelForm,
        'childes': [
            {
                'form': FactorItemFormset,
                'childes': [{}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'QuotationsView')

    # has_formset = True
    # formset_form = QuotationItemForm2
    # formset_model = QuotationItem
    formset_fk_field = 'quotation'
    related_name_fk = 'quotation'

    def get_success_url(self):
        return reverse_lazy('micmod_base:quotations.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        if self.object is None:
            pass
            # import_customers_from_sepidar(extra_data={"creator_user_id": 1, "editor_user_id": 1})
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        # if 'submit_duplicate' in self.request.POST:
        #     return self.duplicate(self.object, [], ['quotation'])
        """ run import customer from sepidar before object create"""
        if self.object is None:
            pass
            # import_customers_from_sepidar(extra_data={"creator_user_id": 1, "editor_user_id": 1})

        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context
        context['heading'] = _('create')
        context['pageview'] = _('quotation')
        user_groups = self.request.user.groups.values_list('name', flat=True)
        if self.object:
            self.object.created_date = datetime2jalali(self.object.created_date).strftime('%y/%m/%d-%H:%M')
            self.object.last_update_date = datetime2jalali(self.object.last_update_date).strftime('%y/%m/%d-%H:%M')
        context['data'] = self.object
        context['app_name'] = self.request.resolver_match.app_name

        related_obj = getattr(self.object, f'{self.related_name_fk}', None)
        # context['detail_logs'] = []
        # if related_obj:
        #     for item in related_obj.all():
        #         context['detail_logs'].append(item.change_logs.all())
        # context['detail_logs'].reverse()
        if self.object:
            qis = self.object.quotation.all()
            counter = 0
            for qi in qis:
                if (self.state_index == 1 or self.state_index == 1) and (bool(qi.local_price_inquiry_done) != bool(qi.need_local_price_inquiry) or \
                        bool(qi.foreign_price_inquiry_done) != bool(qi.need_foreign_price_inquiry)):
                    counter += 1
                    context['allow_next'] = False
                    context['submit_copy_q'] = True
            if counter == len(qis):
                context['submit_copy_q'] = False
        if self.object and self.object.cancel:
            context['comment_form'] = CommentsForm(initial={'submit_type': 'uncanceled'})
        else:
            context['comment_form'] = CommentsForm(initial={'submit_type': 'cancel'})
        for f in context['formset']:
            if f.instance.comments.filter(comment_title__in=['L', 'M', 'N']):
                f.has_alt_code = True
        return context


def search_factor_view(request, *args, **kwargs):
    q = request.GET.get('q')
    quotations = Quotation.objects.filter(customer_party_id__title__icontains=q).order_by('-id')
    res = dict()
    res['items'] = []
    total_count = 0
    for total_count, q in enumerate(quotations):
        item = dict()
        item['id'] = q.pk
        item['customer_title'] = q.customer_party_id.title
        item['customer_party_id'] = q.customer_party_id.sepidar_dl_code
        item['quotation_id'] = q.pk
        item['row_count'] = q.quotation.all().count()
        item['last_work_flow_user'] = q.last_work_flow.creator_user.username
        item['expiration_date'] = q.expiration_date
        item['sale_type'] = q.sale_type.title
        res['items'].append(item)
    else:
        res['items'].append(total_count)
    return JsonResponse(res)
