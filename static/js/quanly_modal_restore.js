/**
 * Giữ dữ liệu form trong modal khi server báo lỗi.
 *
 * Các view sửa (đơn vị bán, topping, sản phẩm, bàn...) redirect về trang danh sách khi form lỗi, nên modal
 * đóng và mất những gì đã nhập. Script này lưu giá trị form lúc bấm lưu (sessionStorage); nếu trang tải lại
 * có thông báo lỗi thì mở lại đúng modal đó (bấm lại nút đã mở nó, khớp theo data-action để trang tự điền
 * tên món...), điền lại giá trị đã nhập và hiện lỗi ngay trong modal.
 */
(() => {
    const STORAGE_KEY = 'quanly_modal_form_stash';
    const MAX_AGE_MS = 2 * 60 * 1000;

    const hasEditableFields = (form) => Array.from(form.elements).some((el) => (
        el.name && !['hidden', 'submit', 'button'].includes(el.type)
    ));

    document.addEventListener('submit', (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || (form.method || '').toLowerCase() !== 'post') return;
        const modal = form.closest('.modal[id]');
        if (!modal || !hasEditableFields(form)) return;
        const values = [];
        Array.from(form.elements).forEach((el) => {
            if (!el.name || el.name === 'csrfmiddlewaretoken' || el.type === 'file') return;
            if (['submit', 'button'].includes(el.type)) return;
            if (el.type === 'checkbox' || el.type === 'radio') {
                values.push({ name: el.name, value: el.value, checked: el.checked });
            } else if (el.multiple) {
                values.push({ name: el.name, selected: Array.from(el.selectedOptions).map((option) => option.value) });
            } else {
                values.push({ name: el.name, value: el.value });
            }
        });
        const stash = {
            path: window.location.pathname,
            modalId: modal.id,
            formIndex: Array.from(modal.querySelectorAll('form')).indexOf(form),
            action: form.getAttribute('action') || '',
            values,
            ts: Date.now(),
        };
        try { window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(stash)); } catch (error) { /* bỏ qua */ }
    });

    const readStash = () => {
        try {
            const raw = window.sessionStorage.getItem(STORAGE_KEY);
            window.sessionStorage.removeItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : null;
        } catch (error) {
            return null;
        }
    };

    const fillForm = (form, values) => {
        const groups = new Set(values.filter((item) => 'checked' in item).map((item) => item.name));
        Array.from(form.elements).forEach((el) => {
            if (groups.has(el.name) && (el.type === 'checkbox' || el.type === 'radio')) el.checked = false;
        });
        values.forEach((item) => {
            const matches = Array.from(form.elements).filter((el) => el.name === item.name);
            if ('checked' in item) {
                const el = matches.find((candidate) => candidate.value === item.value);
                if (el) el.checked = item.checked;
            } else if ('selected' in item) {
                matches.forEach((el) => {
                    Array.from(el.options || []).forEach((option) => { option.selected = item.selected.includes(option.value); });
                });
            } else if (matches[0] && matches[0].type !== 'hidden') {
                matches[0].value = item.value;
                matches[0].dispatchEvent(new Event('input', { bubbles: true }));
            }
        });
    };

    const showErrorInModal = (modal, texts) => {
        const body = modal.querySelector('.modal-body');
        if (!body || !texts.length) return;
        body.querySelector('.js-modal-restore-error')?.remove();
        const alert = document.createElement('div');
        alert.className = 'alert alert-danger py-2 small js-modal-restore-error';
        alert.setAttribute('role', 'alert');
        alert.textContent = texts.join(' ');
        body.prepend(alert);
        modal.addEventListener('hidden.bs.modal', () => alert.remove(), { once: true });
    };

    const restore = () => {
        const stash = readStash();
        if (!stash || stash.path !== window.location.pathname || Date.now() - stash.ts > MAX_AGE_MS) return;
        const errors = Array.from(document.querySelectorAll('#quanlyMessageSource .js-quanly-message'))
            .filter((item) => (item.dataset.tags || '').split(' ').some((tag) => tag === 'error' || tag === 'danger'))
            .map((item) => item.dataset.text || '');
        if (!errors.length) return;
        // Trang đã tự mở lại modal kèm lỗi tại ô (form tạo mới render lại từ server).
        if (document.body.classList.contains('modal-open')) return;
        const modal = document.getElementById(stash.modalId);
        if (!modal || typeof bootstrap === 'undefined') return;

        const trigger = Array.from(document.querySelectorAll(`[data-bs-target="#${CSS.escape(stash.modalId)}"]`))
            .find((el) => stash.action && el.dataset.action === stash.action);
        if (trigger) {
            trigger.click();
        } else {
            bootstrap.Modal.getOrCreateInstance(modal).show();
        }
        const form = modal.querySelectorAll('form')[stash.formIndex];
        if (!form) return;
        if (stash.action && !form.getAttribute('action')) form.setAttribute('action', stash.action);
        fillForm(form, stash.values);
        showErrorInModal(modal, errors);
    };

    document.addEventListener('DOMContentLoaded', () => {
        // Chạy sau các handler DOMContentLoaded của trang (gắn sự kiện cho nút Sửa / Thêm đơn vị...).
        window.setTimeout(restore, 0);
    });
})();
