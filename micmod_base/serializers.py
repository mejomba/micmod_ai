from rest_framework import serializers
from .models import CustomerRequest, CustomerRequestItem


class CustomerRequestItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerRequestItem
        fields = ['id', 'quantity', 'goods_code', 'part_number', 'customer_goods_code', 'customer_part_number']


class CustomerRequestSerializer(serializers.ModelSerializer):
    items = CustomerRequestItemSerializer(many=True, read_only=True)

    class Meta:
        model = CustomerRequest
        fields = ['id', 'request_date', 'expire_date', 'customer', 'items']

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


