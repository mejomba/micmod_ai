from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q

from accounts.models import User
from core.models import BaseModel
from micmod_base.base import SLSDoc, DeliveryTime
from micmod_base.models import Quotation, SaleType, QuotationItem
from tools.utils import show_error

from translator import get_text as _


class Factor(SLSDoc):
    q = models.ForeignKey(Quotation, verbose_name=_('q'), related_name='q', on_delete=models.DO_NOTHING)

    delivery_time = models.CharField(choices=DeliveryTime, max_length=10, null=True, blank=True,
                                     verbose_name=_('delivery_time'), default="2-3 week")
    description = models.TextField(max_length=1000, null=True, blank=True, verbose_name=_('description'))
    guid = models.UUIDField(_('guid'), default=None, editable=False, null=True, blank=True)
    sepidar_quotation_id = models.BigIntegerField(_('sepidar_quotation_id'), null=True, blank=True)
    sepidar_number = models.BigIntegerField(_('sepidar_number'), null=True, blank=True)

    workflows = GenericRelation('workflow.Workflow', related_query_name="model")
    factor_self = models.ForeignKey('self', on_delete=models.DO_NOTHING, related_name='factor_rel', null=True, blank=True)
    self_discount = models.PositiveSmallIntegerField(verbose_name=_('self_discount'), default=0, validators=[MaxValueValidator(100)])
    is_official = models.BooleanField(default=False, verbose_name=_('is_official'))
    official_value = models.FloatField(default=0, verbose_name=_('official_value'), null=True, blank=True)
    cancel = models.BooleanField(default=False, verbose_name=_('cancel'))

    sale_type = models.ForeignKey(SaleType, on_delete=models.DO_NOTHING, related_name='factors')

    @property
    def total_discount(self):
        total = 0
        total_qi_discount = sum([qi.discount_value for qi in self.quotation.all()])
        return total

    @classmethod
    def get_qs(cls, request):
        q = request.POST.get('q')
        qs = cls.objects.get_access_object(request.user, q=q, quotation=True)
        return qs

    @classmethod
    def get_qs_count(cls, user):
        return len(cls.objects.get_access_object(user, q='active', quotation=True))

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


