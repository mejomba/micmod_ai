from django.db import models

from accounts.models import User
from core.models import BaseModel, BaseModeWF
from extra_data.models import Item, Customer
from translator import get_text as _


class Expert(BaseModel):
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='experts', null=True, blank=True)
    name = models.CharField(max_length=255, verbose_name='نام کارشناس', blank=True, null=True)

    def __str__(self):
        return self.name


class Contract(BaseModeWF):
    # contract_title = models.CharField(max_length=100, unique=True)
    goods_code_fk = models.ForeignKey(Item, on_delete=models.DO_NOTHING)
    project_name_en = models.CharField(max_length=250, null=True, blank=True)
    customer_party_id = models.ForeignKey(Customer, verbose_name=_('party_id'), null=True, blank=True,
                                          to_field='sepidar_party_id', on_delete=models.DO_NOTHING,
                                          db_column='customer_party_id')
    customer_sheet_count = models.PositiveIntegerField(default=0)
    customer_board_count = models.PositiveIntegerField(default=0)
    customer_total_board_count = models.PositiveIntegerField(default=0)
    first_setup_time = models.PositiveBigIntegerField(default=0, null=True, blank=True)
    second_setup_time = models.PositiveBigIntegerField(default=0, null=True, blank=True)
    pad_count = models.PositiveIntegerField(default=0)
    ic_pad_count = models.PositiveIntegerField(default=0)
    not_assembly_pad_count = models.PositiveIntegerField(default=0)
    first_setup_cost = models.PositiveBigIntegerField(default=0, null=True, blank=True)
    second_setup_cost = models.PositiveBigIntegerField(default=0, null=True, blank=True)
    pad_cost = models.PositiveIntegerField(default=0, null=True, blank=True)
    ic_pad_cost = models.PositiveIntegerField(default=0, null=True, blank=True)
    total_cost = models.PositiveBigIntegerField(default=0, null=True, blank=True)
    finish = models.BooleanField(default=False)
    def __str__(self):
        return self.contract_title

    @property
    def contract_title(self):
        return f'PCBA_{self.pk}'

    @property
    def contract_cost(self):
        total = (self.customer_total_board_count * self.pad_count * self.pad_cost) + self.first_setup_cost
        return total


class CustomerItemReceipt(BaseModeWF):
    INCOMPLETE = '1'
    COMPLETED = '2'
    STATUS_CHOICES = [(COMPLETED, _('کامل')), (INCOMPLETE, _('ناقص'))]
    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING, related_name='customer_contract')
    receipt_date = models.DateField(null=True, blank=True, verbose_name='تاربخ دریافت')
    status = models.CharField(max_length=2, choices=STATUS_CHOICES, default=INCOMPLETE, verbose_name='وضعیت دریافت کالا')
    total_board_receipt_count = models.PositiveIntegerField(default=0, verbose_name='تعداد کل برد دریافتی', null=True, blank=True)
    parent = models.ForeignKey('self', on_delete=models.DO_NOTHING, null=True, blank=True, verbose_name='رسید مربوطه')
    # items = models.ForeignKey(ItemsInCustomerReceipt, on_delete=models.DO_NOTHING, verbose_name='کالا', null=True, blank=True)
    # goods_code_fk = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='goods_code_customer_receipt')
    # get_item_date = models.DateField(null=True, blank=True, verbose_name='تاریخ تحویل کالا')

    def __str__(self):
        return f'{self.pk} - {self.title}'


class ItemsInCustomerReceipt(BaseModeWF):
    goods_code_fk = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='goods_code_item_customer_receipt', verbose_name='کالا', null=True, blank=True)
    quantity = models.PositiveIntegerField(default=0, verbose_name='تعداد')
    receipt_date = models.DateField(verbose_name='تاریخ دریافت کالا', null=True, blank=True)
    customer_item_receipt = models.ForeignKey(CustomerItemReceipt, related_name='items', on_delete=models.DO_NOTHING, verbose_name='رسید کالای مربوطه')
    part_number = models.CharField(max_length=255, null=True, blank=True, verbose_name='پارت نامبر')

    def part_number_list(self, contract_id):
        try:
            part_numbers = ProjectItemList.objects.filter(contract_id=contract_id)
            l = [("", "--------", "selected")]
            for item in part_numbers:
                l.append((item.pk, item.part_number, ''))
            return {'list': l}
        except Exception as e:
            ...


class ProjectItemList(BaseModeWF):
    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING, verbose_name='قرارداد')
    goods_code_fk = models.ForeignKey(Item, on_delete=models.DO_NOTHING, verbose_name='کد کالا', null=True, blank=True)
    part_number = models.CharField(max_length=255, null=True, blank=True, verbose_name='پارت نامبر')
    quantity = models.PositiveIntegerField(default=0, verbose_name='تعداد')
    description = models.TextField(null=True, blank=True, verbose_name='توضیحات')

    def __str__(self):
        return f'{self.pk}'


