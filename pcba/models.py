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
    # customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING)
    customer_sheet_count = models.PositiveIntegerField(default=0)
    customer_board_count = models.PositiveIntegerField(default=0)
    customer_total_board_count = models.PositiveIntegerField(default=0)
    first_setup_time = models.PositiveBigIntegerField(default=0, null=True, blank=True)
    second_setup_time = models.PositiveBigIntegerField(default=0, null=True, blank=True)
    pad_count = models.PositiveIntegerField(default=0)
    ic_pad_count = models.PositiveIntegerField(default=0)
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
    STATUS_CHOICES = [(COMPLETED, _('Completed')), (INCOMPLETE, _('In Progress'))]
    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING)
    receipt_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=2, choices=STATUS_CHOICES, default=INCOMPLETE)
    total_board_receipt_count = models.PositiveIntegerField(default=0)
    parent = models.ForeignKey('self', on_delete=models.DO_NOTHING, null=True, blank=True)

    def __str__(self):
        return f'{self.pk}-{self.contract.customer_party_id.title}'


class ProjectItemList(BaseModeWF):
    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING)
    goods_code_fk = models.ForeignKey(Item, on_delete=models.DO_NOTHING)
    part_number = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=0)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.pk}'







