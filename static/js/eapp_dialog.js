/*
 * Hộp thoại dùng chung thay cho window.alert / window.confirm của trình duyệt.
 *
 * JS:
 *   const ok = await eappDialog.confirm({ title, message, okText, cancelText, variant });
 *   await eappDialog.alert({ title, message, variant });
 *   const reason = await eappDialog.prompt({ title, message, placeholder, choices: ['…'], required: true });
 *   variant: 'primary' (mặc định) | 'danger' | 'warning' | 'success' | 'info'
 *
 * Khai báo trên form hoặc nút submit (không cần viết JS):
 *   <form data-confirm="Chốt ca?" data-confirm-title="Chốt ca"
 *         data-confirm-ok="Chốt ca" data-confirm-variant="danger">
 *
 * Cần Bootstrap 5 (bootstrap.bundle) nạp trước file này.
 */
(() => {
    if (window.eappDialog) return;

    const VARIANTS = {
        primary: { glyph: '?', button: 'btn-primary' },
        danger: { glyph: '!', button: 'btn-danger' },
        warning: { glyph: '!', button: 'btn-warning' },
        success: { glyph: '✓', button: 'btn-success' },
        info: { glyph: 'i', button: 'btn-primary' },
    };
    const STACK_Z_INDEX = 1080;

    const STYLE = `
        .eapp-dialog .modal-content { border: 0; border-radius: 18px; box-shadow: 0 24px 48px rgba(15, 23, 42, 0.25); }
        .eapp-dialog .modal-body { padding: 1.5rem 1.5rem 1rem; text-align: center; }
        .eapp-dialog-icon {
            width: 52px; height: 52px; border-radius: 50%;
            display: inline-flex; align-items: center; justify-content: center;
            font-size: 1.6rem; font-weight: 800; line-height: 1; margin-bottom: 0.75rem;
        }
        .eapp-dialog-icon.v-primary, .eapp-dialog-icon.v-info { background: rgba(59, 130, 246, 0.14); color: #2563eb; }
        .eapp-dialog-icon.v-danger { background: rgba(239, 68, 68, 0.14); color: #dc2626; }
        .eapp-dialog-icon.v-warning { background: rgba(245, 158, 11, 0.18); color: #b45309; }
        .eapp-dialog-icon.v-success { background: rgba(16, 185, 129, 0.16); color: #047857; }
        .eapp-dialog-title { font-size: 1.1rem; font-weight: 800; color: #0f172a; margin-bottom: 0.35rem; }
        .eapp-dialog-message { color: #475569; white-space: pre-line; margin: 0; }
        .eapp-dialog-choices .btn { border-radius: 999px; font-size: 0.8rem; padding: 0.25rem 0.7rem; }
        .eapp-dialog .modal-footer { border-top: 0; padding: 0 1.5rem 1.5rem; gap: 0.5rem; flex-wrap: nowrap; }
        .eapp-dialog .modal-footer .btn { flex: 1 1 0; margin: 0; font-weight: 700; padding: 0.6rem 1rem; border-radius: 12px; }
    `;

    let modalEl = null;
    let modal = null;
    let resolveCurrent = null;
    let result = false;
    let currentMode = 'confirm';
    let currentRequired = false;
    let queue = Promise.resolve();

    const build = () => {
        const style = document.createElement('style');
        style.textContent = STYLE;
        document.head.appendChild(style);

        modalEl = document.createElement('div');
        modalEl.className = 'modal fade eapp-dialog';
        modalEl.tabIndex = -1;
        modalEl.setAttribute('aria-hidden', 'true');
        modalEl.setAttribute('aria-labelledby', 'eappDialogTitle');
        modalEl.setAttribute('aria-describedby', 'eappDialogMessage');
        modalEl.innerHTML = `
            <div class="modal-dialog modal-dialog-centered" style="max-width: 420px;">
                <div class="modal-content">
                    <div class="modal-body">
                        <div class="eapp-dialog-icon" aria-hidden="true"></div>
                        <div class="eapp-dialog-title" id="eappDialogTitle"></div>
                        <p class="eapp-dialog-message" id="eappDialogMessage"></p>
                        <div class="eapp-dialog-choices d-flex flex-wrap gap-1 justify-content-center mt-3 d-none"></div>
                        <input type="text" class="form-control mt-2 d-none" data-eapp-dialog="input" maxlength="255" aria-labelledby="eappDialogTitle">
                        <div class="invalid-feedback text-start">Vui lòng nhập lý do.</div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-light border" data-eapp-dialog="cancel"></button>
                        <button type="button" class="btn" data-eapp-dialog="ok"></button>
                    </div>
                </div>
            </div>`;
        document.body.appendChild(modalEl);
        modal = new bootstrap.Modal(modalEl);

        const input = modalEl.querySelector('[data-eapp-dialog="input"]');
        modalEl.querySelector('[data-eapp-dialog="ok"]').addEventListener('click', () => {
            if (currentMode === 'prompt') {
                const value = input.value.trim();
                if (currentRequired && !value) {
                    input.classList.add('is-invalid');
                    input.focus();
                    return;
                }
                result = value;
            } else {
                result = true;
            }
            modal.hide();
        });
        input.addEventListener('input', () => input.classList.remove('is-invalid'));
        input.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                modalEl.querySelector('[data-eapp-dialog="ok"]').click();
            }
        });
        modalEl.querySelector('[data-eapp-dialog="cancel"]').addEventListener('click', () => modal.hide());
        modalEl.addEventListener('shown.bs.modal', () => {
            // Mở chồng lên một modal khác: đẩy backdrop của hộp thoại lên trên modal đó.
            if (modalEl.style.zIndex) {
                const backdrops = document.querySelectorAll('.modal-backdrop');
                const last = backdrops[backdrops.length - 1];
                if (last) last.style.zIndex = String(STACK_Z_INDEX - 5);
            }
            if (currentMode === 'prompt') input.focus();
            else modalEl.querySelector('[data-eapp-dialog="ok"]').focus();
        });
        modalEl.addEventListener('hidden.bs.modal', () => {
            modalEl.style.zIndex = '';
            // Bootstrap gỡ modal-open khỏi body kể cả khi modal bên dưới vẫn đang mở.
            if (document.querySelector('.modal.show')) document.body.classList.add('modal-open');
            const resolve = resolveCurrent;
            resolveCurrent = null;
            if (resolve) resolve(result);
        });
    };

    const open = ({ mode, title, message, okText, cancelText, variant, placeholder, choices, required, value }) => {
        if (!window.bootstrap || !window.bootstrap.Modal) {
            // Không có Bootstrap thì không hiển thị được hộp thoại: coi như đồng ý để không chặn thao tác.
            console.warn('eappDialog cần Bootstrap 5:', message);
            return Promise.resolve(mode === 'prompt' ? (value || '') : true);
        }
        if (!modalEl) build();
        const run = () => new Promise((resolve) => {
            const config = VARIANTS[variant] || VARIANTS.primary;
            const icon = modalEl.querySelector('.eapp-dialog-icon');
            icon.className = `eapp-dialog-icon v-${VARIANTS[variant] ? variant : 'primary'}`;
            icon.textContent = config.glyph;
            modalEl.querySelector('.eapp-dialog-title').textContent = title || (mode === 'alert' ? 'Thông báo' : 'Xác nhận');
            const messageEl = modalEl.querySelector('.eapp-dialog-message');
            messageEl.textContent = message || '';
            messageEl.classList.toggle('d-none', !message);
            const okBtn = modalEl.querySelector('[data-eapp-dialog="ok"]');
            okBtn.className = `btn ${config.button}`;
            okBtn.textContent = okText || (mode === 'alert' ? 'Đã hiểu' : 'Đồng ý');
            const cancelBtn = modalEl.querySelector('[data-eapp-dialog="cancel"]');
            cancelBtn.textContent = cancelText || 'Huỷ';
            cancelBtn.classList.toggle('d-none', mode === 'alert');

            const input = modalEl.querySelector('[data-eapp-dialog="input"]');
            const choicesEl = modalEl.querySelector('.eapp-dialog-choices');
            input.classList.toggle('d-none', mode !== 'prompt');
            input.classList.remove('is-invalid');
            input.value = value || '';
            input.placeholder = placeholder || '';
            choicesEl.innerHTML = '';
            (mode === 'prompt' ? choices || [] : []).forEach((choice) => {
                const chip = document.createElement('button');
                chip.type = 'button';
                chip.className = 'btn btn-outline-secondary';
                chip.textContent = choice;
                chip.addEventListener('click', () => {
                    input.value = choice;
                    input.classList.remove('is-invalid');
                    input.focus();
                });
                choicesEl.appendChild(chip);
            });
            choicesEl.classList.toggle('d-none', !choicesEl.children.length);

            currentMode = mode;
            currentRequired = Boolean(required);
            result = mode === 'prompt' ? null : false;
            resolveCurrent = resolve;
            if (document.querySelector('.modal.show')) modalEl.style.zIndex = String(STACK_Z_INDEX);
            modal.show();
        });
        // Nếu đang có hộp thoại mở thì xếp hàng chờ.
        queue = queue.then(run, run);
        return queue;
    };

    window.eappDialog = {
        confirm: (options = {}) => open({ ...options, mode: 'confirm' }),
        // Trả chuỗi đã nhập, hoặc null khi bấm Huỷ. options: placeholder, choices (gợi ý nhanh), required, value.
        prompt: (options = {}) => open({ ...options, mode: 'prompt' }),
        alert: async (options = {}) => {
            await open({ ...options, mode: 'alert' });
        },
    };

    // Khai báo: <form data-confirm="..."> hoặc <button type="submit" data-confirm="...">.
    document.addEventListener('submit', (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || event.defaultPrevented) return;
        const submitter = event.submitter;
        const source = submitter && submitter.dataset.confirm ? submitter : form;
        if (!source.dataset.confirm) return;
        if (form.dataset.eappConfirmed === '1') {
            delete form.dataset.eappConfirmed;
            return;
        }
        event.preventDefault();
        window.eappDialog.confirm({
            title: source.dataset.confirmTitle,
            message: source.dataset.confirm,
            okText: source.dataset.confirmOk,
            cancelText: source.dataset.confirmCancel,
            variant: source.dataset.confirmVariant,
        }).then((ok) => {
            if (!ok) return;
            form.dataset.eappConfirmed = '1';
            if (typeof form.requestSubmit === 'function') form.requestSubmit(submitter || undefined);
            else form.submit();
        });
    });
})();


// Account Live & Reload Status Handler
function updateAccountLiveState() {
    const isOnline = navigator.onLine;
    const indicators = document.querySelectorAll('.account-live-indicator');
    indicators.forEach(indicator => {
        const text = indicator.querySelector('.account-live-text');
        if (isOnline) {
            indicator.classList.remove('offline');
            indicator.classList.add('live');
            if (text) text.textContent = 'Live';
            indicator.setAttribute('title', 'Hệ thống đang kết nối trực tiếp');
        } else {
            indicator.classList.remove('live');
            indicator.classList.add('offline');
            if (text) text.textContent = 'Offline';
            indicator.setAttribute('title', 'Mất kết nối Internet hoặc máy chủ ngoại tuyến');
        }
    });
}
window.addEventListener('online', updateAccountLiveState);
window.addEventListener('offline', updateAccountLiveState);
document.addEventListener('DOMContentLoaded', updateAccountLiveState);

function handleAccountReload(btn) {
    const icon = btn ? (btn.querySelector('.account-reload-icon') || btn.querySelector('i')) : null;
    if (icon) {
        icon.classList.add('account-spin');
    }
    setTimeout(() => {
        window.location.reload();
    }, 150);
}
