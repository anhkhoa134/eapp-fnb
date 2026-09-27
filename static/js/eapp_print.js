/*
 * In qua iframe ẩn: tải trang in với ?autoprint=1, trang in tự gọi window.print()
 * rồi báo lại (postMessage) để gỡ iframe. Các lệnh in được xếp hàng lần lượt để
 * hộp thoại in không chồng nhau. Nút có [data-print-url] được gắn sẵn.
 */
(() => {
    const PRINT_TIMEOUT_MS = 120000;
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

    const eappPrint = (url) => {
        if (!url) return queue;
        queue = queue.then(() => printOnce(url)).catch(() => null);
        return queue;
    };

    window.eappPrint = eappPrint;

    document.addEventListener('click', (event) => {
        const trigger = event.target.closest('[data-print-url]');
        if (!trigger) return;
        event.preventDefault();
        eappPrint(trigger.dataset.printUrl);
    });
})();
