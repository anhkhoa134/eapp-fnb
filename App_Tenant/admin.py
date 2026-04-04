from datetime import timedelta

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from App_Accounts.models import User
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
        self.fields['public_slug'].help_text = 'Để trống thì hệ thống tự động tạo từ tên doanh nghiệp.'
        self.fields['public_slug'].widget.attrs['placeholder'] = 'Để trống thì tự động tạo'
        if not self.instance.pk and not self.is_bound:
            today = timezone.now().date()
            self.initial.setdefault('max_stores', 1)
            self.initial.setdefault('max_dining_tables', 12)
            self.initial.setdefault('max_staff_users', 2)
            self.initial.setdefault('subscription_starts_on', today)
            self.initial.setdefault('subscription_ends_on', today + timedelta(days=365))

    def clean_public_slug(self):
        raw_value = (self.cleaned_data.get('public_slug') or '').strip().lower()
        if raw_value:
            return raw_value

        base_slug = slugify(self.cleaned_data.get('name') or '') or 'doanh-nghiep'
        queryset = Tenant.objects.exclude(pk=self.instance.pk) if self.instance.pk else Tenant.objects.all()
        return _build_unique_value(
            queryset=queryset,
            field_name='public_slug',
            base_value=base_slug,
            reserved_values=RESERVED_PUBLIC_SLUGS,
        )

    def clean(self):
        cleaned = super().clean()
        for key in ('max_stores', 'max_dining_tables', 'max_staff_users'):
            if cleaned.get(key) is None:
                cleaned[key] = 0
        start = cleaned.get('subscription_starts_on')
        end = cleaned.get('subscription_ends_on')
        if start and end and end < start:
            raise ValidationError({'subscription_ends_on': 'Ngày kết thúc phải sau hoặc cùng ngày bắt đầu gói.'})
        return cleaned


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
    list_display = (
        'name',
        'public_slug',
        'is_active',
        'subscription_ends_on',
        'store_usage_display',
        'table_usage_display',
        'staff_usage_display',
    )
    list_filter = ('is_active',)
    search_fields = ('name', 'public_slug')
    prepopulated_fields = {'public_slug': ('name',)}
    ordering = ('name',)
    fieldsets = (
        (None, {'fields': ('name', 'public_slug', 'is_active')}),
        (
            'Gói dịch vụ (thời hạn)',
            {
                'fields': ('subscription_starts_on', 'subscription_ends_on'),
                'description': 'Khi tạo mới: để trống cả hai thì hệ thống gán bắt đầu = hôm nay, kết thúc = 1 năm sau.',
            },
        ),
        (
            'Giới hạn tài nguyên',
            {
                'fields': ('max_stores', 'max_dining_tables', 'max_staff_users'),
                'description': 'Đặt 0 để không giới hạn. Mặc định gói mới: 1 cửa hàng, 12 bàn, 2 nhân viên.',
            },
        ),
    )

    @admin.display(description='Cửa hàng (dùng/giới hạn)')
    def store_usage_display(self, obj):
        u = obj.stores.count()
        m = obj.max_stores
        return f'{u} / {"∞" if m == 0 else m}'

    @admin.display(description='Bàn (dùng/giới hạn)')
    def table_usage_display(self, obj):
        u = obj.dining_table_count()
        m = obj.max_dining_tables
        return f'{u} / {"∞" if m == 0 else m}'

    @admin.display(description='Nhân viên (dùng/giới hạn)')
    def staff_usage_display(self, obj):
        u = obj.staff_user_count()
        m = obj.max_staff_users
        return f'{u} / {"∞" if m == 0 else m}'

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
    list_display = ('name', 'phone', 'tenant', 'is_active', 'is_default')
    list_filter = ('tenant', 'is_active', 'is_default')
    search_fields = ('name', 'phone', 'tenant__name')
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        (None, {'fields': ('tenant', 'name', 'slug', 'address', 'phone', 'is_active', 'is_default')}),
        ('QR thanh toán (POS)', {'fields': ('payment_qr', 'payment_bank_name', 'payment_account_name', 'payment_account_number')}),
    )


class UserStoreAccessAdminForm(forms.ModelForm):
    class Meta:
        model = UserStoreAccess
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant_id = None
        if self.instance.pk:
            if self.instance.user_id:
                tenant_id = self.instance.user.tenant_id
            elif self.instance.store_id:
                tenant_id = self.instance.store.tenant_id
        elif self.data is not None:
            uid = self.data.get('user')
            sid = self.data.get('store')
            if uid:
                tenant_id = User.objects.filter(pk=uid).values_list('tenant_id', flat=True).first()
            elif sid:
                tenant_id = Store.objects.filter(pk=sid).values_list('tenant_id', flat=True).first()
        if tenant_id is not None:
            self.fields['store'].queryset = Store.objects.filter(tenant_id=tenant_id, is_active=True).order_by('name')
            self.fields['user'].queryset = User.objects.filter(tenant_id=tenant_id).order_by('username')

    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get('user')
        store = cleaned_data.get('store')
        if user and store and user.tenant_id != store.tenant_id:
            self.add_error('store', 'Cửa hàng phải cùng doanh nghiệp với tài khoản.')
        return cleaned_data


@admin.register(UserStoreAccess)
class UserStoreAccessAdmin(admin.ModelAdmin):
    form = UserStoreAccessAdminForm
    list_display = ('user', 'store', 'is_default')
    list_filter = ('store__tenant', 'is_default')
    search_fields = ('user__username', 'store__name')
