from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from App_Accounts.models import User
from App_Sales.realtime import pos_store_group_name
from App_Tenant.services import get_user_accessible_stores


class PosStoreConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        raw_store_id = self.scope.get('url_route', {}).get('kwargs', {}).get('store_id')
        try:
            store_id = int(raw_store_id)
        except (TypeError, ValueError):
            await self.close(code=4400)
            return

        can_access = await self._can_access_store(user_id=user.id, store_id=store_id)
        if not can_access:
            await self.close(code=4403)
            return

        self.store_id = store_id
        self.group_name = pos_store_group_name(store_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if getattr(self, 'group_name', None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def qr_changed(self, event):
        await self.send_json(event.get('data', {}))

    @database_sync_to_async
    def _can_access_store(self, *, user_id, store_id):
        try:
            user = User.objects.select_related('tenant').get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return False

        if user.role not in {User.Role.MANAGER, User.Role.STAFF}:
            return False

        return get_user_accessible_stores(user).filter(id=store_id).exists()