class ProductionDayActivities(BaseModeWF):

    # ACTIVITY CHOICES
    COUNTING_AND_ITEM_LIST = '1'
    DEVICE_FIRST_SETUP = '2'
    DEVICE_SECOND_SETUP = '3'
    ASSEMBLY = '4'
    OVEN = '5'
    QS = '6'
    PACKING = '7'
    DELIVERY = '8'
    TOP_ASSEMBLY = '9'
    BOTTOM_ASSEMBLY = '10'
    TOP_OVEN = '11'
    BOTTOM_OVEN = '12'
    DIP_ASSEMBLY = '13'
    GLUING = '14'
    DEEP_OUTSOURCING_ASSEMBLY = '15'
    # DEEP_LOCAL_ASSEMBLY = '16'
    MACHINE_FAILURE = '17'

    # ASSEMBLY CHOICES
    TIN_DOUGH = '1'
    GLUE = '2'

    FIRST_SHIFT = '1'
    SECOND_SHIFT = '2'
    OVER_TIME = '3'

    ASSEMBLY_CHOICES = [(TIN_DOUGH, _('خمیر قلع')), (GLUE, _('چسب'))]
    WORK_TIME_CHOICES = [(FIRST_SHIFT, _('شیفت 1')), (SECOND_SHIFT, _('شیفت 2')), (OVER_TIME, _('اضافه کاری'))]
    ACTIVITY_CHOICES = [(COUNTING_AND_ITEM_LIST, _('شمارش و لیست قطعات')),
                        (DEVICE_FIRST_SETUP, _('ستاپ اولیه دستگاه')), (DEVICE_SECOND_SETUP, _('ستاپ ثانویه دستگاه')),
                        (GLUING, _('خمیر زدن')),(ASSEMBLY, _('مونتاژ')), (TOP_ASSEMBLY, _('مونتاژ TOP')),
                        (BOTTOM_ASSEMBLY, _('مونتاژ BOTTOM')),
                        (DEEP_OUTSOURCING_ASSEMBLY, _('مونتاژ DIP پیمانکاری')),(OVEN, _('آون')), (TOP_OVEN, _('آون TOP')),
                        (BOTTOM_OVEN, _('آون BOTTOM')),(QS, _('QC')), (PACKING, _('بسته‌بندی')),
                        (DELIVERY, _('ارسال')), (DIP_ASSEMBLY, _('مونتاژ DIP داخلی')), (MACHINE_FAILURE, _('خرابی دستگاه')),]

    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING, related_name='production_contract', verbose_name='قرارداد')
    goods_code_fk = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='production_goods_code', verbose_name='کد کالا')
    customer_party_id = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, related_name='production_customer', verbose_name='مشتری')
    production_date = models.DateField(null=True, blank=True, verbose_name='تاریخ')
    activity = models.CharField(max_length=3, choices=ACTIVITY_CHOICES, null=True, blank=True, verbose_name='فعالیت')
    work_time = models.CharField(max_length=3, choices=WORK_TIME_CHOICES, null=True, blank=True, verbose_name='شیفت کاری')
    total_assembly_board_count = models.PositiveIntegerField(null=True, blank=True, default=0, verbose_name='تعداد کل برد مونتاژ شده')
    assembly_type = models.CharField(max_length=3, choices=ASSEMBLY_CHOICES, null=True, blank=True, verbose_name='نوع مونتاژ')
    ruined_board_count = models.IntegerField(null=True, blank=True, default=0, verbose_name='تعداد برد خراب')
    intact_board_count_not_assembly = models.IntegerField(null=True, blank=True, default=0, verbose_name='برد‌های مونتاژ نشده(کسری قطعات)')
    delivery_type = models.CharField(max_length=255, null=True, blank=True, verbose_name='نحوه ارسال')
    customer_item_receipt = models.ForeignKey(CustomerItemReceipt, on_delete=models.DO_NOTHING, null=True, blank=True, verbose_name='فعالیت‌های روز تولید')
    factor_number = models.PositiveIntegerField(null=True, blank=True, verbose_name='شماره فاکتور')
    expert = models.ForeignKey(Expert, on_delete=models.DO_NOTHING, null=True, blank=True, verbose_name='کارشناس')
    start_time = models.TimeField(null=True, blank=True, verbose_name='start_time')
    end_time = models.TimeField(null=True, blank=True, verbose_name='end_time')

    def __str__(self):
        return f'{self.contract.contract_title}'

    @classmethod
    def get_pda_count(cls, user):
        count = (cls.objects.get_access_object(user, q='delivery', lst=False).filter
                 (factor_number=None, activity=cls.DELIVERY)).count()
        return count
