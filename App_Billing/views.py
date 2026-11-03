import uuid
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST
from .forms import SubscriptionRequestForm
from .presentation import request_presentation
from .models import SubscriptionRequest
from .services import account_for, cancel_request, money, submit_request


def serialize(item):
    return {
        'id': str(item.pk), 'reference': item.reference, 'plan': item.plan_name,
        'cycle': item.get_billing_cycle_display(), 'kind': item.get_kind_display(),
        'amount': money(item.approved_amount_vnd if item.approved_amount_vnd is not None else item.amount_vnd),
        'status': item.status, 'status_label': item.get_status_display(),
        'created_at': item.created_at.isoformat(), 'review_note': item.review_note,
    }


@never_cache
@require_http_methods(['GET', 'POST'])
def requests_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Vui lòng đăng nhập để gửi yêu cầu.'}, status=401)
    try:
        account = account_for(request)
    except PermissionDenied as error:
        return JsonResponse({'error': str(error)}, status=403)
    if request.method == 'POST':
        form = SubscriptionRequestForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'error': 'Vui lòng kiểm tra thông tin yêu cầu.', 'errors': form.errors.get_json_data()}, status=400)
        try:
            item = submit_request(request, **form.cleaned_data)
        except ValidationError as error:
            return JsonResponse({'error': ' '.join(error.messages)}, status=400)
        except IntegrityError:
            return JsonResponse({'error': 'Đã có yêu cầu đang xử lý. Vui lòng tải lại lịch sử.'}, status=409)
        return JsonResponse({'message': 'Đã gửi yêu cầu. Quản trị viên sẽ xác nhận và kích hoạt gói.', 'item': serialize(item), 'next_client_token': str(uuid.uuid4())}, status=201)
    items = SubscriptionRequest.objects.filter(account=account)
    page = Paginator(items, 20).get_page(request.GET.get('page', 1))
    return JsonResponse({'items': [serialize(item) for item in page], 'page': page.number, 'pages': page.paginator.num_pages, 'pending': items.filter(status='pending').exists(), 'actions': request_presentation(request)['actions']})


@never_cache
@require_POST
def cancel_view(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Vui lòng đăng nhập.'}, status=401)
    try:
        cancel_request(request, pk)
    except PermissionDenied as error:
        return JsonResponse({'error': str(error)}, status=403)
    except SubscriptionRequest.DoesNotExist:
        return JsonResponse({'error': 'Không tìm thấy yêu cầu.'}, status=404)
    except ValidationError as error:
        return JsonResponse({'error': ' '.join(error.messages)}, status=400)
    return JsonResponse({'message': 'Đã hủy yêu cầu.'})
