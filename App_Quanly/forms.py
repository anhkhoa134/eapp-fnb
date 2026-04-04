from decimal import ROUND_HALF_UP, Decimal

from django import forms
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from App_Accounts.models import User
from App_Catalog.models import Category, Product, ProductTopping, ProductUnit, Topping
from App_Catalog.product_image_utils import MAX_UPLOAD_BYTES, apply_product_image_upload, clear_product_uploaded_images
from App_Sales.models import DiningTable
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
        if tenant:
            self.fields['store_ids'].queryset = Store.objects.filter(tenant=tenant, is_active=True).order_by('name')
        else:
            self.fields['store_ids'].queryset = Store.objects.none()
        _apply_bootstrap_classes(self)

    def _post_clean(self):
        # Tenant không có trên form; gán trước full_clean() (giống ProductForm).
        tenant = getattr(self, 'tenant', None)
        if tenant is not None and not self.instance.tenant_id:
            self.instance.tenant = tenant
        super()._post_clean()

    def clean(self):
        cleaned = super().clean()
        tenant = self.tenant
        if tenant:
            for store in cleaned.get('store_ids') or []:
                if store.tenant_id != tenant.id:
                    raise ValidationError('Cửa hàng chọn không thuộc doanh nghiệp hiện tại.')
        return cleaned


