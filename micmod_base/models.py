import json
import uuid

from django.contrib.contenttypes.models import ContentType
# from datetime import datetime, timedelta
from django.utils.timezone import timedelta
from collections import Counter
from django.db.models import F, Sum, Subquery, OuterRef
from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import MaxValueValidator
from django.db.models import Q
from django.utils import timezone

# from django.contrib.auth.models import User
from accounts.models import User
from django.db import models, connection
from django.conf import settings
from accounts.templatetags.accounts_tag import has_groups,has_permission
from core.models import BaseManager
from extra_data.models import Customer
from tools import utils
from tools.myjalali import Persian
from tools.utils import show_error, diff_time, to_jalali_date

from translator import get_text as _
from workflow.models import WorkFlow
# Create your models here.
from .base import SLSDoc, CustomerGrade, DeliveryTime, MarketGrade, BaseModel, PriceMethod, AbsBaseModel, Currency, PaymentMethod
import datetime
from tools.utils import round_rial


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
        return qs.order_by('index', 'id')
      
    def get_query_set_order_by_index(self):
        return super().get_queryset().order_by('index', 'id')

    def all_quotations_for_factor(self):
        return self.get_queryset().order_by('is_over', 'id')

    # def remaining_quotations_for_factor(self, exclude_qi):
    #     return self.get_queryset().filter(quotation=self.quotation, pk__not_in=exclude_qi)

    def raw_as_qs(self, raw_query):
        """Execute a raw query and return a QuerySet.  The first column in the
        result set must be the id field for the model.
        :type raw_query: str | unicode
        :return: django.db.models.query.QuerySet
        """
        cursor = connection.cursor()
        try:
            cursor.execute(raw_query)
            return self.filter(id__in=(x[0] for x in cursor))
        except Exception as e:
            pass
        finally:
            cursor.close()


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


class CustomerRequest(AbsBaseModel):
    request_date = models.DateTimeField(_('request_date'), null=True, blank=True)
    expire_date = models.DateTimeField(_('expire_date'), null=True, blank=True)
    customer = models.ForeignKey(Customer, verbose_name=_('customer'), null=True, blank=True,
                                          to_field='sepidar_party_id', on_delete=models.DO_NOTHING)
    customer_phone = models.CharField(_('customer_phone'), max_length=16)
    cart_id = models.BigIntegerField(_('cart_id'))
    request_extra_data = models.JSONField(_('extra_data'), null=True, blank=True)


class CustomerRequestItem(AbsBaseModel):
    cr = models.ForeignKey(CustomerRequest, verbose_name=_('cutomer_request'), on_delete=models.DO_NOTHING, related_name='items')
    cart_item_id = models.BigIntegerField(_('cart_item_id'))
    quantity = models.FloatField(_('quantity'))

    product_id = models.BigIntegerField(_('product_id'), null=True, blank=True)
    customer_part_number = models.CharField(_('goods_code'), max_length=255, null=True, blank=True)
    customer_sku = models.CharField(_('goods_name'), max_length=32, null=True, blank=True)
    customer_description = models.TextField(_('customer_description'), max_length=2000, null=True, blank=True)

    request_item_extra_data = models.JSONField(_('extra_data'), null=True, blank=True)


