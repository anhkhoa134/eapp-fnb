from django import forms
from django.contrib import admin
from django.db import transaction
from django.utils.text import slugify

from App_Tenant.models import RESERVED_PUBLIC_SLUGS, Store, Tenant, UserStoreAccess
from App_Tenant.services import provision_tenant_default_setup


def _build_unique_value(queryset, field_name, base_value, reserved_values=None):
    candidate = base_value
    suffix = 2
    reserved_values = set(reserved_values or [])
    while queryset.filter(**{field_name: candidate}).exists() or candidate in reserved_values:
        candidate = f'{base_value}-{suffix}'
        suffix += 1
    return candidate


class TenantAdminForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['public_slug'].required = False
        self.fields['public_slug'].help_text = 'Để trống thì hệ thống tự động tạo từ tên tenant.'
        self.fields['public_slug'].widget.attrs['placeholder'] = 'Để trống thì tự động tạo'

    def clean_public_slug(self):
        raw_value = (self.cleaned_data.get('public_slug') or '').strip().lower()
        if raw_value:
            return raw_value

        base_slug = slugify(self.cleaned_data.get('name') or '') or 'tenant'
        queryset = Tenant.objects.exclude(pk=self.instance.pk) if self.instance.pk else Tenant.objects.all()
        return _build_unique_value(
            queryset=queryset,
            field_name='public_slug',
            base_value=base_slug,
            reserved_values=RESERVED_PUBLIC_SLUGS,
        )


class StoreAdminForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['slug'].help_text = 'Để trống thì hệ thống tự động tạo từ tên cửa hàng.'
        self.fields['slug'].widget.attrs['placeholder'] = 'Để trống thì tự động tạo'

    def clean_slug(self):
        raw_value = (self.cleaned_data.get('slug') or '').strip().lower()
        base_slug = raw_value or (slugify(self.cleaned_data.get('name') or '') or 'store')

        tenant = self.cleaned_data.get('tenant') or getattr(self.instance, 'tenant', None)
        queryset = Store.objects.all()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        return _build_unique_value(
            queryset=queryset,
            field_name='slug',
            base_value=base_slug,
        )


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    form = TenantAdminForm
    list_display = ('name', 'public_slug', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'public_slug')
    prepopulated_fields = {'public_slug': ('name',)}
    ordering = ('name',)

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            if not change:
                provision_tenant_default_setup(obj)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    form = StoreAdminForm
    list_display = ('name', 'tenant', 'is_active', 'is_default')
    list_filter = ('tenant', 'is_active', 'is_default')
    search_fields = ('name', 'tenant__name')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(UserStoreAccess)
class UserStoreAccessAdmin(admin.ModelAdmin):
    list_display = ('user', 'store', 'is_default')
    list_filter = ('store__tenant', 'is_default')
    search_fields = ('user__username', 'store__name')
