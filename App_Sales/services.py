from decimal import Decimal

from django.db.models import Max, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from App_Catalog.models import ProductUnit, StoreProduct
from App_Sales.models import Customer, CustomerTierSetting, Order, Promotion
from App_Tenant.services import get_default_store_for_user, get_user_accessible_stores


def get_accessible_store_or_default(user, store_id=None):
    stores = get_user_accessible_stores(user)
    if store_id:
        return stores.filter(id=store_id).first()
    return get_default_store_for_user(user)


def get_effective_unit_price(*, unit: ProductUnit, store_id: int) -> Decimal:
    link = StoreProduct.objects.filter(store_id=store_id, product=unit.product, is_available=True).first()
    if link and link.custom_price is not None:
        return link.custom_price
    return unit.price


LOYALTY_POINT_STEP = Decimal('10000')


def ensure_customer_tier_settings(tenant):
    return CustomerTierSetting.ensure_defaults_for_tenant(tenant)


def get_customer_tier(total_spent: Decimal, tenant=None) -> str:
    total_spent = total_spent or Decimal('0')
    if tenant:
        settings = ensure_customer_tier_settings(tenant)
        rows = sorted(settings, key=lambda row: row.min_total_spent, reverse=True)
        for row in rows:
            if total_spent >= row.min_total_spent:
                return row.tier
    for tier in reversed(CustomerTierSetting.TIER_ORDER):
        min_total_spent, _discount_percent = CustomerTierSetting.DEFAULTS[tier]
        if total_spent >= min_total_spent:
            return tier
    return Customer.Tier.MEMBER


def get_customer_tier_setting(*, tenant, tier):
    settings = ensure_customer_tier_settings(tenant)
    for row in settings:
        if row.tier == tier:
            return row
    min_total_spent, discount_percent = CustomerTierSetting.DEFAULTS.get(tier, (Decimal('0'), Decimal('0')))
    return CustomerTierSetting(
        tenant=tenant,
        tier=tier,
        min_total_spent=min_total_spent,
        discount_percent=discount_percent,
    )


def calculate_points_for_amount(amount: Decimal) -> int:
    amount = amount or Decimal('0')
    if amount <= 0:
        return 0
    return int(amount // LOYALTY_POINT_STEP)


def recompute_customer_stats(customer: Customer):
    if not customer:
        return None
    stats = Order.objects.filter(
        customer=customer,
        tenant=customer.tenant,
        status=Order.Status.COMPLETED,
    ).aggregate(
        total_spent=Coalesce(Sum('total_amount'), Decimal('0')),
        last_order_at=Max('created_at'),
    )
    total_spent = stats['total_spent'] or Decimal('0')
    customer.total_spent = total_spent
    customer.points_balance = calculate_points_for_amount(total_spent)
    customer.tier = get_customer_tier(total_spent, tenant=customer.tenant)
    customer.last_order_at = stats['last_order_at']
    customer.save(update_fields=['total_spent', 'points_balance', 'tier', 'last_order_at', 'updated_at'])
    return customer


def recompute_all_customer_stats(tenant):
    for customer in Customer.objects.filter(tenant=tenant).iterator():
        recompute_customer_stats(customer)


def get_available_promotions(*, tenant, store, subtotal: Decimal, at=None):
    at = at or timezone.now()
    subtotal = subtotal or Decimal('0')
    return (
        Promotion.objects.filter(tenant=tenant, is_active=True, min_order_amount__lte=subtotal)
        .filter(Q(valid_from__isnull=True) | Q(valid_from__lte=at))
        .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=at))
        .filter(Q(stores__isnull=True) | Q(stores=store))
        .distinct()
        .order_by('name', 'id')
    )


def calculate_promotion_discount(*, promotion: Promotion | None, subtotal: Decimal) -> Decimal:
    subtotal = subtotal or Decimal('0')
    if not promotion or subtotal <= 0 or subtotal < promotion.min_order_amount:
        return Decimal('0')
    if promotion.discount_type == Promotion.DiscountType.PERCENT:
        discount = subtotal * (promotion.discount_value / Decimal('100'))
    else:
        discount = promotion.discount_value
    if promotion.max_discount_amount is not None:
        discount = min(discount, promotion.max_discount_amount)
    return max(Decimal('0'), min(discount, subtotal))


def calculate_tier_discount(*, customer: Customer | None, subtotal: Decimal):
    subtotal = subtotal or Decimal('0')
    if not customer or subtotal <= 0:
        return {
            'customer_tier': '',
            'tier_discount_percent': Decimal('0'),
            'tier_discount_amount': Decimal('0'),
        }
    tier = get_customer_tier(customer.total_spent, tenant=customer.tenant)
    setting = get_customer_tier_setting(tenant=customer.tenant, tier=tier)
    discount_percent = setting.discount_percent or Decimal('0')
    discount_amount = subtotal * (discount_percent / Decimal('100'))
    return {
        'customer_tier': tier,
        'tier_discount_percent': discount_percent,
        'tier_discount_amount': max(Decimal('0'), min(discount_amount, subtotal)),
    }


def calculate_order_totals(*, subtotal: Decimal, tax_rate: Decimal, promotion: Promotion | None = None, customer: Customer | None = None):
    promotion_discount_amount = calculate_promotion_discount(promotion=promotion, subtotal=subtotal)
    tier_discount = calculate_tier_discount(customer=customer, subtotal=subtotal)
    tier_discount_amount = tier_discount['tier_discount_amount']
    if tier_discount_amount > promotion_discount_amount:
        discount_amount = tier_discount_amount
        discount_source = Order.DiscountSource.TIER if discount_amount > 0 else Order.DiscountSource.NONE
    else:
        discount_amount = promotion_discount_amount
        discount_source = Order.DiscountSource.PROMOTION if discount_amount > 0 else Order.DiscountSource.NONE
    taxable_amount = max(Decimal('0'), subtotal - discount_amount)
    tax_amount = taxable_amount * tax_rate
    total_amount = taxable_amount + tax_amount
    return {
        'discount_amount': discount_amount,
        'discount_source': discount_source,
        'promotion_discount_amount': promotion_discount_amount,
        'tier_discount_amount': tier_discount_amount,
        'tier_discount_percent': tier_discount['tier_discount_percent'],
        'customer_tier': tier_discount['customer_tier'],
        'tax_amount': tax_amount,
        'total_amount': total_amount,
    }


def resolve_customer_for_checkout(*, tenant, customer_id):
    if not customer_id:
        return None
    try:
        return Customer.objects.get(pk=customer_id, tenant=tenant, is_active=True)
    except Customer.DoesNotExist:
        return None


def resolve_promotion_for_checkout(*, tenant, store, promotion_id, subtotal: Decimal):
    if not promotion_id:
        return None
    return get_available_promotions(tenant=tenant, store=store, subtotal=subtotal).filter(pk=promotion_id).first()
