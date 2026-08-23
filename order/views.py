from datetime import timedelta

from ajax_datatable import AjaxDatatableView
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum, F, ExpressionWrapper, FloatField, Q, Value, Case, When, IntegerField, Subquery, \
    OuterRef
from django.db.models.functions import Coalesce, NullIf
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse, HttpResponseNotAllowed, HttpResponseForbidden
from django.template.loader import render_to_string
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views import View
from django.views.generic import ListView
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from comments.forms import CommentsForm
from core.permissions import HasShopPermission
from core.views import BaseView, Base
from factor.models import Factor, FactorItem, FactorItemSupplyLocation
from factor.services.supply import SupplyLocationService
from inquiry.models import Supplier
from micmod_base.models import QuotationItem, SupplyStatus
from payment.models import PaymentOrder, Payment
from sepidar.api_call import SepidarApiCall
from sepidar.models import Dl
from tools.utils import is_ajax, parse_number
from workflow.models import WorkFlow
from .form_perm import ORDER_FIELDS_BY_PERMISSION
from .forms import OrderForm, PackingForm, PackingItemForm, GIOForm, GIOItemForm, OrderPaymentForm, \
    OrderPaymentItemForm, OrderPaymentItemFormSet, BazarBuyFactorForm, \
    TradeBuyFactorForm, TradePurchaseItemFormSet, BazarPurchaseItemFormSet, ACNTForm, GIOItemFormSet, BazarOrderForm, \
    OrderSafeForm, OrderDelayReasonModelForm
from .models import Order, OrderOrder, Packing, PackingItem, GIO, GIOItem, OrderPayment, OrderPaymentItem, ACNT, \
    SepidarOrderDocument, OrderBazar, WhReserve
from translator import get_text as _
from .serializers import OrderSerializer
import json
from collections import OrderedDict

# def factor_order_item(request, sku, quantity):
#     items = get_object_or_404(QuotationItem, goods_code=sku)
#
#     for item in items.goods_code:
#         order_item = OrderItem.objects.create(order__title=item)


