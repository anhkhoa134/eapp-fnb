/* Thông báo kiểm tra form của trình duyệt bằng tiếng Việt (thay "Please fill out this field.")
 * và tô đỏ ô lỗi. Chỉ ghi đè lỗi native; lỗi tuỳ chỉnh do trang tự setCustomValidity giữ nguyên.
 */
(function () {
    'use strict';
    const MARK = 'eappValidity';

    function messageFor(el) {
        const v = el.validity;
        if (v.valueMissing) {
            if (el.type === 'checkbox') return 'Vui lòng đánh dấu ô này.';
            if (el.type === 'radio' || el.tagName === 'SELECT') return 'Vui lòng chọn một mục.';
            if (el.type === 'file') return 'Vui lòng chọn tệp.';
            return 'Vui lòng nhập thông tin này.';
        }
        if (v.typeMismatch) {
            if (el.type === 'email') return 'Email không hợp lệ, VD: ten@example.com.';
            if (el.type === 'url') return 'Đường dẫn không hợp lệ, VD: https://example.com.';
            return 'Giá trị không hợp lệ.';
        }
        if (v.badInput) return 'Vui lòng nhập số hợp lệ.';
        if (v.patternMismatch) return el.title || 'Giá trị không đúng định dạng.';
        if (v.tooShort) return `Cần tối thiểu ${el.minLength} ký tự.`;
        if (v.tooLong) return `Tối đa ${el.maxLength} ký tự.`;
        if (v.rangeUnderflow) return `Giá trị nhỏ nhất là ${el.min}.`;
        if (v.rangeOverflow) return `Giá trị lớn nhất là ${el.max}.`;
        if (v.stepMismatch) return 'Giá trị không hợp lệ.';
        return '';
    }

    document.addEventListener('invalid', (event) => {
        const el = event.target;
        if (!el || typeof el.setCustomValidity !== 'function') return;
        // Lỗi tuỳ chỉnh của trang (không phải do file này đặt) thì giữ nguyên.
        if (el.validity.customError && el.dataset[MARK] !== '1') return;
        el.setCustomValidity('');
        const text = messageFor(el);
        if (text) {
            el.setCustomValidity(text);
            el.dataset[MARK] = '1';
        }
        el.classList.add('is-invalid');
    }, true);

    const clear = (event) => {
        const el = event.target;
        if (!el || typeof el.setCustomValidity !== 'function') return;
        if (el.dataset[MARK] === '1') {
            el.setCustomValidity('');
            delete el.dataset[MARK];
        }
        if (el.validity.valid) {
            el.classList.remove('is-invalid');
            el.removeAttribute('aria-invalid');
        }
    };
    document.addEventListener('input', clear, true);
    document.addEventListener('change', clear, true);

    // Ô chọn tệp: thay "Choose File – No file chosen" của trình duyệt bằng nhãn tiếng Việt.
    function enhanceFileInput(input) {
        if (input.dataset.fileEnhanced === '1' || input.hasAttribute('data-native-file')) return;
        input.dataset.fileEnhanced = '1';
        const wrap = document.createElement('div');
        wrap.className = 'eapp-file-input';
        const label = document.createElement('div');
        label.className = 'eapp-file-label';
        label.setAttribute('aria-hidden', 'true');
        const btn = document.createElement('span');
        btn.className = 'eapp-file-btn';
        btn.textContent = input.multiple ? 'Chọn tệp' : 'Chọn ảnh/tệp';
        const name = document.createElement('span');
        name.className = 'eapp-file-name';
        label.append(btn, name);
        input.parentNode.insertBefore(wrap, input);
        wrap.append(label, input);
        const sync = () => {
            const files = Array.from(input.files || []);
            name.textContent = files.length ? files.map((f) => f.name).join(', ') : 'Chưa chọn tệp nào';
        };
        input.addEventListener('change', sync);
        input.form?.addEventListener('reset', () => setTimeout(sync, 0));
        sync();
    }

    // Ô ngày: lịch tiếng Việt hiển thị dd/mm/yyyy (input type=date của trình duyệt hiện mm/dd/yyyy
    // theo locale máy). Giá trị gửi lên server giữ nguyên Y-m-d / Y-m-dTH:i.
    function enhanceDateInput(input) {
        if (!window.flatpickr || input.dataset.dateEnhanced === '1' || input.hasAttribute('data-native-date')) return;
        input.dataset.dateEnhanced = '1';
        const withTime = input.type === 'datetime-local';
        const value = input.value;
        const readOnly = input.readOnly;
        input.type = 'text';
        const picker = window.flatpickr(input, {
            locale: (window.flatpickr.l10ns && window.flatpickr.l10ns.vn) || 'default',
            allowInput: !readOnly,
            clickOpens: !readOnly,
            disableMobile: true,
            altInput: true,
            altFormat: withTime ? 'd/m/Y H:i' : 'd/m/Y',
            dateFormat: withTime ? 'Y-m-d\\TH:i' : 'Y-m-d',
            enableTime: withTime,
            time_24hr: true,
            defaultDate: value || null,
        });
        if (picker.altInput) {
            picker.altInput.placeholder = withTime ? 'dd/mm/yyyy hh:mm' : 'dd/mm/yyyy';
            if (input.required) picker.altInput.required = true;
            picker.altInput.readOnly = readOnly;
            // <label for="…"> trỏ vào ô hiển thị thay vì ô ẩn giữ giá trị.
            if (input.id) {
                picker.altInput.id = `${input.id}-display`;
                document.querySelectorAll(`label[for="${CSS.escape(input.id)}"]`).forEach((label) => {
                    label.htmlFor = picker.altInput.id;
                });
            }
        }
    }

    // Dùng thay `input.value = …` cho ô ngày đã gắn lịch (VD modal sửa điền sẵn dữ liệu).
    window.eappSetDateValue = (input, value) => {
        if (!input) return;
        if (input._flatpickr) input._flatpickr.setDate(value || null, false);
        else input.value = value || '';
    };

    const enhanceAll = (root) => {
        (root || document).querySelectorAll('input[type="file"]').forEach(enhanceFileInput);
        (root || document).querySelectorAll('input[type="date"], input[type="datetime-local"]').forEach(enhanceDateInput);
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => enhanceAll());
    else enhanceAll();
    window.eappEnhanceFileInputs = enhanceAll;
})();
