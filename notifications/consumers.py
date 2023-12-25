from channels.consumer import  AsyncConsumer
from channels.exceptions import StopConsumer
import json
from channels.db import database_sync_to_async
from .models import Groups,Messages,ReadStatus


class MessagesConsumer(AsyncConsumer):
    async def websocket_connect(self, event):
        self.user = self.scope['user']
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.notify_group_id = f"notify_group_{self.user.id}"
        print(f'{self.user_id} is connected')

        if self.user and str(self.user.id) == self.user_id:
            await self.channel_layer.group_add(
                self.notify_group_id,
                self.channel_name
            )

            await self.send({
                'type': 'websocket.accept'
            })
        else:
            await self.send({
                'type': 'websocket.close'
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

