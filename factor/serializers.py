from rest_framework import serializers
from rest_framework.fields import SerializerMethodField

from workflow.serializers import WorkflowSerializer
from .models import Factor, FactorItem
from core.serializers import CustomFieldModelSerializer


class FactorItemSerializer(CustomFieldModelSerializer):
    # factor = FactorSerializer(read_only=True)
    supply_status = SerializerMethodField()
    get_fee = SerializerMethodField()
    get_fee_after_discount = SerializerMethodField()
    get_total_price = SerializerMethodField()
    get_total_discount = SerializerMethodField()
    get_total_price_after_discount = SerializerMethodField()

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
    sale_type = SerializerMethodField()
    currency_ref = SerializerMethodField()

    class Meta:
        model = Factor
        fields = '__all__'

    def get_total_discount(self, obj):
        return '000'

    def get_total_price(self, obj):
        return '000'

    def get_total_price_after_discount(self, obj):
        return '000'

    def get_sale_type(self, obj):
        return getattr(obj.sale_type, 'title', None) or None

    def get_currency_ref(self, obj):
        return f'{obj.currency_ref}'

    def get_creator_user(self, obj):
        return f'{obj.creator_user}'

    def get_factor_items(self, obj, **kwargs):
        qs = obj.factoritem_set.all()
        return FactorItemSerializer(qs, many=True).data

    def get_workflow_state_list(self, obj):
        return ["پیش نویس", "تایید مدیر فروش", "تخصیص کارشناس انبار", "جمع آوری", "چک نهایی", "ارسال یا تحویل",
                "تایید تحویل", "مرحله نهایی", ]
