import json
from decimal import Decimal

from asgiref.sync import async_to_sync, sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TestCase, override_settings
from django.urls import reverse

from App_Accounts.models import User
from App_Catalog.models import Category, Product, ProductUnit, StoreCategory, StoreProduct
from App_Sales.models import DiningTable
from App_Tenant.models import Store, Tenant, UserStoreAccess
from Project.asgi import application


@override_settings(
    CHANNEL_LAYERS={
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        }
    }
)
class PosWebSocketTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='WS Tenant', public_slug='ws-tenant')
        self.store_1 = Store.objects.create(tenant=self.tenant, name='Store 1', is_default=True)
        self.store_2 = Store.objects.create(tenant=self.tenant, name='Store 2')

        self.staff_store_1 = User.objects.create_user(
            username='ws_staff_1',
            password='123456',
            tenant=self.tenant,
            role=User.Role.STAFF,
        )
        self.staff_store_2 = User.objects.create_user(
            username='ws_staff_2',
            password='123456',
            tenant=self.tenant,
            role=User.Role.STAFF,
        )

        UserStoreAccess.objects.create(user=self.staff_store_1, store=self.store_1, is_default=True)
        UserStoreAccess.objects.create(user=self.staff_store_2, store=self.store_2, is_default=True)

        self.category = Category.objects.create(tenant=self.tenant, name='Nước')
        StoreCategory.objects.create(store=self.store_1, category=self.category, is_visible=True)
        self.product = Product.objects.create(tenant=self.tenant, category=self.category, name='Trà')
        self.unit = ProductUnit.objects.create(product=self.product, name='M', price=Decimal('39000'))
        StoreProduct.objects.create(store=self.store_1, product=self.product, is_available=True)

        self.table = DiningTable.objects.create(
            tenant=self.tenant,
            store=self.store_1,
            code='WS-01',
            name='Bàn WS 01',
            qr_token='token-ws-01',
            is_active=True,
            display_order=1,
        )

    def _session_cookie_for(self, user):
        self.client.force_login(user)
        return self.client.cookies['sessionid'].value

    def test_pos_ws_security_anonymous_and_forbidden(self):
        forbidden_cookie = self._session_cookie_for(self.staff_store_2)
        allowed_cookie = self._session_cookie_for(self.staff_store_1)

        async def scenario():
            anonymous = WebsocketCommunicator(application, f'/ws/pos/store/{self.store_1.id}/')
            connected, _ = await anonymous.connect()
            self.assertFalse(connected)

            forbidden = WebsocketCommunicator(
                application,
                f'/ws/pos/store/{self.store_1.id}/',
                headers=[(b'cookie', f'sessionid={forbidden_cookie}'.encode('utf-8'))],
            )
            connected, _ = await forbidden.connect()
            self.assertFalse(connected)

            allowed = WebsocketCommunicator(
                application,
                f'/ws/pos/store/{self.store_1.id}/',
                headers=[(b'cookie', f'sessionid={allowed_cookie}'.encode('utf-8'))],
            )
            connected, _ = await allowed.connect()
            self.assertTrue(connected)
            await allowed.disconnect()

        async_to_sync(scenario)()

    def test_pos_ws_receives_create_event_from_public_qr_api(self):
        cookie = self._session_cookie_for(self.staff_store_1)

        async def scenario():
            pos_ws = WebsocketCommunicator(
                application,
                f'/ws/pos/store/{self.store_1.id}/',
                headers=[(b'cookie', f'sessionid={cookie}'.encode('utf-8'))],
            )
            connected, _ = await pos_ws.connect()
            self.assertTrue(connected)

            payload = {
                'table_code': self.table.code,
                'token': self.table.qr_token,
                'note': 'WebSocket create',
                'items': [
                    {
                        'product_id': self.product.id,
                        'unit_id': self.unit.id,
                        'quantity': 1,
                    }
                ],
            }
            response = await sync_to_async(
                self.client.post,
                thread_sensitive=True,
            )(
                reverse('App_Public_API:qr_orders_create'),
                data=json.dumps(payload),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 201)

            message = await pos_ws.receive_json_from(timeout=1)
            self.assertEqual(message.get('type'), 'qr.changed')
            self.assertEqual(message.get('store_id'), self.store_1.id)
            self.assertEqual(message.get('reason'), 'created')
            self.assertIsInstance(message.get('order_id'), int)

            await pos_ws.disconnect()

        async_to_sync(scenario)()