class Quotation(SLSDoc):
    customer_request = models.ForeignKey(CustomerRequest, on_delete=models.DO_NOTHING, related_name='customer_quotations', null=True, blank=True)
    sales_admin_confirm = models.BooleanField(_('sales_admin_confirm'), default=False)
    description_sales = models.TextField(null=True, blank=True, verbose_name=_('description_sales'))
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
    description = models.TextField(max_length=2000, null=True, blank=True, verbose_name=_('description'))
    guid = models.UUIDField(_('guid'), default=None, editable=False, null=True, blank=True)
    sepidar_quotation_id = models.BigIntegerField(_('sepidar_quotation_id'), null=True, blank=True)
    sepidar_number = models.BigIntegerField(_('sepidar_number'), null=True, blank=True)

    workflows = GenericRelation('workflow.Workflow', related_query_name="model")
    quotation_self = models.ForeignKey('self', on_delete=models.DO_NOTHING, related_name='quotation_rel', null=True, blank=True)
    self_discount = models.PositiveSmallIntegerField(verbose_name=_('self_discount'), default=0, validators=[MaxValueValidator(100)])
    is_official = models.BooleanField(default=False, verbose_name=_('is_official'))
    official_value = models.FloatField(default=0, verbose_name=_('official_value'), null=True, blank=True)
    cancel = models.BooleanField(default=False, verbose_name=_('cancel'))
    force_inquiry = models.BooleanField(verbose_name=_('force_inquiry'), default=False)
    sale_type = models.ForeignKey(SaleType, on_delete=models.DO_NOTHING, related_name='quotations')
    is_direct = models.BooleanField(default=False, null=True, blank=True)

    custom_objects = QuotationManager()
    absolute_url_update = 'micmod_base:quotations.view'

    @classmethod
    def sale_user_report(cls, current_user, wf_states, from_date, to_date):
        filter_by_time = Q()
        if from_date and to_date:
            f_date = Persian(from_date).gregorian_datetime()
            t_date = Persian(to_date).gregorian_datetime()
            filter_by_time = Q(created_date__range=(f_date, t_date))
        is_sales_admin = current_user.groups.filter(name='sales_admin').exists()
        if is_sales_admin:
            sales_user = current_user.team.all().order_by('z_index')
        else:
            sales_user = [current_user]

        res = dict()
        inquiry_state = 'استعلام قیمت'
        for sale_user in sales_user:

            how_long_in_local_inquiry = []
            how_long_in_foreign_inquiry = []

            res[sale_user] = []
            local_price_condition = Q(last_work_flow__to_user=sale_user) & \
                                    Q(last_work_flow__current_state_name=inquiry_state) & \
                                    Q(quotation__need_local_price_inquiry=True) & \
                                    Q(quotation__is_deleted=False) & \
                                    Q(cancel=False)

            foreign_price_condition = Q(last_work_flow__to_user=sale_user) & \
                                      Q(last_work_flow__current_state_name=inquiry_state) & \
                                      Q(quotation__need_foreign_price_inquiry=True)& \
                                      Q(quotation__is_deleted=False) & \
                                      Q(cancel=False)
            foreign_inquiry_states_obj = cls.objects.filter(Q(last_work_flow__to_user=sale_user) &
                                                            Q(last_work_flow__current_state_name=inquiry_state) &
                                                            (Q(quotation__need_foreign_price_inquiry=True) &
                                                             Q(quotation__foreign_price_inquiry_done=False)) &
                                                            Q(quotation__is_deleted=False) & Q(cancel=False)).distinct()

            local_inquiry_states_obj = cls.objects.filter(Q(last_work_flow__to_user=sale_user) &
                                                          Q(last_work_flow__current_state_name=inquiry_state) &
                                                          (Q(quotation__need_local_price_inquiry=True) &
                                                           Q(quotation__local_price_inquiry_done=False)) &
                                                          Q(quotation__is_deleted=False) & Q(cancel=False)).distinct()

            if foreign_inquiry_states_obj or local_inquiry_states_obj:
                for local_inquiry_state_obj in local_inquiry_states_obj:
                    how_long_local_inquiry = diff_time(local_inquiry_state_obj.last_update_date, datetime.datetime.now())
                    how_long_in_local_inquiry.append(how_long_local_inquiry)
                for foreign_inquiry_state_obj in foreign_inquiry_states_obj:
                    how_long_foreign_inquiry = diff_time(foreign_inquiry_state_obj.last_update_date, datetime.datetime.now())
                    how_long_in_foreign_inquiry.append(how_long_foreign_inquiry)

            for wf_state in wf_states:
                condition = Q(last_work_flow__to_user=sale_user) & Q(last_work_flow__current_state_name=wf_state)
                wf = cls.objects.filter(filter_by_time & condition & Q(cancel=False)).count()
                wf_cancel = cls.objects.filter(filter_by_time & condition & Q(cancel=True)).count()
                res[sale_user].append((wf, wf_cancel))

            local_price_inquiry = cls.objects.filter(filter_by_time & local_price_condition).distinct().count()
            local_price_inquiry_not_responded = cls.objects.filter(filter_by_time & local_price_condition, quotation__local_price_inquiry_done=False).distinct()#.count()
            foreign_price_inquiry = cls.objects.filter(filter_by_time & foreign_price_condition).distinct().count()
            foreign_price_inquiry_not_responded = cls.objects.filter(filter_by_time & foreign_price_condition, quotation__foreign_price_inquiry_done=False).distinct()#.count()
            all_user_quotation = cls.objects.filter(last_work_flow__to_user=sale_user).count()
            # else:
            #     local_price_inquiry = cls.objects.filter(local_price_condition).distinct().count()
            #     foreign_price_inquiry = cls.objects.filter(foreign_price_condition).distinct().count()
            res[sale_user].append(all_user_quotation)
            res[sale_user].append((foreign_price_inquiry, local_price_inquiry,
                                   local_price_inquiry_not_responded, foreign_price_inquiry_not_responded,
                                   how_long_in_local_inquiry, how_long_in_foreign_inquiry))

        return res

    @property
    def total_discount(self):
        total = 0
        total_qi_discount = sum([qi.discount_value for qi in self.quotation.all()])
        return total

    @classmethod
    def get_qs(cls, request):
        q = request.POST.get('q')
        qs = cls.objects.get_access_object(request.user, q=q, quotation=True, lst=False).filter(is_direct=False)
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
    def sepidar_price(self):
        try:
            return sum(x.price for x in self.quotation.all())
        except Exception as e:
            show_error(e, __file__)
            return None

    @property
    def tax_amount(self):
        try:
            x = sum(x.tax for x in self.quotation.all())
            return x
            if x:
                return round(x, 1)
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
    def not_over_q(self):
        factored_count = 0
        not_factored_count = 0
        wh_count = 0
        order_count = 0
        all_fis = 0
        all_qis = 0
        if self.pk:
            qis = self.quotation.all()
            all_qis = qis.count()
            for item in qis:
                factor_items = item.qi.all()

                factor_item = item.qi.aggregate(total=Sum('quantity'))['total'] or 0
                for fi in factor_items:
                    supply_locations = fi.supply_locations.is_wh
                    if supply_locations:
                        wh_count += 1
                    else:
                        order_count += 1
                if factor_item > 0:
                    not_over = factor_item < item.quantity
                    # is_over = factor_item >= item.quantity
                    if not_over:
                        not_factored_count += 1
                    elif not not_over:
                        factored_count += 1
        nothing = all_qis - (not_factored_count + factored_count) if all_qis > not_factored_count + factored_count else 0
        all_fis = wh_count + order_count
        return factored_count, not_factored_count, wh_count, order_count, all_fis, nothing

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
        return sum_price

    @property
    def payment(self):
        sum_price = sum([qi.row_price for qi in self.quotation.all()])
        tax = sum([qi.tax for qi in self.quotation.all()])
        discount = sum([qi.discount_value for qi in self.quotation.all()])
        # sum_price = self.sum_prices

        # tax = self.tax_amount
        additions = self.addition or 0
        # if self.self_discount:
        #     discount = sum_price - ((self.self_discount / 100) * sum_price)
        # else:
        #     discount = 0

        total = sum_price + additions - discount + tax

        if self.currency_ref.title_en == 'Rial':
            return int(sum_price), int(additions), int(discount), int(tax), int(total)
        return sum_price, additions, discount, tax, total

    def fee_quotation(self):
        from inquiry.models import InquiryResult
        qis_pk = self.quotation.all().values_list('pk', flat=True)
        iqrs = InquiryResult.objects.filter(quotation_item__pk__in=qis_pk)

        # زیرکوئری برای پیدا کردن pk آخرین InquiryResult مربوط به هر QuotationItem
        latest_inquiry_subquery = InquiryResult.objects.filter(
            quotation_item=OuterRef('pk')
        ).order_by('-created_date')

        latest_inquiry_subquery = QuotationItem.objects.filter(
            pk=OuterRef('pk')
        ).order_by('-created_date')

        # فیلتر کردن فقط آخرین InquiryResult
        iqrs = InquiryResult.objects.filter(
            # quotation_item__pk__in=qis_pk,
            quotation_item_id__in=Subquery(latest_inquiry_subquery.values('quotation_item_rel')[:1]),
            # pk__in=Subquery(latest_inquiry_subquery.values('pk')[:1]),
        )
        pass


