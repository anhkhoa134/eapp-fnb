/*
 * In qua iframe ẩn: tải trang in với ?autoprint=1, trang in tự gọi window.print()
 * rồi báo lại (postMessage) để gỡ iframe. Các lệnh in được xếp hàng lần lượt để
 * hộp thoại in không chồng nhau. Nút có [data-print-url] được gắn sẵn.
 * Trang có nạp eapp_direct_print.js và đã chọn máy in nhiệt thì in thẳng tới máy đó
 * (eappPrint(url, 'kitchen') / data-print-role="kitchen" dùng máy in phiếu bếp).
 */
(() => {
    // Chrome/Edge máy tính chặn script khi hộp thoại in đang mở, nên mốc này chỉ chạy sau khi đóng hộp thoại.
    // Trình duyệt không chặn và không phát "afterprint" (một số bản iOS) thì đây là lúc gỡ iframe:
    // trước đây 120 giây làm phiếu in sau (VD phiếu bếp sau hoá đơn) phải chờ 2 phút.
    const PRINT_TIMEOUT_MS = 30000;
    let queue = Promise.resolve();

    const printOnce = (url) => new Promise((resolve) => {
        const target = new URL(url, window.location.origin);
        target.searchParams.set('autoprint', '1');
        const frame = document.createElement('iframe');
        frame.setAttribute('aria-hidden', 'true');
        frame.tabIndex = -1;
        frame.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;';
        let timer = null;
        const onMessage = (event) => {
            if (event.origin !== window.location.origin || event.source !== frame.contentWindow) return;
            if (event.data && event.data.type === 'eapp-print-done') finish();
        };
        const finish = () => {
            window.removeEventListener('message', onMessage);
            if (timer) clearTimeout(timer);
            // Đợi hộp thoại in đóng hẳn rồi mới gỡ iframe.
            setTimeout(() => {
                frame.remove();
                resolve();
            }, 500);
        };
        window.addEventListener('message', onMessage);
        timer = setTimeout(finish, PRINT_TIMEOUT_MS);
        frame.src = target.pathname + target.search;
        document.body.appendChild(frame);
    });

    // Thiết bị đã chọn máy in nhiệt (eapp_direct_print.js): in thẳng, không mở hộp thoại.
    // Chỉ quay về hộp thoại khi chưa kết nối được máy in (trang in chưa tải nên máy chủ chưa đếm lần in);
    // lỗi sau đó thì báo qua sự kiện "eapp-print-error", không mở hộp thoại để tránh in hai lần.
    // role: 'receipt' (hoá đơn, tạm tính, in thử) hoặc 'kitchen' (phiếu bếp), chọn máy in tương ứng.
    const printDirectOrDialog = async (url, role) => {
        const direct = window.eappDirectPrint;
        if (!direct || !direct.current(role)) return printOnce(url);
        try {
            await direct.printUrl(url, role);
        } catch (error) {
            const fallback = error && error.code === 'NO_DEVICE';
            window.dispatchEvent(new CustomEvent('eapp-print-error', {
                detail: { message: (error && error.message) || 'Không in được.', fallback },
            }));
            if (fallback) await printOnce(url);
        }
    };

    const eappPrint = (url, role = 'receipt') => {
        if (!url) return queue;
        queue = queue.then(() => printDirectOrDialog(url, role)).catch(() => null);
        return queue;
    };

    window.eappPrint = eappPrint;

    document.addEventListener('click', (event) => {
        const trigger = event.target.closest('[data-print-url]');
        if (!trigger) return;
        event.preventDefault();
        eappPrint(trigger.dataset.printUrl, trigger.dataset.printRole || 'receipt');
    });
})();
