from rest_framework import serializers
from .models import Order
from core.serializers import CustomFieldModelSerializer


class OrderSerializer(CustomFieldModelSerializer):
    get_workflow_state_list = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = '__all__'

    def get_workflow_state_list(self, obj):
        return ["پیش نویس", "تایید مدیر فروش", "تایید بازرگانی", "تایید مهندس", "ارسال به تامین کننده",
                "تایید تامین کننده", "تایید نهایی بازرگانی", "پرداخت/GIO/PACKING", "مرحله نهایی"]