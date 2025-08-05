from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
import requests
from jalali_core import JalaliToGregorian
from datetime import datetime


# def create_or_update_payment(portal_payment: Payment, is_update=False):
def create_or_update_payment(request, obj, portal_payment=None):
    url = f'{settings.SHOP_PROTOCOL}://{settings.SHOP_HOST}:{settings.SHOP_PORT}/'
    endpoint = 'api2/accounting-payment/{0}/?struct_name=online_payment'
    url += endpoint
    app_label = obj._meta.app_label
    model_name = obj._meta.model_name
    ctt_id = ContentType.objects.get_for_model(obj._meta.model).pk
    obj_id = obj.pk
    total_amount = request.POST.get(f'{app_label}__{model_name}__{ctt_id}__{obj_id}-total_amount')

    if total_amount:
        g_from_date = request.POST.get(f'{app_label}__{model_name}__{ctt_id}__{obj_id}-g_from_date')
        g_to_date = request.POST.get(f'{app_label}__{model_name}__{ctt_id}__{obj_id}-g_to_date')
        gregorian_g_from_date = JalaliToGregorian(*list(map(int, g_from_date.split('-')))) if g_from_date else None
        gregorian_g_to_date = JalaliToGregorian(*list(map(int, g_to_date.split('-')))) if g_to_date else None
        description = request.POST.get(f'{app_label}__{model_name}__{ctt_id}__{obj_id}-description')
        file_prefix = f'{app_label}__{model_name}__{ctt_id}__{obj_id}-file'
        content_type = ContentType.objects.get_for_model(obj._meta.model)

        api_payload = {
            "payment_method": "online_payment",
            "amount_paid": total_amount,
            "reference": "portal",
            "reference_id": None,
            "reference_document": None,
            "reference_document_id": None,
            "reference_document_title": None,
            "description": description,
            "object_id": 27,
            "content_type": 75,
            "cart": 90
        }

        # if is_update:
        #     response = requests.post(url.format(portal_payment.id), json=payload)
        # else:
        response = requests.post(url, json=api_payload)

        payment_data = {
            "g_from_date": datetime(*gregorian_g_from_date.getGregorianList()) if gregorian_g_from_date else None,
            "g_to_date": datetime(*gregorian_g_to_date.getGregorianList()) if gregorian_g_to_date else None,
            "description": description,
            "total_amount": total_amount,
            "content_type": content_type,
            "object_id": obj_id,
            "creator_user": request.user,
            "editor_user": request.user,
        }
        if response.status_code in (200, 201) or True:
            obj.save_payment(request, payment_data, file_prefix)
        elif response.status_code == 204:
            payment = obj.payments.filter(pk=obj_id).first()
            if payment:
                payment.is_deleted = True
                payment.extra_data.request = request
                payment.save()
        else:
            raise Exception("Shop error: عملیات مجاز نیست")


