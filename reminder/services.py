from inquiry.tasks import send_reminder_notification
from reminder.utils import calculate_first_send_time


def schedule_reminder(reminder):
    first_time = calculate_first_send_time(reminder)

    send_reminder_notification.apply_async(
        args=[reminder.id, first_time],
        eta=first_time
    )
