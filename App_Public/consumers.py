from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from App_Sales.models import DiningTable, QROrder
from App_Sales.realtime import public_qr_order_group_name


class PublicQROrderConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        raw_order_id = self.scope.get('url_route', {}).get('kwargs', {}).get('order_id')
        try:
            order_id = int(raw_order_id)
        except (TypeError, ValueError):
            await self.close(code=4400)
            return

        raw_query = (self.scope.get('query_string') or b'').decode('utf-8')
        query = parse_qs(raw_query)
        table_code = ((query.get('table_code') or [''])[0] or '').strip().upper()
        token = ((query.get('token') or [''])[0] or '').strip()

        if not table_code or not token:
            await self.close(code=4400)
            return

        is_valid = await self._is_valid_order_credentials(order_id=order_id, table_code=table_code, token=token)
        if not is_valid:
            await self.close(code=4403)
            return

        self.order_id = order_id
        self.group_name = public_qr_order_group_name(order_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if getattr(self, 'group_name', None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def qr_order_changed(self, event):
        await self.send_json(event.get('data', {}))

    @database_sync_to_async
    def _is_valid_order_credentials(self, *, order_id, table_code, token):
        table = DiningTable.objects.select_related('tenant', 'store').filter(
            code=table_code,
            qr_token=token,
            is_active=True,
            tenant__is_active=True,
            store__is_active=True,
        ).first()
        if not table:
            return False

        return QROrder.objects.filter(id=order_id, tenant=table.tenant, table=table).exists()
