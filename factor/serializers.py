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

    class Meta:
        model = Factor
        fields = '__all__'

    def get_factor_items(self, obj, **kwargs):
        qs = obj.factoritem_set.all()
        return FactorItemSerializer(qs, many=True).data
