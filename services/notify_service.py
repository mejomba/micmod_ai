import requests
from django.contrib.contenttypes.models import ContentType
from django.conf import settings


def notify_wf_to_shop(wf):
    if not wf.content_type:
        return

    url = f'{settings.SHOP_PROTOCOL}://{settings.SHOP_HOST}:{settings.SHOP_PORT}/'
    endpoint = 'api2/sales-orderondemanddocument/13/?struct_name=order_on_demand_str&no_metadata'
    url += endpoint

    content_type_object = ContentType.objects.get(id=wf.content_type.pk)
    obj = content_type_object.get_object_for_this_type(id=wf.object_id)
    customer_request = getattr(obj, 'customer_request', None) or getattr(obj, 'customer_request_item', None)
    # ctt = obj.content_type()

    if customer_request:
        data = {
            "order_on_demand": customer_request.pk,  # customer request.pk
            "doc_number": obj.pk,  # object_id
            "doc_type": f'{obj._meta.model.__name__}',  # ctt_name
            "doc_title": "test",  # ?
            "prev_doc_status": obj.last_work_flow.current_state_name,  # prev wf status name
            "doc_status": wf.current_state_name,  # wf status name
            "description": "description..."
        }

        requests.post(url, json=data)
