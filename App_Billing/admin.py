from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from .forms import ReviewForm
from .models import PaymentAttempt, SubscriptionRequest
from .services import review_request


class BillingAdminMixin:
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SubscriptionRequest)
class SubscriptionRequestAdmin(BillingAdminMixin, admin.ModelAdmin):
    list_display = ['reference', 'account', 'requested_by', 'plan_name', 'billing_cycle', 'kind', 'amount_vnd', 'status', 'created_at', 'review_link']
    list_filter = ['status', 'billing_cycle', 'kind']
    search_fields = ['reference', 'plan_name', 'customer_note']
    readonly_fields = [field.name for field in SubscriptionRequest._meta.fields]
    list_select_related = ['account', 'requested_by']
    actions = None

    @admin.display(description='Xử lý')
    def review_link(self, obj):
        if obj.status != 'pending':
            return '—'
        return format_html('<a href="{}">Xem và xử lý</a>', reverse('admin:billing_request_review', args=[obj.pk]))

    def get_urls(self):
        return [path('<uuid:pk>/review/', self.admin_site.admin_view(self.review_view), name='billing_request_review')] + super().get_urls()

    def review_view(self, request, pk):
        if not self.has_module_permission(request):
            raise PermissionDenied
        item = get_object_or_404(SubscriptionRequest, pk=pk)
        form = ReviewForm(request.POST or None, initial={'confirmed_amount': item.amount_vnd})
        if request.method == 'POST' and form.is_valid():
            try:
                review_request(pk, request.user, decision=form.cleaned_data['decision'], note=form.cleaned_data['note'], confirmed_amount=form.cleaned_data['confirmed_amount'])
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Đã xử lý yêu cầu gói dịch vụ.')
                return redirect('admin:App_Billing_subscriptionrequest_changelist')
        return TemplateResponse(request, 'App_Billing/admin_review.html', {**self.admin_site.each_context(request), 'title': 'Xử lý yêu cầu gói dịch vụ', 'item': item, 'form': form, 'opts': self.model._meta})


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(BillingAdminMixin, admin.ModelAdmin):
    list_display = ['request', 'provider', 'expected_amount_vnd', 'received_amount_vnd', 'status', 'confirmed_at']
    list_filter = ['provider', 'status']
    search_fields = ['request__reference', 'provider_reference']
    readonly_fields = [field.name for field in PaymentAttempt._meta.fields]
    list_select_related = ['request']
    actions = None
