from channels.consumer import  AsyncConsumer
from channels.exceptions import StopConsumer
import json
from channels.db import database_sync_to_async
from .models import Quotation, QuotationItem


class QuotationItemConsumer(AsyncConsumer):
    async def websocket_connect(self, event):
        self.user = self.scope['user']
        self.notify_group_id = f"quotation_item_pending_group"

        await self.channel_layer.group_add(
            self.notify_group_id,
            self.channel_name
        )

        await self.send({
            'type': 'websocket.accept'
        })

    async def websocket_disconnect(self, event):
        await self.channel_layer.group_discard(
            self.notify_group_id,
            self.channel_name
        )
        raise StopConsumer()

    async def websocket_receive(self, event):
        text_data = event.get('text', None)
        bytes_data = event.get('bytes', None)

        if text_data:
            text_data_json = json.loads(text_data)
            message_id = text_data_json.get('id')
            action = text_data_json.get('action')
            if action == "start_listening":
                await Messages.start_connection(self.user)
            elif action == "read_message":
                await Messages.read_message(message_id)


    async def send_push_notify(self, notification):
        await self.send({
            'type': 'websocket.send',
            'text': notification["message"]
        })

