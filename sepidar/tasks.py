from celery import shared_task

from tools.import_data import import_customers_from_sepidar


@shared_task
def import_customers_from_sepidar_task(extra_data):
    extra_data = {"creator_user_id": 1, "editor_user_id": 1}
    import_customers_from_sepidar(extra_data)
