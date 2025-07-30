from rest_framework import serializers
from .models import Factor, FactorItem


class FactorItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = FactorItem
        fields = ['id', 'quantity', ]


class CustomerRequestSerializer(serializers.ModelSerializer):
    items = FactorItemSerializer(many=True)

    class Meta:
        model = Factor
        fields = ['id', 'created_date']
