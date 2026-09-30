const assert = require('node:assert/strict');
const { test } = require('node:test');
const { webcrypto } = require('node:crypto');
const { createTracker } = require('../../static/js/public_order_request.js');

function storage() {
    const values = new Map();
    return { get: (key) => values.get(key) || null, set: (key, value) => values.set(key, value), remove: (key) => values.delete(key) };
}
const payload = () => ({ note: 'Ít đá', items: [{ product_id: 1, unit_id: 2, quantity: 2 }] });
const cart = () => [{ product_id: 1, quantity: 2, name: 'Trà đào' }];

test('lost response and page reload reuse the original key, payload and cart', () => {
    const db = storage();
    const tracker = createTracker(db, 'table-1', webcrypto);
    const body = payload();
    const rows = cart();
    const original = tracker.begin(body, rows);
    body.note = 'Changed after sending';
    rows[0].quantity = 99;
    tracker.rejected(0);
    tracker.rejected(500);
    const reloaded = createTracker(db, 'table-1', webcrypto);
    assert.deepEqual(reloaded.begin(body, rows), original);
    assert.equal(reloaded.current().payload.note, 'Ít đá');
    assert.equal(reloaded.current().cart[0].quantity, 2);
    assert.match(original.payload.client_request_id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});

test('success allows an intentional new order with identical contents', () => {
    const tracker = createTracker(storage(), 'table-1', webcrypto);
    const first = tracker.begin(payload(), cart());
    tracker.clear();
    const next = tracker.begin(payload(), cart());
    assert.notEqual(first.payload.client_request_id, next.payload.client_request_id);
});

test('known validation failure releases the attempt; conflict retains it', () => {
    const tracker = createTracker(storage(), 'table-1', webcrypto);
    const first = tracker.begin(payload(), cart());
    tracker.rejected(409);
    assert.equal(tracker.current().payload.client_request_id, first.payload.client_request_id);
    tracker.rejected(400);
    assert.equal(tracker.current(), null);
    assert.notEqual(tracker.begin(payload(), cart()).payload.client_request_id, first.payload.client_request_id);
});

test('storage failure prevents sending and recovery retains the same key', () => {
    const db = storage();
    const set = db.set;
    db.set = () => {};
    const tracker = createTracker(db, 'table-1', webcrypto);
    assert.throws(() => tracker.begin(payload(), cart()), /Không lưu được/);
    const id = tracker.current().payload.client_request_id;
    db.set = set;
    assert.equal(tracker.begin(payload(), cart()).payload.client_request_id, id);
});

test('contexts are isolated and browsers without randomUUID use cryptographic UUID v4', () => {
    const db = storage();
    const crypto = { getRandomValues: (bytes) => webcrypto.getRandomValues(bytes) };
    const first = createTracker(db, 'table-1', crypto).begin(payload(), cart());
    assert.equal(createTracker(db, 'takeaway-store-1', crypto).current(), null);
    const second = createTracker(db, 'table-2', crypto).begin(payload(), cart());
    assert.notEqual(first.payload.client_request_id, second.payload.client_request_id);
    assert.match(first.payload.client_request_id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});
