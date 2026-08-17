from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import SerializerMethodField

from micmod_base.models import Quotation, QuotationItem
from workflow.serializers import WorkflowSerializer
from .models import Factor, FactorItem
from core.serializers import CustomFieldModelSerializer


class FactorItemSerializer(CustomFieldModelSerializer):
    # factor = FactorSerializer(read_only=True)
    supply_status = SerializerMethodField()
    fee = SerializerMethodField()
    fee_after_discount = SerializerMethodField()
    total_price = SerializerMethodField()
    total_discount = SerializerMethodField()
    total_price_after_discount = SerializerMethodField()
    total_tax = SerializerMethodField()

    class Meta:
        model = FactorItem
        fields = '__all__'

    def get_fee(self, obj):
        return obj.fee_()

    def get_fee_after_discount(self, obj):
        return obj.fee_after_discount

    def get_total_price(self, obj):
        return self.get_fee(obj) * obj.quantity

    def get_total_discount(self, obj):
        return getattr(obj, 'discount_value', None) or 0

    def get_total_price_after_discount(self, obj):
        return obj.total_price_after_discount

    def get_total_tax(self, obj):
        return getattr(obj, 'tax', None) or 0

    def get_supply_status(self, obj):
        if obj.factoritemsupplylocation_set.filter(order__isnull=False).exists():
            return False
        else:
            return True


