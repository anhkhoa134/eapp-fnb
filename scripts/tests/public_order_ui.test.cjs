// Execute the actual ordering script with DOM stubs; no browser/profile data.
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { test } = require('node:test');
const { webcrypto } = require('node:crypto');
const vm = require('node:vm');
const root = resolve(__dirname, '../..');
const trackerSource = readFileSync(resolve(root, 'static/js/public_order_request.js'), 'utf8');
const appSource = readFileSync(resolve(root, 'templates/App_Public/_ordering_app.html'), 'utf8')
    .split('<script>')[1].split('</script>')[0].replace(/{%.*?%}/g, '/test-api/');

function page(mode, storage, fetch) {
    const elements = new Map();
    const element = (id) => {
        if (!elements.has(id)) elements.set(id, {
            value: '', textContent: '', innerHTML: '', disabled: false, events: {},
            classList: { toggle() {}, add() {}, remove() {} },
            addEventListener(event, fn) { this.events[event] = fn; },
            querySelector(selector) { return element(id + selector); }, querySelectorAll() { return []; },
            appendChild() {}, remove() {}, focus() {}, scrollIntoView() {},
        });
        return elements.get(id);
    };
    const cfg = { mode, ordering_enabled: true, tenant_slug: 'demo', table_code: 'T1', token: 'test-token',
        store: { id: 1 }, categories: [], products: [{ id: 1, name: 'Trà', units: [{ id: 2, name: 'M', price: 45000 }] }] };
    element('order-bootstrap-data').textContent = JSON.stringify(cfg);
    const context = vm.createContext({
        crypto: webcrypto, Intl, URLSearchParams, console, fetch,
        navigator: {}, setTimeout() { return 1; }, clearTimeout() {}, setInterval() { return 1; }, clearInterval() {},
        document: { getElementById: element, querySelectorAll: () => [], createElement: () => element('toast'), addEventListener() {} },
        window: { localStorage: { getItem: (key) => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: (key) => storage.delete(key) },
            addEventListener() {}, matchMedia: () => ({ matches: true }) },
        bootstrap: { Offcanvas: { getInstance: () => null } },
    });
    vm.runInContext(trackerSource, context);
    vm.runInContext(appSource, context);
    return { element, submit: () => element('od-submit').events.click() };
}

for (const mode of ['dine_in', 'takeaway']) {
    test(`${mode}: lost response -> reload -> retry preserves the request and clears pending state on success`, async () => {
        const storage = new Map();
        const contextKey = mode === 'takeaway' ? 'demo::store-1' : 'demo::T1';
        const requestKey = `eapp_order_request::${mode}::${contextKey}`;
        storage.set(`eapp_order_cart::${mode}::${contextKey}`, JSON.stringify([
            { product_id: 1, unit_id: 2, name: 'Trà', unit_name: 'M', quantity: 2, unit_price: 45000, toppings: [] },
        ]));
        const requests = [];
        const send = async (_url, options) => {
            const body = JSON.parse(options.body);
            requests.push(body);
            if (requests.length === 1) throw new Error('Response lost after commit');
            assert.deepEqual(body, requests[0]);
            return { ok: true, status: 200, json: async () => ({ replayed: true, access_key: 'takeaway-access',
                order: { id: 17, status: 'PENDING', items: [], total: 90000 } }) };
        };
        const first = page(mode, storage, send);
        first.element('od-order-note').value = 'Ghi chú trước khi gửi';
        first.element('od-customer-name').value = 'Khách';
        first.element('od-customer-phone').value = '0901234567';
        await first.submit();
        assert.equal(first.element('od-submitspan').textContent, 'Kiểm tra đơn đã gửi');
        assert.equal(first.element('od-order-note').disabled, true);
        assert.ok(storage.has(requestKey));
        const reloaded = page(mode, storage, send);
        assert.equal(reloaded.element('od-order-note').value, 'Ghi chú trước khi gửi');
        assert.equal(reloaded.element('od-submitspan').textContent, 'Kiểm tra đơn đã gửi');
        await reloaded.submit();
        assert.equal(requests.length, 2);
        assert.equal(storage.has(requestKey), false);
        const activeKey = mode === 'takeaway' ? `eapp_takeaway_order::${contextKey}` : `eapp_qr_active_order::${contextKey}`;
        assert.ok(storage.get(activeKey).includes('17'));
        assert.equal(reloaded.element('od-order-note').disabled, false);
    });
}
