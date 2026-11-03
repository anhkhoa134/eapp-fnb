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
    function estimate() {
        const currentForm = form();
        if (!currentForm) return;
        const option = currentForm.elements.plan_key.selectedOptions[0];
        const cycle = currentForm.elements.billing_cycle.value;
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
    async function refresh() {
        cleanupModal();
        const root = panel();
        if (!root || root.dataset.canManage !== 'true' || loading) return;
        loading = true;
        try {
            const data = await request(`${root.dataset.endpoint}?page=${page}`);
            if (!root.isConnected) return;
            page = data.page;
            const pending = document.querySelector('[data-billing-pending]');
            if (pending) pending.hidden = !data.pending;
            const body = root.querySelector('[data-billing-history]');
            body.replaceChildren();
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
            }
            if (!data.items.length) { const row = document.createElement('tr'); const cell = td(row, 'Chưa có yêu cầu nâng cấp hoặc gia hạn.'); cell.colSpan = 7; cell.className = 'text-center text-muted py-4'; body.append(row); }
            root.querySelector('[data-billing-page]').textContent = `Trang ${data.page} / ${data.pages}`;
            root.querySelector('[data-billing-prev]').disabled = data.page <= 1;
            root.querySelector('[data-billing-next]').disabled = data.page >= data.pages;
        } catch (error) { message('[data-billing-feedback]', error.message); }
        finally { loading = false; }
    }
    document.addEventListener('click', async (event) => {
        const select = event.target.closest('[data-billing-select]');
        if (select) {
            cleanupModal();
            const root = panel();
            if (!root) return;
            if (root.dataset.canManage !== 'true') {
                if (root.dataset.loginUrl) window.location.assign(root.dataset.loginUrl);
                else message('[data-billing-feedback]', 'Chỉ người quản lý tài khoản được gửi yêu cầu.');
                return;
            }
            const currentForm = form();
            const pricing = select.closest('[data-billing-period], [data-pricing-period]');
            currentForm.elements.plan_key.value = select.dataset.billingSelect;
            currentForm.elements.billing_cycle.value = pricing?.dataset.billingPeriod || pricing?.dataset.pricingPeriod || 'month';
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
