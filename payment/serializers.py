from files.serializers import GenericFileSerializer
from .models import GenericPaymentItem
from core.serializers import CustomFieldModelSerializer
from rest_framework import serializers


class GenericPaymentSerializer(CustomFieldModelSerializer):
    attachment = serializers.SerializerMethodField()

    class Meta:
        model = GenericPaymentItem
        fields = '__all__'

    def get_attachment(self, obj):
        qs = obj.files.all()
        return GenericFileSerializer(qs, many=True, fields=['id', 'path']).data


class PaymentForShopSerializer(CustomFieldModelSerializer):
    payment_method = serializers.CharField(max_length=255, default='online_payment')
    amount_paid = serializers.SerializerMethodField()
    reference = serializers.CharField(max_length=255, default='portal')
    reference_id = serializers.SerializerMethodField()
    reference_document = serializers.CharField(max_length=255, required=True)  # quotation, factor, order, ...
    reference_document_id = serializers.SerializerMethodField()  # quotation.id, factor.id, order.id, ...
    reference_document_title = serializers.SerializerMethodField()  # quotation.id, factor.id, order.id, ...
    description = serializers.CharField(max_length=1000, allow_null=True)
    cart = serializers.SerializerMethodField()

    class Meta:
        model = GenericPaymentItem
        fields = '__all__'

    def get_amount_paid(self, obj):
        return obj.total_amount

    def get_reference_id(self, obj):
        return obj.pk

    def get_reference_document_id(self, obj):
        return obj.object_id

    def get_cart(self, obj):
        return obj.content_object
