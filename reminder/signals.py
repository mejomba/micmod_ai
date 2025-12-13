from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Reminder
from .services import schedule_reminder


@receiver(post_save, sender=Reminder)
def reminder_save(sender, instance, created, **kwargs):
    if created:
        schedule_reminder(instance)
    else:
        schedule_reminder(instance)

