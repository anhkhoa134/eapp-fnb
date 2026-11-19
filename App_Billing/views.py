import json
import logging
import uuid
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from . import sepay
from .forms import SubscriptionRequestForm
from .presentation import request_presentation
from .models import SubscriptionRequest
from .services import account_for, cancel_request, money, record_provider_payment, submit_request

logger = logging.getLogger(__name__)


def serialize(item):
    return {
        'id': str(item.pk), 'reference': item.reference, 'plan': item.plan_name,
        'cycle': item.get_billing_cycle_display(), 'kind': item.get_kind_display(),
        'amount': money(item.approved_amount_vnd if item.approved_amount_vnd is not None else item.amount_vnd),
        'status': item.status, 'status_label': item.get_status_display(),
        'created_at': item.created_at.isoformat(), 'review_note': item.review_note,
        'payment': sepay.payment_info(item),
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
        data = serialize(item)
        message = ('Đã gửi yêu cầu. Quét mã QR trong lịch sử để chuyển khoản, gói tự kích hoạt khi nhận đủ tiền.'
                   if data['payment'] else 'Đã gửi yêu cầu. Quản trị viên sẽ xác nhận và kích hoạt gói.')
        return JsonResponse({'message': message, 'item': data, 'next_client_token': str(uuid.uuid4())}, status=201)
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


@csrf_exempt
@require_POST
def sepay_webhook(request):
    """SePay "Money in" -> tự kích hoạt gói. Luôn trả 200 khi đã xác thực để SePay không gửi lại vô ích;
    các trường hợp tiền đã vào nhưng không kích hoạt được ghi log ERROR (Sentry) để đối soát tay."""
    if not sepay.enabled():
        raise Http404
    ok, reason = sepay.verify_signature(request)
    if not ok:
        logger.warning('SePay webhook auth failed (%s) ua=%s', reason, request.META.get('HTTP_USER_AGENT', '')[:120])
        return JsonResponse({'success': False}, status=401)
    try:
        payload = json.loads(request.body)
    except ValueError:
        return JsonResponse({'success': False}, status=400)
    event, reason = sepay.parse_event(payload)
    if event is None:
        log = logger.info if reason == 'not_this_app' else logger.warning
        log('SePay webhook ignored (%s) tx=%s', reason, payload.get('id') if isinstance(payload, dict) else None)
        return JsonResponse({'success': True})
    try:
        item = record_provider_payment(event['reference'], provider=sepay.PROVIDER,
                                       transaction_id=event['transaction_id'], amount_vnd=event['amount_vnd'])
    except (ValidationError, SubscriptionRequest.DoesNotExist) as error:
        logger.error('SePay: tiền đã vào nhưng không kích hoạt được %s (tx=%s, %sđ): %s',
                     event['reference'], event['transaction_id'], event['amount_vnd'],
                     ' '.join(getattr(error, 'messages', [str(error)])))
        return JsonResponse({'success': True})
    logger.info('SePay: đã kích hoạt %s (tx=%s, %sđ)', item.reference, event['transaction_id'], event['amount_vnd'])
    return JsonResponse({'success': True})