class FactorSerializer(CustomFieldModelSerializer):
    factor_items = SerializerMethodField()
    workflow_state_list = SerializerMethodField()
    last_work_flow = WorkflowSerializer()
    creator_user = SerializerMethodField()
    total_price = SerializerMethodField()
    total_price_after_discount = SerializerMethodField()
    total_discount = SerializerMethodField()
    total_tax = SerializerMethodField()
    sale_type = SerializerMethodField()
    currency_ref = SerializerMethodField()
    deliver_method = SerializerMethodField()
    customer_party_id = SerializerMethodField()
    customer_phone = SerializerMethodField()

    class Meta:
        model = Factor
        exclude = ['checker']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.fields['last_work_flow'].required = False
            self.fields['last_work_flow'].allow_null = True
        except Exception as e:
            pass

    def to_internal_value(self, data):
        internal_value = super().to_internal_value(data)

        if 'customer_party_id' in data:
            internal_value['customer_party_id_id'] = data.get('customer_party_id')

        if 'factor_items' in data:
            internal_value['factor_items'] = data.get('factor_items')

        return internal_value

    def create(self, validated_data):
        print('create factor from shop')
        request = self.context.get('request')
        items_data = validated_data.pop('factor_items')

        """ crate quotation """
        default_quotation_data = {
            "sale_type_id": 9,  # نقدی ریال
            "self_discount": 0,
            "is_official": False,
            "official_value": 0,
            "payment_method": "0,Cash"  # نقدی
        }
        quotation_data = {
            "customer_party_id_id": validated_data.get('customer_party_id_id'),
            "request_date": timezone.now(),
            "expiration_date": timezone.now(),
            "is_direct": True,
        }
        q = Quotation(**quotation_data, **default_quotation_data)
        q.extra_data.request = request
        q.save()
        wf = q.submit_flow(request, is_new=True)
        q.last_work_flow = wf
        q.save()

        """ crate quotation item """
        qis = []
        for item in items_data:
            quotation_item_data = {
                'goods_code_fk_id': item.get('goods_code_id'),
                "quantity": item.get('quantity'),
            }
            qi = QuotationItem(quotation=q, **quotation_item_data)
            qi.extra_data.request = request
            qi.save()
            request_sl = item.get('supply_location').split('__')[1]
            goods_qty = qi.goods_code_fk.free_qty_dict()

            if quantity_dict := goods_qty.get(request_sl):
                if quantity_dict.get('free') < item.get('quantity'):
                    raise ValidationError(detail={'quantity error': item}, code=400)
            else:
                raise ValidationError(detail={'quantity error': item.get('goods_code_id')}, code=400)

            qis.append([qi, item])

        """ crate factor """
        default_factor_data = {
            "sale_type_id": 9,  # نقدی ریال
            "self_discount": 0,
            "is_official": False,
            "official_value": 0,
            "payment_method": "0,Cash"  # نقدی
        }
        f = Factor(q=q, **validated_data, **default_factor_data)
        f.extra_data.request = request
        f.save()

        """ crate factor item """
        for idx, (qi, item) in enumerate(qis):
            default_factor_item_data = {
                'reserve_count': qi.quantity,
                'supply_location': item.get('supply_location'),
                'is_bazar': False,
                "quantity": qi.quantity,
                "goods_code_id": qi.goods_code_fk.pk,
                "part_number_show": qi.goods_code_fk.part_number,
            }
            fi = FactorItem(factor=f, qi=qi, **default_factor_item_data)
            fi.extra_data.request = request
            fi.extra_data.idx = idx
            fi.save()

        return f

    def update(self, instance, validated_data):
        print('update factor from shop')
        request = self.context.get('request')
        items_data = validated_data.pop('factor_items', [])

        # بروزرسانی فیلدها
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # پردازش آیتم‌ها
        updated_ids = []
        for item_data in items_data:
            item_id = item_data.get('id')

            if item_id:
                # بررسی وجود آیتم
                try:
                    item = FactorItem.objects.get(id=item_id, factor=instance)
                    item.extra_data.request = request

                    # **چک کردن شروط خاص قبل از آپدیت**
                    if not self.can_update_item(item, item_data):
                        raise serializers.ValidationError(
                            f"آیتم {item.id} قابل آپدیت نیست"
                        )

                    # آپدیت آیتم موجود
                    for attr, value in item_data.items():
                        if attr != 'id':
                            setattr(item, attr, value)
                    item.save()
                    updated_ids.append(item.id)

                except FactorItem.DoesNotExist:
                    raise serializers.ValidationError(
                        f"آیتم با id {item_id} وجود ندارد"
                    )
            else:
                # ایجاد آیتم جدید
                new_item = FactorItem.objects.create(factor=instance, **item_data)
                updated_ids.append(new_item.id)

        # حذف آیتم‌هایی که در لیست نبودند (اختیاری)
        # instance.items.exclude(id__in=updated_ids).delete()

        return instance

    def can_update_item(self, item, new_data):
        """بررسی شروط خاص برای آپدیت آیتم"""
        return True

    def get_total_discount(self, obj):
        return getattr(obj, 'sum_discount', None) or 0

    def get_total_price(self, obj):
        return getattr(obj, 'get_price', None) or 0

    def get_total_price_after_discount(self, obj):
        return self.get_total_price(obj) - self.get_total_discount(obj)

    def get_total_tax(self, obj):
        return getattr(obj, 'sum_tax', None) or 0

    def get_sale_type(self, obj):
        return getattr(obj.sale_type, 'title', None) or None

    def get_currency_ref(self, obj):
        return f'{obj.currency_ref}'

    def get_creator_user(self, obj):
        return f'{obj.creator_user}'

    def get_deliver_method(self, obj):
        # return getattr(obj.deliver_method, 'type', None) or None
        if obj.deliver_method:
            return obj.deliver_method.get_type_display()
        else:
            return None
    def get_customer_party_id(self, obj):
        customer = getattr(obj, 'customer_party_id', None)
        if not customer:
            q = obj.q
            if q:
                customer = getattr(obj.q, 'customer_party_id')

        return customer.title if customer else None

    def get_customer_phone(self, obj):
        customer = getattr(obj, 'customer_party_id', None)
        if not customer:
            q = obj.q
            if q:
                customer = getattr(obj.q, 'customer_party_id')

        return customer.phone if customer else None

    def get_factor_items(self, obj, **kwargs):
        qs = obj.factoritem_set.all()
        return FactorItemSerializer(qs, many=True).data

    def get_workflow_state_list(self, obj):
        return ["پیش نویس", "تایید مدیر فروش", "تخصیص کارشناس انبار", "جمع آوری", "چک نهایی", "ارسال یا تحویل",
                "تایید تحویل", "مرحله نهایی", ]
