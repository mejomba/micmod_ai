from rest_framework import serializers
from .models import Order
from core.serializers import CustomFieldModelSerializer


class OrderSerializer(CustomFieldModelSerializer):

    class Meta:
        model = Order
        fields = '__all__'
