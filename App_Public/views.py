from django.core.paginator import Paginator
from django.db.models import Min, Prefetch
from django.shortcuts import get_object_or_404, render

from App_Catalog.models import Product, ProductUnit
from App_Tenant.models import Store, Tenant


def tenant_catalog(request, public_slug):
    tenant = get_object_or_404(Tenant, public_slug=public_slug, is_active=True)
    stores = Store.objects.filter(tenant=tenant, is_active=True).order_by('name')

    selected_store_id = (request.GET.get('store') or '').strip()
    selected_store = None
    if selected_store_id and selected_store_id.isdigit():
        selected_store = stores.filter(id=selected_store_id).first()
    if not selected_store:
        selected_store = stores.filter(is_default=True).first() or stores.first()

    products = []
    page_obj = None
    selected_query = (request.GET.get('q') or '').strip()

    if selected_store:
        base_qs = (
            Product.objects.filter(
                tenant=tenant,
                is_active=True,
                store_links__store=selected_store,
                store_links__is_available=True,
                units__is_active=True,
            )
            .select_related('category')
            .prefetch_related(
                Prefetch(
                    'units',
                    queryset=ProductUnit.objects.filter(is_active=True).order_by('display_order', 'id'),
                )
            )
            .annotate(min_price=Min('units__price'))
            .distinct()
            .order_by('name')
        )

        visible_category_ids = set(
            selected_store.category_links.filter(is_visible=True).values_list('category_id', flat=True)
        )
        if visible_category_ids:
            base_qs = base_qs.filter(category_id__in=visible_category_ids)

        if selected_query:
            base_qs = base_qs.filter(name__icontains=selected_query)

        paginator = Paginator(base_qs, 20)
        page_obj = paginator.get_page(request.GET.get('page'))
        products = list(page_obj.object_list)

    return render(
        request,
        'App_Public/catalog.html',
        {
            'tenant': tenant,
            'stores': stores,
            'selected_store': selected_store,
            'products': products,
            'page_obj': page_obj,
            'selected_query': selected_query,
        },
    )
