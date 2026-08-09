from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.fields import SerializerMethodField
from rest_framework.permissions import IsAuthenticated

from core.permissions import HasShopPermission
from .models import Item

from core.serializers import CustomFieldModelSerializer


class ItemSerializer(serializers.ModelSerializer):
    product_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        read_only=True,
        allow_empty=False
    )

    class Meta:
        model = Item
        fields = ['id', 'sku', 'part_number', 'skus']
        read_only_fields = []
