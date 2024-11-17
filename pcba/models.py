from django.db import models

from core.models import BaseModel, BaseModeWF
from extra_data.models import Item, Customer
from translator import get_text as _


class Contract(BaseModeWF):
    contract_title = models.CharField(max_length=100, unique=True)
    goods_code_fk = models.ForeignKey(Item, on_delete=models.DO_NOTHING)
    project_name_en = models.CharField(max_length=250)
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

    def __str__(self):
        return self.contract_title


class CustomerItemReceipt(BaseModeWF):
    INCOMPLETE = '1'
    COMPLETED = '2'
    STATUS_CHOICES = [(COMPLETED, _('کامل')), (INCOMPLETE, _('ناقص'))]
    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING, related_name='customer_contract')
    receipt_date = models.DateField(null=True, blank=True, verbose_name='تاربخ دریافت')
    status = models.CharField(max_length=2, choices=STATUS_CHOICES, default=INCOMPLETE, verbose_name='وضعیت دریافت کالا')
    total_board_receipt_count = models.PositiveIntegerField(default=0, verbose_name='تعداد کل برد دریافتی')
    parent = models.ForeignKey('self', on_delete=models.DO_NOTHING, null=True, blank=True, verbose_name='رسید مربوطه')
    # items = models.ForeignKey(ItemsInCustomerReceipt, on_delete=models.DO_NOTHING, verbose_name='کالا', null=True, blank=True)
    # goods_code_fk = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='goods_code_customer_receipt')
    # get_item_date = models.DateField(null=True, blank=True, verbose_name='تاریخ تحویل کالا')

    def __str__(self):
        return f'{self.pk} - {self.title}'


class ItemsInCustomerReceipt(BaseModeWF):
    goods_code_fk = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='goods_code_item_customer_receipt', verbose_name='کالا')
    quantity = models.PositiveIntegerField(default=0, verbose_name='تعداد')
    receipt_date = models.DateField(verbose_name='تاریخ دریافت کالا')
    customer_item_receipt = models.ForeignKey(CustomerItemReceipt, related_name='items', on_delete=models.DO_NOTHING, verbose_name='رسید کالای مربوطه')


class ProjectItemList(BaseModeWF):
    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING, verbose_name='قرارداد')
    goods_code_fk = models.ForeignKey(Item, on_delete=models.DO_NOTHING, verbose_name='کد کالا')
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

    # ASSEMBLY CHOICES
    TIN_DOUGH = '1'
    GLUE = '2'

    ASSEMBLY_CHOICES = [(TIN_DOUGH, _('خمیر قلع')), (GLUE, _('چسب'))]
    ACTIVITY_CHOICES = [(COUNTING_AND_ITEM_LIST, _('شمارش و لیست قطعات')),
                        (DEVICE_FIRST_SETUP, _('ستاپ اولیه دستگاه')), (DEVICE_SECOND_SETUP, _('ستاپ ثانویه دستگاه')),
                        (ASSEMBLY, _('مونتاژ')), (OVEN, _('آون')), (QS, _('QC')), (PACKING, _('بسته‌بندی')),
                        (DELIVERY, _('ارسال'))]

    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING, related_name='production_contract', verbose_name='قرارداد')
    goods_code_fk = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='production_goods_code', verbose_name='کد کالا')
    customer_party_id = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, related_name='production_customer', verbose_name='مشتری')
    production_date = models.DateField(null=True, blank=True, verbose_name='تاریخ')
    activity = models.CharField(max_length=3, choices=ACTIVITY_CHOICES, null=True, blank=True, verbose_name='فعالیت')
    total_assembly_board_count = models.PositiveIntegerField(null=True, blank=True, default=0, verbose_name='تعداد کل برد مونتاژ شده')
    assembly_type = models.CharField(max_length=3, choices=ASSEMBLY_CHOICES, null=True, blank=True, verbose_name='نوع مونتاژ')
    ruined_board_count = models.IntegerField(null=True, blank=True, default=0, verbose_name='تعداد برد خراب')
    intact_board_count_not_assembly = models.IntegerField(null=True, blank=True, default=0, verbose_name='برد‌های مونتاژ نشده(کسری قطعات)')
    delivery_type = models.CharField(max_length=255, null=True, blank=True, verbose_name='نحوه ارسال')

    def __str__(self):
        return f'{self.contract.contract_title}'
