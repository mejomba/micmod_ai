from datetime import timedelta
from django.utils import timezone
from dateutil.relativedelta import relativedelta


def calculate_first_send_time(reminder):
    base_time = reminder.start_date or timezone.now()

    if reminder.time_unit == 'day':
        return base_time + timedelta(days=reminder.time_value)

    if reminder.time_unit == 'month':
        return base_time + relativedelta(months=reminder.time_value)

    if reminder.time_unit == 'year':
        return base_time + relativedelta(years=reminder.time_value)

    return base_time


def calculate_next_time(reminder, last_scheduled_time):
    if reminder.repeat_interval_unit == 'day':
        return last_scheduled_time + timedelta(
            days=reminder.repeat_interval_value
        )

    if reminder.repeat_interval_unit == 'month':
        return last_scheduled_time + relativedelta(
            months=reminder.repeat_interval_value
        )

    if reminder.repeat_interval_unit == 'year':
        return last_scheduled_time + relativedelta(
            years=reminder.repeat_interval_value
        )

    return None
