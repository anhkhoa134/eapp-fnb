from django import forms

from App_Catalog.models import Category, Product, ProductUnit
from App_Tenant.models import Store


def _apply_bootstrap_classes(form):
    for field in form.fields.values():
        widget = field.widget
        existing_class = widget.attrs.get('class', '')

        if isinstance(widget, forms.CheckboxInput):
            widget.attrs['class'] = f'{existing_class} form-check-input'.strip()
            continue

        if isinstance(widget, forms.CheckboxSelectMultiple):
            continue

        if isinstance(widget, forms.Select):
            widget.attrs['class'] = f'{existing_class} form-select'.strip()
            continue

        if isinstance(widget, forms.Textarea):
            widget.attrs['class'] = f'{existing_class} form-control'.strip()
            widget.attrs.setdefault('rows', 3)
            continue

        widget.attrs['class'] = f'{existing_class} form-control'.strip()


class CategoryForm(forms.ModelForm):
    store_ids = forms.ModelMultipleChoiceField(
        queryset=Store.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Hiển thị ở cửa hàng',
    )

    class Meta:
        model = Category
        fields = ['name', 'description', 'is_active']

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.fields['store_ids'].queryset = Store.objects.filter(tenant=tenant, is_active=True).order_by('name')
        _apply_bootstrap_classes(self)


class ProductForm(forms.ModelForm):
    store_ids = forms.ModelMultipleChoiceField(
        queryset=Store.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Bán tại cửa hàng',
    )

    class Meta:
        model = Product
        fields = ['name', 'category', 'short_description', 'description', 'image_url', 'is_active']

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.fields['category'].queryset = Category.objects.filter(tenant=tenant, is_active=True).order_by('name')
        self.fields['store_ids'].queryset = Store.objects.filter(tenant=tenant, is_active=True).order_by('name')
        _apply_bootstrap_classes(self)


class ProductUnitForm(forms.ModelForm):
    class Meta:
        model = ProductUnit
        fields = ['name', 'price', 'sku', 'display_order', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap_classes(self)
