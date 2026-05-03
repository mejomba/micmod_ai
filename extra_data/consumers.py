import json
import hashlib
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.cache import cache
from django.utils import timezone
import time


class FormConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.form_id = self.scope['url_route']['kwargs']['form_id']
        self.user_id = self.scope['user'].id
        self.room_group_name = f'form_{self.form_id}'
        self.client_id = f"{self.user_id}_{time.time()}_{id(self)}"

        # گروه بندی بر اساس فرم
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # ارسال وضعیت فعلی فرم به کاربر جدید
        current_state = await self.get_current_form_state()
        await self.send(text_data=json.dumps({
            'type': 'sync_state',
            'data': current_state,
            'version': current_state.get('version', 1)
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')

        # محدودیت نرخ کاربر
        if not await self.check_rate_limit():
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'درخواست بیش از حد مجاز'
            }))
            return

        if action == 'update_field':
            # اعتبارسنجی و ذخیره با optimistic locking
            updated = await self.save_field_update(
                field_name=data['field_name'],
                value=data['value'],
                client_version=data.get('client_version', 0)
            )

            if updated:
                # اطلاع‌رسانی به همه کاربران
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'field_updated',
                        'field_name': data['field_name'],
                        'value': data['value'],
                        'user_id': self.user_id,
                        'client_id': self.client_id,
                        'timestamp': timezone.now().isoformat(),
                        'version': data.get('client_version', 0) + 1
                    }
                )
            else:
                # Conflict: ارسال آخرین نسخه برای همگام‌سازی
                current_state = await self.get_current_form_state()
                await self.send(text_data=json.dumps({
                    'type': 'conflict',
                    'current_data': current_state,
                    'message': 'داده‌ها تغییر کرده، لطفا صفحه را به‌روز کنید'
                }))

    async def field_updated(self, event):
        # فیلتر کردن ارسال به فرستنده اصلی (اختیاری)
        if event.get('client_id') == self.client_id:
            return

        await self.send(text_data=json.dumps({
            'type': 'field_update',
            'field_name': event['field_name'],
            'value': event['value'],
            'user_id': event['user_id'],
            'timestamp': event['timestamp'],
            'version': event['version']
        }))

    @database_sync_to_async
    def get_current_form_state(self):
        # from extra_data.models import Form
        from extra_data.forms import ItemWeightForm
        from django.db import transaction
        from extra_data.models import ItemWeight

        with transaction.atomic():

            obj = ItemWeight.objects.get(id=self.form_id)
            form = ItemWeightForm(instance=obj)
            return {
                'data': form.data,
                'version': form.version,
                'last_update': form.last_update.isoformat()
            }

    @database_sync_to_async
    def save_field_update(self, field_name, value, client_version):
        # from your_app.models import Form
        from extra_data.models import ItemWeight
        from django.db import transaction

        with transaction.atomic():
            form = ItemWeight.objects.select_for_update().get(id=self.form_id)

            # Optimistic locking با نسخه
            if form.version != client_version:
                return False

            # به‌روزرسانی فیلد
            form.data[field_name] = value
            form.version += 1
            form.save()

            # ذخیره در کش برای دسترسی سریع
            cache.set(f'form_{self.form_id}_state', {
                'data': form.data,
                'version': form.version
            }, timeout=300)

            return True

    async def check_rate_limit(self):
        cache_key = f'ratelimit_ws_{self.user_id}_{self.form_id}'
        current = cache.get(cache_key, 0)
        if current >= 5:  # حداکثر 5 درخواست در ثانیه
            return False
        cache.set(cache_key, current + 1, timeout=1)
        return True