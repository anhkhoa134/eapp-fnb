/*
 * Tab "Mẫu phiếu" trong Thiết lập (POS, màn hình bếp): đọc / lưu nội dung phiếu in của cửa hàng
 * qua /api/pos/stores/<id>/print-settings/. Form: templates/App_Sales/print/_receipt_settings_form.html.
 */
(() => {
    const bind = (form) => {
        const storeSelect = form.dataset.storeSelect ? document.querySelector(form.dataset.storeSelect) : null;
        const storeLabel = form.querySelector('[data-rs-store]');
        const message = form.querySelector('[data-rs-message]');
        const submitBtn = form.querySelector('button[type="submit"]');
        const storeId = () => (storeSelect && storeSelect.value) || form.dataset.defaultStore;
        const urlFor = (id) => form.dataset.urlTemplate.replace('/0/', `/${id}/`);
        const fields = () => Array.from(form.elements).filter((el) => el.name && el.name !== 'csrfmiddlewaretoken');

        const say = (text, tone) => {
            message.textContent = text || '';
            message.className = `small mt-2 ${tone === 'danger' ? 'text-danger' : 'text-success'}`;
            message.hidden = !text;
        };
        const request = async (url, options = {}) => {
            const response = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' }, ...options });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.detail || 'Không tải được mẫu phiếu.');
            return data;
        };
        const fill = (data) => {
            fields().forEach((el) => {
                if (el.type === 'checkbox') el.checked = Boolean(data.settings[el.name]);
                else el.value = data.settings[el.name] ?? '';
            });
            storeLabel.textContent = `Áp dụng cho cửa hàng: ${data.store_name}`;
        };

        let loadSeq = 0;
        const load = async () => {
            const id = storeId();
            if (!id) {
                storeLabel.textContent = 'Chưa có cửa hàng để thiết lập.';
                return;
            }
            const seq = ++loadSeq;
            storeLabel.textContent = 'Đang tải mẫu phiếu…';
            try {
                const data = await request(urlFor(id));
                if (seq === loadSeq) fill(data);
            } catch (error) {
                if (seq === loadSeq) storeLabel.textContent = error.message;
            }
        };

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const payload = {};
            fields().forEach((el) => { payload[el.name] = el.type === 'checkbox' ? el.checked : el.value; });
            if (submitBtn) submitBtn.disabled = true;
            try {
                const data = await request(urlFor(storeId()), {
                    method: 'POST',
                    headers: {
                        Accept: 'application/json',
                        'Content-Type': 'application/json',
                        'X-CSRFToken': form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '',
                    },
                    body: JSON.stringify(payload),
                });
                fill(data);
                say('Đã lưu. Các phiếu in từ bây giờ dùng mẫu mới.');
            } catch (error) {
                say(error.message, 'danger');
            } finally {
                if (submitBtn) submitBtn.disabled = false;
            }
        });
        form.querySelector('[data-rs-preview]').addEventListener('click', () => {
            const url = new URL(form.dataset.previewUrl, window.location.origin);
            if (storeId()) url.searchParams.set('store_id', storeId());
            window.open(url.toString(), '_blank', 'noopener');
        });
        storeSelect?.addEventListener('change', () => { say(''); load(); });
        load();
    };

    document.querySelectorAll('[data-receipt-settings]').forEach(bind);
})();
