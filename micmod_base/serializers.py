from rest_framework import serializers
from rest_framework.fields import SerializerMethodField

from factor.models import Factor, FactorItem
from factor.serializers import FactorItemSerializer, FactorSerializer
from order.models import Order
from order.serializers import OrderSerializer
from payment.models import GenericPaymentItem
from payment.serializers import GenericPaymentSerializer
from .models import CustomerRequest, CustomerRequestItem, QuotationItem, Quotation

from core.serializers import CustomFieldModelSerializer


class QuotationItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = QuotationItem
        fields = ['id', 'quantity', 'goods_code_fk']


class QuotationSerializer(CustomFieldModelSerializer):
    quotation_items = SerializerMethodField()

    class Meta:
        model = Quotation
        fields = '__all__'
        # fields = ['id', 'request_date', 'quotation', 'created_date']

    def get_quotation_items(self, obj):
        qs = obj.quotation.all()
        return QuotationItemSerializer(qs, many=True).data


class CustomerRequestItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False, read_only=True)

    class Meta:
        model = CustomerRequestItem
        exclude = ['is_deleted', 'cr']
        # fields = ['id', 'quantity', 'goods_code', 'part_number', 'customer_goods_code', 'customer_part_number',
        #           'request_item_extra_data', 'cart_item_id', 'created_date', 'last_update_date']


class CustomerRequestSerializer(serializers.ModelSerializer):
    items = CustomerRequestItemSerializer(many=True)
    customer_quotations = SerializerMethodField()
    customer_factors = SerializerMethodField()
    customer_orders = SerializerMethodField()
    customer_payments = SerializerMethodField()

    class Meta:
        model = CustomerRequest
        exclude = ['is_deleted',]
        # fields = ['id', 'request_date', 'expire_date', 'customer', 'items', 'request_extra_data', 'customer_phone',
        #           'cart_id', 'created_date', 'last_update_date']

    def get_customer_quotations(self, obj):
        qs = Quotation.objects.filter(customer_request=obj)
        return QuotationSerializer(qs, many=True, fields=['id', 'quotation_items']).data

    def get_customer_factors(self, obj):
        qs = Factor.objects.filter(customer_request=obj)
        return FactorSerializer(qs, many=True, fields=['id']).data

    def get_customer_orders(self, obj):
        qs = Order.objects.filter(customer_request_item__in=obj.items.all())
        return OrderSerializer(qs, many=True, fields=['id']).data

    def get_customer_payments(self, obj):
        qs = obj.payments.all()
        for q in obj.customer_quotations.all():
            qs |= q.payments.all()

        return GenericPaymentSerializer(qs, many=True, fields=['id', 'total_amount', 'g_from_date', 'g_to_date', 'description', 'attachment']).data

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        customer_request = CustomerRequest.objects.create(**validated_data)

        for item_data in items_data:
            CustomerRequestItem.objects.create(cr=customer_request, **item_data)

        return customer_request

    # def update(self, instance, validated_data):
    #     items_data = validated_data.pop('items', None)
    #
    #     # update CustomerRequest
    #     for attr, value in validated_data.items():
    #         setattr(instance, attr, value)
    #     instance.save()
    #
    #     # update CustomerRequestItem
    #     if items_data is not None:
    #         existing_items = {item.id: item for item in instance.items.all()}
    #         incoming_ids = []
    #
    #         for item_data in items_data:
    #             item_id = item_data.get('id')
    #             if item_id and item_id in existing_items:
    #                 # update existing item
    #                 item_instance = existing_items[item_id]
    #                 for attr, value in item_data.items():
    #                     setattr(item_instance, attr, value)
    #                 item_instance.save()
    #                 incoming_ids.append(item_id)
    #             else:
    #                 # create new item
    #                 CustomerRequestItem.objects.create(cr=instance, **item_data)
    #
    #         # Delete items that are not in the input.
    #         for item_id, item_instance in existing_items.items():
    #             if item_id not in incoming_ids:
    #                 item_instance.delete()
    #
    #     return instance
    #

    def update(self, instance, validated_data):
        request = self.context.get('request')
        is_partial = request.method == 'PATCH'

        items_data = validated_data.pop('items', None)

        # update CustomerRequest fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            existing_items = {item.id: item for item in instance.items.all()}
            incoming_ids = []

            for item_data in items_data:
                item_id = item_data.get('id')
                if item_id and item_id in existing_items:
                    item_instance = existing_items[item_id]
                    for attr, value in item_data.items():
                        setattr(item_instance, attr, value)
                    item_instance.save()
                    incoming_ids.append(item_id)
                else:
                    CustomerRequestItem.objects.create(cr=instance, **item_data)

            if not is_partial:
                # در حالت PUT فقط اون‌هایی که اومدن بمونن
                for item_id, item_instance in existing_items.items():
                    if item_id not in incoming_ids:
                        item_instance.delete()

        return instance



