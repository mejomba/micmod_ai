from rest_framework import serializers
from rest_framework.fields import SerializerMethodField

from .models import Factor, FactorItem
from core.serializers import CustomFieldModelSerializer


class FactorItemSerializer(CustomFieldModelSerializer):
    # factor = FactorSerializer(read_only=True)

    class Meta:
        model = FactorItem
        fields = '__all__'


class FactorSerializer(CustomFieldModelSerializer):
    # factoritem_set = FactorItemSerializer(many=True)
    factor_items = SerializerMethodField()
    workflow_state_list = SerializerMethodField()

    class Meta:
        model = Factor
        fields = '__all__'

    def get_factor_items(self, obj, **kwargs):
        qs = obj.factoritem_set.all()
        return FactorItemSerializer(qs, many=True).data

    def get_workflow_state_list(self, obj):
        return ["پیش نویس", "تایید مدیر فروش", "تخصیص کارشناس انبار", "جمع آوری", "چک نهایی", "ارسال یا تحویل",
                "تایید تحویل", "مرحله نهایی", ]