class QuotationItem(BaseModel):
    sales_description = models.CharField(_('sales_description'), max_length=255, null=True, blank=True)
    customer_request_item = models.ForeignKey(CustomerRequestItem, on_delete=models.DO_NOTHING, null=True, blank=True, related_name='customer_quotation_items')
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
    goods_code_fk = models.ForeignKey('extra_data.Item', on_delete=models.DO_NOTHING, related_name='quotation_item_rel', null=True, blank=True)
    itemid = models.BigIntegerField(null=True, blank=True, verbose_name=_("itemid"))
    goods_name = models.CharField(null=True, blank=True, verbose_name=_("goods_name"), max_length=200)
    stock_amount = models.FloatField(null=True, blank=True, verbose_name=_("stock_amount"))
    stock_amount_res = models.FloatField(null=True, blank=True, verbose_name=_("stock_amount_res"))
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

    price_method = models.CharField(max_length=128, verbose_name=_('price_method'), null=True, blank=True)
    final_price = models.FloatField(null=True, blank=True, verbose_name=_("final_price"))
    final_price_sh = models.FloatField(null=True, blank=True, verbose_name=_("final_price"))

    need_foreign_price_inquiry = models.BooleanField(verbose_name=_('need_foreign_price_inquiry'), default=False)
    foreign_price_inquiry_done = models.BooleanField(verbose_name=_('foreign_price_inquiry_done'), default=False)
    need_local_price_inquiry = models.BooleanField(verbose_name=_('need_local_price_inquiry'), default=False)
    local_price_inquiry_done = models.BooleanField(verbose_name=_('local_price_inquiry_done'), default=False)

    description = models.CharField(max_length=200, null=True, blank=True, verbose_name=_('description'))
    trade_price_code = models.ForeignKey('inquiry.PriceInquiryResult', on_delete=models.DO_NOTHING, verbose_name=_('trade_price_code'), related_name='trade_quotation_rel', null=True, blank=True)
    bazar_price_code = models.ForeignKey('inquiry.PriceInquiryResult', on_delete=models.DO_NOTHING, verbose_name=_('bazar_price_code'), related_name='bazar_quotation_rel', null=True, blank=True)
    selected_price_code = models.ForeignKey('inquiry.PriceInquiryResult', on_delete=models.DO_NOTHING,
                                            verbose_name=_('selected_price_code'), related_name='selected_price_quotation_rel',
                                            null=True, blank=True)
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
    price_target = models.FloatField(_('price_target'), null=True, blank=True)
    discount_per_item = models.FloatField(_('discount_per_item'), default=0)
    is_over = models.BooleanField(_('is_over'), default=False)
    price_json = models.JSONField(_('price_json'), null=True, blank=True)

    objects = QuotationItemManager()

    @property
    def price_json_for_template(self):
        out = self.price_json
        all_match_express = any(item['type'] == 'express' for item in self.price_json)
        all_match_air = any(item['type'] == 'air' for item in self.price_json)
        all_match_sea = any(item['type'] == 'sea' for item in self.price_json)

        if not all_match_express:
            out.append(
                {'ref': None, 'date': None, 'seen': None, 'type': 'express',
                 'iqref': None, 'jdate': None, 'title': None, 'value': None, 'access_type': None,
                 'unique_title': 'express'}
            )

        if not all_match_air:
            out.append(
                {'ref': None, 'date': None, 'seen': None, 'type': 'air',
                 'iqref': None, 'jdate': None, 'title': None, 'value': None, 'access_type': None,
                 'unique_title': 'air'}
            )

        if not all_match_sea:
            out.append(
                {'ref': None, 'date': None, 'seen': None, 'type': 'sea',
                 'iqref': None, 'jdate': None, 'title': None, 'value': None, 'access_type': None,
                 'unique_title': 'sea'}
            )

        return out

    @property
    def get_price_method_type(self):
        for item in self.price_json or []:  # self.price_json is `list of dict`
            if item.get('unique_title') == self.price_method:
                return item.get('type')

    @property
    def get_old_price_method_type(self):
        d = {
            'price_market': 'bazar',
            'price_sheet1': 'express',
            'price_sheet2': 'air',
            'price_sheet3': 'sea',
        }
        out = d.get(self.price_method) if self.price_method in d.keys() else self.price_method
        return out

    @classmethod
    def get_model_config(cls, app_label, model_name, filter_str):
        return {
            'fields': ['goods_code', 'goods_name', 'quantity', 'fee', 'created_date', 'goods_last_price', 'goods_q_last_price', 'discount_per_item'],
            'labels': ['کد کالا', 'نام کالا', 'تعداد', 'قیمت نهایی', 'تاریخ ایجاد', 'آخرین فاکتور', 'آخرین پیش‌فاکتور', 'تخفیف در هر ردیف']
        }
        # queryset = []
        # fields = []
        # labels = []
        # # model = apps.get_model(app_label, model_name)
        # for field in cls._meta.get_fields():
        #     if hasattr(field, 'verbose_name'):
        #         fields.append(field.name)
        #         labels.append(field.verbose_name)
        #     else:
        #         fields.append(field.name)
        #         labels.append(field.name)
        # config_json = {
        #     'fields': fields,
        #     'labels': labels
        # }
        # if filter_str:
        #     for filtr in filter_str:  # filter_str = [{'id':'4559'}, {'sku':'7589'}, ...]
        #         for k, v in filtr.items():
        #             # x = getattr(self, k, None)
        #             queryset = model.objects.filter(**{k: v})
        # else:
        #     queryset = model.objects.all()
        #
        # return queryset, config_json

    @property
    def lead_time_day(self):
        import re
        pattern = r'(\d)+-(\d)+.*\b(days|week|month)\b'
        b = ''
        if self.lead_time:
            try:
                matches = re.findall(pattern, self.lead_time)
                a, b, c = matches[0]
                if c == 'days':
                    pass
                if c == 'weeks':
                    b *= 7
                if c == 'months':
                    b *= 30
            except Exception as e:
                b = ''
        return b

    # @property
    # def appearance_or_real_part_number(self):
    #     try:
    #         customer = self.quotation.customer_party_id
    #         item = self.goods_code_fk
    #         customer_part_number = self.qi.all().first() #CustomerPartNumber.objects.filter(customer=customer, item=item).order_by('id').last()
    #         if customer_part_number:
    #             return customer_part_number.part_number_show
    #         else:
    #             return self.goods_code_fk.part_number
    #     except Exception as e:
    #         ...

    # @property
    # def appearance_or_real_part_number_(self):
    #     try:
    #         l = [("", "--------", "selected")]
    #         for item in self.qi.all():
    #             l.append((item.pk, item.part_number_show, ''))
    #         return {'list': l}
    #     except Exception as e:
    #         ...

    @property
    def not_over(self):
        factored_count = 0
        not_factored_count = 0
        wh_count = 0
        order_count = 0
        is_wh_complete = False
        is_wh_incomplete = False
        is_order_complete = False
        is_order_incomplete = False
        is_order_wh_complete = False
        is_order_wh_incomplete = False
        related_supply_locations = []
        for fi in self.qi.all() if self.pk else []:
            # if fi.supply_locations.order_m2m.exists():
            #     for oo in fi.supply_locations.order_m2m.all():
            #         related_supply_locations.append(
            #             {
            #                 fi.factor.pk: {
            #                     fi.pk: (fi.supply_locations.is_wh, oo.pk, oo.quantity,
            #                             oo.estimate_arrive_at)
            #                 }
            #             }
            #         )
            #
            #         related_supply_locations.append(
            #             {
            #                 fi.factor.pk: {
            #                     fi.pk: (fi.supply_locations.is_wh, fi.supply_locations.pk, fi.supply_locations.quantity,
            #                             fi.supply_locations.estimate_arrive_at)
            #                 }
            #             }
            #         )
            #     related_supply_locations = (fi.pk, fi.supply_locations.pk, fi.supply_locations.quantity,
            #                                 fi.supply_locations.estimate_arrive_at)
            related_supply_locations.append((fi.factor.pk, fi.supply_locations.pk, fi.supply_locations.quantity, fi.supply_locations.estimate_arrive_at))
        # related_supply_locations = [(fi.supply_locations.pk, fi.supply_locations.quantity, fi.supply_locations.estimate_arrive_at) for fi in self.qi.all() if self.pk]
        # related_supply_locations = self.qi.all()[0].supply_locations if self.pk else False

        q_wh = 0
        q_order = 0

        nothing = False
        if self.pk:
            factor_items = self.qi.all()
            factor_item_quantity = self.qi.aggregate(total=Sum('quantity'))['total'] or 0
            if factor_item_quantity > 0:
                x = []
                # not_over = factor_item_quantity < self.quantity
                is_over = factor_item_quantity >= self.quantity  # کامل مستهلک شده
                for fi in factor_items:
                    # wh_supply_location = fi.supply_locations.local_sepidar_wh_code
                    if fi.supply_locations.cancel:
                        for oo in fi.supply_locations.order_base_items.all():
                            if oo.sepidar_wh_code:
                                q_wh += oo.quantity
                            else:
                                q_order += oo.quantity
                    else:
                        q_order += fi.supply_locations.quantity
                    # if fi.supply_locations.is_wh:
                    #     q_wh += fi.supply_locations.quantity
                    # elif not fi.supply_locations.is_wh:
                    #     if fi.supply_locations.cancel:
                    #         for oo in fi.supply_locations.order_base_items.all():
                    #             q_order += oo.quantity
                    #     elif not fi.supply_locations.cancel:
                    #         q_order += fi.supply_locations.quantity

                    # if wh_supply_location and is_over:
                    #     is_wh_complete = True  # فاکتور قطعی
                    # elif wh_supply_location and not is_over:
                    #     is_wh_incomplete = True  # فاکتور ناقص
                    # elif not wh_supply_location and is_over:
                    #     is_order_complete = True
                    # elif not wh_supply_location and not is_over:
                    #     is_order_incomplete = True
                sum_quantity = sum([q_wh, q_order])
                if q_wh and q_order and sum_quantity >= self.quantity:
                    is_order_wh_complete = True
                elif q_wh and q_order and sum_quantity < self.quantity:
                    is_order_wh_incomplete = True
                elif q_wh and sum_quantity >= self.quantity:
                    is_wh_complete = True
                elif q_wh and sum_quantity < self.quantity:
                    is_wh_incomplete = True
                elif q_order and sum_quantity >= self.quantity:
                    is_order_complete = True
                elif q_order and sum_quantity < self.quantity:
                    is_order_incomplete = True

            else:
                nothing = True
            # all([fi.supply_locations.local_sepidar_wh_code for fi in factor_items True if factor_items else False])

        return (
            is_wh_complete, is_order_complete, is_order_wh_complete,
            is_wh_incomplete, is_order_incomplete, is_order_wh_incomplete,
            nothing, related_supply_locations
                )


    @property
    def total_quantity_in_factor(self):
        total_quantity = 0
        total_quantity_wh = 0
        all_factor_items = self.qi.all()
        for f in all_factor_items:
            if f.supply_locations.order_base_items.all().exists():
                for item in f.supply_locations.order_base_items.all():
                    if item.sepidar_wh_code:
                        total_quantity_wh += item.quantity
                        total_quantity += item.quantity
                    else:
                        total_quantity += item.quantity
            # if f.supply_locations.local_sepidar_wh_code:
            #     total_quantity_wh += f.quantity if f.quantity else 0
            else:
                total_quantity += f.quantity if f.quantity else 0
        return total_quantity, total_quantity_wh

    @property
    def remaining_quantity_in_factor(self):
        remaining_quantity = self.quantity - self.total_quantity_in_factor[0]
        if remaining_quantity > 0:
            return remaining_quantity
        else:
            return 0

    @classmethod
    def quotation_item_all_pending(cls, inquiry_type=None, path=None):
        past_path = '/micmod_base/quotationitem/past/quotationitems'
        inquiry_type_filter = Q(foreign_price_inquiry_done=True) & Q(need_foreign_price_inquiry=False) | \
                           Q(foreign_price_inquiry_done=False) & Q(need_foreign_price_inquiry=True) | \
                           Q(local_price_inquiry_done=True) & Q(need_local_price_inquiry=False) | \
                           Q(local_price_inquiry_done=False) & Q(need_local_price_inquiry=True)

        assigned_trade = (Q(task_start=True) | Q(task_start2=True) | Q(assigned_trade_user__isnull=False) | Q(assigned_trade_user2__isnull=False))

        if inquiry_type == 'trade':
            if path == past_path:
                inquiry_type_filter = (Q(quotation__cancel=True) | Q(is_deleted=True) |
                                       (Q(need_foreign_price_inquiry=True) & Q(foreign_price_inquiry_done=True)))

            else:
                inquiry_type_filter = (Q(foreign_price_inquiry_done=True) & Q(need_foreign_price_inquiry=False) |
                                       Q(foreign_price_inquiry_done=False) & Q(need_foreign_price_inquiry=True)) & \
                                      (Q(quotation__cancel=False) & Q(is_deleted=False))

        elif inquiry_type == 'bazar':
            if path == past_path:
                inquiry_type_filter = (Q(quotation__cancel=True) | Q(is_deleted=True) |
                                       (Q(need_local_price_inquiry=True) & Q(local_price_inquiry_done=True)))

            else:
                inquiry_type_filter = (Q(local_price_inquiry_done=True) & Q(need_local_price_inquiry=False) |
                                       Q(local_price_inquiry_done=False) & Q(need_local_price_inquiry=True)) & \
                                      (Q(quotation__cancel=False) & Q(is_deleted=False))

        # inquiry_state_condition = Q(quotation__last_work_flow__current_state_name='استعلام قیمت') | \
        #                            (
        #                                 Q(quotation__last_work_flow__state='استعلام قیمت') &
        #                                 Q(quotation__last_work_flow__current_state_name='پیش فاکتور اولیه') &
        #                                 (Q(task_start=True) | Q(task_start2=True) | Q(assigned_trade_user__isnull=False) | Q(assigned_trade_user2__isnull=False))
        #                            )


        inquiry_state_condition = Q(quotation__last_work_flow__current_state_name='استعلام قیمت') | \
                                   (
                                      Q(quotation__last_work_flow__state='استعلام قیمت') &
                                      Q(quotation__last_work_flow__current_state_name='پیش فاکتور اولیه') &
                                      (Q(task_start=True) | Q(task_start2=True) | Q(assigned_trade_user__isnull=False) | Q(assigned_trade_user2__isnull=False))
                                   )
        if path == past_path:
            x = cls.objects.full_queryset(inquiry_type_filter).order_by('-quotation_id')
        else:
            from django.db.models import Subquery

            quotation_items = cls.objects.full_queryset().filter(
                inquiry_type_filter,
                quotation_id__in=Subquery(
                    WorkFlow.objects.filter(
                        content_type=ContentType.objects.get_for_model(Quotation),
                        current_state_name="استعلام قیمت"
                    ).values('object_id')
                )
            ).order_by('-quotation_id')
            return quotation_items
            x = cls.objects.full_queryset(inquiry_state_condition, inquiry_type_filter).order_by('-quotation_id')
            # x = cls.objects.full_queryset(inquiry_type_filter, foreign_price_inquiry_done=False, need_foreign_price_inquiry=True, is_deleted=False, quotation__cancel=False).order_by('-quotation_id')
        return x

    @classmethod
    def get_inquiry_report(cls):
        trade_user = User.objects.filter(groups__name__in=['trade_user', 'trade_admin']).distinct().order_by('z_index')

        from pytz import timezone as ptz
        tz = ptz("UTC")
        yesterday = timezone.now() - timedelta(days=1)
        now = timezone.now()
        yesterday = datetime.datetime(year=yesterday.year, month=yesterday.month, day=yesterday.day, hour=16, minute=30,
                                      second=1, tzinfo=datetime.timezone.utc)  # begin from 20:00 yesterday

        today = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=16, minute=30, tzinfo=tz)  # end at 20:00 today

        d =dict()
        quotation_items = cls.objects.filter(Q(assigned_trade_user__in=trade_user) |
                                             Q(assigned_trade_user2__in=trade_user))
        for user in trade_user:
            if user.pk == 13:
                pass
            user_filter = Q(assigned_trade_user=user) | Q(assigned_trade_user2=user)
            time_filter = (Q(assigned_trade_user_date__gte=yesterday, assigned_trade_user_date__lte=today, assigned_trade_user=user) |
                           Q(assigned_trade_user_date2__gte=yesterday, assigned_trade_user_date2__lte=today, assigned_trade_user2=user))
            task_start_filter = (Q(task_start=True, assigned_trade_user=user) | Q(task_start2=True, assigned_trade_user2=user))
            task_not_start_filter = (Q(task_start=False, assigned_trade_user=user) | Q(task_start2=False, assigned_trade_user2=user))
            price_inquiry_filter = (Q(foreign_price_inquiry_done=True, assigned_trade_user=user) | Q(foreign_price_inquiry_done=True, assigned_trade_user2=user))

            all_tasks_qs = quotation_items.filter(user_filter)
            today_assigned = all_tasks_qs.filter(time_filter).count()
            today_task_start = all_tasks_qs.filter(task_start_filter, time_filter).count()
            today_all_price_inquiry_done = all_tasks_qs.filter(price_inquiry_filter, time_filter).count()
            all_price_inquiry_done = all_tasks_qs.filter(price_inquiry_filter).count()
            all_tasks = all_tasks_qs.count()
            reminder_task = all_tasks_qs.filter(foreign_price_inquiry_done=False, need_foreign_price_inquiry=True, is_deleted=False, quotation__cancel=False).count()

            # reminder_task = all_tasks - all_price_inquiry_done
            # reminder_task = all_tasks_qs.filter(need_foreign_price_inquiry=True, foreign_price_inquiry_done=False, is_deleted=False,
            #                                    quotation__cancel=False, quotation__last_work_flow__current_state_name='استعلام قیمت').count() #all_tasks_qs.filter(time_filter).count() - all_price_inquiry_done


            d[user] = today_assigned, today_task_start, today_all_price_inquiry_done, reminder_task, all_tasks, task_not_start_filter
        return d

    def pre_process_on_post_method(self, data=None):
        obj = self if self.pk else None
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

    def create_price_json_for_old_qi(self):
        # return
        print(f'row: {self.index}, qi: {self.pk}')
        price = self.fee_()

        self.final_price = price
        iqr = self.quotation_item_rel.all().last()
        price_list = [iqr, self.selected_price_code]

        price_list_json = []
        for item in price_list:
            if item:
                if getattr(item, 'express_transportation_cost_1', None):
                    price_list_json.append(
                        {
                            "ref": None,
                            "date": item.price_update_date.isoformat() if item.price_update_date else None,
                            "jdate": to_jalali_date(item.price_update_date) if item.price_update_date else None,
                            "seen": None,
                            "type": 'exp',
                            "iqref": None,
                            "title": '2-3 هفته',
                            "value": item.express_transportation_cost_3 if self.quotation.currency_ref.title_en.lower() != 'rial' else item.express_transportation_cost_1,
                            "access_type": None,
                            "unique_title": 'express'
                        }
                    )
                if getattr(item, 'air_transportation_cost_1', None):
                    price_list_json.append(
                        {
                            "ref": None,
                            "date": item.price_update_date.isoformat() if item and item.price_update_date else None,
                            "jdate": to_jalali_date(item.price_update_date) if item and item.price_update_date else None,
                            "seen": None,
                            "type": 'air',
                            "iqref": None,
                            "title": '3-5 هفته',
                            "value": item.air_transportation_cost_3 if self.quotation.currency_ref.title_en.lower() != 'rial' else item.air_transportation_cost_1,
                            "access_type": None,
                            "unique_title": 'air'
                        }
                    )
                if getattr(item, 'sea_transportation_cost_1', None):
                    price_list_json.append(
                        {
                            "ref": None,
                            "date": item.price_update_date.isoformat() if item and item.price_update_date else None,
                            "jdate": to_jalali_date(item.price_update_date) if item and item.price_update_date else None,
                            "seen": None,
                            "type": 'sea',
                            "iqref": None,
                            "title": '12-14 هفته',
                            "value": item.sea_transportation_cost_3 if self.quotation.currency_ref.title_en.lower() != 'rial' else item.sea_transportation_cost_1,
                            "access_type": None,
                            "unique_title": 'sea'
                        }
                    )
                if getattr(item, 'goods_price_market', None):
                    price_list_json.append(
                        {
                            "ref": None,
                            "date": item.price_update_date.isoformat() if item and item.price_update_date else None,
                            "jdate": to_jalali_date(item.price_update_date) if item and item.price_update_date else None,
                            "seen": None,
                            "type": 'bazar',
                            "iqref": None,
                            "title": 'بازار',
                            "value": item.goods_price_market,
                            "access_type": None,
                            "unique_title": 'bazar'
                        }
                    )
                if getattr(item, 'goods_last_price', None):
                    price_list_json.append(
                        {
                            "ref": None,
                            "date": item.goods_last_sale.isoformat() if item else None,
                            "jdate": to_jalali_date(item.goods_last_sale) if item else None,
                            "seen": None,
                            "type": 'فاکتور',
                            "iqref": None,
                            "title": 'فاکتور',
                            "value": item.goods_last_price,
                            "access_type": None,
                            "unique_title": 'goods_last_price',
                            "quantity": item.goods_total_sales,
                        }
                    )
                if getattr(item, 'goods_q_last_price', None):
                    price_list_json.append(
                        {
                            "ref": None,
                            "date": item.goods_q_last_sale.isoformat() if item else None,
                            "jdate": to_jalali_date(item.goods_q_last_sale) if item else None,
                            "seen": None,
                            "type": 'پیش فاکتور',
                            "iqref": None,
                            "title": 'پیش فاکتور',
                            "value": item.goods_q_last_price,
                            "access_type": None,
                            "unique_title": 'goods_q_last_price',
                            "quantity": item.goods_q_total_sales,
                        }
                    )
        self.price_json = price_list_json
        self.save()

    def fee_(self):
        if self.final_price:
            return self.final_price
        iqr = self.quotation_item_rel.all().last()
        if iqr is None:
            return self.final_price or 0
        if iqr.quotation_item.quotation.currency_ref.title == 'ریال':
            currency_ref = 'RIAL'
        else:
            currency_ref = 'RMB'
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
                x = iqr.express_transportation_cost_1 if self.quotation.currency_ref_id == 1 else iqr.express_transportation_cost_3
                return round_rial(x, currency_ref) if isinstance(x, (int, float)) else 1
            case 'price_sheet2':
                x = iqr.air_transportation_cost_1 if self.quotation.currency_ref_id == 1 else iqr.air_transportation_cost_3
                return round_rial(x, currency_ref) if isinstance(x, (int, float)) else 1
            case 'price_sheet3':
                x = iqr.sea_transportation_cost_1 if self.quotation.currency_ref_id == 1 else iqr.sea_transportation_cost_3
                return round_rial(x, currency_ref) if isinstance(x, (int, float)) else 1
            case 'price_market':
                x = iqr.goods_price_market
                return round_rial(x, currency_ref='RIAL') if isinstance(x, (int, float)) else 1

    @property
    def net_price(self):
        try:
            return (self.fee_()) * self.quantity if self.pk and self.fee_() else 0
        except Exception as e:
            return 0
            raise ValueError('قیمت یا تعداد در یکی از ردیف ها اشتباه است')

    @property
    def net_price_and_tax_discount(self):
        try:
            net_price = self.net_price
            net_discount = self.quantity * self.discount_per_item
            tax_discount = (net_price - net_discount) * (1 - ((100 + settings.TAX_VALUE - self.quotation.official_value) / (100 + settings.TAX_VALUE)))
            return net_discount - tax_discount
        except Exception as e:
            return 0
            raise ValueError('قیمت یا تعداد در یکی از ردیف ها اشتباه است')

    @property
    def net_price_after_tax_discount(self):
        x = self.net_price
        value = self.net_price
        if self.quotation.is_official:
            value -= (self.net_price * (self.quotation.official_value / 100))
        return value

    @property
    def fee(self):
        if self.quotation.is_official:
            official_value = settings.TAX_VALUE if self.quotation.official_value >= 10 else self.quotation.official_value
            total_ = (100 - (official_value)) / 100
        else:
            total_ = (100 - self.quotation.self_discount) / 100
        try:
            fee_price = self.fee_() - self.discount_per_item
        except Exception as e:
            print('========== fee price is None ============')
            fee_price = None
        if fee_price is None:
            return 0

        return fee_price * total_

    @property
    def sepidar_discount(self):
        if self.quotation.is_official:
            official_value = settings.TAX_VALUE if self.quotation.official_value >= 10 else self.quotation.official_value
            total_ = official_value / 100
        else:
            total_ = self.quotation.self_discount / 100

        fee_price = self.fee_()
        if fee_price is None:
            return 0

        return fee_price * total_

    @property
    def sepidar_fee(self):
        fee_price = self.fee_()
        if fee_price is None:
            return 0

        return fee_price

    @property
    def row_price(self):
        return round_rial(float(self.net_price))

    @property
    def price(self):
        try:
            if self.quotation.currency_ref.title == 'ریال':
                return round_rial(int(self.net_price - self.discount_value + self.tax))
            else:
                return self.net_price - self.discount_value + self.tax
            return self.fee_() * self.quantity + (self.tax * (self.quotation.official_value * 10)/100)
            return self.fee_() * self.quantity + self.tax
        except Exception as e:
            show_error(e, __file__)
            return 0

    @property
    def duty(self):
        try:
            if self.quotation.is_official:
                return self.fee_() * self.quantity * 0
            else:
                return 0
        except Exception as e:
            show_error(e, __file__)
            return 0

    @property
    def tax(self):
        try:
            if self.quotation.is_official:
                x = (self.net_price - sum(self.discount_tuple)) * (settings.TAX_VALUE / 100)
                if self.quotation.currency_ref.title_en == 'Rial':
                    return int(x)
                return x
                if x:
                    return round(x, 1)
            else:
                return 0
        except Exception as e:
            show_error(e, __file__)
            return None

    @property
    def discount_tuple(self):
        try:
            net_price = self.net_price
            row_discount = self.quantity * self.discount_per_item
            row_discount_base_percentage = net_price * (self.quotation.self_discount / 100) if self.pk else 0
            tax_discount = (net_price - row_discount - row_discount_base_percentage) * (
                        1 - ((100 + settings.TAX_VALUE - self.quotation.official_value) / (100 + settings.TAX_VALUE)))
        except Exception as e:
            row_discount = tax_discount = row_discount_base_percentage = 0
        return tax_discount, row_discount_base_percentage, row_discount

    @property
    def discount_value(self):
        x = sum(self.discount_tuple)
        try:
            return int(x)
        except Exception as e:
            print(e)
            return 0


    @classmethod
    def inquiry_not_started(cls, trade_user):
        trade_users = User.objects.filter(groups__name__in=['trade_user', 'trade_admin'])
        my_inquiry_not_started_count = 0
        item_in_china = 0
        new_inquiry = 0
        for user in trade_users:
            if trade_user == user:
                f = Q(foreign_price_inquiry_done=True) & Q(need_foreign_price_inquiry=False) | \
                    Q(foreign_price_inquiry_done=False) & Q(need_foreign_price_inquiry=True) & \
                    (Q(quotation__cancel=False) & Q(is_deleted=False))

                filter_condition = (Q(assigned_trade_user=trade_user) & Q(task_start=False)) | \
                                   (Q(assigned_trade_user2=trade_user) & Q(task_start2=False)) & \
                                   (Q(quotation__last_work_flow__current_state_name='استعلام قیمت'))

                filter_condition_china = Q(item_in_china=True) & Q(quotation__last_work_flow__current_state_name='استعلام قیمت')
                not_started = cls.objects.filter(f, filter_condition)

                my_inquiry_not_started_count = not_started.count()
                item_in_china = cls.objects.filter(f, filter_condition_china).order_by('-quotation_id').count()
                new_inquiry = cls.quotation_item_all_pending(inquiry_type=trade_user.base_group, path=None).count()
                break

        filter_condition = (Q(need_foreign_price_inquiry=True) & Q(foreign_price_inquiry_done=False) &
                            Q(assigned_trade_user__isnull=True) & Q(assigned_trade_user2__isnull=True) &
                            Q(task_start=False) & Q(task_start2=False) & Q(quotation__cancel=False) &
                            Q(quotation__last_work_flow__current_state_name='استعلام قیمت'))
        
        inquiry_not_started_count = QuotationItem.objects.filter(filter_condition).count()
        return my_inquiry_not_started_count, inquiry_not_started_count, item_in_china, new_inquiry



    class Meta:
        ordering = ['id']
