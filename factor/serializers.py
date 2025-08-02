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
    jafar = SerializerMethodField()

    class Meta:
        model = Factor
        fields = '__all__'

    def get_jafar(self, obj, **kwargs):
        qs = obj.factoritem_set.all()
        return FactorItemSerializer(qs, many=True).data
