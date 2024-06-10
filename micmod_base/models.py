import uuid
# from datetime import datetime, timedelta
from django.utils.timezone import timedelta

from django.db.models import F
from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import MaxValueValidator
from django.db.models import Q
from django.utils import timezone

# from django.contrib.auth.models import User
from accounts.models import User
from django.db import models
from django.conf import settings
from accounts.templatetags.accounts_tag import has_groups,has_permission
from core.models import BaseManager
from extra_data.models import Customer
from tools import utils
from tools.utils import show_error

from translator import get_text as _
from workflow.models import WorkFlow
# Create your models here.
from .base import SLSDoc, CustomerGrade, DeliveryTime, MarketGrade, BaseModel, PriceMethod, AbsBaseModel, Currency, PaymentMethod


class QuotationManager(models.Manager):
    def own_quotations(self, request):
        has_permission(request.user,"")
        if has_groups(request.user, "total_admin,sales_admin"):
            return self.all()
        else:
            return self.filter(creator_user=request.user)


class QuotationItemManager(BaseManager):
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.order_by('id')


class Month(AbsBaseModel):
    title = models.CharField(verbose_name=_('title'), max_length=20)
    month = models.IntegerField(verbose_name=_('number'), default=0)


class SaleType(AbsBaseModel):
    number = models.IntegerField(verbose_name=_('number'))
    title = models.CharField(verbose_name=_('title'), max_length=20)
    month = models.ForeignKey(Month,verbose_name=_('month'), on_delete=models.DO_NOTHING, related_name='sale_types')
    currency = models.ForeignKey(Currency,verbose_name=_('currency'),on_delete=models.DO_NOTHING, related_name='sale_types')
    extra_percentage = models.IntegerField(verbose_name=_('extra_percentage'), default=0)

    def __str__(self):
        return f'{self.title}'

