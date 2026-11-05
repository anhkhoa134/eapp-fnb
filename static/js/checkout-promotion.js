/* Quick promotion creation keeps checkout state while switching between Bootstrap modals. */
(function () {
    'use strict';
    function create({payment, input, save, selected, closePickers, fixedCap = true}) {
        const element = document.getElementById('quickPromotionModal');
        if (!element) return null;
        const form = element.querySelector('form');
        const error = document.getElementById('quickPromotionError');
        const submit = document.getElementById('saveQuickPromotion');
        const fields = form.querySelector('fieldset');
        const type = form.elements.discount_type;
        const value = form.elements.discount_value;
        const cap = form.elements.max_discount_amount;
        let saving = false, opened = false, restorePayment = false, created = null;
        const syncType = () => {
            if (type.value === 'percent') value.max = '100';
            else value.removeAttribute('max');
            cap.disabled = !fixedCap && type.value !== 'percent';
        };
        type.addEventListener('change', syncType);
        element.addEventListener('hide.bs.modal', event => {
            if (saving) event.preventDefault();
        });
        element.addEventListener('shown.bs.modal', () => form.elements.name.focus());
        element.addEventListener('hidden.bs.modal', () => {
            opened = false;
            const result = created;
            created = null;
            const finish = () => { if (result) selected(result); };
            if (restorePayment) {
                payment.addEventListener('shown.bs.modal', finish, {once: true});
                bootstrap.Modal.getOrCreateInstance(payment).show();
            } else finish();
        });
        form.addEventListener('submit', async event => {
            event.preventDefault();
            if (saving || !form.reportValidity()) return;
            const payload = Object.fromEntries(new FormData(form));
            saving = true;
            submit.disabled = true;
            fields.disabled = true;
            error.textContent = '';
            error.classList.add('d-none');
            try {
                created = await save(payload);
                saving = false;
                bootstrap.Modal.getOrCreateInstance(element).hide();
            } catch (err) {
                error.textContent = err.message || 'Không tạo được khuyến mãi. Vui lòng thử lại.';
                error.classList.remove('d-none');
            } finally {
                saving = false;
                submit.disabled = false;
                fields.disabled = false;
                syncType();
            }
        });
        return {open() {
            if (opened || saving) return;
            opened = true;
            created = null;
            closePickers();
            form.reset();
            syncType();
            const typed = input.value.trim();
            if (/^[A-Za-z0-9_-]{1,40}$/.test(typed)) form.elements.code.value = typed.toUpperCase();
            error.textContent = '';
            error.classList.add('d-none');
            restorePayment = payment.classList.contains('show');
            const show = () => bootstrap.Modal.getOrCreateInstance(element).show();
            if (restorePayment) {
                payment.addEventListener('hidden.bs.modal', show, {once: true});
                bootstrap.Modal.getOrCreateInstance(payment).hide();
            } else show();
        }};
    }
    window.EAPPQuickPromotion = {create};
})();
