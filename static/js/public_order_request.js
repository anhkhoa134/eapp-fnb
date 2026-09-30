/* Persist one unresolved creation attempt, including its immutable request body. */
(function (root) {
    'use strict';
    const clone = (value) => JSON.parse(JSON.stringify(value));
    const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    function newId(crypto) {
        if (crypto.randomUUID) return crypto.randomUUID();
        const bytes = crypto.getRandomValues(new Uint8Array(16));
        bytes[6] = (bytes[6] & 15) | 64;
        bytes[8] = (bytes[8] & 63) | 128;
        const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
        return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    }

    function createTracker(storage, key, crypto = root.crypto) {
        let pending = null;
        try {
            const saved = JSON.parse(storage.get(key) || 'null');
            if (saved && uuidPattern.test(saved.payload?.client_request_id)
                && Array.isArray(saved.payload.items) && Array.isArray(saved.cart)) pending = saved;
        } catch (_) { /* A corrupt browser cache is not a submitted request. */ }
        return {
            current() { return pending ? clone(pending) : null; },
            begin(payload, cart) {
                if (!pending) pending = { payload: { ...clone(payload), client_request_id: newId(crypto) }, cart: clone(cart) };
                // Fail before sending if this browser cannot persist recovery data.
                const serialized = JSON.stringify(pending);
                storage.set(key, serialized);
                if (storage.get(key) !== serialized) {
                    throw new Error('Không lưu được giỏ hàng trên trình duyệt. Vui lòng cho phép lưu dữ liệu rồi thử lại.');
                }
                return clone(pending);
            },
            clear() { storage.remove(key); pending = null; },
            // These API validation responses are returned before an order is saved.
            // Retain the attempt on network/5xx/409 errors: the outcome is uncertain.
            rejected(status) { if ([400, 403, 404, 405, 413, 429].includes(status)) this.clear(); },
        };
    }

    root.PublicOrderRequest = { createTracker };
    if (typeof module !== 'undefined' && module.exports) module.exports = root.PublicOrderRequest;
})(globalThis);