class FactorItem(BaseModel):
    factor = models.ForeignKey(Factor, on_delete=models.DO_NOTHING, verbose_name=_('factor'))
    qi = models.ForeignKey(QuotationItem, verbose_name=_('qi'), related_name='qi', on_delete=models.DO_NOTHING)

    index = models.IntegerField(null=True, blank=True, verbose_name=_("index"))
    quantity = models.BigIntegerField(null=True, blank=True, verbose_name=_("quantity"))
    delivery_time = models.CharField(choices=DeliveryTime, max_length=20, null=True, blank=True,
                                     verbose_name=_('delivery_time'))
    custom_price = models.FloatField(_('custom_price'), null=True, blank=True)

    # @classmethod
    # def quotation_item_all_pending(cls, inquiry_type=None, path=None):
    #     past_path = '/micmod_base/quotationitem/past/quotationitems'
    #     inquiry_type_filter = Q(foreign_price_inquiry_done=True) & Q(need_foreign_price_inquiry=False) | \
    #                        Q(foreign_price_inquiry_done=False) & Q(need_foreign_price_inquiry=True) | \
    #                        Q(local_price_inquiry_done=True) & Q(need_local_price_inquiry=False) | \
    #                        Q(local_price_inquiry_done=False) & Q(need_local_price_inquiry=True)
    #
    #     if inquiry_type == 'trade':
    #         if path == past_path:
    #             inquiry_type_filter = Q(need_foreign_price_inquiry=True) & Q(foreign_price_inquiry_done=True)
    #         else:
    #             inquiry_type_filter = Q(foreign_price_inquiry_done=True) & Q(need_foreign_price_inquiry=False) | \
    #                                   Q(foreign_price_inquiry_done=False) & Q(need_foreign_price_inquiry=True)
    #
    #     elif inquiry_type == 'bazar':
    #         if path == past_path:
    #             inquiry_type_filter = Q(need_local_price_inquiry=True) & Q(local_price_inquiry_done=True)
    #         else:
    #             inquiry_type_filter = Q(local_price_inquiry_done=True) & Q(need_local_price_inquiry=False) | \
    #                                   Q(local_price_inquiry_done=False) & Q(need_local_price_inquiry=True)
    #     if path == past_path:
    #         x = cls.objects.full_queryset(inquiry_type_filter).order_by('-quotation_id')
    #     else:
    #         x = cls.objects.full_queryset(inquiry_type_filter, quotation__last_work_flow__current_state_name='استعلام قیمت', quotation__cancel=False).order_by('-quotation_id')
    #     return x
    #
    # @classmethod
    # def get_inquiry_report(cls):
    #     trade_user = User.objects.filter(groups__name__in=['trade_user', 'trade_admin']).distinct()#.order_by('username')
    #
    #     from pytz import timezone as ptz
    #     tz = ptz("UTC")
    #     yesterday = timezone.now() - timedelta(days=1)
    #     now = timezone.now()
    #     yesterday = datetime.datetime(year=yesterday.year, month=yesterday.month, day=yesterday.day, hour=16, minute=30,
    #                                   second=1, tzinfo=datetime.timezone.utc)  # begin from 20:00 yesterday
    #
    #     today = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=16, minute=30, tzinfo=tz)  # end at 20:00 today
    #
    #     d =dict()
    #     quotation_items = cls.objects.filter(Q(assigned_trade_user__in=trade_user) |
    #                                          Q(assigned_trade_user2__in=trade_user))
    #     for user in trade_user:
    #         if user.pk == 13:
    #             pass
    #         user_filter = Q(assigned_trade_user=user) | Q(assigned_trade_user2=user)
    #         time_filter = (Q(assigned_trade_user_date__gte=yesterday, assigned_trade_user_date__lte=today, assigned_trade_user=user) |
    #                        Q(assigned_trade_user_date2__gte=yesterday, assigned_trade_user_date2__lte=today, assigned_trade_user2=user))
    #         task_start_filter = (Q(task_start=True, assigned_trade_user=user) | Q(task_start2=True, assigned_trade_user2=user))
    #         price_inquiry_filter = (Q(foreign_price_inquiry_done=True, assigned_trade_user=user) | Q(foreign_price_inquiry_done=True, assigned_trade_user2=user))
    #
    #         all_tasks_qs = quotation_items.filter(user_filter)
    #         today_assigned = all_tasks_qs.filter(time_filter).count()
    #         today_task_start = all_tasks_qs.filter(task_start_filter, time_filter).count()
    #         all_price_inquiry_done = all_tasks_qs.filter(price_inquiry_filter, time_filter).count()
    #         all_tasks = all_tasks_qs.count()
    #
    #         reminder_task = all_tasks_qs.filter(time_filter).count() - all_price_inquiry_done
    #
    #         d[user.username] = today_assigned, today_task_start, all_price_inquiry_done, reminder_task, all_tasks
    #     return d

    # def pre_process_on_post_method(self, data=None):
    #     obj = self if self.pk else None
    #     self.task_start_date = timezone.now() if (not obj or not obj.task_start_date) and self.task_start else obj.task_start_date if obj else None
    #     self.task_start_date2 = timezone.now() if (not obj or not obj.task_start_date2) and self.task_start2 else obj.task_start_date2 if obj else None
    #     self.assigned_trade_user_date = timezone.now() if (not obj or not obj.assigned_trade_user_date) and obj.assigned_trade_user else self.assigned_trade_user_date if obj else None
    #     self.assigned_trade_user_date2 = timezone.now() if (not obj or not obj.assigned_trade_user_date2) and obj.assigned_trade_user2 else self.assigned_trade_user_date2 if obj else None

    # def progress_from_task_start(self, total_hour=72):
    #     return utils.progress_value(self.task_start_date, timezone.now(), total_hour)

    # def progress_from_task_start2(self, total_hour=72):
    #     return utils.progress_value(self.task_start_date2, timezone.now(), total_hour)

    # @classmethod
    # def active(cls, user):
    #     count = 0
    #     qs = cls.objects.none()
    #     if getattr(user, 'base_group', None):
    #         if 'trade' in user.base_group:
    #             qs = cls.quotation_item_all_pending(inquiry_type='trade', path=None)
    #         elif 'bazar' in user.base_group:
    #             qs = cls.quotation_item_all_pending(inquiry_type='bazar', path=None)
    #     return qs.count()

    # @classmethod
    # def item_in_china_(cls, user):
    #     qs = cls.objects.none()
    #     inquiry_type_filter = Q(foreign_price_inquiry_done=True) & Q(need_foreign_price_inquiry=False) | \
    #                           Q(foreign_price_inquiry_done=False) & Q(need_foreign_price_inquiry=True)
    #     if getattr(user, 'base_group', None):
    #         if 'trade' in user.base_group:
    #             qs = cls.objects.filter(inquiry_type_filter, item_in_china=True, quotation__last_work_flow__current_state_name='استعلام قیمت').order_by('-quotation_id')
    #     return qs.count()

    # @property
    # def local_pending(self):
    #     return self.need_local_price_inquiry != self.local_price_inquiry_done

    # @property
    # def foreign_pending(self):
    #     return self.need_foreign_price_inquiry != self.foreign_price_inquiry_done

    # def fee_(self):
    #     iqr = self.quotation_item_rel.all().last()
    #     if iqr is None:
    #         return self.final_price or 0
    #     if iqr.quotation_item.quotation.currency_ref.title == 'ریال':
    #         currency_ref = 'RIAL'
    #     else:
    #         currency_ref = 'RMB'
    #     match self.price_method:
    #         case 'last_sale':
    #             return iqr.goods_last_price
    #         case 'last_sale_q':
    #             return iqr.goods_q_last_price
    #         case 'price_avg':
    #             return iqr.goods_avg_price
    #         case 'sales_admin':
    #             return self.final_price
    #         case 'price_sheet1':
    #             x = iqr.express_transportation_cost_1 if self.quotation.currency_ref_id == 1 else iqr.express_transportation_cost_3
    #             return round_rial(x, currency_ref) if isinstance(x, (int, float)) else 1
    #         case 'price_sheet2':
    #             x = iqr.air_transportation_cost_1 if self.quotation.currency_ref_id == 1 else iqr.air_transportation_cost_3
    #             return round_rial(x, currency_ref) if isinstance(x, (int, float)) else 1
    #         case 'price_sheet3':
    #             x = iqr.sea_transportation_cost_1 if self.quotation.currency_ref_id == 1 else iqr.sea_transportation_cost_3
    #             return round_rial(x, currency_ref) if isinstance(x, (int, float)) else 1
    #         case 'price_market':
    #             x = iqr.goods_price_market
    #             return round_rial(x, currency_ref='RIAL') if isinstance(x, (int, float)) else 1

    # @property
    # def net_price(self):
    #     try:
    #         return self.fee_() * self.quantity if self.pk and self.fee_() else 0
    #     except Exception as e:
    #         return 0
    #         raise ValueError('قیمت یا تعداد در یکی از ردیف ها اشتباه است')

    # @property
    # def net_price_after_tax_discount(self):
    #     value = self.net_price
    #     if self.quotation.is_official:
    #         value -= (self.net_price * (self.quotation.official_value / 100))
    #     return value

    # @property
    # def fee(self):
    #     if self.quotation.is_official:
    #         official_value = settings.TAX_VALUE if self.quotation.official_value >= 10 else self.quotation.official_value
    #         total_ = (100 - (official_value)) / 100
    #     else:
    #         total_ = (100 - self.quotation.self_discount) / 100
    #
    #     fee_price = self.fee_()
    #     if fee_price is None:
    #         return 0

        # return fee_price * total_

    # @property
    # def sepidar_discount(self):
    #     if self.quotation.is_official:
    #         official_value = settings.TAX_VALUE if self.quotation.official_value >= 10 else self.quotation.official_value
    #         total_ = official_value / 100
    #     else:
    #         total_ = self.quotation.self_discount / 100
    #
    #     fee_price = self.fee_()
    #     if fee_price is None:
    #         return 0
    #
    #     return fee_price * total_

    # @property
    # def sepidar_fee(self):
    #     fee_price = self.fee_()
    #     if fee_price is None:
    #         return 0
    #
    #     return fee_price
    #
    # @property
    # def row_price(self):
    #     return round_rial(int(self.net_price))
    #
    # @property
    # def price(self):
    #     try:
    #         if self.quotation.currency_ref.title == 'ریال':
    #             return round_rial(int(self.net_price - self.discount_value + self.tax))
    #         else:
    #             return self.net_price - self.discount_value + self.tax
    #         return self.fee_() * self.quantity + (self.tax * (self.quotation.official_value * 10)/100)
    #         return self.fee_() * self.quantity + self.tax
    #     except Exception as e:
    #         show_error(e, __file__)
    #         return 0
    #
    # @property
    # def duty(self):
    #     try:
    #         if self.quotation.is_official:
    #             return self.fee_() * self.quantity * 0
    #         else:
    #             return 0
    #     except Exception as e:
    #         show_error(e, __file__)
    #         return 0
    #
    # @property
    # def tax(self):
    #     try:
    #         if self.quotation.is_official:
    #             # return self.fee_() * self.quantity * 0.1
    #             return self.net_price_after_tax_discount * (settings.TAX_VALUE / 100)
    #         else:
    #             return 0
    #     except Exception as e:
    #         show_error(e, __file__)
    #         return None
    #
    # @property
    # def discount_tuple(self):
    #     try:
    #         row_discount = self.discount_per_item * self.quantity if self.pk else 0
    #         tax_discount = self.net_price * (self.quotation.official_value / 100) if self.pk and self.quotation.is_official else 0
    #         discount_for_all = (self.net_price - tax_discount) * (self.quotation.self_discount / 100) if self.pk else 0
    #     except Exception as e:
    #         # raise Exception(f'اشکال در ردیف {self.pk} \n{__file__} \n در خط {e.__traceback__.tb_lineno}')
    #         row_discount = tax_discount = discount_for_all = 0
    #     return tax_discount, discount_for_all, row_discount
    #
    # @property
    # def discount_value(self):
    #     return sum(self.discount_tuple)

    class Meta:
        ordering = ['id']

