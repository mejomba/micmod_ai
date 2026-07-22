from rest_framework import serializers
from rest_framework.fields import SerializerMethodField

from workflow.serializers import WorkflowSerializer
from .models import Factor, FactorItem
from core.serializers import CustomFieldModelSerializer


class FactorItemSerializer(CustomFieldModelSerializer):
    # factor = FactorSerializer(read_only=True)
    supply_status = SerializerMethodField()
    fee = SerializerMethodField()
    fee_after_discount = SerializerMethodField()
    total_price = SerializerMethodField()
    total_discount = SerializerMethodField()
    total_price_after_discount = SerializerMethodField()
    total_tax = SerializerMethodField()

    class Meta:
        model = FactorItem
        fields = '__all__'

    def get_fee(self, obj):
        return obj.fee_()

    def get_fee_after_discount(self, obj):
        return self.get_fee(obj) - getattr(obj, 'discount_per_item', None) or 0

    def get_total_price(self, obj):
        return self.get_fee(obj) * obj.quantity

    def get_total_discount(self, obj):
        return getattr(obj, 'discount_value', None) or 0

    def get_total_price_after_discount(self, obj):
        return self.get_total_price(obj) - self.get_total_discount(obj)

    def get_total_tax(self, obj):
        return getattr(obj, 'tax', None) or 0

    def get_supply_status(self, obj):
        if obj.factoritemsupplylocation_set.filter(order__isnull=False).exists():
            return False
        else:
            return True


class FactorSerializer(CustomFieldModelSerializer):
    # factoritem_set = FactorItemSerializer(many=True)
    factor_items = SerializerMethodField()
    workflow_state_list = SerializerMethodField()
    last_work_flow = WorkflowSerializer()
    creator_user = SerializerMethodField()
    total_price = SerializerMethodField()
    total_price_after_discount = SerializerMethodField()
    total_discount = SerializerMethodField()
    total_tax = SerializerMethodField()
    sale_type = SerializerMethodField()
    currency_ref = SerializerMethodField()
    deliver_method = SerializerMethodField()

    class Meta:
        model = Factor
        fields = '__all__'

    def get_total_discount(self, obj):
        return getattr(obj, 'sum_discount', None) or 0

    def get_total_price(self, obj):
        return getattr(obj, 'get_price', None) or 0

    def get_total_price_after_discount(self, obj):
        return self.get_total_price(obj) - self.get_total_discount(obj)

    def get_total_tax(self, obj):
        return getattr(obj, 'sum_tax', None) or 0

    def get_sale_type(self, obj):
        return getattr(obj.sale_type, 'title', None) or None

    def get_currency_ref(self, obj):
        return f'{obj.currency_ref}'

    def get_creator_user(self, obj):
        return f'{obj.creator_user}'

    def get_deliver_method(self, obj):
        # return getattr(obj.deliver_method, 'type', None) or None
        if obj.deliver_method:
            return obj.deliver_method.get_type_display()
        else:
            return None

    def get_factor_items(self, obj, **kwargs):
        qs = obj.factoritem_set.all()
        return FactorItemSerializer(qs, many=True).data

    def get_workflow_state_list(self, obj):
        return ["پیش نویس", "تایید مدیر فروش", "تخصیص کارشناس انبار", "جمع آوری", "چک نهایی", "ارسال یا تحویل",
                "تایید تحویل", "مرحله نهایی", ]
