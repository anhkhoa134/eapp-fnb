import uuid

from django.conf import settings
from django.db import models

from App_Core.models import TimeStampedModel


class Order(TimeStampedModel):
    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Cash'
        CARD = 'card', 'Card/QR'

    class Status(models.TextChoices):
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.PROTECT, related_name='orders')
    store = models.ForeignKey('App_Tenant.Store', on_delete=models.PROTECT, related_name='orders')
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    order_code = models.CharField(max_length=30, unique=True, editable=False)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    customer_paid = models.DecimalField(max_digits=14, decimal_places=2)
    change_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'store', 'created_at']),
            models.Index(fields=['tenant', 'status', 'created_at']),
        ]
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.order_code:
            self.order_code = f'ORD-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_code


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('App_Catalog.Product', on_delete=models.SET_NULL, null=True, blank=True)
    unit = models.ForeignKey('App_Catalog.ProductUnit', on_delete=models.SET_NULL, null=True, blank=True)
    snapshot_product_name = models.CharField(max_length=180)
    snapshot_unit_name = models.CharField(max_length=120)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    quantity = models.PositiveIntegerField()
    note = models.CharField(max_length=255, blank=True)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        indexes = [
            models.Index(fields=['order', 'snapshot_product_name']),
        ]

    def save(self, *args, **kwargs):
        self.line_total = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.snapshot_product_name} x{self.quantity}'
