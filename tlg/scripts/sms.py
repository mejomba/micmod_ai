import requests
from typing import List
from tlg.models import SMS
from tools.utils import show_error
from django.conf import settings


def send_sms(sender_phone: str, receiver_list: List, text: str):
    try:
        receiver_str = ','.join(receiver_list)
        if not sender_phone:
            sender_obj = SMS.objects.first()
        else:
            sender_obj = SMS.objects.filter(phone_number=sender_phone).first()
        if receiver_str and sender_obj:
            sms_config = {
                "username": sender_obj.username,
                "password": sender_obj.password,
                "from": sender_obj.phone_number,
                "to": receiver_str,
                "text": text,
                "isFlash": False
            }
            headers = {
                'Content-Type': 'application/json'
            }
            res = requests.post(settings.SEND_SMS_URL, json=sms_config, headers=headers)
            res_value = res.json().get('Value')

            if res_value:
                res_value = res_value.split(',')

            if res.status_code == 200 and res_value:
                if len(res_value[0]) > 2:
                    return True, ','.join(res_value)
                else:
                    return False, ','.join(res_value)
            else:
                return False, ','.join(res_value)
        else:
            return False, 'sender or receiver invalid'
    except Exception as e:
        show_error(e, __file__)
        return False, 'exception occurred'
