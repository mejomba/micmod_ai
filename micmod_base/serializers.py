from rest_framework import serializers
from rest_framework.fields import SerializerMethodField

from factor.models import Factor, FactorItem
from factor.serializers import FactorItemSerializer, FactorSerializer
from order.models import Order
from order.serializers import OrderSerializer
from payment.models import GenericPaymentItem
from payment.serializers import GenericPaymentSerializer
from workflow.serializers import WorkflowSerializer
from .models import CustomerRequest, CustomerRequestItem, QuotationItem, Quotation

from core.serializers import CustomFieldModelSerializer


class QuotationItemSerializer(CustomFieldModelSerializer):
    part_number = serializers.CharField(source='goods_code_fk.part_number', read_only=True)
    request_date = serializers.CharField(source='quotation.request_date', read_only=True)
    fee = serializers.SerializerMethodField()
    fee_after_discount = serializers.SerializerMethodField()
    row_total_price = serializers.SerializerMethodField()
    row_tax = serializers.SerializerMethodField()
    row_total_discount = serializers.SerializerMethodField()

    class Meta:
        model = QuotationItem
        fields = '__all__'

    def get_fee(self, obj):
        return obj.fee_() or 0

    def get_fee_after_discount(self, obj):
        return self.get_fee(obj) - getattr(obj, 'discount_per_item', 0) or 0

    def get_row_total_discount(self, obj):
        return obj.discount_value

    def get_row_total_price(self, obj):
        return obj.row_price

    def get_row_total_price_after_discount(self, obj):
        return self.get_row_total_price(obj) - self.get_row_total_discount(obj)

    def get_row_tax(self, obj):
        return obj.tax


class CustomerQuotationSerializer(CustomFieldModelSerializer):
    quotation_items = SerializerMethodField()
    total_discount = SerializerMethodField()

    class Meta:
        model = Quotation
        fields = '__all__'
        # fields = ['id', 'request_date', 'quotation', 'created_date']

    def get_quotation_items(self, obj):
        qs = obj.quotation.all()
        return QuotationItemSerializer(qs, many=True,).data

    def get_total_discount(self, obj):
        return '000'


class QuotationSerializer(CustomFieldModelSerializer):
    quotation_items = SerializerMethodField()
    last_work_flow = WorkflowSerializer()
    workflow_state_list = SerializerMethodField()
    creator_user = SerializerMethodField()
    total_price = SerializerMethodField()
    total_tax = SerializerMethodField()
    total_price_after_discount = SerializerMethodField()
    total_discount = SerializerMethodField()
    sale_type = SerializerMethodField()
    currency_ref = SerializerMethodField()
    customer_phone = SerializerMethodField()
    customer_party_id = SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for item in self.instance:
            item.payment_data = item.payment

    class Meta:
        model = Quotation
        fields = '__all__'
        # fields = ['id', 'request_date', 'quotation', 'created_date']

    def get_total_tax(self, obj):
        return obj.payment_data[3]

    def get_total_discount(self, obj):
        return obj.payment_data[2]

    def get_total_price(self, obj):
        return obj.payment_data[0]

    def get_total_price_after_discount(self, obj):
        return obj.payment_data[4]

    def get_sale_type(self, obj):
        return getattr(obj.sale_type, 'title', None) or None

    def get_currency_ref(self, obj):
        return f'{obj.currency_ref}'

    def get_creator_user(self, obj):
        return f'{obj.creator_user}'

    def get_customer_party_id(self, obj):
        customer = getattr(obj, 'customer_party_id', None)
        return customer.title if customer else None

    def get_customer_phone(self, obj):
        customer = getattr(obj, 'customer_party_id', None)
        return customer.phone if customer else None

    def get_quotation_items(self, obj):
        qs = obj.quotation.all()
        fields = ['id', 'fee', 'fee_after_discount', 'quantity', 'goods_code_fk', 'part_number', 'request_date',
                  'discount_per_item', 'row_total_price', 'row_tax', 'delivery_time', 'description', 'row_total_discount']
        return QuotationItemSerializer(qs, many=True, fields=fields).data

    def get_workflow_state_list(self, obj):
        return ["پیش فاکتور اولیه", "استعلام قیمت", "تایید پیش فاکتور", "تایید مشتری", "تایید کارشناس", "مرحله نهایی",]


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
        print('create customer request')
        items_data = validated_data.pop('items')
        customer_request = CustomerRequest.objects.create(**validated_data)

        for item_data in items_data:
            CustomerRequestItem.objects.create(cr=customer_request, **item_data)

        return customer_request

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


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationItem
        fields = ['id', 'sku', 'part_number',]
        read_only_fields = []


class QuotationItemGroupSerializer(serializers.ModelSerializer):
    goods_code_fk = ItemSerializer(many=True, read_only=True)

    class Meta:
        model = QuotationItem
        fields = ['id', 'quotation', 'goods_code_fk', 'quantity', 'final_price',]
        read_only_fields = []

    def validate(self, data):
        if data['quantity'] <= 0:
            raise serializers.ValidationError("تعداد باید بزرگتر از صفر باشد")
        if data['unit_price'] <= 0:
            raise serializers.ValidationError("قیمت واحد باید بزرگتر از صفر باشد")
        return data


class QuotationGroupSerializer(serializers.ModelSerializer):
    qis = QuotationItemGroupSerializer(many=True, read_only=True)
    total_rows = serializers.IntegerField(source='rows.count', read_only=True)
    customer = serializers.CharField(source='customer_party_id.title', read_only=True)

    class Meta:
        model = Quotation
        fields = ['id', 'qis', 'customer']


class CustomerSerializer(serializers.ModelSerializer):
    items = CustomerRequestItemSerializer(many=True)
    customer_quotations = SerializerMethodField()
    customer_factors = SerializerMethodField()
    customer_orders = SerializerMethodField()
    customer_payments = SerializerMethodField()

    class Meta:
        model = CustomerRequest
        exclude = ['is_deleted',]

    def get_customer_quotations(self, obj):
        qs = Quotation.objects.filter(customer_party_id=obj)
        return QuotationSerializer(qs, many=True, fields=['id', 'quotation_items']).data

    def get_customer_factors(self, obj):
        qs = Factor.objects.filter(customer_party_id=obj)
        return FactorSerializer(qs, many=True, fields=['id']).data

    def get_customer_orders(self, obj):
        qs = Order.objects.filter(customer_party_id=obj)
        return OrderSerializer(qs, many=True, fields=['id']).data

    def get_customer_payments(self, obj):
        qs = obj.payments.all()
        for q in obj.customer_quotations.all():
            qs |= q.payments.all()

        return GenericPaymentSerializer(qs, many=True, fields=['id', 'total_amount', 'g_from_date', 'g_to_date', 'description', 'attachment']).data

    def create(self, validated_data):
        print('create customer request')
        items_data = validated_data.pop('items')
        customer_request = CustomerRequest.objects.create(**validated_data)

        for item_data in items_data:
            CustomerRequestItem.objects.create(cr=customer_request, **item_data)

        return customer_request

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