class SafeOrderView(LoginRequiredMixin, BaseView):
    safe_methods = set()
    template_name = 'order/safe_order.html'
    form_class = OrderSafeForm
    model = Order
    form_struct = {
        'form': OrderSafeForm,
        'childes': [{},]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'OrderView')
    has_flow = True
    wf_last_step_is_open = True
    formset_model = FactorItem

    def check_version(self, *args, **kwargs):
        last_version = self.request.POST.get('last_version')
        current_version = getattr(self.object, 'version', None)
        if int(last_version) != int(current_version):
            link = f"""<a class="btn btn-warning" href='{reverse_lazy("order:order.view.safe", kwargs={"pk": self.object.pk})}'>این دکمه</a>"""
            msg = mark_safe(f"""<span class="text-danger">سفارش ذخیره نشد</span> این سفارش توسط فرد دیگری تغییر یافته است. از طریق {link} صفحه را مجدد لود کنید.""")
            messages.warning(self.request, msg)
            return self.get(self.request, *args, **kwargs)


    def dispatch(self, request, *args, **kwargs):
        view_name = self.request.GET.get('view_name', None)
        if view_name in self.__class__.safe_methods and hasattr(self, view_name):
            method = getattr(self, view_name)
            return method(request, *args, **kwargs)

        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        return self._build_order_form(**self.get_form_kwargs())

    def _build_order_form(self, data=None, instance=None, initial=None, **kwargs):
        allowed, hidden, show = self._get_order_allowed_fields()
        return OrderSafeForm(allowed_fields=allowed, allowed_hidden=hidden, only_show=show, data=data,
                             instance=instance, initial=initial, **kwargs)

    def _get_order_allowed_fields(self):
        # permissions = self.request.user.get_all_permissions()
        permissions = {
                f"{perm.content_type.app_label}.{perm.codename}"
                for perm in self.request.user.user_permissions.all()
            }
        user_exist_perm = []
        allowed_hidden = []
        allowed_edit = []
        allowed_show = []
        for p in permissions:
            exist_perm = ORDER_FIELDS_BY_PERMISSION.get(p, None)
            if exist_perm:
                user_exist_perm.append(exist_perm)

        for perm in user_exist_perm:
            if perm:
                data = perm.get(self.state_index or 0)
                if data:
                    allowed_hidden += data['hidden']
                    allowed_edit += data['edit']
                    allowed_show += data['show']

        if not allowed_edit and not allowed_show:
            raise PermissionDenied("شما دسترسی لازم برای ویرایش این سفارش را ندارید.")
        hidden = []
        edit = []
        show = []
        for h in allowed_hidden:
            if h not in hidden:
                hidden.append(h)

        for e in allowed_edit:
            if e not in edit:
                edit.append(e)

        for s in allowed_show:
            if s not in show:
                show.append(s)
        return edit, hidden, show

    def get_success_url(self):
        return reverse_lazy('order:order.view.safe', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        try:
            self.auto_complete()
            if not self.object or not self.object.pk:
                is_new = True
            else:
                is_new = False
                self.check_version()

            self.get_form_kwargs()

            # self.object = self.get_object()
            self.form = self.get_form()
            if not self.form.is_valid():
                return self.render_to_response(self.get_context_data(form=self.form))
            self.form.instance.extra_data.request = self.request
            self.object = self.form.save()
            if not self.object:
                self.object = self.get_object()

            if self.form.file_model and self.form.file_groups_2:
                self.object.save_file(request=self.request,
                                      file_groups=self.form.file_groups_2,
                                      file_model=self.form.file_model,
                                      obj=self.object,
                                      input_prefix='file'
                                      )
            self.object.save_comment(self.request, CommentsForm)
            canceled_order = Order.objects.filter(pk=self.object.pk, comments__comment_title='T').order_by('-id').first()
            if canceled_order:
                # wf = WorkFlow.objects.create(action='back', flow_name='order', creator_user=self.request.user,
                #                              editor_user=self.request.user, wf_status=2,
                #                              from_user=self.object.last_work_flow.to_user,
                #                              to_user=self.object.last_work_flow.to_user,
                #                              content_type=self.model.content_type(), object_id=self.object.pk,
                #                              belong_to_group='sales', current_state_name='تایید مدیر فروش',
                #                              wf_description=self.request.POST.get('wf_description'),
                #                              state=self.object.last_work_flow.current_state_name)
                # self.object.last_work_flow = wf
                self.object.sales_admin_cancel = True
                self.object.extra_data.request = self.request
                self.object.save()


            wf_obj = self.submit_flow(is_new=is_new)
            self.object.last_work_flow = wf_obj
            self.object.extra_data.request = self.request
            self.object.save()

        except Exception as e:
            self.form._non_form_errors = self.form.error_class([str(e)])
            return self.render_to_response(self.get_context_data(form=self.form))

        return redirect(self.get_success_url())

    def submit_flow(self, is_new):
        groups = {
                    0: {"group": "sales_user", "state_name": "پیش نویس"},
                    1: {"group": "sales_admin", "state_name": "تایید مدیر فروش"},
                    2: {"group": "trade_order", "state_name": "تایید بازرگانی"},
                    3: {"group": "trade_order", "state_name": "تایید مهندس"},
                    4: {"group": "trade_order", "state_name": "ارسال به تامین کننده"},
                    5: {"group": "trade_order", "state_name": "تایید تامین کننده"},
                    6: {"group": "trade_order", "state_name": "تایید نهایی بازرگانی"},
                    7: {"group": "trade_order", "state_name": "پرداخت / PACKING / GIO"},
                    8: {"group": "trade_order", "state_name": "مرحله نهایی"},
                }

        last_flow = self.object.last_work_flow
        current_state_index = self.state_index
        if 0 < current_state_index < 8:
            next_state_index = getattr(self, 'state_index') + 1
            previews_state_index = getattr(self, 'state_index') - 1

        if current_state_index == 0:
            next_state_index = getattr(self, 'state_index') + 1
            previews_state_index = 0

        if current_state_index == 8:
            next_state_index = 8
            previews_state_index = getattr(self, 'state_index') - 1

        current_group_name = groups.get(current_state_index).get('group')
        next_group_name = groups.get(next_state_index).get('group')
        previews_group_name = groups.get(previews_state_index).get('group')

        current_state_name = groups.get(current_state_index).get('state_name')
        next_state_name = groups.get(next_state_index).get('state_name')
        previews_state_name = groups.get(previews_state_index).get('state_name')

        if 'next' in self.request.POST:  # 3 next
            current_group_last_wf_obj = self.object.workflows.filter(belong_to_group=next_group_name)
            if current_group_last_wf_obj:
                to_user = current_group_last_wf_obj.latest("pk").from_user
            else:
                next_state_user = get_user_model().objects.filter(groups__name=next_group_name)
                to_user = next_state_user.last()

            wf = WorkFlow.objects.create(action='next', flow_name='order',creator_user=self.request.user,
                                         editor_user=self.request.user, wf_status=3, from_user=getattr(last_flow, "to_user", None) or self.request.user,
                                         to_user=to_user,
                                         content_type=self.model.content_type(), object_id=self.object.pk,
                                         belong_to_group=current_group_name, current_state_name=next_state_name,
                                         wf_description=self.request.POST.get('wf_description'),
                                         state=current_state_name)
            return wf
        elif 'draft' in self.request.POST and (is_new or not last_flow):  # 5 first draft
            wf = WorkFlow.objects.create(action='draft', flow_name='order', wf_status=5,
                                         creator_user=self.request.user,
                                         editor_user=self.request.user,
                                         from_user=self.request.user,
                                         to_user=self.request.user,
                                         content_type=self.model.content_type(), object_id=self.object.pk,
                                         belong_to_group=current_group_name, current_state_name=current_state_name,
                                         wf_description=self.request.POST.get('wf_description'),
                                         state=current_state_name)
            return wf

        elif 'back' in self.request.POST:  # 2 back
            current_group_last_wf_obj = self.object.workflows.filter(belong_to_group=previews_group_name).latest("pk")
            if current_group_last_wf_obj:
                to_user = current_group_last_wf_obj.from_user
            else:
                previews_state_user = get_user_model().objects.filter(groups__name=previews_group_name)
                to_user = previews_state_user.first()

            wf = WorkFlow.objects.create(action='back', flow_name='order',creator_user=self.request.user,
                                         editor_user=self.request.user, wf_status=2,
                                         from_user=last_flow.to_user,
                                         to_user=to_user,
                                         content_type=self.model.content_type(), object_id=self.object.pk,
                                         belong_to_group=current_group_name, current_state_name=previews_state_name,
                                         wf_description=self.request.POST.get('wf_description'),
                                         state=current_state_name)
            return wf

        elif 'change_user' in self.request.POST:  # 4 change user
            to_user = self.request.POST.get('to_current_group_user')
            wf = WorkFlow.objects.create(action='change user', flow_name='order', creator_user=self.request.user,
                                         editor_user=self.request.user, wf_status=4,
                                         from_user=last_flow.to_user,
                                         to_user_id=to_user,
                                         content_type=self.model.content_type(), object_id=self.object.pk,
                                         belong_to_group=current_group_name, current_state_name=current_state_name,
                                         wf_description=self.request.POST.get('wf_description'),
                                         state=current_state_name)
            return wf

        return last_flow

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.base_group == 'mac':
            if self.object.buy_operator != "mac" and self.object.pay_operator != "mac":
                raise PermissionError()

        context['app_name'] = self.request.resolver_match.app_name
        if self.object:
            context['trade_price_list'] = self.object.final_item.items.filter(active=True, is_deleted=False) if self.object else self.object.item.items.none()
            context['trade_parent_price_list'] = self.object.final_item.parent.items.filter(~Q(creator_user__groups__name__in=['bazar_user']), active=True, is_deleted=False) if self.object.final_item.parent else self.object.item.items.none()

        context['section_id'] = 'order'

        if self.state_index > 1 and self.request.user.base_group == 'sales':
            """اگر در مراحل بازرگانی بودم کاربر فروش نمیتواند سند را به مرحله بعد و قبل ببرد"""
            context['allow_next'] = False
            context['allow_back'] = False
        elif self.state_index < 2 and not self.request.user.base_group == 'sales':
            """فقط کاربران فروش میتوانند در مراحل اولیه سفارش را جلو عقب بفرستن"""
            context['allow_next'] = False
            context['allow_back'] = False
        elif self.state_index == 1 and not self.request.user.groups.filter(name='sales_admin').exists():
            """در مرحله تایید مدیر فروش کاربر فروش میتواند سفارش را به عقب برگزداند اما نمیتواند جلو ببرد"""
            context['allow_next'] = False
            context['allow_back'] = True
        else:
            context['allow_next'] = True  # context.get('allow_next')
            context['allow_back'] = True  # context.get('allow_back')

        if self.object and self.object.sales_admin_cancel:
            context['allow_next'] = False

        if self.request.method == "POST":
            context["form"] = self._build_order_form(
                data=self.request.POST,
                instance=self.object,
            )
        else:
            if self.object:
                ...

        if self.state_index == 7:
            context['packing_items'] = PackingItem.objects.filter(order=self.object).order_by('-id')
            context['gio_items'] = GIOItem.objects.filter(order=self.object).order_by('-id')
            context['payment_items'] = OrderPaymentItem.objects.filter(order=self.object).order_by('-id')

        # context['delay_reason_form'] = OrderDelayReasonModelForm(initial={'order': self.object},
        #                                                          order_instance=self.object,
        #                                                          prefix='delay')
        context['last_version'] = getattr(self.object, 'version', None) or 0
        return context

    def form_valid(self, form):
        from tools import const
        res = super().form_valid(form)
        if 'back' in self.request.POST and self.state_index == 4 and not self.object.mohandes_confirmation:
            flow_data = {
                "wf_status": 2,  # back
                "action": 'ایجاد خودکار',
                "flow_name": 'سفارش',
                "state": const.WF__ORDER__4_STATE,
                "wf_description": "بدون نیاز به تایید مهندس",
                "belong_to_group": 'trade_order',
                "object_id": self.object.pk,
                "content_type": ContentType.objects.get_for_model(self.object),
                "creator_user": self.request.user,
                "editor_user": self.request.user,
                "from_user": self.request.user,
                "to_user": self.request.user,  # get_user_model().objects.filter(groups__name='order_admin').first(),
                "current_state_name": const.WF__ORDER__5_CURRENT_STATE_NAME,
            }

            wf = WorkFlow.objects.create(**flow_data)
            self.object.last_work_flow = wf
            self.object.extra_data.request = self.request
            self.object.save()
        if 'mohandes_confirmation' not in self.request.POST and self.state_index == 2 and 'change_user' not in self.request.POST and 'back' not in self.request.POST and 'next' in self.request.POST:
            flow_data = {
                "wf_status": 3,  # next
                "action": 'ایجاد خودکار',
                "flow_name": 'سفارش',
                "state": const.WF__ORDER__4_STATE,
                "wf_description": "بدون نیاز به تایید مهندس",
                "belong_to_group": 'trade_order',
                "object_id": self.object.pk,
                "content_type": ContentType.objects.get_for_model(self.object),
                "creator_user": self.request.user,
                "editor_user": self.request.user,
                "from_user": self.request.user,
                "to_user": self.request.user,  # get_user_model().objects.filter(groups__name='order_admin').first(),
                "current_state_name": const.WF__ORDER__5_CURRENT_STATE_NAME,
            }

            wf = WorkFlow.objects.create(**flow_data)
            self.object.last_work_flow = wf
            self.object.extra_data.request = self.request
            self.object.save()
        return res


class OrderView(LoginRequiredMixin, BaseView):
    template_name = 'order/view.html'
    form_class = OrderForm
    model = Order
    wf_last_step_is_open = True
    has_flow = True
    form_struct = {
        'form': OrderForm,
        'childes': [
            {},
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'OrderView')

    def get_success_url(self):
        return reverse_lazy('order:order.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        from tools import const
        res = super().form_valid(form)
        if 'back' in self.request.POST and self.state_index == 4 and not self.object.mohandes_confirmation:
            flow_data = {
                "wf_status": 2,  # back
                "action": 'ایجاد خودکار',
                "flow_name": 'سفارش',
                "state": const.WF__ORDER__4_STATE,
                "wf_description": "بدون نیاز به تایید مهندس",
                "belong_to_group": 'trade_order',
                "object_id": self.object.pk,
                "content_type": ContentType.objects.get_for_model(self.object),
                "creator_user": self.request.user,
                "editor_user": self.request.user,
                "from_user": self.request.user,
                "to_user": self.request.user,  # get_user_model().objects.filter(groups__name='order_admin').first(),
                "current_state_name": const.WF__ORDER__5_CURRENT_STATE_NAME,
            }

            wf = WorkFlow.objects.create(**flow_data)
            self.object.last_work_flow = wf
            self.object.extra_data.request = self.request
            self.object.save()
        if 'mohandes_confirmation' not in self.request.POST and self.state_index == 2 and 'change_user' not in self.request.POST and 'back' not in self.request.POST and 'next' in self.request.POST:
            flow_data = {
                "wf_status": 3,  # next
                "action": 'ایجاد خودکار',
                "flow_name": 'سفارش',
                "state": const.WF__ORDER__4_STATE,
                "wf_description": "بدون نیاز به تایید مهندس",
                "belong_to_group": 'trade_order',
                "object_id": self.object.pk,
                "content_type": ContentType.objects.get_for_model(self.object),
                "creator_user": self.request.user,
                "editor_user": self.request.user,
                "from_user": self.request.user,
                "to_user": self.request.user,  # get_user_model().objects.filter(groups__name='order_admin').first(),
                "current_state_name": const.WF__ORDER__5_CURRENT_STATE_NAME,
            }

            wf = WorkFlow.objects.create(**flow_data)
            self.object.last_work_flow = wf
            self.object.extra_data.request = self.request
            self.object.save()
        return res

    def get(self, request, *args, **kwargs):
        get = super().get(request, *args, **kwargs)
        if self.request.user.base_group == 'mac' and not self.object.apply_mac:
            raise PermissionDenied()
        else:
            return get

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        context['trade_price_list'] = self.object.item.items.filter(active=True) if self.object else []
        context['section_id'] = 'order'
        if self.state_index == 7:
            context['packing_items'] = PackingItem.objects.filter(order=self.object).order_by('-id')
            context['gio_items'] = GIOItem.objects.filter(order=self.object).order_by('-id')
            context['payment_items'] = OrderPaymentItem.objects.filter(order=self.object).order_by('-id')
        return context


class BazarBuyFactorView(LoginRequiredMixin, View):
    template_name = 'order/bazar_view.html'
    form_class = OrderForm
    model = Order
    # wf_last_step_is_open = True
    has_flow = False
    form_struct = {
        'form': OrderForm,
        'childes': [
            {},
        ]
    }
    # flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'OrderView')

    def get_success_url(self):
        return reverse_lazy('order:bazar_buyfactor.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        invoice_form = BazarBuyFactorForm(request.POST)
        item_formset = BazarPurchaseItemFormSet(request.POST)

        if invoice_form.is_valid() and item_formset.is_valid():
            invoice_data = invoice_form.cleaned_data
            items_data = [f.cleaned_data for f in item_formset if f.cleaned_data]
            print(invoice_data, items_data)
            # اینجا می‌تونی پردازش دلخواه رو انجام بدی
            return self.get_success_url()
        return super().post(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        invoice_form = BazarBuyFactorForm()
        item_formset = BazarPurchaseItemFormSet()

        context = {
            'form': invoice_form,
            'formset': item_formset,
        }
        return render(request, self.template_name, context)

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class TradeBuyFactorView(LoginRequiredMixin, View):
    template_name = 'order/trade_buy_factor_view.html'
    form_class = OrderForm
    model = Order
    # wf_last_step_is_open = True
    has_flow = False
    form_struct = {
        'form': OrderForm,
        'childes': [
            {},
        ]
    }
    # flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'OrderView')

    def get_success_url(self):
        return reverse_lazy('order:bazar_order.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        invoice_form = TradeBuyFactorForm(request.POST)
        item_formset = TradePurchaseItemFormSet(request.POST)

        if invoice_form.is_valid() and item_formset.is_valid():
            invoice_data = invoice_form.cleaned_data
            items_data = [f.cleaned_data for f in item_formset if f.cleaned_data]
            print(invoice_data, items_data)
            # اینجا می‌تونی پردازش دلخواه رو انجام بدی
            return self.get_success_url()
        return super().post(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        invoice_form = TradeBuyFactorForm()
        item_formset = TradePurchaseItemFormSet()

        context = {
            'form': invoice_form,
            'formset': item_formset,
        }
        return render(request, self.template_name, context)

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'order/list.html'


class OrderDataTableListView(AjaxDatatableView):
    model = Order
    title = 'order_list'
    initial_order = [["created_date", "des"], ]
    length_menu = [[10, 20, 50, -1], [10, 20, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'
    show_column_filters = True
    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'title': "id", 'orderable': True, 'visible': True, },
        {'name': 'order_title', 'orderable': True, 'visible': True, },
        {'name': 'order_method', 'orderable': False, 'visible': True, 'searchable': False},
        {'name': 'last_work_flow', 'title': 'status', 'visible': True, 'orderable': True,
         'lookup_field': '__current_state_name__icontains'},
        {'name': 'estimated_arrive_date', 'orderable': False, 'searchable': False, 'title': 'Estimated Arrive Date', 'visible': True},
        {'name': 'creator_user', 'title': 'creator_user', 'visible': True, 'orderable': True, 'lookup_field': '__username__icontains'},
        {'name': 'trade_user', 'title': 'trade_user', 'visible': True, 'orderable': True, 'lookup_field': '__username__icontains'},
        {'name': 'order_number', 'orderable': True, 'title': 'Order No', 'visible': True},
        {'name': 'item', 'orderable': True, 'title': 'SKU', 'visible': True, 'lookup_field': '__sku__icontains'},
        {'name': 'item__part_number', 'orderable': True, 'title': 'Part Number(S)', 'visible': True, 'lookup_field': '__icontains'},
        {'name': 'qi__quotation__customer_party_id', 'orderable': True, 'title': 'Customer', 'visible': True, 'lookup_field': '__title__icontains'},
        {'name': 'item_trade', 'orderable': True, 'title': 'SKU (T)', 'visible': True, 'lookup_field': '__sku__icontains'},
        {'name': 'item_trade__part_number', 'orderable': True, 'title': 'part number(T)', 'visible': True, 'lookup_field': '__icontains'},
        {'name': 'qi__quotation__id', 'orderable': True, 'title': 'Pre Invoice No', 'visible': True, 'lookup_field': '__icontains'},
        {'name': 'created_date', 'orderable': True, 'visible': True, },
        {'name': 'transportation_method', 'orderable': True, 'visible': True, 'title': 'Transportation Method'},
        {'name': 'quantity', 'orderable': True, 'visible': True, 'title': 'Request Qty', },
        {'name': 'description_sale', 'orderable': True, 'visible': True, 'title': 'Sales Description'},
        # {'name': 'xxx', 'orderable': True, 'visible': True, 'title': 'دلیل تاخیر'},
        {'name': 'quantity_trade', 'orderable': True, 'visible': True, 'title': 'Order Qty (T)', },
        {'name': 'co_conf', 'searchable': False, 'orderable': False, 'visible': True, 'title': 'زمان تایید مهندس', },
    ]

    def get_gio_annotated_qs(self, qs):
        return qs.annotate(
            final_quantity_db=Coalesce(
                NullIf(F('quantity_mac'), Value(0.0)),
                NullIf(F('quantity_trade'), Value(0.0)),
                F('quantity'),
                Value(0.0),
                output_field=FloatField()
            ),
            total_arrived_db=Coalesce(
                Sum('gio_items__quantity', filter=Q(gio_items__is_deleted=False)),
                Value(0.0),
                output_field=FloatField()
            ),
        )

    def _get_expressions(self):
        final_qty = Coalesce(
            NullIf(F('quantity_mac'), Value(0.0)),
            NullIf(F('quantity_trade'), Value(0.0)),
            NullIf(F('quantity'), Value(0.0)),
            Value(0.0),
            output_field=FloatField()
        )
        final_price = Coalesce(
            NullIf(F('price'), Value(0.0)),
            NullIf(F('price_mac'), Value(0.0)),
            NullIf(F('price_trade'), Value(0.0)),
            Value(0.0),
            output_field=FloatField()
        )
        payment_subquery = Subquery(
            OrderPaymentItem.objects.filter(
                order=OuterRef('pk'),
                is_deleted=False
            ).values('order').annotate(
                total=Sum('total_amount')
            ).values('total')[:1],
            output_field=FloatField()
        )
        packing_subquery = Subquery(
            PackingItem.objects.filter(
                order=OuterRef('pk'),
                is_deleted=False
            ).values('order').annotate(
                total=Sum('wh_receipt_quantity')
            ).values('total')[:1],
            output_field=FloatField()
        )
        return final_qty, final_price, payment_subquery, packing_subquery

    def get_packing_payment_annotated_qs(self, qs):
        final_qty, final_price, payment_subquery, packing_subquery = self._get_expressions()
        return qs.annotate(
            final_quantity_db=final_qty,
            total_price_db=ExpressionWrapper(final_price * final_qty, output_field=FloatField()),
            total_payment_db=Coalesce(payment_subquery, Value(0.0), output_field=FloatField()),
            total_packing_db=Coalesce(packing_subquery, Value(0.0), output_field=FloatField()),
        )

    def get_initial_queryset(self, request=None):

        q = request.POST.get('q')
        user_group = request.user.base_group

        user_groups = None

        if user_group == 'trade':
            user_groups = request.user.groups.filter(name='trade_user')

        elif user_group == 'bazar':
            user_groups = request.user.groups.filter(name='bazar_user')

        if user_groups:
            qs = self.model.get_qs(
                self.request,
                lst=False,
                groups_list=user_groups
            )
        else:
            qs = self.model.get_qs(
                self.request,
                lst=False
            )

        if q == 'all':
            pass

        elif q == 'dependent':
            qs = qs.filter(
                cancel=True,
                last_work_flow__current_state_name='تایید مدیر فروش'
            )

        elif q == 'sales_admin':
            qs = qs.filter(
                cancel=False,
                last_work_flow__current_state_name='تایید مدیر فروش'
            )

        elif q == 'bazar_user':
            qs = qs.filter(is_bazar=True)

        elif q == 'not_complete':

            not_complete_order = Q()

            orders = qs.filter(cancel=True)

            for order in orders:
                not_complete = 0

                for item in order.order_base_items.all():
                    not_complete += item.quantity

                res = not_complete - order.quantity

                if res < 0:
                    not_complete_order |= Q(id=order.id)

            if not_complete_order:
                qs = qs.filter(not_complete_order)
            else:
                qs = qs.none()

        elif q == 'is_wh':
            qs = qs.filter(is_wh=True)

        elif q == 'is_trade':
            qs = qs.filter(
                is_wh=False,
                is_bazar=False
            )

        elif q == 'quantity_difference':
            has_mac_diff = Q(quantity_mac__isnull=False) & ~Q(quantity_mac=F('quantity')) & ~Q(quantity_mac=0.0)
            has_trade_diff = Q(quantity_trade__isnull=False) & ~Q(quantity_trade=F('quantity')) & ~Q(quantity_trade=0.0)
            qs = qs.filter(has_mac_diff | has_trade_diff, is_deleted=False).distinct()

        elif q == 'need_sale_admin_confirmation':
            qs = qs.filter(sales_admin_confirmation=True, is_deleted=False)

        elif q == 'has_delay':
            qs = qs.filter(delay_reason__isnull=False, is_deleted=False)

        elif q == 'has_error':
            if request.user.groups.filter(name='sales_user'):
                qs = qs.filter(
                    comments__comment_title='R', last_work_flow__current_state_name__in=['پیش نویس', 'تایید مدیر فروش']
                    , is_deleted=False
                ).distinct()

        elif q == 'pcb_item':
            qs = qs.filter(item__purchase_group__title='PCB', is_deleted=False).distinct()

        elif q == 'back':
            qs = qs.filter(
                last_work_flow__wf_status=2, is_deleted=False
            )

        elif q == 'is_sample':
            qs = qs.filter(
                is_sample=True, is_deleted=False
            )
        elif q == 'is_force_order':
            qs = qs.filter(
                is_force_order=True, is_deleted=False
            )
        elif q == 'cancel_request':
            qs = qs.filter(
                comments__comment_title='U', last_work_flow__current_state_name__in=['تایید بازرگانی', 'تایید مهندس', 'ارسال به تامین کننده']
                , sales_admin_cancel=False, is_deleted=False
            ).distinct()
        elif q == 'cancel_denied':
            qs = qs.filter(
                comments__comment_title='V'
                , sales_admin_cancel=False, is_deleted=False
            ).distinct()
        elif q == 'gio_complete':
            qs = self.get_gio_annotated_qs(qs)
            qs = qs.filter(
                total_arrived_db__gte=F('final_quantity_db'),
                final_quantity_db__gt=0, last_work_flow__current_state_name__in=['پرداخت / PACKING / GIO'],
                is_deleted=False
            ).distinct()
        elif q == 'gio_incomplete':
            qs = self.get_gio_annotated_qs(qs)
            qs = qs.filter(
                final_quantity_db__gt=0,
                total_arrived_db__lt=F('final_quantity_db'),
                last_work_flow__current_state_name__in=['پرداخت / PACKING / GIO'], is_deleted=False
            ).distinct()
        elif q == 'payment_complete':
            qs = self.get_packing_payment_annotated_qs(qs).filter(
                total_price_db__gt=0,
                total_payment_db__gte=F('total_price_db'),
                last_work_flow__current_state_name__in=['پرداخت / PACKING / GIO'],
            ).distinct()

        elif q == 'payment_incomplete':
            qs = self.get_packing_payment_annotated_qs(qs).filter(
                total_price_db__gt=0,
                total_payment_db__lt=F('total_price_db'),
                last_work_flow__current_state_name__in=['پرداخت / PACKING / GIO'],
            ).distinct()

        elif q == 'packing_complete':
            qs = self.get_packing_payment_annotated_qs(qs).filter(
                final_quantity_db__gt=0,
                total_packing_db__gte=F('final_quantity_db'),
                last_work_flow__current_state_name__in=['پرداخت / PACKING / GIO'],
            ).distinct()

        elif q == 'packing_incomplete':
            qs = self.get_packing_payment_annotated_qs(qs).filter(
                final_quantity_db__gt=0,
                total_packing_db__lt=F('final_quantity_db'),
                last_work_flow__current_state_name__in=['پرداخت / PACKING / GIO'],
            ).distinct()

        if user_group == 'trade':
            qs = qs.filter(is_bazar=False)

        elif user_group == 'sales':
            qs = qs.filter(
                is_deleted=False,
                cancel=False,
                is_bazar=False
            ).filter(
                ~Q(order_title__icontains='خودکار')
            )

        if request.user.groups.filter(name='mac').exists():

            qs = qs.filter(
                is_deleted=False,
                apply_mac=True
            )

        elif request.user.groups.filter(name='trade_user').exists():

            qs = qs.filter(
                is_deleted=False,
                cancel=False,
                is_bazar=False
            ).filter(
                ~Q(order_title__icontains='خودکار')
            ).filter(
                ~Q(last_work_flow__current_state_name='پیش نویس')
            )

        return qs.distinct()

    def customize_row(self, row, obj):
        # row['order_method'] = f'<span>{obj.order_method}</span>'
        row['item__part_number'] = f'<span>{obj.item.part_number}</span>' if obj.item else ""
        try:
            row['qi__quotation__customer_party_id'] = f'<span>{obj.qi.quotation.customer_party_id.title}</span>' if obj.qi else obj.customer_party_id.title
        except Exception as e:
            row['qi__quotation__customer_party_id'] = ''
        row['qi__quotation__id'] = f'<span>{obj.qi.quotation.id}</span>' if obj.qi else ""
        row['item_trade__part_number'] = f'<span>{obj.item_trade.part_number}</span>' if obj.item_trade else ""
        o = obj.workflows.filter(current_state_name='تایید مهندس').first()
        row['co_conf'] = f'<span>{o.created_date.strftime("%Y-%b-%d %H:%m")}</span>' if o else ""

        row['order_number'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('order:order.view.safe', args=(obj.id,)),
            obj.order_number if obj.order_number else 'بدون عنوان'
        )
        row['qi'] = f'<span>{obj.qi.quotation.customer_party_id.title}</span>' if obj.qi else ""
        row['total_price'] = f'<span>{parse_number(obj.total_price):,}</span>'
        row['is_kasri'] = f'<span class="badge badge-success">بله</span>' if obj.is_kasri else f'<span class="badge badge-danger">خیر</span>'
        row['is_force_order'] = f'<span class="badge badge-success">بله</span>' if obj.is_force_order else f'<span class="badge badge-danger">خیر</span>'
        row['qi__quotation'] = f'<span>{obj.qi.quotation.id}</span>' if obj.qi else ""
        row['estimated_arrive_date'] = obj.estimate_arrive_at
        row['comments'] = '<hr>'.join([f"{x.comment_content} <br> ({x.elapsed_time})" for x in obj.comments.filter(comment_title='R')])  # "R" is order error from trade user
        row['payment'] = '<hr>'.join([
                            (
                                f"<a target='_blank' href='{reverse_lazy('order:order.payment.update', kwargs={'pk': x.payment.pk})}'>{x.total_amount} {x.payment.currency}</a>"
                                if x.payment
                                else "<span class='text-muted'>بدون پرداخت</span>"
                            )
                            for x in obj.order_payment_items.select_related('payment').all()
                        ])
        row['weight'] = f'{parse_number(obj.final_total_weight):,}'
        row['item__purchase_group'] = obj.final_purchase_group

        row['work_day'] = obj.trade_work_day

        # row['edit'] = mark_safe(f"""
        # <a href="#" target="_blank" class="me-3 edit-packing-item tooltip_" data-url="/order/packingitem/update/1/" data-bs-toggle="modal" data-bs-target="#id_kt_empty_modal_lg">
        #     <i class="ki-duotone ki-pencil fs-2 text-info">
        #         <span class="path1"></span>
        #         <span class="path2"></span>
        #     </i>
        # </a>
        # """)
        
    def get_column_defs(self, request):
        if self.request.user.base_group == 'bazar':
            self.column_defs = [
                AjaxDatatableView.render_row_tools_column_def(),
                {'name': 'id', 'title': "شناسه", 'orderable': True, 'visible': True, },
                {'name': 'order_number', 'orderable': True, 'title': 'Order No', 'visible': True},
                {'name': 'order_title', 'orderable': True, 'visible': True, 'title': "عنوان سفارش"},
                {'name': 'last_work_flow', 'title': 'وضعیت', 'visible': True, 'orderable': True, 'lookup_field': '__current_state_name__icontains'},
                {'name': 'item', 'orderable': True, 'title': 'کد کالا', 'visible': True, 'lookup_field': '__sku__icontains'},
                {'name': 'item__part_number', 'orderable': True, 'title': 'پارت نامبر', 'visible': True, 'lookup_field': '__icontains'},
                # {'name': 'qi__quotation__customer_party_id', 'orderable': True, 'title': 'مشتری', 'visible': True, 'lookup_field': '__title__icontains'},
                {'name': 'qi__quotation__id', 'orderable': True, 'title': 'پیش فاکتور', 'visible': True, 'lookup_field': '__icontains'},
                {'name': 'created_date', 'orderable': True, 'visible': True, },
                {'name': 'quantity', 'orderable': True, 'visible': True, 'title': 'تعداد', },
                {'name': 'description_sale', 'orderable': True, 'visible': True, 'title': 'توضیحات فروش'},
                {'name': 'trade_user', 'title': 'trade_user', 'visible': True, 'orderable': True,
                 'lookup_field': '__username__icontains'},
            ]
        elif self.request.user.base_group == 'sales':
            self.column_defs = [
                AjaxDatatableView.render_row_tools_column_def(),
                {'name': 'id', 'title': "id", 'orderable': True, 'visible': True, },
                {'name': 'order_number', 'orderable': True, 'title': 'Order No', 'visible': True},
                {'name': 'order_title', 'orderable': False, 'visible': True, },
                {'name': 'title', 'orderable': False, 'visible': True, },
                {'name': 'comments', 'orderable': True, 'title': '<div>خطای بازرگانی</div>', 'visible': True, 'lookup_field': '__comment_content__icontains'},
                # {'name': 'order_method', 'title': 'Order Type', 'visible': True, 'searchable': False, 'orderable': False, },
                {'name': 'last_work_flow', 'title': 'status', 'visible': True, 'orderable': True, 'lookup_field': '__current_state_name__icontains'},
                {'name': 'estimated_arrive_date', 'title': 'Estimated Arrive Date', 'visible': True, 'searchable': False, 'orderable': False, },
                {'name': 'creator_user', 'title': 'creator_user', 'visible': True, 'orderable': True, 'lookup_field': '__username__icontains'},
                {'name': 'item', 'orderable': True, 'title': 'SKU', 'visible': True, 'lookup_field': '__sku__icontains'},
                {'name': 'item__part_number', 'orderable': True, 'title': 'Part Number(S)', 'visible': True, 'lookup_field': '__icontains'},
                {'name': 'qi__quotation__customer_party_id', 'orderable': True, 'title': 'Customer', 'visible': True, 'lookup_field': '__title__icontains'},
                {'name': 'item_trade', 'orderable': True, 'title': 'SKU (T)', 'visible': True, 'lookup_field': '__sku__icontains'},
                {'name': 'item_trade__part_number', 'orderable': True, 'title': 'part number(T)', 'visible': True, 'lookup_field': '__icontains'},
                {'name': 'qi__quotation__id', 'orderable': True, 'title': 'Pre Invoice No', 'visible': True, 'lookup_field': '__icontains'},
                {'name': 'created_date', 'orderable': True, 'visible': True, },
                {'name': 'commitment_date_to_customer', 'orderable': True, 'visible': True, },
                {'name': 'transportation_method', 'orderable': True, 'visible': True, 'title': 'Transportation Method'},
                {'name': 'quantity', 'orderable': True, 'visible': True, 'title': 'Request Qty', },
                {'name': 'description_sale', 'orderable': True, 'visible': True, 'title': 'Sales Description'},
                {'name': 'quantity_trade', 'orderable': True, 'visible': True, 'title': 'Order Qty (T)', },
                {'name': 'co_conf', 'searchable': False, 'orderable': False, 'visible': True, 'title': 'زمان تایید مهندس', },
                {'name': 'trade_user', 'title': 'trade_user', 'visible': True, 'orderable': True,
                 'lookup_field': '__username__icontains'},
            ]
        elif self.request.user.base_group == 'trade':
            self.column_defs = [
                AjaxDatatableView.render_row_tools_column_def(),
                {'name': 'id', 'title': "id", 'orderable': True, 'visible': False, },
                {'name': 'order_number', 'orderable': True, 'title': 'Order No', 'visible': True},
                {'name': 'order_title', 'orderable': False, 'visible': True, },
                {'name': 'comments', 'orderable': True, 'title': '<div>خطای بازرگانی</div>', 'visible': True, 'lookup_field': '__comment_content__icontains'},
                # {'name': 'order_method', 'title': 'Order Type', 'visible': True, 'searchable': False, 'orderable': False,},
                {'name': 'last_work_flow', 'title': 'status', 'visible': True, 'orderable': True,
                 'lookup_field': '__current_state_name__icontains'},
                {'name': 'estimated_arrive_date', 'title': 'Estimated Arrive Date', 'visible': True, 'searchable': False, 'orderable': False,},
                {'name': 'creator_user', 'title': 'creator_user', 'visible': True, 'orderable': True, 'lookup_field': '__username__icontains'},
                {'name': 'item', 'orderable': True, 'title': 'SKU', 'visible': True, 'lookup_field': '__sku__icontains'},
                {'name': 'item__part_number', 'orderable': True, 'title': 'Part Number(S)', 'visible': True, 'lookup_field': '__icontains'},
                # {'name': 'qi__quotation__customer_party_id', 'orderable': True, 'title': 'Customer', 'visible': True, 'lookup_field': '__title__icontains'},
                {'name': 'item_trade', 'orderable': True, 'title': 'SKU (T)', 'visible': True, 'lookup_field': '__sku__icontains'},
                {'name': 'item_trade__part_number', 'orderable': True, 'title': 'part number(T)', 'visible': True, 'lookup_field': '__icontains'},
                {'name': 'qi__quotation__id', 'orderable': True, 'title': 'Pre Invoice No', 'visible': True, 'lookup_field': '__icontains'},
                {'name': 'created_date', 'orderable': True, 'visible': True, },
                {'name': 'transportation_method', 'orderable': True, 'visible': True, 'title': 'Transportation Method'},
                {'name': 'quantity', 'orderable': True, 'visible': True, 'title': 'Request Qty', },
                {'name': 'weight', 'orderable': False, 'searchable': False, 'visible': True, 'title': 'weight total', },
                {'name': 'item__purchase_group', 'orderable': False, 'visible': True, 'title': 'purchase group', 'lookup_field': '__title__icontains' },
                {'name': 'description_sale', 'orderable': True, 'visible': True, 'title': 'Sales Description'},
                {'name': 'quantity_trade', 'orderable': True, 'visible': True, 'title': 'Order Qty (T)', },
                {'name': 'co_conf', 'searchable': False, 'orderable': False, 'visible': True, 'title': 'زمان تایید مهندس', },
                {'name': 'trade_user', 'title': 'trade_user', 'visible': True, 'orderable': True,
                 'lookup_field': '__username__icontains'},
                {'name': 'payment', 'orderable': True, 'searchable': False, 'visible': True, 'title': 'پرداخت', },
                {'name': 'total_price', 'orderable': False, 'searchable': False, 'visible': True, 'title': 'مبلغ کل', },
                {'name': 'is_kasri', 'orderable': True, 'searchable': True, 'visible': True, 'title': 'کسری انبار', },
                {'name': 'is_force_order', 'orderable': True, 'searchable': True, 'visible': True, 'title': 'force', },
                {'name': 'work_day', 'visible': True, 'title': 'روز کاری', },
                # {'name': 'gio', 'orderable': False, 'visible': True, 'title': 'زمان تایید مهندس', },
                # {'name': 'packing', 'orderable': False, 'visible': True, 'title': 'زمان تایید مهندس', },
            ]
        elif self.request.user.base_group == 'mac':
            self.column_defs = [
                AjaxDatatableView.render_row_tools_column_def(),
                {'name': 'id', 'title': _("id"), 'orderable': True, 'visible': True, },
                {'name': 'order_number', 'orderable': True, 'title': 'Order No', 'visible': True},
                {'name': 'order_title', 'orderable': True, 'visible': True, 'title': "title"},
                {'name': 'last_work_flow', 'title': 'status', 'visible': True, 'orderable': True, 'lookup_field': '__current_state_name__icontains'},
                {'name': 'item', 'orderable': True, 'title': 'sku', 'visible': True, 'lookup_field': '__sku__icontains'},
                {'name': 'item__part_number', 'orderable': True, 'title': 'part number', 'visible': True, 'lookup_field': '__icontains'},
                # {'name': 'qi__quotation__customer_party_id', 'orderable': True, 'title': 'مشتری', 'visible': True, 'lookup_field': '__title__icontains'},
                # {'name': 'qi__quotation__id', 'orderable': True, 'title': 'پیش فاکتور', 'visible': True, 'lookup_field': '__icontains'},
                {'name': 'quantity', 'orderable': True, 'visible': True, 'title': 'quantity', },
                {'name': 'created_date', 'title': 'created date', 'orderable': True, 'visible': True, },
                {'name': 'description_sale', 'orderable': True, 'visible': True, 'title': 'sales description'},
            ]

        return super().get_column_defs(request)


class BazarOrderForBuyFactorDataTableListView(AjaxDatatableView):
    model = Order
    title = 'order_list'
    initial_order = [["id", "des"], ]
    length_menu = [[10, 25, 50, -1], [10, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'
    show_column_filters = True
    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'title': "id", 'orderable': True, 'visible': True, "className": 'id'},
        {'name': 'quantity', 'orderable': True, 'visible': True, 'title': 'تعداد', 'className': 'quantity'},
        {'name': 'buy_factor_quantity_in_sepidar', 'orderable': True, 'visible': True, 'title': '<div class="px-0">تعداد در<br>فاکتور خرید</div>', 'className': 'buy_factor_quantity_in_sepidar'},
        {'name': 'item', 'orderable': True, 'title': 'کد کالا', 'visible': True, 'lookup_field': '__sku__icontains', 'className': 'item'},
        {'name': 'item__sepidar_id_0', 'visible': True, 'className': 'itemref d-none'},
        {'name': 'item__part_number', 'orderable': True, 'title': 'نام کالا', 'visible': True,
         'lookup_field': '__icontains', 'className': 'partnumber'},
        {'name': 'qi__quotation__id', 'orderable': True, 'title': 'پیش فاکتور', 'visible': True,
         'lookup_field': '__icontains'},
        {'name': 'creator_user', 'title': 'ایجاد کننده', 'visible': True, 'orderable': True,
         'lookup_field': '__username__icontains'},
        {'name': 'created_date', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'description_sale', 'orderable': True, 'visible': True, 'title': 'توضیحات'},
        {'name': 'buy_factor', 'orderable': False, 'visible': True, 'title': '<div class="px-0">فاکتور خرید</div>', },
    ]

    def get_initial_queryset(self, request=None):
        qs = self.model.objects.filter(is_bazar=True, is_deleted=False, is_wh=False).filter(
            Q(buy_factor_quantity_in_sepidar__lt=F('quantity')) | Q(buy_factor_quantity_in_sepidar__isnull=True)
        )
        return qs

    def customize_row(self, row, obj):
        from tools.utils import to_jalali_date
        row['created_date'] = to_jalali_date(obj.created_date)
        row['item__sepidar_id_0'] = obj.item.sepidar_id_0
        row['order_method'] = f'<span>{obj.order_method}</span>'
        row['item__part_number'] = f'<span>{obj.item.part_number}</span>' if obj.item else ""
        row['qi__quotation__customer_party_id'] = f'<span>{obj.qi.quotation.customer_party_id.title}</span>' if obj.qi else ""
        row['qi__quotation__id'] = f'<span>{obj.qi.quotation.id}</span>' if obj.qi else ""
        row['estimated_arrive_date'] = obj.estimate_arrive_at
        row['buy_factor'] = '<span class="fw-bold p-3 cursor-pointer font-size-20 action" onclick="bazar_buy_factor(event);calculate_price()" >➕</span>'


class BazarOrderDataTableListView(AjaxDatatableView):
    model = OrderBazar
    title = 'order_list'
    initial_order = [["id", "des"], ]
    length_menu = [[10, 25, 50, -1], [10, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'
    show_column_filters = True
    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'title': "id", 'orderable': True, 'visible': True, "className": 'id'},
        {'name': 'item', 'orderable': True, 'title': 'کد کالا', 'visible': True, 'lookup_field': '__sku__icontains',
         'className': 'item'},
        {'name': 'item__sepidar_id_0', 'visible': True, 'className': 'itemref d-none'},
        {'name': 'item__part_number', 'orderable': True, 'title': 'نام کالا', 'visible': True,
         'lookup_field': '__icontains', 'className': 'partnumber'},
        {'name': 'quantity', 'orderable': True, 'visible': True, 'title': 'تعداد', 'className': 'quantity'},
        {'name': 'buy_factor_quantity_in_sepidar', 'orderable': True, 'visible': True, 'title': '<div class="px-0">تعداد در<br>فاکتور خرید</div>', 'className': 'buy_factor_quantity_in_sepidar'},
        {'name': 'order_bazar_fis__fi__factor__id', 'orderable': True, 'title': 'فاکتور', 'visible': True,
         'lookup_field': '__icontains'},
        {'name': 'creator_user', 'title': 'ایجاد کننده', 'visible': True, 'orderable': True,
         'lookup_field': '__username__icontains'},
        {'name': 'created_date', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'description', 'orderable': True, 'visible': True, 'title': 'توضیحات'},
        {'name': 'is_over', 'orderable': True, 'visible': True, 'title': 'خاتمه یافته'},
    ]

    def get_initial_queryset(self, request=None):
        qs = self.model.objects.all()
        return qs

    def customize_row(self, row, obj):
        from tools.utils import to_jalali_date
        row['pk'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('order:bazar.order.view', args=(obj.id,)),
            obj.id if obj.id else '-')
        row['quantity'] = parse_number(obj.quantity)
        row['buy_factor_quantity_in_sepidar'] = parse_number(obj.buy_factor_quantity_in_sepidar)
        row['created_date'] = to_jalali_date(obj.created_date)
        row['item__sepidar_id_0'] = obj.item.sepidar_id_0
        row['order_bazar_fis__fi__factor__id'] = f'<span>{", ".join([str(x.fi.factor.pk) for x in obj.order_bazar_fis.all()])}</span>'
        row['item__part_number'] = f'<span>{obj.item.part_number}</span>' if obj.item else ""


class NewBazarBuyFactorView(LoginRequiredMixin, View):
    template_name = 'order/new_bazar_view.html'
    form_class = OrderForm
    model = Order
    # wf_last_step_is_open = True
    has_flow = False
    form_struct = {
        'form': OrderForm,
        'childes': [
            {},
        ]
    }
    # flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'OrderView')

    def get_success_url(self):
        return reverse_lazy('order:bazar_order.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        invoice_form = BazarBuyFactorForm(request.POST)
        item_formset = BazarPurchaseItemFormSet(request.POST)

        if invoice_form.is_valid() and item_formset.is_valid():
            invoice_data = invoice_form.cleaned_data
            items_data = [f.cleaned_data for f in item_formset if f.cleaned_data]
            print(invoice_data, items_data)
            # اینجا می‌تونی پردازش دلخواه رو انجام بدی
            return self.get_success_url()
        return super().post(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        invoice_form = BazarBuyFactorForm()
        item_formset = BazarPurchaseItemFormSet()

        context = {
            'form': invoice_form,
            'formset': item_formset,
        }
        return render(request, self.template_name, context)

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class NewBazarOrderDataTableListView(AjaxDatatableView):
    model = OrderBazar
    title = 'order_list'
    initial_order = [["id", "des"], ]
    length_menu = [[10, 25, 50, -1], [10, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'
    show_column_filters = True
    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'title': "id", 'orderable': True, 'visible': True, "className": 'id'},
        {'name': 'quantity', 'orderable': True, 'visible': True, 'title': 'تعداد', 'className': 'quantity'},
        {'name': 'buy_factor_quantity_in_sepidar', 'orderable': True, 'visible': True, 'title': '<div class="px-0">تعداد در<br>فاکتور خرید</div>', 'className': 'buy_factor_quantity_in_sepidar'},
        {'name': 'item', 'orderable': True, 'title': 'کد کالا', 'visible': True, 'lookup_field': '__sku__icontains', 'className': 'item'},
        {'name': 'item__sepidar_id_0', 'visible': True, 'className': 'itemref d-none'},
        {'name': 'item__part_number', 'orderable': True, 'title': 'نام کالا', 'visible': True,
         'lookup_field': '__icontains', 'className': 'partnumber'},
        {'name': 'order_bazar_fis__fi__factor__id', 'orderable': True, 'title': 'فاکتور', 'visible': True,
         'lookup_field': '__icontains'},
        {'name': 'creator_user', 'title': 'ایجاد کننده', 'visible': True, 'orderable': True,
         'lookup_field': '__username__icontains'},
        {'name': 'created_date', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'description', 'orderable': True, 'visible': True, 'title': 'توضیحات'},
        {'name': 'buy_factor', 'orderable': False, 'visible': True, 'title': '<div class="px-0">فاکتور خرید</div>', },
    ]

    def get_initial_queryset(self, request=None):
        qs = self.model.objects.filter(is_deleted=False, cancel=False, is_over=False).filter(
            Q(buy_factor_quantity_in_sepidar__lt=F('quantity')) | Q(buy_factor_quantity_in_sepidar__isnull=True)
        )
        return qs

    def customize_row(self, row, obj):
        if obj.pk == 7:
            pass
        from tools.utils import to_jalali_date
        row['quantity'] = parse_number(obj.quantity)
        row['created_date'] = to_jalali_date(obj.created_date)
        row['item__sepidar_id_0'] = obj.item.sepidar_id_0
        row['item__part_number'] = f'<span>{obj.item.part_number}</span>' if obj.item else ""
        row['order_bazar_fis__fi__factor__id'] = f'<span>{", ".join([str(x.fi.factor.pk) for x in obj.order_bazar_fis.all()])}</span>'
        row['buy_factor'] = '<span class="fw-bold p-3 cursor-pointer font-size-20 action" onclick="bazar_buy_factor(event);calculate_price()" >➕</span>'


class TradeOrderDataTableListView(AjaxDatatableView):
    model = Order
    title = 'order_list'
    initial_order = [["id", "des"], ]
    length_menu = [[10, 25, 50, -1], [10, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'
    show_column_filters = True
    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'title': "id", 'orderable': True, 'visible': True, "className": 'id'},
        {'name': 'quantity', 'orderable': True, 'visible': True, 'title': 'تعداد', 'className': 'quantity'},
        {'name': 'buy_factor_quantity_in_sepidar', 'orderable': True, 'visible': True, 'title': '<div class="px-0">تعداد در<br>فاکتور خرید</div>', 'className': 'buy_factor_quantity_in_sepidar'},
        {'name': 'item', 'orderable': True, 'title': 'کد کالا', 'visible': True, 'lookup_field': '__sku__icontains', 'className': 'item'},
        {'name': 'item__sepidar_id_0', 'visible': True, 'className': 'itemref d-none'},
        {'name': 'item__part_number', 'orderable': True, 'title': 'نام کالا', 'visible': True,
         'lookup_field': '__icontains', 'className': 'partnumber'},
        {'name': 'qi__quotation__id', 'orderable': True, 'title': 'پیش فاکتور', 'visible': True,
         'lookup_field': '__icontains'},
        {'name': 'creator_user', 'title': 'ایجاد کننده', 'visible': True, 'orderable': True,
         'lookup_field': '__username__icontains'},
        {'name': 'created_date', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'description_sale', 'orderable': True, 'visible': True, 'title': 'توضیحات'},
        {'name': 'buy_factor', 'orderable': False, 'visible': True, 'title': '<div class="px-0">فاکتور خرید</div>', },
    ]

    def get_initial_queryset(self, request=None):
        qs = self.model.objects.filter(is_bazar=False, is_deleted=False, is_wh=False).filter(
            Q(buy_factor_quantity_in_sepidar__lt=F('quantity')) | Q(buy_factor_quantity_in_sepidar__isnull=True)
        )
        return qs

    def customize_row(self, row, obj):
        from tools.utils import to_jalali_date
        row['created_date'] = to_jalali_date(obj.created_date)
        row['item__sepidar_id_0'] = obj.item.sepidar_id_0
        row['order_method'] = f'<span>{obj.order_method}</span>'
        row['item__part_number'] = f'<span>{obj.item.part_number}</span>' if obj.item else ""
        row['qi__quotation__customer_party_id'] = f'<span>{obj.qi.quotation.customer_party_id.title}</span>' if obj.qi else ""
        row['qi__quotation__id'] = f'<span>{obj.qi.quotation.id}</span>' if obj.qi else ""
        row['estimated_arrive_date'] = obj.estimate_arrive_at
        row['buy_factor'] = '<span class="fw-bold p-3 cursor-pointer font-size-20 action" onclick="bazar_buy_factor(event);calculate_price()" >➕</span>'


class BazarOrderView(LoginRequiredMixin, BaseView):
    template_name = 'order/bazar_create_update_view.html'
    form_class = BazarOrderForm
    model = OrderBazar
    form_struct = {
        'form': BazarOrderForm,
        'childes': [
            {},
        ]
    }
    # flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'OrderView')

    def get_success_url(self):
        return reverse_lazy('order:bazar.order.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class BazarOrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'order/bazar_list.html'


class OrderAction(ListView):
    model = Order
    template_name = 'order/order_action.html'
    paginate_by = 50

    def get_queryset(self):
        x = Order.objects.filter(order_base_items__isnull=False).distinct()
        return x

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context['forms'] = []
        for o in context['object_list']:
            f = OrderForm(instance=o)
            context['forms'].append(f)
        context['form'] = True
        return context


def ajax_order_order_add(request):
    import json
    data = json.loads(request.body)
    data['creator_user'] = request.user
    data['editor_user'] = request.user
    quantity = data.get('quantity')
    obj, created = OrderOrder.objects.get_or_create(defaults=data, order_base_id=data.get('order_base_id'), order_rel_id=data.get('order_rel_id'))
    if quantity and not created:
        obj.quantity += quantity
        obj.save()
    form = OrderForm(instance=obj.order_base)
    html = render_to_string('order/partial/order_order_report.html', context={'form': form})
    return JsonResponse({'res': html})


class PackingView(LoginRequiredMixin, BaseView):
    template_name = 'order/packing_view.html'
    form_class = PackingForm
    model = Packing
    wf_last_step_is_open = True
    has_flow = True
    success_message = 'با موفقیت ذخیره شد'
    form_struct = {
        'form': PackingForm,
        'childes': [
            {
                'form': PackingItemForm,
                'childes': [{}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'PackingView')

    def get_success_url(self):
        return reverse_lazy('order:packing.update', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        context['wf_access'] = self.wf_access
        context['packing_items'] = self.object.packing_item_rel.all if self.object else None
        context['state_index'] = self.state_index
        return context


class packing_list_form(LoginRequiredMixin, BaseView):
    template_name = 'order/packing_item_form.html'
    form_class = PackingItemForm
    model = PackingItem
    # wf_last_step_is_open = True
    # has_flow = False
    form_struct = {
        'form': PackingItemForm,
        'childes': [
            {},
        ]
    }
    # flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'PackingView')

    def get_success_url(self):
        return reverse_lazy('order:packingitem.update', kwargs={'pk': self.object.packing.pk})

    def post(self, request, *args, **kwargs):
        x = super().post(request, *args, **kwargs)
        if is_ajax(request):
            return JsonResponse({'res': 'success'})
        else:
            return x

    def form_valid(self, form):
        x = super().form_valid(form)
        return JsonResponse({'res': True})

    def get(self, request, pk=None, *args, **kwargs):
        if is_ajax(request):
            # packing = Packing.objects.filter(pk=self.request.GET.get('pk')).first()
            # form = PackingItemForm(initial={'packing': packing or self.object.packing}, instance=self.object)
            # context = self.get_context_data()
            # context = {}
            # context['form'] = form
            res = render_to_string(self.template_name, context=self.get_context_data())
            return JsonResponse({'res': res})
        return JsonResponse({'res': 'only ajax request'})

    def get_context_data(self, **kwargs):
        context = {}
        # context = super().get_context_data(**kwargs)
        packing = Packing.objects.filter(pk=self.request.GET.get('pk')).first()
        form = PackingItemForm(initial={'packing': packing or self.object.packing, 'request': self.request}, instance=self.object)
        context['app_name'] = self.request.resolver_match.app_name
        context['form'] = form
        return context


class PackingListView(LoginRequiredMixin, ListView):
    """
    sku list view
    """
    model = Packing
    template_name = 'order/packing_list.html'
    context_object_name = 'items'


class PackingDataTableListView(AjaxDatatableView):
    model = Packing
    title = 'packing'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'visible': False, 'title': "packing_id", 'className': 'py-1', },
        {'name': 'pk', 'visible': True, 'title': _('id'), 'className': 'py-1', },
        # {'name': 'packing', 'visible': True, 'title': 'packing_id', 'className': 'py-1', },
        {'name': 'carton_qty', 'visible': True, 'title': "Carton Qty", 'className': 'py-1', },
        {'name': 'weight', 'visible': True, 'title': "weight(KG)", 'className': 'py-1', },
        {'name': 'packing_number', 'visible': True, 'title': "packing_no", 'className': 'py-1', },
        {'name': 'created_date', 'visible': True, 'title': "pack_date", 'className': 'py-1', },
        {'name': 'shipment_type', 'visible': True, 'title': "shipment type", 'className': 'py-1', },
        {'name': 'bl_number', 'title': "BL Number", 'className': 'py-1', },
        {'name': 'departure_date', 'title': "<div style='width:100px:'>Departure from origin port Date</div>", 'className': 'py-1', },
        {'name': 'arrival_date', 'title': "Arrival to destination port Date", 'className': 'py-1', },
        {'name': 'sales_manager_needed', 'title': "Sales manager Needed", 'className': 'py-1', },
        {'name': 'sales_manager_check_date', 'title': "Sales manager check Date", 'className': 'py-1', },
        {'name': 'delivery_to_salehi_date', 'title': "Delivered to Mr Salehi Date", 'className': 'py-1', },
        {'name': 'cl_90_date', 'title': "Clearance Date 90%", 'className': 'py-1', },
        {'name': 'cl_10_date', 'title': "Clearance Date 10%", 'className': 'py-1', },
        {'name': 'cl_100_date', 'title': "Clearance Date 100%", 'className': 'py-1', },
        {'name': 'arrive_to_wh_date', 'title': "Arrive to wherehouse Date", 'className': 'py-1', },
        {'name': 'estimated_delivery_date', 'title': "Est Delivery Date", 'className': 'py-1', },
        {'name': 'creator_user', 'title': _('creator_user'), 'className': 'py-1', },
    ]

    def customize_row(self, row, obj):
        row['pk'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('order:packing.update', args=(obj.id,)),
            obj.id if obj.id else 'بدون عنوان'
        )
        row['carton_qty'] = f'{obj.computed_carton_qty}' if obj.computed_carton_qty else '-'
        row['weight'] = f'{obj.computed_weight_kg}' if obj.computed_weight_kg else '-'


class GIOView(LoginRequiredMixin, BaseView):
    template_name = 'order/gio_view.html'
    form_class = GIOForm
    model = GIO
    # wf_last_step_is_open = True
    # has_flow = True
    success_message = 'با موفقیت ذخیره شد'
    form_struct = {
        'form': GIOForm,
        'childes': [
            {
                'form': GIOItemForm
            },
        ]
    }
    # flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'GIOView')

    def get_success_url(self):
        return reverse_lazy('order:gio.update', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        # if is_ajax(self.request):
        #     res = json.loads(self.request.body)
        #     # kwargs['quantity'] = res['quantity']
        #     # kwargs['gio_date'] = res['gio_date']
        #     # kwargs['description'] = res['description']
        #     self.request.POST._mutable = False
        #     request.POST = res
        #     self.request.POST._mutable = True
        #     return super().post(request, *args, **kwargs)

        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class GIOItemView(LoginRequiredMixin, BaseView):
    template_name = 'order/gio_item.html'
    form_class = GIOItemForm
    model = GIOItem
    form_struct = {
        'form': GIOItemForm,
        'childes': [
            {},
        ]
    }

    def get_success_url(self):
        return reverse_lazy('order:gio.update', kwargs={'pk': self.object.gio.pk})

    def post(self, request, *args, **kwargs):
        order_id = self.request.POST.get('order')
        part_number = self.request.POST.get('part_number')
        gio_id = self.request.POST.get('gio')
        quantity = float(self.request.POST.get('quantity', 0))
        if order_id:
            order = Order.objects.filter(pk=order_id).first()

            order_quantity = order.final_quantity

            if quantity > order_quantity:
                messages.error(request, f'تعداد انتخابی در GIO نمیتواند بیشتر از تعداد ثبت شده در سفارش باشد. {quantity} > {order.final_quantity}')
                return JsonResponse({'res': 'fail'})

            if not self.object and GIOItem.objects.filter(order=order_id, gio_id=gio_id).exists():
                messages.error(request, f'سفارش {order_id} قبلا در این GIO ثبت شده است')
                return JsonResponse({'res': 'fail'})

            gio_items = GIOItem.objects.filter(order_id=order_id).exclude(gio_id=gio_id)

            if gio_items:
                order_quantity_in_gio_items = gio_items.aggregate(sum_quantity=Sum('quantity'))['sum_quantity']
                if quantity > (order.final_quantity - order_quantity_in_gio_items):
                    messages.error(request, f'''تعداد {order_quantity_in_gio_items} عدد از سفارش {order_id} در GIO(ها)ی {"و ".join([mark_safe(f"<a href={reverse('order:gio.update', kwargs={'pk': x.gio.pk})}>{x.gio.pk}</a>") for x in gio_items])} ثبت شده است''')
                    return JsonResponse({'res': 'fail'})

            x = super().post(request, *args, **kwargs)
            if is_ajax(request):
                return JsonResponse({'res': 'success'})
            else:
                return x
        else:
            x = super().post(request, *args, **kwargs)
            if is_ajax(request):
                return JsonResponse({'res': 'success'})
            else:
                return x

    def form_valid(self, form):
        x = super().form_valid(form)
        return JsonResponse({'res': True})

    def get(self, request, pk=None, *args, **kwargs):
        if is_ajax(request):
            context = self.get_context_data()
            res = render_to_string(self.template_name, context=context)
            return JsonResponse({'res': res})
        return JsonResponse({'res': 'only ajax request'})

    def get_context_data(self, **kwargs):
        context = {}
        gio = GIO.objects.filter(pk=self.request.GET.get('pk')).first()
        form = self.form_class(initial={'gio': gio or self.object.gio}, instance=self.object)
        context['app_name'] = self.request.resolver_match.app_name
        context['form'] = form
        return context


class GIOListView(LoginRequiredMixin, View):
    """
    sku list view
    """
    # model = Packing
    template_name = 'order/gio_list.html'
    context_object_name = 'items'

    def get(self, request, *args, **kwargs):
        context = {}
        return render(request, self.template_name, context)


class GIODataTableListView(AjaxDatatableView):
    model = GIO
    title = 'GIO'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'visible': False, 'title': _('id'), 'className': 'py-1',},
        {'name': 'pk', 'visible': True, 'title': _('id'), 'className': 'py-1',},
        {'name': 'gio_date', 'visible': True, 'title': _('gio_date'), 'className': 'py-1',},
        {'name': 'gioitems__order', 'visible': True, 'title': _('Order'), 'className': 'py-1'},
        {'name': 'creator_user', 'title': _('creator_user'), 'className': 'py-1', },
        {'name': 'created_date', 'orderable': True, 'visible': True, },
    ]

    def get_initial_queryset(self, request=None):
        qs = self.model.objects.all()
        q = self.request.POST.get('q')
        if q == 'all':
            return qs
        elif q == 'need_sku_approval':
            qs = self.model.objects.filter(gioitems__order__isnull=True, gioitems__part_number__isnull=False)
            return qs
        else:
            return qs


    def customize_row(self, row, obj):
        row['pk'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('order:gio.update', args=(obj.id,)),
            obj.id if obj.id else 'بدون عنوان'
        )
        order_ids = list(set(obj.gioitems.filter(order__isnull=False).values_list('order_id', flat=True)))
        order_links = [
            f'<a class="fw-bold" target=_blank href="{reverse("order:order.view", args=(order_id,))}">{order_id}</a>'
            for order_id in order_ids
        ]
        row['gioitems__order'] = ", ".join(order_links)


class PaymentView(LoginRequiredMixin, BaseView):
    template_name = 'order/payment_view.html'
    form_class = OrderPaymentForm
    model = OrderPayment
    wf_last_step_is_open = True
    has_flow = True
    has_formset = True
    formset_form = OrderPaymentItemFormSet
    formset_model = OrderPaymentItem
    formset_fk_field = 'payment'
    related_name_fk = 'payment_item'
    success_message = 'با موفقیت ذخیره شد'
    form_struct = {
        'form': OrderPaymentForm,
        'childes': [
            {
                'form': OrderPaymentItemFormSet,
                'childes': [{}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'PaymentView')

    def get_success_url(self):
        return reverse_lazy('order:order.payment.update', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        if self.object and self.object.sepidar_response:
            context['save_not_allowed'] = True
            context['not_allow_message'] = 'امکان ویرایش سندی که به سپیدار ارسال شده وجود ندارد'
        return context


class PaymentItemView(LoginRequiredMixin, BaseView):
    template_name = 'order/payment_item_view.html'
    form_class = OrderPaymentItemForm
    model = OrderPaymentItem
    form_struct = {
        'form': OrderPaymentItemForm,
        'childes': [
            {},
        ]
    }

    def get_success_url(self):
        return reverse_lazy('order:order.paymentitem.update', kwargs={'pk': self.object.payment.pk})

    def post(self, request, *args, **kwargs):
        x = super().post(request, *args, **kwargs)
        if is_ajax(request):
            return JsonResponse({'res': 'success'})
        else:
            return x

    def form_valid(self, form):
        x = super().form_valid(form)
        return JsonResponse({'res': True})

    def get(self, request, pk=None, *args, **kwargs):
        if is_ajax(request):
            context = self.get_context_data()
            res = render_to_string(self.template_name, context=context)
            return JsonResponse({'res': res})
        return JsonResponse({'res': 'only ajax request'})

    def get_context_data(self, **kwargs):
        context = {}
        payment = OrderPayment.objects.filter(pk=self.request.GET.get('pk')).first()
        form = self.form_class(initial={'payment': payment or self.object.payment}, instance=self.object)
        context['app_name'] = self.request.resolver_match.app_name
        context['form'] = form
        return context


class PaymentListView(LoginRequiredMixin, View):
    """
    sku list view
    """
    model = OrderPayment
    template_name = 'order/payment_list.html'
    context_object_name = 'items'

    def get(self, request, *args, **kwargs):
        context = {}
        return render(request, self.template_name, context)


class PaymentDataTableListView(AjaxDatatableView):
    model = OrderPayment
    title = 'Payment'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'order_payment_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'visible': False, 'title': _('id'), 'className': 'py-1',},
        {'name': 'pk', 'visible': True, 'title': _('id'), 'className': 'py-1',},
        # {'name': 'action', 'visible': True, 'title': _('action'), 'className': 'py-1', 'searchable': False},
        {'name': 'last_work_flow', 'visible': True, 'title': _('status'), 'className': 'py-1', 'lookup_field': '__current_state_name__icontains',},
        {'name': 'bank', 'visible': True, 'title': _('ACNT'), 'className': 'py-1', 'lookup_field': '__info_bank__icontains',},
        {'name': 'total_amount', 'title': _('total_amount'), 'className': 'py-1', },
        {'name': 'currency', 'visible': True, 'title': _('currency'), 'className': 'py-1', },
        {'name': 'exchange_rate', 'title': _('exchange_rate'), 'className': 'py-1', },
        {'name': 'orders', 'orderable': True, 'visible': True, 'title': _('orders'),},
        {'name': 'description', 'orderable': True, 'visible': True, },
        {'name': 'creator_user', 'orderable': True, 'visible': True, 'title': _('creator_user'), 'lookup_field': '__profile__first_name__icontains'},
        {'name': 'editor_user', 'orderable': True, 'visible': True, 'title': _('editor_user'), 'lookup_field': '__profile__first_name__icontains'},
        {'name': 'created_date', 'orderable': True, 'visible': True, },
    ]

    def customize_row(self, row, obj):
        row['pk'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('order:order.payment.update', args=(obj.id,)),
            obj.id if obj.id else 'بدون عنوان'
        )

        row['orders'] = ', '.join([str(x.order.pk) for x in obj.payment_item.all()])


class PaymentItemListView(LoginRequiredMixin, View):
    """
    sku list view
    """
    model = OrderPaymentItem
    template_name = 'order/payment_item_list.html'
    context_object_name = 'items'

    def get(self, request, *args, **kwargs):
        context = {}
        return render(request, self.template_name, context)


class PaymentItemDataTableListView(AjaxDatatableView):
    model = OrderPaymentItem
    title = 'PaymentItem'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'visible': False, 'title': _('id'), 'className': '', },
        {'name': 'pk', 'visible': True, 'title': _('id'), 'className': '', },
        {'name': 'order__order_number', 'visible': True, 'title': 'Order-NO', 'className': '', },
        {'name': 'created_date', 'visible': True, 'title': 'Date', 'className': '', },
        {'name': 'order__supplier_trade', 'visible': True, 'title': 'Supplier', 'className': '', 'lookup_field': '__title__icontains', },
        {'name': 'order__po_number_trade', 'visible': True, 'title': 'PO NO.', 'lookup_field': '__icontains', 'searchable': True},
        {'name': 'order__transportation_method', 'visible': True, 'title': 'EXP', },
        {'name': 'order__item', 'visible': True, 'title': 'Part NO.', 'lookup_field': '__part_number__icontains'},
        {'name': 'order__quantity_trade', 'visible': True, 'title': 'QTY', 'className': '', },
        {'name': 'order__price_trade', 'visible': True, 'title': 'Price', 'className': '', },
        {'name': 'order_total_price', 'visible': True, 'title': 'Total', 'className': '', },

        # {'name': 'destination_currency', 'visible': True, 'title': 'Destination Currency', 'className': '', },
        {'name': 'payment__currency', 'visible': True, 'title': 'Destination Currency', 'className': '', 'lookup_field': '__title__icontains',  },
        {'name': 'order__currency', 'visible': True, 'title': 'Currency', 'className': '', 'lookup_field': '__title__icontains', },
        {'name': 'exchange_rate', 'visible': True, 'title': 'Rate', 'className': '', },
        {'name': 'total_amount', 'visible': True, 'title': 'Amount', 'className': '', },
        {'name': 'from_date', 'visible': True, 'title': 'Pay Date', 'className': '', },
        {'name': 'bank', 'visible': True, 'title': 'Bank Info', 'className': '', },
        {'name': 'paid_amount', 'visible': True, 'title': '<div class="px-8">Paid Amount</div>', 'className': '', },
        {'name': 'reference', 'visible': True, 'title': 'Reference', 'className': '', },
        {'name': 'attachment', 'visible': True, 'title': '<div class="px-6">Files</div>', 'className': '', },
        {'name': 'action', 'visible': True, 'title': '<div class="px-8">Action</div>', 'className': '', },
    ]

    def get_initial_queryset(self, request=None):
        payment_pk: str = self.request.POST.get('q')
        if payment_pk.isdigit():
            qs = self.model.objects.filter(payment=payment_pk)
        else:
            qs = self.model.objects.all()
        return qs

    def customize_row(self, row, obj):
        row['order__order_number'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('order:order.paymentitem.update', args=(obj.id,)),
            obj.order.order_number if obj.order else '_'
        )
        row['payment__currency'] = f'{obj.payment.currency}' if obj.payment else '_'
        row['order__supplier_trade'] = f'{obj.order.supplier_trade}' if obj.order.supplier_trade else '_'

        row['order__po_number_trade'] = f'{obj.order.po_number_trade}' if obj.order.po_number_trade else '_'

        row['order__transportation_method'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('order:order.paymentitem.update', args=(obj.id,)),
            obj.order.transportation_method if obj.order else '_'
        )

        row['order__item'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('order:order.paymentitem.update', args=(obj.id,)),
            obj.order.item.part_number if obj.order.item else '_'
        )

        row['order__quantity_trade'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('order:order.paymentitem.update', args=(obj.id,)),
            obj.order.quantity_trade if obj.order else '_'
        )

        row['order__price_trade'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('order:order.paymentitem.update', args=(obj.id,)),
            obj.order.price_trade if obj.order else '_'
        )

        row['order_total_price'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('order:order.paymentitem.update', args=(obj.id,)),
            round(obj.order.total_price, 4) if obj.order else '_'
        )

        row['order__currency'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('order:order.paymentitem.update', args=(obj.id,)),
            obj.order.currency if obj.order else '_'
        )

        row['paid_amount'] = f'{obj.total_amount/obj.exchange_rate:0.5f}'
        row['reference'] = '111'

        row['attachment'] = ""
        for file in obj.files.all():
            row['attachment'] += f"""<a href="{file.path.url}" class="me-2" target="_blank"><i class="fas fa-file-upload icon-lg fs-4"></i></a>"""

        row['action'] = f"""
            <span>
                <a href="#" target="_blank" class="edit-payment-item tooltip_" onclick="edit_with_modal(this)" data-url="{ reverse('order:order.paymentitem.update', kwargs={'pk': obj.pk})}" data-bs-toggle="modal" data-bs-target="#id_kt_empty_modal_lg">
                    <span class="tooltiptext">ویرایش</span>
                    <i class="ki-duotone ki-pencil fs-3 text-info">
                        <span class="path1"></span>
                        <span class="path2"></span>
                    </i>
                </a>
                <a class="tooltip_ cursor-pointer" onclick="change_log_with_modal(this)"
                    data-bs-toggle="modal"
                    data-bs-target="#id_kt_empty_modal_lg"
                    data-model_name="{self.model.__name__}"
                    data-object_id="{obj.pk}"
                    data-app_name="{self.request.resolver_match.app_name}"
                    name="name_change_log">
                    <span class="tooltiptext">تاریخچه تغییرات</span>
                    <i class="ki-duotone ki-book-open fs-3 text-primary">
                     <span class="path1"></span>
                     <span class="path2"></span>
                     <span class="path3"></span>
                     <span class="path4"></span>
                    </i>
                </a>
                <a href="#" target="_blank" class="me-3 delete-payment-item text-danger tooltip_" onclick="delete_with_modal(this)" data-url="{reverse('core:delete.confirm')}?model={self.model.__name__}&object_id={obj.pk}&app_label={self.request.resolver_match.app_name}" data-bs-toggle="modal" data-bs-target="#id_kt_empty_modal_sm">
                    <span class="tooltiptext">حذف</span>
                    <i class="ki-duotone ki-trash fs-3 text-danger">
                        <span class="path1"></span>
                        <span class="path2"></span>
                        <span class="path3"></span>
                        <span class="path4"></span>
                        <span class="path5"></span>
                    </i>
                </a>
            </span>
        """


class CustomerRequestOrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasShopPermission]
    queryset = Order.objects.all().order_by('-created_date')
    serializer_class = OrderSerializer
    http_method_names = ['get']

    @action(detail=False, methods=['get'], url_path='by-request/(?P<customer_request_id>[^/.]+)')
    def list_by_request(self, request, customer_request_id=None):
        queryset = self.get_queryset().filter(customer_request_item_id=customer_request_id)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        return JsonResponse({'detail': 'url with "pk" required'})


class OrderAndSepidar(View):
    valid_view = ('trade_buy_factor', 'new_bazar_buy_factor', 'bazar_buy_factor', 'payment_for_order_to_sepidar', 'wh_to_wh_preview', 'wh_to_wh_execute')
    valid_for_get = ('trade_buy_factor_preview', 'payment_for_order_to_sepidar_preview', 'wh_to_wh_preview')

    def dispatch(self, request, *args, **kwargs):
        view_name = self.request.GET.get('view_name')
        if self.request.method != 'POST' and view_name not in self.valid_for_get:
            return HttpResponseNotAllowed(["POST"])

        if view_name and (view_name in self.valid_view or view_name in self.valid_for_get):
            return getattr(self, view_name)(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        from tools import utils
        try:
            body = self.request.body or '{}'
            data = json.loads(body)
            grouped = utils.grouped_value(data, target_suffixes=('portal_order_id', '-quantity', '-itemref'))
            res = SepidarApiCall.buy_factor_to_sepidar(obj=data, request=self.request)
            if hasattr(res, 'errors'):
                # messages.error(self.request, res.get('errors'))
                return JsonResponse({'res': 'fail'})

            elif res and res.get('valid'):
                buy_factor_number = res.get('number')
                buy_factor_id = res.get('buy_factor_id')
                lookup = {(x[1].get('itemref'), x[1].get('quantity')): x[1] for x in grouped.items() if x[0] != '0'}
                """
                lookup output like this:
                lookup = {
                    (itemref, quantity): {itemref:'x', 'portal_order_id': 'y', 'quantity': 'z'}
                }
                """
                buy_factor_items = {key: value for x in res.get('buy_factor_items') for key, value in x.items()}
                for key, value in lookup.items():
                    buy_factor_item = buy_factor_items.get(key)
                    inventory_purchase_invoice_item_id = buy_factor_item.get('inventory_purchase_invoice_item_id')
                    order_pk = value.get('portal_order_id')
                    o = Order.objects.filter(pk=order_pk).first()
                    o.buy_factors.append({str((buy_factor_id, buy_factor_number)): (inventory_purchase_invoice_item_id, key[1])})
                    o.buy_factor_quantity_in_sepidar = (o.buy_factor_quantity_in_sepidar or 0) + int(key[1])
                    o.editor_user = self.request.user
                    o.save()
                new_btn = """
                <button 
                    type="button" 
                    id="submit-buy-factor" 
                    class="btn btn-secondary mt-5 me-5"
                    onclick="window.location.href = window.location.href">
                    جدید
                </button>
                """
                return JsonResponse({'res': f'<span class="ms-3"><span class="bg-success text-white rounded p-2">فاکتور خرید به سپیدار ارسال شد، کد: {buy_factor_number}</span></span> <a href="/order/bazar/buy_factor/view/?" class="btn btn-sm btn-primary">جدید</a>'}, status=201)
            else:
                return JsonResponse({'res': res}, status=400)
        except Exception as e:
            return JsonResponse({'res': {"error": e.args[0]}}, status=400)

    def trade_buy_factor_preview(self, request, *args, **kwargs):
        gio_id = self.request.GET.get('gio_id')
        gio = GIO.objects.get(pk=gio_id)
        buy_factor_contex = {}
        html = render_to_string('order/partial/sepidar/trade_buy_factor_preview.html', context=buy_factor_contex)

        return JsonResponse({'res': html})

    def trade_buy_factor(self, request, *args, **kwargs):
        """ from GIO generate
            1: `buy factor`
            2: `inventory_receipt_before_central_wh`
            3: `voucher`
            in sepidar
        """
        try:
            from tools import utils
            gio_id = json.loads(self.request.body or '{}').get('gio_id')
            gio_object = GIO.objects.filter(pk=gio_id).first()
            if not gio_object:
                return

            gio_items = gio_object.gioitems.all()
            if not gio_items:
                return

            gio_items_group_by_supplier_and_currency = dict()

            supplier_currency_list = []
            for gioi in gio_items:
                if 'rmb' in gioi.order.currency.title_en.lower() or "یوآن" in gioi.order.currency.title.lower():
                    currency_name = 'rmb'
                elif 'ero' in gioi.order.currency.title_en.lower() or "یورو" in gioi.order.currency.title.lower():
                    currency_name = 'ero'
                elif 'usd' in gioi.order.currency.title_en.lower() or "دلار" in gioi.order.currency.title.lower():
                    currency_name = 'usd'

                key1 = gioi.order.final_supplier.dlref or settings.SEPIDAR_CONST_DATA.get(f'no_name_vendor_{currency_name}')
                key2 = gioi.order.currency.sepidar_id

                final_key = f'{key1}___{key2}'
                supplier_currency_list.append(final_key)
                gio_items_group_by_supplier_and_currency.setdefault(final_key, []).append(gioi)

            res = SepidarApiCall.gio_to_sepidar(gio_items_group_by_supplier_and_currency, request)

            if res.get('errors'):
                return JsonResponse(res, status=500)

            for supplier_currency in supplier_currency_list:
                gio_res = res.get(supplier_currency)
                if gio_res:
                    grouped_gioi = gio_items_group_by_supplier_and_currency.get(supplier_currency)
                    for gio_item in grouped_gioi:

                        if SepidarOrderDocument.objects.filter(order=gio_item.order).exists():
                            order_document_obj = SepidarOrderDocument.objects.get(order=gio_item.order)
                            data = order_document_obj.data
                            data['gio']['sepidar'].append(gio_res['gio']['sepidar'][0])
                            order_document_obj.data = data
                            order_document_obj.save()
                        else:
                            SepidarOrderDocument.objects.create(order=gio_item.order, data=gio_res)

            gio_json_response = {"purchase_invoice":[], "before_central_wh_receipt":[], "voucher":[]}
            for supplier_currency, gio_res in res.items():
                purchase_invoice = gio_res['gio']['sepidar'][0]['purchase_invoice']['id']
                before_central_wh_receipt = gio_res['gio']['sepidar'][0]['before_central_wh_receipt']['id']
                voucher = gio_res['gio']['sepidar'][0]['voucher']['id']
                gio_json_response['purchase_invoice'].append(purchase_invoice)
                gio_json_response['before_central_wh_receipt'].append(before_central_wh_receipt)
                gio_json_response['voucher'].append(voucher)

            gio_object.sepidar_buy_factor_response_json = gio_json_response
            # gio_object.sepidar_inventory_receipt_response_json = wh_res
            gio_object.extra_data.request = self.request
            gio_object.save()

            return JsonResponse({'res': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def bazar_buy_factor(self, request, *args, **kwargs):
        from tools import utils
        try:
            body = self.request.body or '{}'
            data = json.loads(body)
            grouped = utils.grouped_value(data, target_suffixes=('portal_order_id', '-quantity', '-itemref'))
            res = SepidarApiCall.buy_factor_to_sepidar(obj=data, request=self.request)
            if hasattr(res, 'errors'):
                # messages.error(self.request, res.get('errors'))
                return JsonResponse({'res': 'fail'})

            elif res and res.get('valid'):
                buy_factor_number = res.get('number')
                buy_factor_id = res.get('buy_factor_id')
                lookup = {(x[1].get('itemref'), x[1].get('quantity')): x[1] for x in grouped.items() if x[0] != '0'}
                """
                lookup output like this:
                lookup = {
                    (itemref, quantity): {itemref:'x', 'portal_order_id': 'y', 'quantity': 'z'}
                }
                """
                buy_factor_items = {key: value for x in res.get('buy_factor_items') for key, value in x.items()}
                for key, value in lookup.items():
                    buy_factor_item = buy_factor_items.get(key)
                    inventory_purchase_invoice_item_id = buy_factor_item.get('inventory_purchase_invoice_item_id')
                    order_pk = value.get('portal_order_id')
                    o = Order.objects.filter(pk=order_pk).first()
                    o.buy_factors.append(
                        {str((buy_factor_id, buy_factor_number)): (inventory_purchase_invoice_item_id, key[1])})
                    o.buy_factor_quantity_in_sepidar = (o.buy_factor_quantity_in_sepidar or 0) + int(key[1])
                    o.editor_user = self.request.user
                    o.save()

                return JsonResponse({
                                        'res': f'<span class="ms-3"><span class="bg-success text-white rounded p-2">فاکتور خرید به سپیدار ارسال شد، کد: {buy_factor_number}</span></span> <a href="/order/bazar/buy_factor/view/?" class="btn btn-sm">جدید</a>'},
                                    status=201)
            else:
                return JsonResponse({'res': res}, status=400)
        except Exception as e:
            return JsonResponse({'res': {"error": e.args[0]}}, status=400)

    def new_bazar_buy_factor(self, request, *args, **kwargs):
        from tools import utils
        try:
            body = self.request.body or '{}'
            data = json.loads(body)
            grouped = utils.grouped_value(data, target_suffixes=('portal_order_id', '-quantity', '-itemref'))
            res = SepidarApiCall.buy_factor_to_sepidar(obj=data, request=self.request)
            if hasattr(res, 'errors'):
                # messages.error(self.request, res.get('errors'))
                return JsonResponse({'res': 'fail'})

            elif res and res.get('valid'):
                buy_factor_number = res.get('number')
                buy_factor_id = res.get('buy_factor_id')
                lookup = {(x[1].get('itemref'), x[1].get('quantity')): x[1] for x in grouped.items() if x[0] != '0'}
                """
                lookup output like this:
                lookup = {
                    (itemref, quantity): {itemref:'x', 'portal_order_id': 'y', 'quantity': 'z'}
                }
                """
                buy_factor_items = {key: value for x in res.get('buy_factor_items') for key, value in x.items()}
                for key, value in lookup.items():
                    buy_factor_item = buy_factor_items.get(key)
                    inventory_purchase_invoice_item_id = buy_factor_item.get('inventory_purchase_invoice_item_id')
                    order_pk = value.get('portal_order_id')
                    o = OrderBazar.objects.filter(pk=order_pk).first()
                    o.buy_factors.append(
                        {str((buy_factor_id, buy_factor_number)): (inventory_purchase_invoice_item_id, key[1])})
                    o.buy_factor_quantity_in_sepidar = (o.buy_factor_quantity_in_sepidar or 0) + int(key[1])
                    o.editor_user = self.request.user
                    o.save()

                return JsonResponse({
                                        'res': f'<span class="ms-3"><span class="bg-success text-white rounded p-2">فاکتور خرید به سپیدار ارسال شد، کد: {buy_factor_number}</span></span> <a href="/order/bazar/buy_factor/view/?" class="btn btn-sm btn-primary">جدید</a>'},
                                    status=201)
            else:
                return JsonResponse({'res': res}, status=400)
        except Exception as e:
            return JsonResponse({'res': {"error": e.args[0]}}, status=400)

    def payment_for_order_to_sepidar_preview(self, request, *args, **kwargs):
        context = dict()

        payment_id = self.request.GET.get('payment_id')
        payment = OrderPayment.objects.get(pk=payment_id)
        currency_for_orders = [x.order.currency for x in payment.payment_item.all()]

        groups = OrderedDict()
        for item in payment.payment_item.all():
            item.rate = Dl.account_currency_rate(item.order.final_supplier.dlref,
                                                 settings.SEPIDAR_CONST_DATA.get('fiscalyearref'),
                                                 settings.SEPIDAR_CONST_DATA.get('hesab_pardakhtani'),
                                                 payment.currency.sepidar_id
                                                 )
            groups.setdefault(item.order.currency, []).append(item)

        context['groups'] = list()
        if len(groups.values()) != 1:
            return JsonResponse({'res': 'نوع ارز انتخابی در سفارش ها متفاوت است'})

        for g in groups.values():
            print(g)
            context['groups'].append(g)

        context['payment'] = payment

        html = render_to_string('order/partial/sepidar/payment_for_order_to_sepidar_preview.html', context=context)

        return JsonResponse({'res': html})

    def payment_for_order_to_sepidar(self, request, *args, **kwargs):
        from tools import utils
        payment_id = self.request.GET.get('payment_id')
        payment = OrderPayment.objects.get(pk=payment_id)
        context = dict()

        groups = OrderedDict()
        for item in payment.payment_item.all():
            groups.setdefault(item.order.currency, []).append(item)

        context['groups'] = list()
        for g in groups.values():
            print(g)
            context['groups'].append(g)
            res = SepidarApiCall.payment_to_sepidar(g, self.request)
            if res[0]:
                payment.sepidar_response = res[1]
                payment.save()
            else:
                context['payment'] = payment
                context['errors'] = res[1]

                html = render_to_string('order/partial/sepidar/payment_for_order_to_sepidar_response.html',
                                        context=context)

                return JsonResponse({'res': html})


        context['payment'] = payment

        html = render_to_string('order/partial/sepidar/payment_for_order_to_sepidar_response.html', context=context)

        return JsonResponse({'res': html})

    def wh_to_wh_preview(self, request, *args, **kwargs):
        context = dict()

        packing_id = self.request.GET.get('packing_id')
        context['packing'] = Packing.objects.get(pk=packing_id)
        context['packing_items'] = PackingItem.objects.filter(packing_id=packing_id)
        html = render_to_string('order/partial/sepidar/wh_to_wh_preview.html', context=context)

        return JsonResponse({'res': html})

    def wh_to_wh_execute(self, request, *args, **kwargs):
        """ from packing in wh state generate
         1: Inventorydelivery
         2: Inventoryreceipt
         to sepidar
         """
        packing_id = self.request.GET.get('packing_id')
        packing = Packing.objects.get(pk=packing_id)

        # res = SepidarApiCall.wh_to_wh(packing, request)
        res = SepidarApiCall.packing(packing, request)

        try:
            if res.get('errors'):
                return JsonResponse({"res": res['errors']}, status=500)
            else:
                packing.sepidar_wh_to_wh = res['packing']['sepidar'][0]
                for packing_item in packing.packing_item_rel.all():
                    order_ = packing_item.order

                    """
                    پیدا کردن همه سفارش های میانی که از سفارش فعلی تامین میشوند 
                    و آپدیت کردن فیلد کد انبار سپیدار که یعنی سفارش تامین کننده در انبار رسید شده
                     و همه سفارش هایی که از آن تامین میشدند الان در انبار هستند
                    """
                    oo_queryset = OrderOrder.objects.filter(order_rel=order_)
                    if oo_queryset:
                        oo_queryset.update(sepidar_wh_code=settings.SEPIDAR_CONST_DATA.get('central_wh_id'))

                        for oo in oo_queryset:
                            """
                            به ازای هر سفارشی که در جدول میانی از این سفارش تامین میشده
                             حساب میکنیم تعداد کل تامین شده ها اگر برابر با تعداد مورد نیاز در خود همان سفارش بود
                              پس آن سفارش در انبار رسید شده و آپدیت میشود
                            """
                            o = oo.order_base
                            sum_supply_order_quantity = OrderOrder.objects.filter(order_base=o, sepidar_wh_code__isnull=False).aggregate(sum_quantity=Sum('quantity'))['sum_quantity'] or 0
                            if sum_supply_order_quantity == o.quantity:
                                o.is_wh = True
                                o.receipt_in_wh = True
                                o.sepidar_wh_code = settings.SEPIDAR_CONST_DATA.get('central_wh_id')
                                o.extra_data.request = request
                                o.save()

                    order_document = getattr(order_, 'sepidar_document', None)

                    """
                    اگر اصلا داکیومنت برای پکینگ وجود نداشت ایجاد میکنیم
                    اگر داکیومنت داشت اما پکینگ نداشت فقط کلید پکینگ را اضافه میکنیم
                    اگر داکیومنت داشت و پکینگ هم داشت رکورد جدید را به لیست اضافه میکنیم یعنی این سفارش در بیش از یک پکینگ بوده و به سپیدار رفته
                    """
                    res['packing']['sepidar'][0]['wh_delivery']['quantity'] = packing_item.wh_receipt_quantity
                    res['packing']['sepidar'][0]['wh_receipt']['quantity'] = packing_item.wh_receipt_quantity
                    if not order_document:
                        SepidarOrderDocument.objects.create(order=order_, data=res)
                    elif order_document and not order_document.data.get('packing'):
                        order_document.data['packing'] = res['packing']['sepidar']
                    elif order_document and order_document.data.get('packing'):
                        order_document.data['packing'].append(res['packing']['sepidar'][0])

                    order_document.save()

                    order_.is_wh = True
                    order_.receipt_in_wh = True
                    order_.sepidar_wh_code = settings.SEPIDAR_CONST_DATA.get('central_wh_id')
                    order_.extra_data.request = self.request
                    order_.save()
                    packing.extra_data.request = self.request
                    packing.save()
        except Exception as e:
            return JsonResponse({"res": str(e)}, status=500)

        context = dict()
        context['packing'] = packing
        html = render_to_string('order/partial/sepidar/wh_to_wh_sepidar_response.html', context=context)

        return JsonResponse({'res': html})


class OrderOfFactor(BaseView):
    template = 'order/order_of_factors.html'
    model = Order

    def setup(self, request, *args, **kwargs):
        """Initialize attributes shared by all view methods."""
        if hasattr(self, "get") and not hasattr(self, "head"):
            self.head = self.get
        self.request = request
        self.args = args
        self.kwargs = kwargs
        self.flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'OrderView')
        if self.request.method == 'POST':
            try:
                self.object = Order.objects.get(pk=kwargs.get('pk'))
                self.state_index = self.get_flow_index(self.object)
            except Exception as e:
                print(e, e.__traceback__.tb_lineno)

    def dispatch(self, request, *args, **kwargs):
        if kwargs.get('pk') == '0':
            return self.list(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)
    
    def list(self, request, *args, **kwargs):
        orders = self.model.objects.filter(pk__gt=100)
        forms = []
        for order in orders:
            form = dict()
            self.flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'OrderView')
            self.state_index = self.get_flow_index(order)
            if order.cancel:
                form[order] = []
                m2m = order.order_m2m.distinct()
                for x in m2m:
                    oo = OrderOrder.objects.filter(order_base=order, order_rel=x,
                                                   is_deleted=False).first()
                    if not oo:
                        continue
                    x.oo = oo
                    x.flow_config = self.flow_config
                    x.state_pair = x.state(self.flow_config, self.get_flow_index(x), self.request, x)
                    form[order].append((OrderForm(instance=x), oo))
            else:
                order.state_pair = order.state(self.flow_config,
                                               self.get_flow_index(order),
                                               self.request, order)
                form = OrderForm(instance=order)

            forms.append(form)

        context = dict()
        context['factor_items'] = orders
        context['forms'] = forms
        context['access'] = True

        # if self.request.user == factor_items.first().creator_user or factor_items.first().creator_user in self.request.user.team.all():
        #     context['access'] = True

        return render(request, self.template, context)

        factor_items = (
            FactorItem.objects
            .select_related('supply_locations')
        )

        forms = []
        for fi in factor_items:
            form = dict()
            oo_list = list()
            if fi.supply_locations.cancel:
                form[fi.supply_locations] = []
                m2m = fi.supply_locations.order_m2m.distinct()
                for x in m2m:
                    oo = OrderOrder.objects.filter(order_base=fi.supply_locations, order_rel=x,
                                                   is_deleted=False).first()
                    if not oo:
                        continue
                    x.oo = oo
                    x.flow_config = self.flow_config
                    x.state_pair = x.state(self.flow_config, self.get_flow_index(x), self.request, x)
                    form[fi.supply_locations].append((OrderForm(instance=x), oo))
            else:
                fi.supply_locations.state_pair = fi.supply_locations.state(self.flow_config,
                                                                           self.get_flow_index(fi.supply_locations),
                                                                           self.request, fi.supply_locations)
                form = OrderForm(instance=fi.supply_locations)
            forms.append(form)

        context = dict()
        context['factor_items'] = factor_items
        context['forms'] = forms

        if self.request.user == factor_items.first().creator_user or factor_items.first().creator_user in self.request.user.team.all():
            context['access'] = True


        return render(request, self.template, context)

    def get(self, request, pk, *args, **kwargs):
        self.flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'OrderView')
        if '__' in pk:
            pk = pk.split('__')[1]
        else:
            pk = int(pk)
        factor_items = (
            FactorItem.objects
            .select_related('supply_locations')  # join با جدول Order
            .filter(factor_id=pk)
        )

        forms = []
        for fi in factor_items:
            form = dict()
            oo_list = list()
            if fi.supply_locations.cancel:
                form[fi.supply_locations] = []
                m2m = fi.supply_locations.order_m2m.distinct()
                for x in m2m:
                    oo = OrderOrder.objects.filter(order_base=fi.supply_locations, order_rel=x, is_deleted=False).first()
                    if not oo:
                        continue
                    x.oo = oo
                    x.flow_config = self.flow_config
                    x.state_pair = x.state(self.flow_config, self.get_flow_index(x), self.request, x)
                    form[fi.supply_locations].append((OrderForm(instance=x), oo))
            else:
                fi.supply_locations.state_pair = fi.supply_locations.state(self.flow_config, self.get_flow_index(fi.supply_locations), self.request, fi.supply_locations)
                form = OrderForm(instance=fi.supply_locations)
            forms.append(form)

        context = dict()
        context['factor_items'] = factor_items
        context['forms'] = forms

        if self.request.user == factor_items.first().creator_user or factor_items.first().creator_user in self.request.user.team.all():
            context['access'] = True

        return render(request, self.template, context)

    def delete_order_order(self):
        pair_quantity = int(float((self.data.get('pair_quantity', 0))))
        main_order_pk = int(float((self.data.get('main_order_pk', 0))))
        main_order = Order.objects.filter(pk=main_order_pk).first()
        order = Order.objects.filter(pk=self.pk).first()

        if order.is_wh and main_order.order_m2m.exists():

            oo = OrderOrder.objects.filter(order_base_id=main_order_pk, order_rel_id=self.pk).first()
            oo.is_deleted = True
            oo.extra_data.request = self.request
            oo.save()
            order.is_deleted = True
            order.extra_data.request = self.request
            order.save()
        else:
            oo = OrderOrder.objects.filter(order_base_id=main_order_pk, order_rel_id=self.pk).first()
            oo.is_deleted = True
            oo.extra_data.request = self.request
            oo.save()

        # form = OrderForm(instance=order_rel)
        # html = render_to_string('order/partial/order_of_factors_row.html', context={})

        return JsonResponse({'res': ""})

    def _go_next(self, obj):
        self.state_index = self.get_flow_index(obj)
        group_name = self.flow_config.get('flow_users_groups')[self.state_index]
        next_group_name = self.flow_config.get('flow_users_groups')[self.state_index + 1]
        flow_data = {
            "wf_status": 3,  # next
            "action": 'ایجاد',
            "flow_name": 'سفارش',
            "state": self.flow_config.get('flow_state_list')[self.state_index],
            "wf_description": 'ارسال به مرحله بعد از لیست محل تامین های فاکتور',
            "belong_to_group": group_name,
            "object_id": obj.pk,
            "content_type": ContentType.objects.get_for_model(obj),
            "creator_user": self.request.user,
            "editor_user": self.request.user,
            "from_user": obj.last_work_flow.to_user,
            "to_user": self.get_flow_user(next_group_name),
            "current_state_name": obj.current_state_name(self.flow_config, self.state_index + 1),
            "deadline": timezone.now() + timedelta(days=1)
        }
        wf = WorkFlow.objects.create(**flow_data)
        obj.last_work_flow = wf
        obj.save()
        pass

    def _go_back(self, obj):
        self.state_index = self.get_flow_index(obj)
        group_name = self.flow_config.get('flow_users_groups')[self.state_index]
        back_group_name = self.flow_config.get('flow_users_groups')[self.state_index - 1]
        flow_data = {
            "wf_status": 2,  # back
            "action": 'ایجاد',
            "flow_name": 'سفارش',
            "state": self.flow_config.get('flow_state_list')[self.state_index],
            "wf_description": 'عودت از لیست محل تامین های فاکتور',
            "belong_to_group": group_name,
            "object_id": obj.pk,
            "content_type": ContentType.objects.get_for_model(obj),
            "creator_user": self.request.user,
            "editor_user": self.request.user,
            "from_user": obj.last_work_flow.to_user,
            "to_user": self.get_flow_user(back_group_name),
            "current_state_name": obj.current_state_name(self.flow_config, self.state_index - 1),
            "deadline": timezone.now() + timedelta(days=1)
        }
        wf = WorkFlow.objects.create(**flow_data)
        obj.last_work_flow = wf
        obj.save()
        pass

    def wf_action(self, obj):
        if self.submit_action == 'next':
            return self._go_next(obj)
        elif self.submit_action == 'back':
            return self._go_back(obj)

    def post(self, request, pk, *args, **kwargs):
        self.flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'OrderView')
        self.state_index = self.get_flow_index(self.object)
        self.wh_code = None
        data = json.loads(self.request.body or {})
        self.data = data
        self.submit_action = self.data.get('submit_action')

        if '__' in pk:
            self.wh_code = int(pk.split('__')[1])
        else:
            self.pk = int(pk)

        if self.wh_code:
            """process wh oo"""
            pair_quantity = int(float((self.data.get('pair_quantity', 0))))
            main_order_pk = int(float((self.data.get('main_order_pk', 0))))
            main_order_obj = Order.objects.get(pk=main_order_pk)
            Order.objects.create({
                'item': main_order_obj.item
            })
            self.save_order_order()
        else:
            pair_quantity = int(float((self.data.get('pair_quantity', 0))))
            main_order_pk = int(float((self.data.get('main_order_pk', 0))))

            if self.data.get('submit_action', '') == 'delete':
                res = self.delete_order_order()
                return res

            if 'order_order' in self.data:
                res = self.save_order_order()
                main_order = res.get('main_order')
                oo = res.get('oo')
                order_rel = res.get('order_rel')
                self.wf_action(order_rel)
                order_rel.state_pair = order_rel.state(self.flow_config, self.get_flow_index(order_rel), self.request, order_rel)

                form = OrderForm(instance=order_rel)
                html = render_to_string('order/partial/order_of_factors_row.html',
                                        {'order_form': form, 'order_pair': oo, 'main_order': main_order}
                                        )

                return JsonResponse(
                    {'res': html, 'need_supply': main_order.needed_qty, 'supplied': main_order.total_supply_qty})

            if (pair_quantity or pair_quantity == 0) and main_order_pk:
                """update pair order"""
                data.pop('quantity')
                main_order = Order.objects.filter(pk=main_order_pk).first()
                order = Order.objects.filter(pk=pk).first()
                main_order_qty = main_order.quantity if main_order else 0
                total_supply_qty = main_order.total_supply_qty
                needed_qty = main_order_qty - total_supply_qty

                oo = OrderOrder.objects.filter(order_base_id=main_order_pk, order_rel_id=pk).first()
                if oo:
                    max_needed_qty = oo.quantity + needed_qty

                    order.oo = oo
                    if oo.sepidar_wh_code:
                        real_sepidar_wh_quantity = order.sepidar_wh_item_pair_quantity  # if order.is_wh else order.quantity
                        free_sepidar_wh_quantity = real_sepidar_wh_quantity - order.item.reserved_count_in_portal(wh_code=oo.sepidar_wh_code) + oo.quantity

                        oo.quantity = min(pair_quantity, free_sepidar_wh_quantity, max_needed_qty)
                        order.quantity = min(pair_quantity, max_needed_qty, free_sepidar_wh_quantity)
                    else:
                        related_order_remaining_quantity = order.remaining_quantity  # if order.is_wh else order.quantity
                        free_related_order_quantity = related_order_remaining_quantity + oo.quantity

                        oo.quantity = min(pair_quantity, free_related_order_quantity, max_needed_qty)
                        # order.quantity = min(pair_quantity, max_needed_qty, free_related_order_quantity)

                    oo.extra_data.request = self.request
                    order.extra_data.request = self.request
                    order.save()
                    oo.save()

                    form = OrderForm(data=data, instance=order)
                    form_fields = set(form.fields.keys())
                    provided_fields = set(data.keys())
                    missing_fields = form_fields - provided_fields

                    # مقدار None برای فیلدهای غایب نمی‌ذاریم (برخلاف رفتار پیش‌فرض فرم)
                    for field in missing_fields:
                        form.fields.pop(field)

                    if form.is_valid():
                        form.instance.extra_data.request = self.request
                        obj = form.save()
                        self.wf_action(obj)
                        form.instance.state_pair = form.instance.state(self.flow_config, self.get_flow_index(form.instance), self.request, form.instance)
                        form = OrderForm(instance=obj)

                    html = render_to_string('order/partial/order_of_factors_row.html', {'order_form': form, 'order_pair': oo, 'main_order': main_order})
                    return JsonResponse({'res': html, 'need_supply': main_order.needed_qty, 'supplied': main_order.total_supply_qty})
            else:
                """update independent order"""
                order = Order.objects.get(pk=pk)
                form = OrderForm(data=data, instance=order)
                form_fields = set(form.fields.keys())
                provided_fields = set(data.keys())
                missing_fields = form_fields - provided_fields

                # مقدار None برای فیلدهای غایب نمی‌ذاریم (برخلاف رفتار پیش‌فرض فرم)
                for field in missing_fields:
                    form.fields.pop(field)

                if form.is_valid():
                    form.instance.extra_data.request = self.request
                    obj = form.save()
                    self.wf_action(obj)
                    obj.state_pair = obj.state(self.flow_config, self.get_flow_index(obj), self.request, obj)
                    form = OrderForm(instance=obj)
                html = render_to_string('order/partial/order_of_factors_row.html', {'order_form': form})
                return JsonResponse({'res': html})

    def save_order_order(self):
        main_order_pk = self.data.get('main_order_pk')
        order_rel_pk = self.data.get('order_rel_pk')
        main_order = Order.objects.filter(pk=main_order_pk).first()
        order_rel = Order.objects.filter(pk=order_rel_pk).first()
        pair_quantity = float(self.data.get('pair_quantity'))

        total_supply_qty = main_order.total_supply_qty
        main_order_qty = main_order.quantity if main_order else 0
        needed_qty = main_order_qty - total_supply_qty
        from django.db.models import Sum

        order_rel_used_quantity = order_rel.order_rel_items.aggregate(total=Sum('quantity'))['total'] or 0

        order_rel_max_available_qty = order_rel.quantity - order_rel_used_quantity

        oo = OrderOrder.objects.filter(order_base=main_order, order_rel=order_rel)
        oo_quantity = 0
        if oo:
            oo_quantity = oo.first().quantity

        order_order_data = {
            'order_base': main_order,
            'order_rel': order_rel,
            'creator_user': self.request.user,
            'editor_user': self.request.user,
            'quantity': min((pair_quantity + oo_quantity), order_rel_max_available_qty, needed_qty),
            'fi': main_order.factor_items.first()
        }


        if oo:
            oo = oo.update(**order_order_data)
        else:
            oo = OrderOrder.objects.create(**order_order_data)
        return {'oo': oo, 'main_order': main_order, 'order_rel': order_rel}

    def save_order_as_wh(self):
        pair_quantity = self.data.get('pair_quantity')
        Order.objects.create()


def other_available_orders(request, main_order_pk, *args, **kwargs):
    main_order = Order.objects.get(pk=main_order_pk)
    item = main_order.item
    illegal_order_ids = [x.order_rel.pk for x in main_order.order_base_items.all()] if main_order.pk else []
    illegal_order_ids.append(main_order.pk)
    other_orders = main_order.__class__.objects.filter(item=item).exclude(pk__in=illegal_order_ids)
    stock_qty_api = SepidarApiCall.get_stock_quantity([item.sepidar_id_0]) if item else {}
    api_res = stock_qty_api.get('res')
    res = []
    if api_res:
        for name_code, stock_qty in api_res.items():
            if stock_qty:
                sepidar_wh_name = name_code[0]
                sepidar_wh_code = name_code[1]
                quantity_sum = item.reserved_count_in_portal(sepidar_wh_code)
                if stock_qty.is_integer():
                    qty = int(stock_qty)
                    if qty - quantity_sum < 0:
                        res.append(
                            {sepidar_wh_code: f'☑️ {sepidar_wh_name} (کل:{qty:,}) - (آزاد: منفی{int(abs(qty - quantity_sum)):,})'})
                    else:
                        res.append({sepidar_wh_code: f'☑️ {sepidar_wh_name} (کل:{qty:,}) - (آزاد:{int(qty - quantity_sum):,})'})
                else:
                    res.append({sepidar_wh_code: (f'wh__{sepidar_wh_code}', f'☑️ {sepidar_wh_name} {stock_qty}')})


    context = dict({'other_wh': res})
    context['other_orders'] = other_orders

    html = render_to_string('order/partial/other_available_orders.html', context)
    return JsonResponse({'res': html})


def get_order_order(request, order_pk, *args, **kwargs):
    from types import SimpleNamespace
    wh_code = None
    main_order_pk = int(request.GET.get('main_order', 0))
    main_order_obj = Order.objects.get(pk=main_order_pk)
    context = dict()

    if "__" in order_pk:
        wh_code = int(order_pk.split('__')[1])
        # res = SepidarApiCall.get_stock_item_pair_quantity([main_order_obj.item.sepidar_id_0], wh_code)
        # if res:
        #     res = res.get('results')[0].get('quantity')

    if wh_code:
        """process wh reservation"""
        initial_data = {
            "item": main_order_obj.item,
            "quantity": 5,
            "transportation_method": None,
            "order_type": None
        }
        x = OrderForm(initial=initial_data, data=initial_data)
        x = OrderForm(data=initial_data)


        x = SimpleNamespace()
        x.instance = SimpleNamespace()
        x.instance.final_item = main_order_obj.final_item
        x.instance.item = main_order_obj.item
        x.instance.sepidar_wh_quantity = '-'
        x.instance.final_item.part_number = main_order_obj.item.part_number
        x.instance.quantity = 10

        context['order_form'] = x

        html = render_to_string('order/partial/selected_other_order.html', context)
        return JsonResponse({'res': html})
    else:
        """process order reservation"""
        order = Order.objects.get(pk=order_pk)
        item = order.item

        form = OrderForm(instance=order)
        context['order_form'] = form

        html = render_to_string('order/partial/selected_other_order.html', context)
        return JsonResponse({'res': html})


class ACNTView(LoginRequiredMixin, BaseView):
    template_name = 'order/acnt_list.html'
    form_class = ACNTForm
    model = ACNT
    form_struct = {
        'form': ACNTForm,
        'childes': [
            {},
        ]
    }

    def get_success_url(self):
        return reverse_lazy('order:acnt.update', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        x = super().post(request, *args, **kwargs)
        if is_ajax(request):
            return JsonResponse({'res': 'success'})
        else:
            return x

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs)


class ACNTListView(LoginRequiredMixin, View):
    """
    sku list view
    """
    model = ACNT
    template_name = 'order/acnt_list.html'
    context_object_name = 'items'

    def get(self, request, *args, **kwargs):
        context = {}
        return render(request, self.template_name, context)


class ACNTDataTableListView(AjaxDatatableView):
    model = ACNT
    title = 'ACNT'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'visible': False, 'title': _('id'), 'className': 'py-1',},
        {'name': 'pk', 'visible': True, 'title': _('id'), 'className': 'py-1',},
        {'name': 'info_bank', 'visible': True, 'title': _('info_bank'), 'className': 'py-1',},
        {'name': 'currency', 'visible': True, 'title': _('currency'), 'className': 'py-1', },
        {'name': 'first_amount', 'title': _('first_amount'), 'className': 'py-1', },
        {'name': 'is_blocked', 'orderable': True, 'visible': True, },
        {'name': 'description', 'orderable': True, 'visible': True, },
        {'name': 'creator_user', 'orderable': True, 'visible': True, 'title': _('creator_user')},
        {'name': 'editor_user', 'orderable': True, 'visible': True, 'title': _('editor_user')},
        {'name': 'created_date', 'orderable': True, 'visible': True, },
    ]

    def customize_row(self, row, obj):
        row['pk'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('order:acnt.update', args=(obj.id,)),
            obj.id if obj.id else 'بدون عنوان'
        )


def get_wh_reserve_order(request, *args, **kwargs):
    wh_code = request.GET.get('wh_code')
    sku = request.GET.get('sku')
    res = dict()
    order_state_name = ['پیش نویس', 'تایید مدیر فروش']
    if wh_code:
        oo = OrderOrder.objects.filter(sepidar_wh_code=wh_code, order_base__item__sku=sku, order_base__last_work_flow__current_state_name__in=order_state_name)
        for item in oo:
            if item.quantity:
                res[item.pk] = f'{item.order_base.pk}: {item.quantity} -- {item.order_base.creator_user}'

        return JsonResponse(res)


def wh_packing_view(request, sepidar_buy_factor_id=-1, *args, **kwargs):
    template_name = 'order/wh_packing_list.html'

    if request.method == 'POST':
        try:
            order_ids = request.GET.get('order_ids', '').split(',')
            receipt_quantity = json.loads(request.body)
            obj = {'receipt_quantity': receipt_quantity, "sepidar_buy_factor_id": sepidar_buy_factor_id, 'user': request.user.sepidar_code}
            res = SepidarApiCall.wh_receipt_from_bazar(obj, request)
            if "errors" in res:
                return JsonResponse({'res': res['errors']}, status=500)
            else:
                for order_id in order_ids:
                    Order.objects.filter(pk=order_id).update(is_wh=True, receipt_in_wh=True,
                                                             sepidar_wh_code=settings.SEPIDAR_CONST_DATA.get(
                                                                 'central_wh_id'))
                    if SepidarOrderDocument.objects.filter(order_id=order_id).exists():
                        order_document_obj = SepidarOrderDocument.objects.get(order=order_id)
                        data = order_document_obj.data
                        if data.get('bazar'):
                            data['bazar']['sepidar'].append(res['bazar']['sepidar'])
                        else:
                            data['bazar'] = {'sepidar': [res['bazar']['sepidar']]}
                        order_document_obj.data = data
                        order_document_obj.save()
                    else:
                        SepidarOrderDocument.objects.create(order_id=order_id, data=res)

                # تبدیل محل تامین به رسید شده در انبار

                # service = SupplyLocationService()
                # wh_code = settings.SEPIDAR_CONST_DATA.get('central_wh_id')
                #
                # with transaction.atomic():
                #     for order_id in order_ids:
                #         # Order.objects.filter(pk=order_id).update(is_wh=True, receipt_in_wh=True, sepidar_wh_code=settings.SEPIDAR_CONST_DATA.get('central_wh_id'))
                #         if not order_id:
                #             continue
                #         order = (
                #             OrderBazar.objects
                #             .select_for_update()
                #             .get(pk=order_id)
                #         )
                #         order.receipt_in_wh = True
                #         order.sepidar_wh_code = wh_code
                #         order.save(update_fields=['receipt_in_wh', 'sepidar_wh_code'])
                #
                #         # تعداد رسیده‌ی این سفارش از همان payload
                #         qty = float(receipt_quantity.get(str(order_id), 0) or 0)
                #
                #         service.migrate_bazar_order_to_warehouse(
                #             order, wh_code, received_qty=order.quantity
                #         )

                # if SepidarOrderDocument.objects.filter(order_id=order_id).exists():
                #     order_document_obj = SepidarOrderDocument.objects.get(order=order_id)
                #     data = order_document_obj.data
                #     if data.get('bazar'):
                #         data['bazar']['sepidar'].append(res['bazar']['sepidar'])
                #     else:
                #         data['bazar'] = {'sepidar': [res['bazar']['sepidar']]}
                #     order_document_obj.data = data
                #     order_document_obj.save()
                # else:
                #     SepidarOrderDocument.objects.create(order_id=order_id, data=res)

                return JsonResponse({'res': f'{res}'})
        except Exception as e:
            return JsonResponse({'res': str(e)}, status=500)
    else:
        if sepidar_buy_factor_id < 0:
            import ast
            orders = Order.objects.filter(buy_factors__isnull=False, is_deleted=False, is_bazar=True, receipt_in_wh=False).exclude(buy_factors=[])
            bazar_orders = OrderBazar.objects.filter(buy_factors__isnull=False, is_deleted=False, receipt_in_wh=False).exclude(buy_factors=[])
            trade_orders = PackingItem.objects.filter(packing__last_work_flow__current_state_name='انبار').select_related('order', 'packing__last_work_flow').distinct()
            for item in trade_orders:
                print(item.order)

            buy_factor_id_dict = dict()
            for order in bazar_orders:
                for buy_factor in order.buy_factors:
                    for key, value in buy_factor.items():
                        key_tuple = ast.literal_eval(key)
                        # key_tuple = key_tuple[0]
                        if key_tuple in buy_factor_id_dict:
                            buy_factor_id_dict[key_tuple].append(order.pk)
                        else:
                            buy_factor_id_dict[key_tuple] = [order.pk]

            for order in orders:
                for buy_factor in order.buy_factors:
                    for key, value in buy_factor.items():
                        key_tuple = ast.literal_eval(key)
                        # key_tuple = key_tuple[0]
                        if key_tuple in buy_factor_id_dict:
                            buy_factor_id_dict[key_tuple].append(order.pk)
                        else:
                            buy_factor_id_dict[key_tuple] = [order.pk]

            context = {"buy_factor_id_dict": buy_factor_id_dict}
            return render(request, template_name, context=context)

        res = SepidarApiCall.get('inventorypurchaseinvoice', sepidar_buy_factor_id)

        if res.ok:
            data = res.json()
            data_ = {
                'vendor': data['fk_strs']['vendordlref'],
                'items': [
                    {
                        'sku': row['sku'],
                        'partnumber': row['fk_strs']['itemref'],
                        'quantity': row['quantity'],
                        'remaining_quantity': row['remainingquantity'],
                        'id': row['inventorypurchaseinvoiceitemid']
                    } for row in data['inventorypurchaseinvoice_item']
                ]
            }
            return JsonResponse({'res': data_})
        else:
            return JsonResponse({'res': res.json()})

# def wh_packing_view(request, sepidar_buy_factor_id=-1, *args, **kwargs):
# این نسخه ای هست که با سفارش های جدید کار میکنه
#     template_name = 'order/wh_packing_list.html'
#
#     if request.method == 'POST':
#         try:
#             order_ids = request.GET.get('order_ids', '').split(',')
#             receipt_quantity = json.loads(request.body)
#             obj = {'receipt_quantity': receipt_quantity, "sepidar_buy_factor_id": sepidar_buy_factor_id, 'user': request.user.sepidar_code}
#             res = SepidarApiCall.wh_receipt_from_bazar(obj, request)
#             if "errors" in res:
#                 return JsonResponse({'res': res['errors']}, status=500)
#             else:
#                 # تبدیل محل تامین به رسید شده در انبار
#
#                 service = SupplyLocationService()
#                 wh_code = settings.SEPIDAR_CONST_DATA.get('central_wh_id')
#
#                 with transaction.atomic():
#                     for order_id in order_ids:
#                         # Order.objects.filter(pk=order_id).update(is_wh=True, receipt_in_wh=True, sepidar_wh_code=settings.SEPIDAR_CONST_DATA.get('central_wh_id'))
#                         if not order_id:
#                             continue
#                         order = (
#                             OrderBazar.objects
#                             .select_for_update()
#                             .get(pk=order_id)
#                         )
#                         order.receipt_in_wh = True
#                         order.sepidar_wh_code = wh_code
#                         order.save(update_fields=['receipt_in_wh', 'sepidar_wh_code'])
#
#                         # تعداد رسیده‌ی این سفارش از همان payload
#                         qty = float(receipt_quantity.get(str(order_id), 0) or 0)
#
#                         service.migrate_bazar_order_to_warehouse(
#                             order, wh_code, received_qty=order.quantity
#                         )
#
#                 # if SepidarOrderDocument.objects.filter(order_id=order_id).exists():
#                 #     order_document_obj = SepidarOrderDocument.objects.get(order=order_id)
#                 #     data = order_document_obj.data
#                 #     if data.get('bazar'):
#                 #         data['bazar']['sepidar'].append(res['bazar']['sepidar'])
#                 #     else:
#                 #         data['bazar'] = {'sepidar': [res['bazar']['sepidar']]}
#                 #     order_document_obj.data = data
#                 #     order_document_obj.save()
#                 # else:
#                 #     SepidarOrderDocument.objects.create(order_id=order_id, data=res)
#
#                 return JsonResponse({'res': f'{res}'})
#         except Exception as e:
#             return JsonResponse({'res': str(e)}, status=500)
#     else:
#         if sepidar_buy_factor_id < 0:
#             import ast
#             orders = Order.objects.filter(buy_factors__isnull=False, is_deleted=False, is_bazar=True, receipt_in_wh=False).exclude(buy_factors=[])
#             bazar_orders = OrderBazar.objects.filter(buy_factors__isnull=False, is_deleted=False, receipt_in_wh=False).exclude(buy_factors=[])
#             trade_orders = PackingItem.objects.filter(packing__last_work_flow__current_state_name='انبار').select_related('order', 'packing__last_work_flow').distinct()
#             for item in trade_orders:
#                 print(item.order)
#
#             buy_factor_id_dict = dict()
#             for order in bazar_orders:
#                 for buy_factor in order.buy_factors:
#                     for key, value in buy_factor.items():
#                         key_tuple = ast.literal_eval(key)
#                         # key_tuple = key_tuple[0]
#                         if key_tuple in buy_factor_id_dict:
#                             buy_factor_id_dict[key_tuple].append(order.pk)
#                         else:
#                             buy_factor_id_dict[key_tuple] = [order.pk]
#
#             for order in orders:
#                 for buy_factor in order.buy_factors:
#                     for key, value in buy_factor.items():
#                         key_tuple = ast.literal_eval(key)
#                         # key_tuple = key_tuple[0]
#                         if key_tuple in buy_factor_id_dict:
#                             buy_factor_id_dict[key_tuple].append(order.pk)
#                         else:
#                             buy_factor_id_dict[key_tuple] = [order.pk]
#
#             context = {"buy_factor_id_dict": buy_factor_id_dict}
#             return render(request, template_name, context=context)
#
#         res = SepidarApiCall.get('inventorypurchaseinvoice', sepidar_buy_factor_id)
#
#         if res.ok:
#             data = res.json()
#             data_ = {
#                 'vendor': data['fk_strs']['vendordlref'],
#                 'items': [
#                     {
#                         'sku': row['sku'],
#                         'partnumber': row['fk_strs']['itemref'],
#                         'quantity': row['quantity'],
#                         'remaining_quantity': row['remainingquantity'],
#                         'id': row['inventorypurchaseinvoiceitemid']
#                     } for row in data['inventorypurchaseinvoice_item']
#                 ]
#             }
#             return JsonResponse({'res': data_})
#         else:
#             return JsonResponse({'res': res.json()})


def portal_reserve_(request, sku, *args, **kwargs):
    if sku:
        oos = OrderOrder.objects.filter(item_id=sku,
                                        fi__factor__sepidar_id__isnull=True,
                                        is_deleted=False,
                                        order_base__sepidar_wh_code__isnull=False) #.select_related('fi__creator_user', 'fi__index', 'fi__factor')
        order_receipt_in_wh = Order.objects.filter(item_id=sku, is_wh=True, receipt_in_wh=True,
                                                   is_deleted=False, factor_items__factor__sepidar_id__isnull=True,
                                                   cancel=False, is_kasri=False)
        out = list()
        for oo in oos:
            creator_user = oo.fi.creator_user
            quantity = oo.quantity
            factor_id = oo.fi.factor.pk
            row = oo.fi.index
            if row:
                row += 1
            else:
                row = '-'

            out.append({'creator_user': creator_user, 'quantity': parse_number(quantity), 'factor': factor_id, 'row_index': row})

        for o in order_receipt_in_wh:
            creator_user = o.creator_user
            quantity = o.quantity
            factor_id = o.factor_items.all().values_list('factor_id', flat=True)
            row = 0  # 'o.fi.index'
            if row:
                row += 1
            else:
                row = '-'

            out.append({'creator_user': creator_user, 'quantity': parse_number(quantity), 'factor': factor_id, 'row_index': row})

        whs = WhReserve.objects.filter(item_id=sku, is_deleted=False)
        for wh in whs:
            for sl in wh.wh_reserve_fis.all():
                if not sl.fi.factor.sepidar_id:
                    creator_user = sl.fi.factor.creator_user
                    quantity = sl.quantity
                    factor_id = sl.fi.factor.pk
                    row = sl.fi.index or '-'
                    out.append({'creator_user': creator_user, 'quantity': parse_number(quantity), 'factor': factor_id, 'row_index': row})

        context = {'data': out, 'sku': sku}
        html = render_to_string('order/partial/portal_reserve.html', context=context)
        return JsonResponse({'res': html})

    else:
        return JsonResponse({'res': ' خطا در دریافت کد کالا'})


class QuickGIOView(LoginRequiredMixin, View):
    template_name = 'order/gio/quick_gio_create.html' # for update use 'order/gio/quick_gio_create.html'
    form_class = GIOForm
    model = GIO
    # wf_last_step_is_open = True
    has_flow = False
    form_struct = {
        'form': GIOForm,
        'childes': [
            {},
        ]
    }
    # flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'OrderView')
    
    def setup(self, request, *args, **kwargs):
        if kwargs.get('pk'):
            self.template_name = 'order/gio/quick_gio_update.html'
            self.object = self.get_object(kwargs.get('pk'))
        return super().setup(request, *args, **kwargs)

    # def get_success_url(self):
    #     return reverse_lazy('order:quick_gio', kwargs={'pk': self.object.pk})

    def post(self, request, pk=None, *args, **kwargs):
        data = json.loads(request.body) or {}
        data = {k: v for k, v in data.items() if 'form-0-' not in k}  # remove form-0- from data
        total_forms = data.get('form-TOTAL_FORMS', 1)  # first form is empty

        gio_data = {
            "gio_date": data.pop('gio_date', None),
            'description': data.pop('description', None),
            'creator_user': self.request.user,
            'editor_user': self.request.user
        }

        try:
            with transaction.atomic():
                gio_obj = GIO(**gio_data)
                gio_obj.extra_data.request = self.request
                gio_obj.save()

                gio_items_data = {k: v for k, v in data.items() if 'form-' in k}  # remove form-0- from data
                for row in range(1, total_forms):
                    quantity = gio_items_data.get(f'form-{row}-quantity')
                    order_id = gio_items_data.get(f'form-{row}-order')
                    o = Order.objects.get(pk=order_id)

                    is_valid_for_gio = o.validate_for_gio(quantity)
                    if not is_valid_for_gio[0]:
                        return JsonResponse({'res': {'ERROR: ': is_valid_for_gio[1]}}, status=400)

                    gio_item_data = {
                        'quantity': quantity,
                        'description': gio_items_data.get(f'form-{row}-description'),
                        'order_id': order_id,
                        'gio': gio_obj
                    }
                    # sid = transaction.savepoint()

                    try:
                        gio_item_obj = GIOItem(**gio_item_data)
                        gio_item_obj.extra_data.request = self.request
                        gio_item_obj.save()
                        # sid = transaction.savepoint_commit(sid)
                    except Exception as e:
                        # transaction.savepoint_rollback(sid)
                        raise e
        except Exception as e:
            res = {'res': {'ERROR: ': str(e)}}
            return JsonResponse(res, status=400)

        return JsonResponse({'res': {'url': reverse_lazy('order:quick_gio', kwargs={'pk': gio_obj.pk})}}, status=200) # redirect(reverse_lazy('order:quick_gio', kwargs={'pk': gio_obj.pk}))

    def get(self, request, pk=None, *args, **kwargs):
        gio_object = self.get_object(pk)

        gio_form = GIOForm(instance=gio_object)
        gio_item_formset = GIOItemFormSet()

        context = {
            'form': gio_form,
            'formset': gio_item_formset,
        }
        
        return render(request, self.template_name, context)

    def get_object(self, pk):
        if pk:
            return GIO.objects.get(pk=pk)
        else:
            return None

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class QuickGIODataTableListView(AjaxDatatableView):
    model = Order
    title = 'order_list'
    initial_order = [["id", "des"], ]
    length_menu = [[10, 25, 50, -1], [10, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'
    show_column_filters = True
    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'title': "id", 'orderable': True, 'visible': True, "className": 'order d-none'},
        {'name': 'show_order_str', 'title': "show_order_str", 'orderable': True, 'visible': True, "className": 'py-1 show_order_str d-none'},
        {'name': 'order_number', 'title': "order_number", 'orderable': True, 'visible': True, "className": 'py-1'},
        {'name': 'quantity', 'orderable': True, 'visible': True, 'title': 'تعداد', 'className': 'quantity'},
        {'name': 'item', 'orderable': True, 'title': 'کد کالا', 'visible': True, 'lookup_field': '__sku__icontains', 'className': 'py-1'},
        {'name': 'item__sepidar_id_0', 'visible': True, 'className': 'itemref d-none'},
        {'name': 'item__part_number', 'orderable': True, 'title': 'نام کالا', 'visible': True, 'lookup_field': '__icontains', 'className': 'partnumber'},
        {'name': 'creator_user', 'title': 'ایجاد کننده', 'visible': True, 'orderable': True, 'lookup_field': '__username__icontains'},
        {'name': 'created_date', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'description_sale', 'orderable': True, 'visible': True, 'title': 'توضیحات فروش'},
        {'name': 'description_trade', 'orderable': True, 'visible': True, 'title': 'توضیحات بازرگانی'},
        {'name': 'buy_factor', 'orderable': False, 'visible': True, 'title': '<div class="px-0">Add</div>', },
    ]

    def get_initial_queryset(self, request=None):
        qs = self.model.objects.filter(is_deleted=False, is_wh=False, last_work_flow__current_state_name='پرداخت / PACKING / GIO')
        # .filter(Q(buy_factor_quantity_in_sepidar__lt=F('quantity')) | Q(buy_factor_quantity_in_sepidar__isnull=True)))
        return qs

    def customize_row(self, row, obj):
        from tools.utils import to_jalali_date
        row['created_date'] = to_jalali_date(obj.created_date)
        row['quantity'] = obj.final_quantity
        row['item__sepidar_id_0'] = obj.item.sepidar_id_0
        row['order_method'] = f'<span>{obj.order_method}</span>'
        row['item__part_number'] = f'<span>{obj.item.part_number}</span>' if obj.item else ""
        row['qi__quotation__customer_party_id'] = f'<span>{obj.qi.quotation.customer_party_id.title}</span>' if obj.qi else ""
        row['qi__quotation__id'] = f'<span>{obj.qi.quotation.id}</span>' if obj.qi else ""
        row['estimated_arrive_date'] = obj.estimate_arrive_at
        row['show_order_str'] = mark_safe(f'<div class="d-flex gap-6"> <span>{obj.order_number}</span> / <span>sku:{obj.final_item}</span> <span class="bg-light-info px-1">{obj.final_item.part_number}</span></div>')
        row['buy_factor'] = '<span class="fw-bold p-3 cursor-pointer font-size-16 py-5 action" data-is_selected=no onclick="order_to_gio_item(event)" >➕</span>'