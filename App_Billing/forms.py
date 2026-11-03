from django import forms
from . import adapter
from .models import SubscriptionRequest


class SubscriptionRequestForm(forms.Form):
    plan_key = forms.ChoiceField(label='Gói yêu cầu')
    billing_cycle = forms.ChoiceField(label='Kỳ hạn', choices=SubscriptionRequest.Cycle.choices)
    customer_note = forms.CharField(label='Ghi chú', required=False, max_length=2000)
    client_token = forms.UUIDField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['plan_key'].choices = [(p['key'], p['name']) for p in adapter.plans()]


class ReviewForm(forms.Form):
    decision = forms.ChoiceField(label='Xử lý', choices=[('approved', 'Xác nhận và kích hoạt / gia hạn'), ('rejected', 'Từ chối'), ('cancelled', 'Hủy yêu cầu')])
    confirmed_amount = forms.IntegerField(label='Số tiền xác nhận (VND)', min_value=0, required=False)
    payment_confirmed = forms.BooleanField(label='Đã xác nhận thanh toán / thỏa thuận với khách hàng', required=False)
    note = forms.CharField(label='Phản hồi cho khách hàng', max_length=2000, required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def clean(self):
        data = super().clean()
        if data.get('decision') == 'approved' and not data.get('payment_confirmed'):
            self.add_error('payment_confirmed', 'Vui lòng xác nhận trước khi kích hoạt gói.')
        return data
