import json
from decimal import Decimal

from asgiref.sync import async_to_sync, sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TestCase, override_settings
from django.urls import reverse

from App_Accounts.models import User
from App_Catalog.models import Category, Product, ProductUnit, StoreCategory, StoreProduct
from App_Sales.models import DiningTable, QROrder, QROrderItem
from App_Tenant.models import Store, Tenant, UserStoreAccess
from Project.asgi import application


@override_settings(
    CHANNEL_LAYERS={
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        }
    }
)
class PublicQrWebSocketTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Public WS Tenant', public_slug='public-ws')
        self.store = Store.objects.create(tenant=self.tenant, name='Store WS', is_default=True)

        self.category = Category.objects.create(tenant=self.tenant, name='Nước uống')
        StoreCategory.objects.create(store=self.store, category=self.category, is_visible=True)
        self.product = Product.objects.create(tenant=self.tenant, category=self.category, name='Cà phê')
        self.unit = ProductUnit.objects.create(product=self.product, name='M', price=Decimal('29000'))
        StoreProduct.objects.create(store=self.store, product=self.product, is_available=True)

        self.table = DiningTable.objects.create(
            tenant=self.tenant,
            store=self.store,
            code='PUB-WS-01',
            name='Bàn Public WS',
            qr_token='token-public-ws',
            is_active=True,
            display_order=1,
        )

        self.staff = User.objects.create_user(
            username='public_ws_staff',
            password='123456',
            tenant=self.tenant,
            role=User.Role.STAFF,
        )
        UserStoreAccess.objects.create(user=self.staff, store=self.store, is_default=True)

        self.pending_order = QROrder.objects.create(
            tenant=self.tenant,
            store=self.store,
            table=self.table,
            status=QROrder.Status.PENDING,
            customer_note='Pending websocket order',
        )
        QROrderItem.objects.create(
            qr_order=self.pending_order,
            product=self.product,
            unit=self.unit,
            snapshot_product_name=self.product.name,
            snapshot_unit_name=self.unit.name,
            unit_price_snapshot=self.unit.price,
            quantity=1,
            note='',
            line_total=Decimal('29000'),
        )

    def test_public_qr_ws_security(self):
        async def scenario():
            missing_token = WebsocketCommunicator(
                application,
                f'/ws/public/qr/order/{self.pending_order.id}/?table_code={self.table.code}&token=bad',
            )
            connected, _ = await missing_token.connect()
            self.assertFalse(connected)

            wrong_order = WebsocketCommunicator(
                application,
                f'/ws/public/qr/order/{self.pending_order.id + 999}/?table_code={self.table.code}&token={self.table.qr_token}',
            )
            connected, _ = await wrong_order.connect()
            self.assertFalse(connected)

            valid = WebsocketCommunicator(
                application,
                f'/ws/public/qr/order/{self.pending_order.id}/?table_code={self.table.code}&token={self.table.qr_token}',
            )
            connected, _ = await valid.connect()
            self.assertTrue(connected)
            await valid.disconnect()

        async_to_sync(scenario)()

    def test_public_qr_ws_receives_approve_event(self):
        self.client.force_login(self.staff)

        async def scenario():
            communicator = WebsocketCommunicator(
                application,
                f'/ws/public/qr/order/{self.pending_order.id}/?table_code={self.table.code}&token={self.table.qr_token}',
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            response = await sync_to_async(
                self.client.post,
                thread_sensitive=True,
            )(
                reverse('App_Sales_API:qr_order_approve', kwargs={'order_id': self.pending_order.id}),
                data='{}',
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 200)

            message = await communicator.receive_json_from(timeout=1)
            self.assertEqual(message.get('type'), 'qr.order.changed')
            self.assertEqual(message.get('order_id'), self.pending_order.id)
            self.assertEqual(message.get('status'), QROrder.Status.APPROVED)
            self.assertEqual(message.get('reason'), 'approved')

            await communicator.disconnect()

        async_to_sync(scenario)()