class Quotation(SLSDoc):
    # translations = TranslatedFields(
    customer_party_id = models.ForeignKey(Customer, verbose_name=_('party_id'), null=True, blank=True, to_field='sepidar_party_id', on_delete=models.DO_NOTHING, db_column='customer_party_id')
    # customer_party_id = models.BigIntegerField(verbose_name=_('party_id'), null=True, blank=True)
    request_date = models.DateField(null=False, blank=False, verbose_name=_('request_date'))
    expiration_date = models.DateField(null=True, blank=True, verbose_name=_('expiration_date'))
    customer_code = models.CharField(max_length=20, null=True, blank=True, verbose_name=_('customer_code'))
    customer_grade = models.CharField(choices=CustomerGrade, max_length=10, null=True, blank=True,
                                      verbose_name=_('customer_grade'), default="-1,A")
    delivery_time = models.CharField(choices=DeliveryTime, max_length=10, null=True, blank=True,
                                     verbose_name=_('delivery_time'), default="2-3 week")
    payment_method = models.CharField(choices=PaymentMethod, max_length=10, null=True, blank=True,
                                      verbose_name=_('payment_method'), default="6,2 Month")
    market_grade = models.CharField(choices=MarketGrade, max_length=10, null=True, blank=True,
                                    verbose_name=_('market_grade'), default="5,A")
    description = models.CharField(max_length=200, null=True, blank=True, verbose_name=_('description'))
    guid = models.UUIDField(_('guid'), default=None, editable=False, null=True, blank=True)
    sepidar_quotation_id = models.BigIntegerField(_('sepidar_quotation_id'), null=True, blank=True)
    sepidar_number = models.BigIntegerField(_('sepidar_number'), null=True, blank=True)

    workflows = GenericRelation('workflow.Workflow', related_query_name="model")
    quotation_self = models.ForeignKey('self', on_delete=models.DO_NOTHING, related_name='quotation_rel', null=True, blank=True)
    self_discount = models.PositiveSmallIntegerField(verbose_name=_('self_discount'), default=0, validators=[MaxValueValidator(100)])
    is_official = models.BooleanField(default=False, verbose_name=_('is_official'))
    official_value = models.PositiveSmallIntegerField(default=0, verbose_name=_('official_value'), null=True, blank=True)
    cancel = models.BooleanField(default=False, verbose_name=_('cancel'))
    force_inquiry = models.BooleanField(verbose_name=_('force_inquiry'), default=False)
    sale_type = models.ForeignKey(SaleType, on_delete=models.DO_NOTHING, related_name='quotations')

    custom_objects = QuotationManager()
    absolute_url_update = 'micmod_base:quotations.view'

    @classmethod
    def get_qs(cls, request):
        q = request.POST.get('q')
        qs = cls.objects.get_access_object(request.user, q=q, quotation=True)
        return qs

    @classmethod
    def get_qs_count(cls, user):
        return len(cls.objects.get_access_object(user, q='active', quotation=True))

    def progress_from_inquiry_state(self, total_hour=72):
        if self.is_inquiry_state:
            wf = self.workflows.last()
            return utils.progress_value(wf.created_date, timezone.now(), total_hour)
        else:
            return 0

    @classmethod
    def today_quotation_pending(cls, request, **kwargs):
        user_groups_name = request.user.groups.values_list('name', flat=True) if hasattr(request,
                                                                                         'user') else request.groups.values_list(
            'name', flat=True)
        quotations_record_lst = list()

        trade_user_filter = Q(foreign_price_inquiry_done=True) & Q(need_foreign_price_inquiry=False) | \
                            Q(foreign_price_inquiry_done=False) & Q(need_foreign_price_inquiry=True)

        bazar_user_filter = Q(local_price_inquiry_done=True) & Q(need_local_price_inquiry=False) | \
                            Q(local_price_inquiry_done=False) & Q(need_local_price_inquiry=True)

    @classmethod
    def quotation_pending(cls, request, **kwargs):
        user_groups_name = request.user.groups.values_list('name', flat=True) if hasattr(request, 'user') else request.groups.values_list('name', flat=True)
        quotations_record_lst = list()
        qis = []
        request_path = None
        past_path = '/micmod_base/quotationitem/past/quotationitems'
        if hasattr(request, 'path'):
            request_path = request.path

        if hasattr(request, 'path') and request.path == past_path:
            superuser_filter = Q(need_foreign_price_inquiry=True) & \
                               Q(foreign_price_inquiry_done=True) | \
                               Q(need_local_price_inquiry=True) & \
                               Q(local_price_inquiry_done=True)

            trade_user_filter = Q(need_foreign_price_inquiry=True) & Q(foreign_price_inquiry_done=True)
            bazar_user_filter = Q(need_local_price_inquiry=True) & Q(local_price_inquiry_done=True)

        else:
            superuser_filter = Q(foreign_price_inquiry_done=True) & Q(need_foreign_price_inquiry=False) | \
                               Q(foreign_price_inquiry_done=False) & Q(need_foreign_price_inquiry=True) | \
                               Q(local_price_inquiry_done=True) & Q(need_local_price_inquiry=False) | \
                               Q(local_price_inquiry_done=False) & Q(need_local_price_inquiry=True)

            trade_user_filter = Q(foreign_price_inquiry_done=True) & Q(need_foreign_price_inquiry=False) | \
                                Q(foreign_price_inquiry_done=False) & Q(need_foreign_price_inquiry=True)

            bazar_user_filter = Q(local_price_inquiry_done=True) & Q(need_local_price_inquiry=False) | \
                                Q(local_price_inquiry_done=False) & Q(need_local_price_inquiry=True)

        f = kwargs.get('filter')
        extra_filter = kwargs.get('extra_filter')

        if f is not None:
            qs = Quotation.objects.filter(**f).order_by('-last_update_date')
        else:
            qs = Quotation.objects.all().order_by('-last_update_date')
        # qs = qs.order_by('force_inquiry', 'workflows__created_date')
        for q in qs:
            if hasattr(request, 'user') and request.user.is_superuser and (q.is_inquiry_state or request_path == past_path):
                if extra_filter is not None:
                    qis = q.quotation.filter(superuser_filter, **extra_filter)
                else:
                    qis = q.quotation.filter(superuser_filter)
            elif 'trade_user' in user_groups_name and (q.is_inquiry_state or request_path == past_path):
                if extra_filter is not None and extra_filter.get('my_quotations'):
                    trade_extra_filter = Q(assigned_trade_user=request.user) | Q(assigned_trade_user2=request.user)
                    qis = q.quotation.filter(trade_user_filter, trade_extra_filter)
                elif extra_filter is not None and extra_filter.get('inquiry_not_assigned'):
                    trade_extra_filter = Q(assigned_trade_user__isnull=True) & Q(assigned_trade_user2__isnull=True)
                    qis = q.quotation.filter(trade_user_filter, trade_extra_filter)
                elif extra_filter is not None and extra_filter.get('goods_code'):
                    qis = q.quotation.filter(trade_user_filter, **extra_filter)
                # elif extra_filter is not None and extra_filter.get('goods_code') and extra_filter.get('my_quotations'):
                #     trade_extra_filter = Q(assigned_trade_user=request.user) | Q(assigned_trade_user2=request.user)
                #     qis = q.quotation.filter(trade_user_filter, trade_extra_filter)
                #     qis = qis.filter(goods_code=extra_filter.get('goods_code'))
                elif extra_filter is not None and extra_filter.get('my_inquiry_not_started'):
                    trade_extra_filter = (Q(assigned_trade_user=request.user) & Q(task_start=False)) | \
                                         (Q(assigned_trade_user2=request.user) & Q(task_start2=False))
                    qis = q.quotation.filter(trade_user_filter, trade_extra_filter)
                else:
                    qis = q.quotation.filter(trade_user_filter)

            elif 'bazar_user' in user_groups_name and (q.is_inquiry_state or request_path == past_path):
                if extra_filter is not None:
                    qis = q.quotation.filter(bazar_user_filter, **extra_filter)
                else:
                    qis = q.quotation.filter(bazar_user_filter)
            else:
                qis = []

            if qis:
                quotations_record_lst.append(qis)

        return quotations_record_lst

    @property
    def is_inquiry_state(self):
        wf_draft = 1
        wf_back = 2
        wf_next = 3

        wf_state_1 = 'پیش فاکتور اولیه'
        wf_state_2 = 'استعلام قیمت'
        wf_state_3 = 'تایید پیش فاکتور'

        last_wf = self.workflows.all().order_by('id').last()
        if last_wf is None:
            return False
        if (last_wf.state == wf_state_1 and last_wf.wf_status == wf_next) or \
           (last_wf.state == wf_state_3 and last_wf.wf_status == wf_back) or \
           (last_wf.state == wf_state_2 and last_wf.wf_status == wf_draft):
            return True
        else:
            return False

    @property
    def get_inquiry_state(self):
        wf_back = 2
        wf_next = 3

        wf_state_0 = 'اولین پیشنویس'
        wf_state_1 = 'پیش فاکتور اولیه'
        wf_state_2 = 'استعلام قیمت'
        wf_state_3 = 'تایید پیش فاکتور'
        wf_state_4 = 'تایید مشتری'
        wf_state_5 = 'تایید کارشناس'
        wf_state_6 = 'مرحله ی نهایی'

        last_wf = self.workflows.all().order_by('id').last()

        if last_wf:

            if last_wf.state == wf_state_0:
                return wf_state_1

            elif ((last_wf.state == wf_state_1 and last_wf.wf_status == wf_next) or
                    (last_wf.state == wf_state_3 and last_wf.wf_status == wf_back)):
                return wf_state_2

            elif ((last_wf.state == wf_state_2 and last_wf.wf_status == wf_next) or
                    (last_wf.state == wf_state_4 and last_wf.wf_status == wf_back)):
                return wf_state_3

            elif ((last_wf.state == wf_state_3 and last_wf.wf_status == wf_next) or
                    (last_wf.state == wf_state_5 and last_wf.wf_status == wf_back)):
                return wf_state_4

            elif ((last_wf.state == wf_state_4 and last_wf.wf_status == wf_next) or
                    (last_wf.state == wf_state_6 and last_wf.wf_status == wf_back)):
                return wf_state_5
            elif last_wf.state == wf_state_5 and last_wf.wf_status == wf_next:
                return wf_state_6
            else:
                return last_wf.state

    @property
    def price(self):
        try:
            return sum(x.price for x in self.quotation.all())
        except Exception as e:
            show_error(e, __file__)
            return None

    @property
    def tax_amount(self):
        try:
            return sum(x.tax for x in self.quotation.all())
        except Exception as e:
            show_error(e, __file__)
            return 0

    @property
    def duty_amount(self):
        try:
            return sum(x.duty for x in self.quotation.all())
        except Exception as e:
            show_error(e, __file__)
            return 0

    def __str__(self):
        return str(self.id)

    class Meta:
        verbose_name = _("t-quotation")

    @property
    def get_inquiry_result_count(self):
        if self.pk:
            all_q = self.quotation.all()
            all_count = all_q.count()
            local_inquiry_count = all_q.filter(need_local_price_inquiry=True).count()
            local_inquiry_done_count = all_q.filter(local_price_inquiry_done=True).count()
            foreign_inquiry_count = all_q.filter(need_foreign_price_inquiry=True).count()
            foreign_inquiry_done_count = all_q.filter(foreign_price_inquiry_done=True).count()
            return all_count, local_inquiry_count, local_inquiry_done_count, foreign_inquiry_count, foreign_inquiry_done_count
        else:
            return

    @property
    def sum_prices(self):
        qis = self.quotation.all()
        sum_price = 0
        for qi in qis:
            quantity = qi.quantity
            fee = qi.fee
            price = quantity * fee
            sum_price += price


            if sum_price is None:
                return 0
        return int(sum_price)


