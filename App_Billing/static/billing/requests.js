(() => {
    if (window.eappBillingRequests) { window.eappBillingRequests.refresh(); return; }
    let movedModal = null;
    let modalOwner = null;
    let modalTrigger = null;
    const activeModals = new WeakSet();
    document.addEventListener('show.bs.modal', (event) => activeModals.add(event.target));
    document.addEventListener('hidden.bs.modal', (event) => activeModals.delete(event.target));
    function cleanupModal() {
        if (!movedModal || modalOwner?.isConnected) return;
        const stale = movedModal;
        const instance = window.bootstrap?.Modal.getInstance(stale);
        if (instance && activeModals.has(stale)) {
            // Bootstrap still needs its element until the backdrop transition completes.
            stale.addEventListener('hidden.bs.modal', () => instance.dispose(), {once: true});
            stale.addEventListener('shown.bs.modal', () => instance.hide(), {once: true});
            instance.hide();
        } else instance?.dispose();
        stale.remove(); movedModal = null; modalOwner = null;
    }
    let page = 1;
    let loading = false;
    let pollTimer = null;
    let awaitingPayment = new Set();
    const POLL_MS = 8000;
    let sending = false;
    const panel = () => document.querySelector('[data-billing-requests]');
    const form = () => document.querySelector('[data-billing-request-form]');
    const token = () => form()?.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';
    const money = (amount) => `${new Intl.NumberFormat('vi-VN').format(amount)}đ`;
    const message = (selector, text) => {
        const element = document.querySelector(selector);
        if (element) { element.textContent = text; element.hidden = !text; }
    };
    async function request(url, options = {}) {
        const response = await fetch(url, {credentials: 'same-origin', headers: {'Accept': 'application/json', 'X-CSRFToken': token()}, ...options});
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const fieldErrors = Object.values(data.errors || {}).flat().map((error) => error.message).join(' ');
            throw new Error(fieldErrors || data.error || 'Không thể xử lý yêu cầu. Vui lòng thử lại.');
        }
        return data;
    }
    const cycleFor = (button) => {
        const pricing = button.closest('[data-billing-period], [data-pricing-period]');
        return pricing?.dataset.billingPeriod || pricing?.dataset.pricingPeriod || 'month';
    };
    function updateActions(actions) {
        document.querySelectorAll('[data-billing-select]').forEach((button) => {
            const action = actions?.[button.dataset.billingSelect];
            if (action) {
                for (const cycle of ['month', 'year']) {
                    button.setAttribute(`data-label-${cycle}`, action[cycle].label);
                    button.setAttribute(`data-disabled-${cycle}`, String(action[cycle].disabled));
                    button.setAttribute(`data-variant-${cycle}`, action[cycle].variant || 'select');
                }
                const caption = button.parentElement.querySelector('[data-billing-caption]');
                if (caption) { caption.textContent = action.caption; caption.hidden = !action.caption; }
                const option = Array.from(form()?.elements.plan_key.options || []).find((item) => item.value === button.dataset.billingSelect);
                if (option) option.disabled = action.free && action.month.disabled;
            }
            const cycle = cycleFor(button);
            const label = button.querySelector('.billing-cta-label');
            if (label) label.textContent = button.getAttribute(`data-label-${cycle}`) || 'Chọn gói này';
            button.dataset.billingVariant = button.getAttribute(`data-variant-${cycle}`) || 'select';
            button.disabled = button.getAttribute(`data-disabled-${cycle}`) === 'true';
        });
    }
    function estimate() {
        const currentForm = form();
        if (!currentForm) return;
        const option = currentForm.elements.plan_key.selectedOptions[0];
        const free = option?.dataset.free === 'true';
        const cycleField = currentForm.elements.billing_cycle;
        currentForm.querySelector('[data-billing-cycle-field]').hidden = free;
        for (const choice of cycleField.options) choice.disabled = free ? choice.value !== 'none' : choice.value === 'none';
        if (free) cycleField.value = 'none';
        else if (cycleField.value === 'none' || !cycleField.value) cycleField.value = 'month';
        if (free) {
            message('[data-billing-estimate]', 'Miễn phí · Không thời hạn. Chuyển gói có hiệu lực sau khi quản trị viên xác nhận.');
            return;
        }
        const cycle = cycleField.value;
        const price = option?.getAttribute(`data-price-${cycle}`);
        message('[data-billing-estimate]', price === '' || price == null ? 'Giá liên hệ: quản trị viên sẽ báo giá sau khi nhận yêu cầu.' : `Tạm tính: ${money(Number(price))} cho ${cycle === 'year' ? '12 tháng' : '1 tháng'}.`);
    }
    function td(row, text, detail) {
        const cell = document.createElement('td');
        cell.textContent = text;
        if (detail) { const small = document.createElement('small'); small.className = 'd-block'; small.textContent = detail; cell.append(small); }
        row.append(cell);
        return cell;
    }
    function paymentBox(item) {
        // QR SePay cho yêu cầu đang chờ có giá niêm yết (mỗi tài khoản tối đa một); webhook kích hoạt gói khi nhận đủ tiền.
        const box = document.createElement('div'); box.className = 'billing-payment';
        const image = document.createElement('img'); image.src = item.payment.qr_url; image.alt = `Mã QR chuyển khoản ${item.reference}`;
        image.width = 180; image.height = 180; image.loading = 'lazy'; box.append(image);
        const info = document.createElement('div'); info.className = 'billing-payment-info'; box.append(info);
        const title = document.createElement('strong'); title.textContent = 'Quét mã QR bằng app ngân hàng để thanh toán'; info.append(title);
        const lines = [['Số tiền', money(item.payment.amount_vnd)], ['Nội dung chuyển khoản', item.payment.content],
            ['Ngân hàng', item.payment.bank], ['Số tài khoản', item.payment.account]];
        if (item.payment.holder) lines.push(['Chủ tài khoản', item.payment.holder]);
        const list = document.createElement('dl'); info.append(list);
        for (const [label, value] of lines) {
            const term = document.createElement('dt'); term.textContent = label;
            const detail = document.createElement('dd'); detail.textContent = value; list.append(term, detail);
        }
        const note = document.createElement('p'); note.className = 'billing-payment-note';
        note.textContent = 'Giữ nguyên nội dung chuyển khoản. Gói tự kích hoạt trong khoảng 1 phút sau khi nhận đủ tiền, trang này tự cập nhật.';
        info.append(note);
        return box;
    }
    function schedulePoll(waiting) {
        clearTimeout(pollTimer); pollTimer = null;
        if (waiting) pollTimer = setTimeout(() => { if (document.visibilityState === 'visible') refresh(); else schedulePoll(true); }, POLL_MS);
    }
    async function refresh() {
        cleanupModal();
        updateActions();
        const root = panel();
        if (!root || root.dataset.canManage !== 'true' || loading) return;
        loading = true;
        try {
            const data = await request(`${root.dataset.endpoint}?page=${page}`);
            if (!root.isConnected) return;
            page = data.page;
            updateActions(data.actions);
            const pending = document.querySelector('[data-billing-pending]');
            if (pending) pending.hidden = !data.pending;
            const body = root.querySelector('[data-billing-history]');
            body.replaceChildren();
            const slot = root.querySelector('[data-billing-payment]');
            slot?.replaceChildren();
            let waiting = false;
            for (const item of data.items) {
                const row = document.createElement('tr');
                td(row, new Date(item.created_at).toLocaleString('vi-VN'), item.reference);
                td(row, item.plan, item.kind); td(row, item.cycle); td(row, item.amount);
                const status = document.createElement('span');
                status.className = `billing-status billing-status--${item.status}`; status.textContent = item.status_label;
                td(row, '').append(status); td(row, item.review_note || '—');
                const action = td(row, '');
                if (item.status === 'pending') {
                    const button = document.createElement('button'); button.type = 'button'; button.className = 'btn btn-sm btn-outline-secondary';
                    button.dataset.billingCancel = item.id; button.textContent = 'Hủy'; action.append(button);
                }
                body.append(row);
                if (item.payment && slot && !waiting) { slot.append(paymentBox(item)); waiting = true; }
            }
            const paid = data.items.some((item) => awaitingPayment.has(item.id) && item.status === 'approved');
            awaitingPayment = new Set(data.items.filter((item) => item.payment).map((item) => item.id));
            if (paid) message('[data-billing-feedback]', 'Đã nhận thanh toán, gói đã được kích hoạt. Tải lại trang để cập nhật thông tin gói.');
            if (slot) slot.hidden = !waiting;
            schedulePoll(waiting);
            if (!data.items.length) { const row = document.createElement('tr'); const cell = td(row, 'Chưa có yêu cầu nâng cấp hoặc gia hạn.'); cell.colSpan = 7; cell.className = 'text-center text-muted py-4'; body.append(row); }
            root.querySelector('[data-billing-page]').textContent = `Trang ${data.page} / ${data.pages}`;
            root.querySelector('[data-billing-prev]').disabled = data.page <= 1;
            root.querySelector('[data-billing-next]').disabled = data.page >= data.pages;
        } catch (error) { message('[data-billing-feedback]', error.message); schedulePoll(awaitingPayment.size > 0); }
        finally { loading = false; }
    }
    document.addEventListener('click', async (event) => {
        const periodButton = event.target.closest('[data-billing-period-button], [data-pricing-period-button]');
        if (periodButton) {
            const pricing = periodButton.closest('[data-billing-period], [data-pricing-period]');
            const cycle = periodButton.dataset.billingPeriodButton || periodButton.dataset.pricingPeriodButton;
            if (pricing && ['month', 'year'].includes(cycle)) {
                if (pricing.hasAttribute('data-billing-period')) pricing.dataset.billingPeriod = cycle;
                else pricing.dataset.pricingPeriod = cycle;
                updateActions();
            }
        }
        const select = event.target.closest('[data-billing-select]');
        if (select && !select.disabled) {
            cleanupModal();
            const root = panel();
            if (!root) return;
            if (root.dataset.canManage !== 'true') {
                if (root.dataset.loginUrl) window.location.assign(root.dataset.loginUrl);
                else message('[data-billing-feedback]', 'Chỉ người quản lý tài khoản được gửi yêu cầu.');
                return;
            }
            const currentForm = form();
            currentForm.elements.plan_key.value = select.dataset.billingSelect;
            currentForm.elements.billing_cycle.value = cycleFor(select);
            message('[data-billing-form-message]', ''); estimate();
            const modal = document.getElementById('billingRequestModal');
            // Move out of transformed cards/tab panels so the backdrop never covers the form.
            movedModal = modal; modalOwner = root; modalTrigger = select;
            document.body.append(modal);
            if (window.bootstrap?.Modal) bootstrap.Modal.getOrCreateInstance(modal).show();
            else message('[data-billing-feedback]', 'Biểu mẫu chưa tải xong. Vui lòng tải lại trang.');
        }
        if (event.target.closest('[data-billing-refresh]')) await refresh();
        if (event.target.closest('[data-billing-prev]') && !loading) { page = Math.max(1, page - 1); await refresh(); }
        if (event.target.closest('[data-billing-next]') && !loading) { page += 1; await refresh(); }
        const cancel = event.target.closest('[data-billing-cancel]');
        if (cancel) {
            if (!window.confirm('Hủy yêu cầu đang chờ xử lý này?')) return;
            cancel.disabled = true;
            try {
                const result = await request(`${panel().dataset.endpoint}${cancel.dataset.billingCancel}/cancel/`, {method: 'POST'});
                message('[data-billing-feedback]', result.message); await refresh();
            } catch (error) { message('[data-billing-feedback]', error.message); }
            finally { cancel.disabled = false; }
        }
    });
    document.addEventListener('change', (event) => {
        if (event.target.closest('[data-billing-request-form]')) estimate();
    });
    document.addEventListener('submit', async (event) => {
        const currentForm = event.target.closest('[data-billing-request-form]');
        if (!currentForm) return;
        event.preventDefault();
        if (sending || !currentForm.reportValidity()) return;
        sending = true;
        const button = currentForm.querySelector('[data-billing-submit]'); button.disabled = true;
        message('[data-billing-form-message]', '');
        try {
            const result = await request(currentForm.action, {method: 'POST', body: new FormData(currentForm)});
            message('[data-billing-feedback]', result.message);
            bootstrap.Modal.getOrCreateInstance(document.getElementById('billingRequestModal')).hide();
            currentForm.elements.client_token.value = result.next_client_token;
            currentForm.elements.customer_note.value = '';
            page = 1; await refresh();
        } catch (error) { message('[data-billing-form-message]', error.message); }
        finally { sending = false; button.disabled = false; }
    });
    document.addEventListener('hidden.bs.modal', (event) => {
        if (event.target === movedModal && modalTrigger?.isConnected) modalTrigger.focus();
    });
    document.addEventListener('htmx:afterSwap', () => { page = 1; refresh(); });
    window.eappBillingRequests = {refresh};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', refresh, {once:true});
    else refresh();
})();
