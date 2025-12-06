from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Reminder


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "display_time",
        "display_repeat_interval",
        "reminder_type",
        "expiration_date",
        "start_date",
        "get_users"
    )
    list_filter = (
        "reminder_type",
        "time_unit",
        "repeat_interval_unit",
        "expiration_date",
        "start_date",
    )
    search_fields = (
        "title",
        "short_text",
        "long_text",
    )
    filter_horizontal = ("user",)

    fieldsets = (
        ("اطلاعات کلی", {
            "fields": ("title", "short_text", "long_text", "reminder_type", "user")
        }),
        ("بازه تکرار اصلی", {
            "fields": ("time_value", "time_unit"),
            "description": "مثال: ۵ سال ← مقدار = ۵ ، نوع = سال"
        }),
        ("بازه تکرار داخلی", {
            "fields": ("repeat_interval_value", "repeat_interval_unit"),
            "description": "مثال: هر ۶ ماه یک بار ← مقدار = ۶ ، نوع = ماه"
        }),
        ("دیگر", {
            "fields": ("expiration_date", "start_date")
        }),
    )

    def display_time(self, obj):
        return f"{obj.time_value} {obj.get_time_unit_display()}"
    display_time.short_description = "بازه اصلی"

    def display_repeat_interval(self, obj):
        return f"{obj.repeat_interval_value} {obj.get_repeat_interval_unit_display()}"
    display_repeat_interval.short_description = "تکرار در بازه"

    def get_users(self, obj):
        return ", ".join([u.username for u in obj.user.all()])
    get_users.short_description = "کاربران"