class QuotationItem(BaseModel):
    quotation = models.ForeignKey(Quotation, on_delete=models.DO_NOTHING, related_name='quotation',
                                  verbose_name=_('quotation'))
    created_date = models.DateTimeField(_('create_date'), auto_now_add=True)
    last_update_date = models.DateTimeField(_('last_update_date'), auto_now=True)
    editor_user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True, blank=True, related_name='editor',
                                    verbose_name=_('editor'))
    index = models.IntegerField(null=True, blank=True, verbose_name=_("index"))
    customer_goods_name = models.CharField(null=True, blank=True, verbose_name=_("customer_goods_name"),
                                           max_length=200)
    customer_goods_code = models.CharField(null=True, blank=True, verbose_name=_("customer_goods_code"), max_length=100)
    quantity = models.BigIntegerField(null=True, blank=True, verbose_name=_("quantity"))
    delivery_time = models.CharField(choices=DeliveryTime, max_length=20, null=True, blank=True,
                                     verbose_name=_('delivery_time'))
    goods_code = models.CharField(verbose_name=_("goods_code"), max_length=20)
    itemid = models.BigIntegerField(null=True, blank=True, verbose_name=_("itemid"))
    goods_name = models.CharField(null=True, blank=True, verbose_name=_("goods_name"), max_length=200)
    stock_amount = models.BigIntegerField(null=True, blank=True, verbose_name=_("stock_amount"))
    stock_amount_res = models.BigIntegerField(null=True, blank=True, verbose_name=_("stock_amount_res"))
    stock_json = models.JSONField(null=True, blank=True, verbose_name=_("stock_json"))
    goods_sheet_date = models.DateField(null=True, blank=True, verbose_name=_("goods_sheet_date"))
    goods_price_sheet1 = models.FloatField(null=True, blank=True, verbose_name=_("goods_price_sheet"))
    goods_price_sheet2 = models.FloatField(null=True, blank=True, verbose_name=_("goods_price_sheet"))
    goods_price_sheet3 = models.FloatField(null=True, blank=True, verbose_name=_("goods_price_sheet"))
    goods_price_market = models.FloatField(null=True, blank=True, verbose_name=_("goods_price_market"))
    goods_market_date = models.DateField(null=True, blank=True, verbose_name=_("goods_market_date"))
    goods_avg_price = models.FloatField(null=True, blank=True, verbose_name=_("goods_avg_price"))
    goods_min_price = models.FloatField(null=True, blank=True, verbose_name=_("goods_min_price"))
    goods_max_price = models.FloatField(null=True, blank=True, verbose_name=_("goods_max_price"))
    goods_avg_count = models.FloatField(null=True, blank=True, verbose_name=_("goods_avg_count"))

    goods_code_alt = models.CharField(null=True, blank=True, verbose_name=_("goods_code_alt"), max_length=20)
    goods_name_alt = models.CharField(null=True, blank=True, verbose_name=_("goods_name"), max_length=200)
    goods_last_sale = models.DateField(null=True, blank=True, verbose_name=_("goods_last_sale"))
    goods_last_price = models.FloatField(null=True, blank=True, verbose_name=_("goods_last_price"))
    goods_total_sales = models.FloatField(null=True, blank=True, verbose_name=_("goods_total_sales"))

    goods_q_last_sale = models.DateField(null=True, blank=True, verbose_name=_("goods_last_sale_q"))
    goods_q_last_price = models.FloatField(null=True, blank=True, verbose_name=_("goods_last_price_q"))
    goods_q_total_sales = models.FloatField(null=True, blank=True, verbose_name=_("goods_total_sales_q"))

    price_method = models.CharField(choices=PriceMethod, max_length=20, default="last_sale",
                                    verbose_name=_('price_method'))
    final_price = models.FloatField(null=True, blank=True, verbose_name=_("final_price"))

    need_foreign_price_inquiry = models.BooleanField(verbose_name=_('need_foreign_price_inquiry'), default=False)
    foreign_price_inquiry_done = models.BooleanField(verbose_name=_('foreign_price_inquiry_done'), default=False)
    need_local_price_inquiry = models.BooleanField(verbose_name=_('need_local_price_inquiry'), default=False)
    local_price_inquiry_done = models.BooleanField(verbose_name=_('local_price_inquiry_done'), default=False)

    description = models.CharField(max_length=200, null=True, blank=True, verbose_name=_('description'))
    trade_price_code = models.ForeignKey('inquiry.PriceInquiryResult', on_delete=models.DO_NOTHING, verbose_name=_('trade_price_code'), related_name='trade_quotation_rel', null=True, blank=True)
    bazar_price_code = models.ForeignKey('inquiry.PriceInquiryResult', on_delete=models.DO_NOTHING, verbose_name=_('bazar_price_code'), related_name='bazar_quotation_rel', null=True, blank=True)
    lead_time = models.CharField(verbose_name=_('lead time'), null=True, blank=True)
    assigned_trade_user = models.ForeignKey(User, verbose_name=_('assigned_trade_user'), null=True, blank=True, on_delete=models.DO_NOTHING, related_name='assigned_trade_user_rel')
    assigned_trade_user2 = models.ForeignKey(User, verbose_name=_('assigned_trade_user2'), null=True, blank=True, on_delete=models.DO_NOTHING, related_name='assigned_trade_user2_rel')
    assigned_trade_user_date = models.DateTimeField(verbose_name=_('assigned_trade_user_date'), null=True, blank=True)
    assigned_trade_user_date2 = models.DateTimeField(verbose_name=_('assigned_trade_user_date2'), null=True, blank=True)
    task_start = models.BooleanField(verbose_name=_('task_start'), default=False)
    task_start2 = models.BooleanField(verbose_name=_('task_start2'), default=False)
    task_start_date = models.DateTimeField(verbose_name=_('task_start_date'), null=True, blank=True)
    task_start_date2 = models.DateTimeField(verbose_name=_('task_start_date2'), null=True, blank=True)

    excluded_fields = ['trade_price_code','bazar_price_code',]
    # form_structures = [[{"model":"this","fields":{"enabled":["assigned_trade_user2"]}}]]
    old_goods_code = models.CharField(verbose_name=_("old_goods_code"), max_length=20, null=True, blank=True)
    old_goods_name = models.CharField(verbose_name=_("old_goods_name"), max_length=200, null=True, blank=True)
    item_editor_user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True, blank=True)
    has_delay = models.BooleanField(default=False, verbose_name=_('has_delay'))
    delay_reason = models.CharField(max_length=250, verbose_name=_('delay_reason'), null=True, blank=True)
    delay_time = models.CharField(max_length=100, verbose_name=_('delay_time'), null=True, blank=True)
    item_in_china = models.BooleanField(_('item_in_china'), default=False)

    objects = QuotationItemManager()

    @classmethod
    def quotation_item_all_pending(cls, inquiry_type=None, path=None):
        past_path = '/micmod_base/quotationitem/past/quotationitems'
        inquiry_type_filter = Q(foreign_price_inquiry_done=True) & Q(need_foreign_price_inquiry=False) | \
                           Q(foreign_price_inquiry_done=False) & Q(need_foreign_price_inquiry=True) | \
                           Q(local_price_inquiry_done=True) & Q(need_local_price_inquiry=False) | \
                           Q(local_price_inquiry_done=False) & Q(need_local_price_inquiry=True)

        if inquiry_type == 'trade':
            if path == past_path:
                inquiry_type_filter = Q(need_foreign_price_inquiry=True) & Q(foreign_price_inquiry_done=True)
            else:
                inquiry_type_filter = Q(foreign_price_inquiry_done=True) & Q(need_foreign_price_inquiry=False) | \
                                      Q(foreign_price_inquiry_done=False) & Q(need_foreign_price_inquiry=True)

        elif inquiry_type == 'bazar':
            if path == past_path:
                inquiry_type_filter = Q(need_local_price_inquiry=True) & Q(local_price_inquiry_done=True)
            else:
                inquiry_type_filter = Q(local_price_inquiry_done=True) & Q(need_local_price_inquiry=False) | \
                                      Q(local_price_inquiry_done=False) & Q(need_local_price_inquiry=True)
        if path == past_path:
            x = cls.objects.filter(inquiry_type_filter).order_by('-quotation_id')
        else:
            x = cls.objects.filter(inquiry_type_filter, quotation__last_work_flow__current_state_name='استعلام قیمت').order_by('-quotation_id')
        return x

    @classmethod
    def get_inquiry_report(cls):
        trade_user = User.objects.filter(groups__name__in=['trade_user', 'trade_admin']).distinct()
        today = timezone.now() - timedelta(days=1)
        d =dict()
        quotation_items = cls.objects.filter(Q(assigned_trade_user__in=trade_user) |
                                             Q(assigned_trade_user2__in=trade_user))
        for user in trade_user:

            time_filter = (Q(assigned_trade_user=user, assigned_trade_user_date__gte=today) |
                           Q(assigned_trade_user2=user, assigned_trade_user_date2__gte=today))
            task_start_filter = (Q(assigned_trade_user=user, task_start=True) |
                                 Q(assigned_trade_user2=user, task_start2=True))
            price_inquiry_filter = (Q(assigned_trade_user=user, foreign_price_inquiry_done=True) |
                                    Q(assigned_trade_user2=user, foreign_price_inquiry_done=True))
            all_tasks_filter = (Q(assigned_trade_user=user) | Q(assigned_trade_user2=user))
            today_qi = quotation_items.filter(time_filter).count()
            task_start_qi = quotation_items.filter(task_start_filter).count()
            price_inquiry_qi = quotation_items.filter(price_inquiry_filter).count()
            all_tasks = quotation_items.filter(all_tasks_filter).count()

            d[user.username] = today_qi, task_start_qi, price_inquiry_qi, all_tasks
        return d

    def pre_process_on_post_method(self, data=None):
        obj = self._meta.model.objects.filter(pk=self.pk).first() if self.pk else None
        self.task_start_date = timezone.now() if (not obj or not obj.task_start_date) and self.task_start else obj.task_start_date if obj else None
        self.task_start_date2 = timezone.now() if (not obj or not obj.task_start_date2) and self.task_start2 else obj.task_start_date2 if obj else None
        self.assigned_trade_user_date = timezone.now() if (not obj or not obj.assigned_trade_user_date) and obj.assigned_trade_user else self.assigned_trade_user_date if obj else None
        self.assigned_trade_user_date2 = timezone.now() if (not obj or not obj.assigned_trade_user_date2) and obj.assigned_trade_user2 else self.assigned_trade_user_date2 if obj else None

    def progress_from_task_start(self, total_hour=72):
        return utils.progress_value(self.task_start_date, timezone.now(), total_hour)

    def progress_from_task_start2(self, total_hour=72):
        return utils.progress_value(self.task_start_date2, timezone.now(), total_hour)

    @classmethod
    def active(cls, user):
        count = 0
        qs = cls.objects.none()
        if getattr(user, 'base_group', None):
            if 'trade' in user.base_group:
                qs = cls.quotation_item_all_pending(inquiry_type='trade', path=None)
            elif 'bazar' in user.base_group:
                qs = cls.quotation_item_all_pending(inquiry_type='bazar', path=None)
        return qs.count()

    @classmethod
    def item_in_china_(cls, user):
        count = 0
        qs = cls.objects.none()
        inquiry_type_filter = Q(foreign_price_inquiry_done=True) & Q(need_foreign_price_inquiry=False) | \
                              Q(foreign_price_inquiry_done=False) & Q(need_foreign_price_inquiry=True)
        if getattr(user, 'base_group', None):
            if 'trade' in user.base_group:
                qs = cls.objects.filter(inquiry_type_filter, item_in_china=True, quotation__last_work_flow__current_state_name='استعلام قیمت').order_by('-quotation_id')
        return qs.count()

    @property
    def local_pending(self):
        return self.need_local_price_inquiry != self.local_price_inquiry_done

    @property
    def foreign_pending(self):
        return self.need_foreign_price_inquiry != self.foreign_price_inquiry_done

    def fee_(self):
        iqr = self.quotation_item_rel.all().last()
        if iqr is None:
            return 0
        match self.price_method:
            case 'last_sale':
                return iqr.goods_last_price
            case 'last_sale_q':
                return iqr.goods_q_last_price
            case 'price_avg':
                return iqr.goods_avg_price
            case 'sales_admin':
                return self.final_price
            case 'price_sheet1':
                return iqr.express_transportation_cost_1 if self.quotation.currency_ref_id == 1 else iqr.express_transportation_cost_3
            case 'price_sheet2':
                return iqr.air_transportation_cost_1 if self.quotation.currency_ref_id == 1 else iqr.air_transportation_cost_3
            case 'price_sheet3':
                return iqr.sea_transportation_cost_1 if self.quotation.currency_ref_id == 1 else iqr.sea_transportation_cost_3
            case 'price_market':
                return iqr.goods_price_market

    @property
    def fee(self):
        if self.quotation.is_official:
            total_ = (100 - (self.quotation.official_value + self.quotation.self_discount)) / 100
        else:
            total_ = (100 - self.quotation.self_discount) / 100

        fee_price = self.fee_()
        if fee_price is None:
            return 0

        return fee_price * total_

    @property
    def price(self):
        try:
            # if self.quotation.is_official:
            #     return self.fee * self.quantity * 1.09
            # else:
                return self.fee * self.quantity
        except Exception as e:
            show_error(e, __file__)
            return 0

    @property
    def duty(self):
        try:
            if self.quotation.is_official:
                return self.fee * self.quantity * 0
            else:
                return 0
        except Exception as e:
            show_error(e, __file__)
            return 0

    @property
    def tax(self):
        try:
            if self.quotation.is_official:
                return self.fee * self.quantity * 0.1
            else:
                return 0
        except Exception as e:
            show_error(e, __file__)
            return None


    class Meta:
        ordering = ['id']