class ProductForm(forms.ModelForm):
    store_ids = forms.ModelMultipleChoiceField(
        queryset=Store.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Bán tại cửa hàng',
    )
    image_upload = forms.ImageField(
        label='Ảnh từ máy',
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
    )
    remove_uploaded_images = forms.BooleanField(
        required=False,
        initial=False,
        label='Xóa ảnh đã upload',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    class Meta:
        model = Product
        fields = ['name', 'category', 'description', 'image_url', 'is_active']

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant:
            self.fields['category'].queryset = Category.objects.filter(tenant=tenant, is_active=True).order_by('name')
            self.fields['store_ids'].queryset = Store.objects.filter(tenant=tenant, is_active=True).order_by('name')
        else:
            self.fields['category'].queryset = Category.objects.none()
            self.fields['store_ids'].queryset = Store.objects.none()
        _apply_bootstrap_classes(self)
        self.fields['description'].widget.attrs['rows'] = 2
        cls = (self.fields['image_upload'].widget.attrs.get('class', '') + ' js-product-image-upload').strip()
        self.fields['image_upload'].widget.attrs['class'] = cls

    def _post_clean(self):
        # ModelForm gọi instance.full_clean() trước khi view kịp gán tenant; Product.clean() cần tenant khi có category.
        tenant = getattr(self, 'tenant', None)
        if tenant is not None and not self.instance.tenant_id:
            self.instance.tenant = tenant
        super()._post_clean()

    def clean(self):
        data = super().clean()
        upload = data.get('image_upload')
        remove_u = data.get('remove_uploaded_images')
        if upload and remove_u:
            raise ValidationError('Chọn một: tải ảnh mới hoặc xóa ảnh đã upload.')
        tenant = self.tenant
        category = data.get('category')
        if tenant and category and category.tenant_id != tenant.id:
            self.add_error('category', 'Danh mục không thuộc doanh nghiệp hiện tại.')
        if tenant:
            for store in data.get('store_ids') or []:
                if store.tenant_id != tenant.id:
                    raise ValidationError('Cửa hàng chọn không thuộc doanh nghiệp hiện tại.')
        return data

    def clean_image_upload(self):
        f = self.cleaned_data.get('image_upload')
        if not f:
            return f
        if f.size > MAX_UPLOAD_BYTES:
            raise ValidationError('Ảnh tối đa 5 MB.')
        return f

    def save(self, commit=True):
        instance = super().save(commit=False)
        tenant = getattr(self, 'tenant', None)
        if tenant and not instance.tenant_id:
            instance.tenant = tenant
        upload = self.cleaned_data.get('image_upload')
        remove_upload = self.cleaned_data.get('remove_uploaded_images')
        if upload:
            try:
                apply_product_image_upload(instance, upload)
            except Exception as exc:
                raise ValidationError('Không xử lý được ảnh. Hãy dùng JPG, PNG hoặc WebP.') from exc
        elif remove_upload and instance.pk:
            clear_product_uploaded_images(instance)
        if commit:
            instance.save()
        return instance


class ProductUnitForm(forms.ModelForm):
    class Meta:
        model = ProductUnit
        fields = ['name', 'price', 'sku', 'display_order', 'is_active']
        widgets = {
            'price': forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'off'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap_classes(self)
        cls = (self.fields['price'].widget.attrs.get('class', '') + ' js-price-vnd').strip()
        self.fields['price'].widget.attrs['class'] = cls

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is None:
            return price
        return price.quantize(Decimal('1'), rounding=ROUND_HALF_UP)


class ToppingForm(forms.ModelForm):
    class Meta:
        model = Topping
        fields = ['name', 'display_order', 'is_active']

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        _apply_bootstrap_classes(self)

    def _post_clean(self):
        tenant = getattr(self, 'tenant', None)
        if tenant is not None and not self.instance.tenant_id:
            self.instance.tenant = tenant
        super()._post_clean()


class ProductToppingForm(forms.ModelForm):
    class Meta:
        model = ProductTopping
        fields = ['product', 'topping', 'price', 'display_order', 'is_active']
        widgets = {
            'price': forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'off'}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant:
            self.fields['product'].queryset = Product.objects.filter(tenant=tenant, is_active=True).order_by('name')
            self.fields['topping'].queryset = Topping.objects.filter(tenant=tenant, is_active=True).order_by('name')
        else:
            self.fields['product'].queryset = Product.objects.none()
            self.fields['topping'].queryset = Topping.objects.none()
        _apply_bootstrap_classes(self)
        cls = (self.fields['price'].widget.attrs.get('class', '') + ' js-price-vnd').strip()
        self.fields['price'].widget.attrs['class'] = cls

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get('product')
        topping = cleaned.get('topping')
        if product and topping and product.tenant_id != topping.tenant_id:
            raise ValidationError('Sản phẩm và topping phải cùng doanh nghiệp.')
        return cleaned

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is None:
            return price
        return price.quantize(Decimal('1'), rounding=ROUND_HALF_UP)


STORE_PAYMENT_QR_MAX_BYTES = 2 * 1024 * 1024


class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ['name', 'address', 'is_active', 'is_default']
        labels = {
            'name': 'Tên cửa hàng',
            'address': 'Địa chỉ',
            'is_active': 'Đang hoạt động',
            'is_default': 'Cửa hàng mặc định',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'VD: Chi nhánh trung tâm'}),
            'address': forms.TextInput(attrs={'placeholder': 'Địa chỉ hiển thị nội bộ (tuỳ chọn)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['address'].required = False
        self.fields['is_default'].help_text = (
            'Chỉ nên bật cho một cửa hàng; dùng làm mặc định khi hệ thống cần chọn sẵn cửa.'
        )
        _apply_bootstrap_classes(self)


class StorePaymentForm(forms.ModelForm):
    remove_payment_qr = forms.BooleanField(
        required=False,
        initial=False,
        label='Xóa ảnh QR hiện tại',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    class Meta:
        model = Store
        fields = ['payment_qr', 'payment_bank_name', 'payment_account_name', 'payment_account_number']
        labels = {
            'payment_qr': 'Ảnh mã QR thanh toán',
            'payment_bank_name': 'Tên ngân hàng',
            'payment_account_name': 'Tên chủ tài khoản',
            'payment_account_number': 'Số tài khoản',
        }
        widgets = {
            'payment_bank_name': forms.TextInput(attrs={'placeholder': 'VD: Vietcombank'}),
            'payment_account_name': forms.TextInput(attrs={'placeholder': 'Tên hiển thị trên thẻ / ứng dụng ngân hàng'}),
            'payment_account_number': forms.TextInput(attrs={'placeholder': 'Chỉ số, không khoảng trắng', 'inputmode': 'numeric'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['payment_qr'].required = False
        self.fields['payment_qr'].help_text = 'Ảnh QR để khách quét chuyển khoản (khuyến nghị PNG/JPG, dưới 2MB).'
        _apply_bootstrap_classes(self)
        self.order_fields(
            [
                'payment_qr',
                'remove_payment_qr',
                'payment_bank_name',
                'payment_account_name',
                'payment_account_number',
            ]
        )

    def clean(self):
        data = super().clean()
        if data.get('remove_payment_qr') and data.get('payment_qr'):
            raise ValidationError('Chọn một: tải ảnh mới hoặc xóa ảnh QR hiện tại.')
        return data

    def clean_payment_qr(self):
        f = self.cleaned_data.get('payment_qr')
        if not f:
            return f
        if f.size > STORE_PAYMENT_QR_MAX_BYTES:
            raise ValidationError('Ảnh QR tối đa 2 MB.')
        return f

    def save(self, commit=True):
        remove = self.cleaned_data.get('remove_payment_qr')
        instance = super().save(commit=False)
        if remove:
            instance.payment_qr = None
        if commit:
            instance.save()
        return instance


class DiningTableForm(forms.ModelForm):
    class Meta:
        model = DiningTable
        fields = ['store', 'code', 'name', 'display_order', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={'placeholder': 'VD: A-01'}),
            'name': forms.TextInput(attrs={'placeholder': 'VD: Bàn 01'}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant:
            self.fields['store'].queryset = Store.objects.filter(tenant=tenant, is_active=True).order_by('name')
        else:
            self.fields['store'].queryset = Store.objects.none()
        self.fields['code'].help_text = 'Mã bàn sẽ tự chuyển sang chữ in hoa.'
        _apply_bootstrap_classes(self)

    def _post_clean(self):
        tenant = getattr(self, 'tenant', None)
        if tenant is not None and not self.instance.tenant_id:
            self.instance.tenant = tenant
        super()._post_clean()

    def clean(self):
        cleaned = super().clean()
        tenant = getattr(self, 'tenant', None)
        store = cleaned.get('store')
        if tenant and store and store.tenant_id != tenant.id:
            self.add_error('store', 'Cửa hàng không thuộc doanh nghiệp hiện tại.')
        return cleaned


class StaffCreateForm(forms.Form):
    username = forms.CharField(label='Tên đăng nhập', max_length=150)
    password1 = forms.CharField(label='Mật khẩu', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Xác nhận mật khẩu', widget=forms.PasswordInput)
    store_ids = forms.ModelMultipleChoiceField(
        queryset=Store.objects.none(),
        required=True,
        widget=forms.CheckboxSelectMultiple,
        label='Cấp quyền cửa hàng',
    )
    default_store = forms.ModelChoiceField(
        queryset=Store.objects.none(),
        required=True,
        label='Cửa hàng mặc định',
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant:
            stores = Store.objects.filter(tenant=tenant, is_active=True).order_by('name')
        else:
            stores = Store.objects.none()
        self.fields['store_ids'].queryset = stores
        self.fields['default_store'].queryset = stores
        if tenant:
            pfx = f'{tenant.public_slug}_'
            self.fields['username'].help_text = (
                f'Bắt đầu bằng tiền tố mã doanh nghiệp "{pfx}" — ví dụ: {pfx}thu_ngan, {pfx}nhan_vien_1.'
            )
        _apply_bootstrap_classes(self)

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            raise forms.ValidationError('Vui lòng nhập tên đăng nhập.')
        tenant = self.tenant
        if tenant:
            prefix = f'{tenant.public_slug}_'
            if not username.startswith(prefix):
                raise forms.ValidationError(
                    f'Tên đăng nhập phải bắt đầu bằng tiền tố "{prefix}" (theo mã doanh nghiệp hiện tại).'
                )
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Tên đăng nhập đã tồn tại.')
        return username

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1') or ''
        password2 = cleaned.get('password2') or ''
        if password1 != password2:
            self.add_error('password2', 'Xác nhận mật khẩu không khớp.')
        else:
            try:
                validate_password(password1)
            except ValidationError as exc:
                self.add_error('password1', exc)

        selected_stores = cleaned.get('store_ids')
        default_store = cleaned.get('default_store')
        tenant = self.tenant
        if tenant and selected_stores is not None:
            for store in selected_stores:
                if store.tenant_id != tenant.id:
                    raise ValidationError('Cửa hàng chọn không thuộc doanh nghiệp hiện tại.')
        if tenant and default_store and default_store.tenant_id != tenant.id:
            self.add_error('default_store', 'Cửa hàng mặc định không thuộc doanh nghiệp hiện tại.')
        if selected_stores is not None and default_store and default_store not in selected_stores:
            self.add_error('default_store', 'Cửa hàng mặc định phải thuộc danh sách cửa hàng đã cấp quyền.')
        return cleaned


class StaffEditForm(forms.Form):
    store_ids = forms.ModelMultipleChoiceField(
        queryset=Store.objects.none(),
        required=True,
        widget=forms.CheckboxSelectMultiple,
        label='Cấp quyền cửa hàng',
    )
    default_store = forms.ModelChoiceField(
        queryset=Store.objects.none(),
        required=True,
        label='Cửa hàng mặc định',
    )
    is_active = forms.BooleanField(
        label='Đang hoạt động',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def __init__(self, *args, tenant=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.user = user
        if tenant:
            stores = Store.objects.filter(tenant=tenant, is_active=True).order_by('name')
        else:
            stores = Store.objects.none()
        self.fields['store_ids'].queryset = stores
        self.fields['default_store'].queryset = stores
        if user is not None and not self.is_bound:
            self.fields['is_active'].initial = user.is_active
        _apply_bootstrap_classes(self)

    def clean(self):
        cleaned = super().clean()
        selected_stores = cleaned.get('store_ids')
        default_store = cleaned.get('default_store')
        tenant = self.tenant
        if tenant and selected_stores is not None:
            for store in selected_stores:
                if store.tenant_id != tenant.id:
                    raise ValidationError('Cửa hàng chọn không thuộc doanh nghiệp hiện tại.')
        if tenant and default_store and default_store.tenant_id != tenant.id:
            self.add_error('default_store', 'Cửa hàng mặc định không thuộc doanh nghiệp hiện tại.')
        if selected_stores is not None and default_store and default_store not in selected_stores:
            self.add_error('default_store', 'Cửa hàng mặc định phải thuộc danh sách cửa hàng đã cấp quyền.')
        return cleaned


class StaffPasswordResetForm(SetPasswordForm):
    field_order = ['new_password1', 'new_password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'Mật khẩu mới'
        self.fields['new_password2'].label = 'Xác nhận mật khẩu mới'
        _apply_bootstrap_classes(self)
