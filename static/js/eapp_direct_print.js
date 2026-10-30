/*
 * In thẳng tới máy in nhiệt ESC/POS, không qua hộp thoại in của trình duyệt.
 *   - USB: WebUSB (Chrome/Edge máy tính, Android). Windows cần driver WinUSB cho máy in.
 *   - Bluetooth: Web Serial. Máy in Bluetooth thường (SPP) hiện ra như một cổng serial/COM.
 *   - Bluetooth LE: Web Bluetooth. Chrome chỉ nhớ máy đã chọn qua lần tải trang khi có
 *     navigator.bluetooth.getDevices() (cờ chrome://flags/#enable-web-bluetooth-new-permissions-backend).
 * Trình duyệt chỉ cho chọn thiết bị qua hộp thoại của nó (cần bấm nút), nên "dò" = mở hộp thoại chọn.
 * Chữ được vẽ / chụp thành ảnh rồi gửi (GS v 0) để in được tiếng Việt có dấu trên mọi máy.
 *
 * Mỗi thiết bị chọn máy in theo vai trò: 'receipt' (hoá đơn, tạm tính, in thử) và 'kitchen' (phiếu bếp).
 * Chưa chọn máy in phiếu bếp thì dùng chung máy in hoá đơn.
 *
 *   eappDirectPrint.support()                 -> { usb, serial, ble }
 *   await eappDirectPrint.scan(kind, role)    kind: 'usb' | 'serial' | 'ble'
 *   eappDirectPrint.current(role)             -> { kind, name, kindLabel, inherited } | null
 *   await eappDirectPrint.printUrl(url, role) -> chụp trang in của app (html2canvas) rồi gửi; eapp_print.js tự gọi
 *   await eappDirectPrint.printSample({ role, paper, storeName })
 *   await eappDirectPrint.forget(role)
 *   await eappDirectPrint.status(role)        -> { state: 'none' | 'live' | 'ready' | 'lost' | 'error', text }
 *   await eappDirectPrint.connect(role)       kết nối sẵn (không in); eappDirectPrint.rename(role, name)
 *   eappDirectPrint.bindPicker(element, { storeName })  gắn khối chọn máy in (print/_direct_printer_picker.html)
 *   eappDirectPrint.bindIndicator(button, roles)        đèn trạng thái máy in trên nút mở Thiết lập
 */
(() => {
    if (window.eappDirectPrint) return;

    const STORAGE_PREFIX = 'eapp_direct_printer_';
    const LEGACY_STORAGE_KEY = 'eapp_direct_printer'; // bản đầu chỉ có một máy in = máy in hoá đơn
    const PAPER_STORAGE_KEY = 'eapp_print_paper';
    const ROLES = ['receipt', 'kitchen'];
    const CHANGE_EVENT = 'eapp-direct-printer-change';
    const DOTS = { 58: 384, 80: 576 };
    const STRIP_ROWS = 24;
    // Máy in BLE phổ biến (Xprinter, Goojprt, Phomemo, ISSC...): Web Bluetooth chỉ cho đọc service khai báo trước.
    const BLE_SERVICES = [
        '000018f0-0000-1000-8000-00805f9b34fb',
        'e7810a71-73ae-499d-8c15-faa9aef0c3f2',
        '49535343-fe7d-4ae5-8fa9-9fafd205e455',
        '0000ff00-0000-1000-8000-00805f9b34fb',
        '0000ffe0-0000-1000-8000-00805f9b34fb',
        '0000fee7-0000-1000-8000-00805f9b34fb',
    ];
    const SPP_SERVICE = '00001101-0000-1000-8000-00805f9b34fb';
    const KIND_LABEL = { usb: 'USB', serial: 'Bluetooth / cổng COM', ble: 'Bluetooth LE' };
    const BLE_FLAG = 'chrome://flags/#enable-web-bluetooth-new-permissions-backend';

    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

    // --- Lưu lựa chọn theo vai trò --------------------------------------------------------------

    const readRole = (role) => {
        try {
            const raw = window.localStorage.getItem(STORAGE_PREFIX + role)
                || (role === 'receipt' ? window.localStorage.getItem(LEGACY_STORAGE_KEY) : null);
            return JSON.parse(raw || 'null');
        } catch (error) { return null; }
    };
    const writeRole = (role, value) => {
        try {
            if (value) window.localStorage.setItem(STORAGE_PREFIX + role, JSON.stringify(value));
            else window.localStorage.removeItem(STORAGE_PREFIX + role);
            if (role === 'receipt') window.localStorage.removeItem(LEGACY_STORAGE_KEY);
        } catch (error) { /* bỏ qua */ }
        window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: { role } }));
    };
    // Máy in dùng cho vai trò: của chính nó, hoặc máy in hoá đơn khi phiếu bếp chưa chọn riêng.
    const resolveSaved = (role) => {
        const own = readRole(role);
        if (own) return { saved: own, inherited: false };
        if (role !== 'receipt') {
            const shared = readRole('receipt');
            if (shared) return { saved: shared, inherited: true };
        }
        return null;
    };
    const savedId = (saved) => `${saved.kind}:${JSON.stringify(saved.key || {})}`;

    const support = () => ({
        usb: Boolean(navigator.usb),
        serial: Boolean(navigator.serial),
        ble: Boolean(navigator.bluetooth),
    });
    const bleRemembered = () => Boolean(navigator.bluetooth && navigator.bluetooth.getDevices);

    const hex4 = (n) => (n || 0).toString(16).padStart(4, '0');
    const deviceName = (kind, device) => {
        if (kind === 'usb') return device.productName || `USB ${hex4(device.vendorId)}:${hex4(device.productId)}`;
        if (kind === 'ble') return device.name || 'Máy in Bluetooth LE';
        const info = device.getInfo ? device.getInfo() : {};
        if (info.usbVendorId) return `Cổng COM USB ${hex4(info.usbVendorId)}:${hex4(info.usbProductId)}`;
        return 'Máy in Bluetooth';
    };
    const deviceKey = (kind, device) => {
        if (kind === 'usb') return { vendorId: device.vendorId, productId: device.productId, serialNumber: device.serialNumber || '' };
        if (kind === 'ble') return { id: device.id };
        const info = device.getInfo ? device.getInfo() : {};
        return { usbVendorId: info.usbVendorId || 0, usbProductId: info.usbProductId || 0 };
    };

    // --- Mở kết nối và trả về hàm ghi bytes ---------------------------------------------------

    const openUsb = async (device) => {
        if (!device.opened) await device.open();
        if (!device.configuration) await device.selectConfiguration(1);
        let pick = null;
        device.configuration.interfaces.forEach((iface) => {
            iface.alternates.forEach((alt) => {
                const out = alt.endpoints.find((ep) => ep.direction === 'out' && ep.type === 'bulk');
                // Ưu tiên interface lớp máy in (7); nhiều máy in nhiệt khai báo lớp riêng của hãng (255).
                if (out && (!pick || (alt.interfaceClass === 7 && pick.cls !== 7))) {
                    pick = { iface, alt: alt.alternateSetting, endpoint: out.endpointNumber, cls: alt.interfaceClass };
                }
            });
        });
        if (!pick) throw new Error('Thiết bị USB này không có cổng gửi dữ liệu in.');
        if (!pick.iface.claimed) {
            try {
                await device.claimInterface(pick.iface.interfaceNumber);
            } catch (error) {
                throw new Error('Máy in USB đang bị hệ điều hành giữ (Windows cần driver WinUSB). Dùng In thử qua hộp thoại thay thế.');
            }
        }
        if (pick.alt) await device.selectAlternateInterface(pick.iface.interfaceNumber, pick.alt);
        return {
            write: async (bytes) => { await device.transferOut(pick.endpoint, bytes); },
            throttleMs: 0,
        };
    };

    // Giữ cổng serial và writer mở suốt phiên: máy in Bluetooth SPP (VD MPT-II) hay không nhận dữ liệu
    // khi kết nối lại sau lần in đầu, và writer cũ chưa nhả khoá làm lần in sau báo "WritableStream is locked".
    const serialWriters = new Map(); // port -> writer

    const dropSerial = async (port) => {
        const writer = serialWriters.get(port);
        if (!writer) return;
        serialWriters.delete(port);
        try { writer.releaseLock(); } catch (error) { /* bỏ qua */ }
        try { await port.close(); } catch (error) { /* bỏ qua */ }
    };

    const openSerial = async (port) => {
        if (!serialWriters.has(port)) {
            if (!port.writable) {
                try {
                    await port.open({ baudRate: 9600 });
                } catch (error) {
                    throw new Error('Không mở được cổng máy in. Kiểm tra máy in đã bật, đang ở gần và không kết nối với thiết bị khác.');
                }
            }
            if (port.writable.locked) throw new Error('Cổng máy in đang bận (có thể ở tab khác). Tải lại trang rồi thử lại.');
            serialWriters.set(port, port.writable.getWriter());
        }
        const writer = serialWriters.get(port);
        return {
            write: async (bytes) => {
                try {
                    await writer.ready;
                    await writer.write(bytes);
                } catch (error) {
                    await dropSerial(port); // lần in sau mở lại cổng từ đầu
                    throw new Error('Mất kết nối với máy in. In lại; nếu vẫn lỗi, bấm Dò Bluetooth để chọn lại máy in.');
                }
            },
            throttleMs: 40,
        };
    };

    if (navigator.serial) {
        navigator.serial.addEventListener('disconnect', async (event) => {
            await dropSerial(event.target);
            window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: {} }));
        });
    }

    // Máy in BLE đã cho phép từ lần trước (getDevices) có thể chưa được hệ điều hành "thấy" lại:
    // nghe quảng bá vài giây rồi mới kết nối.
    const waitForAdvertisement = (device, ms) => new Promise((resolve) => {
        if (!device.watchAdvertisements) { resolve(); return; }
        const abort = new AbortController();
        const done = () => { clearTimeout(timer); abort.abort(); resolve(); };
        const timer = setTimeout(done, ms);
        device.addEventListener('advertisementreceived', done, { once: true });
        device.watchAdvertisements({ signal: abort.signal }).catch(done);
    });

    const bleChannels = new WeakMap(); // device -> characteristic
    const bleWatched = new WeakSet();

    const connectBle = async (device) => {
        if (!bleWatched.has(device)) {
            bleWatched.add(device);
            // Máy in tắt / ngủ / ra khỏi tầm: đèn chuyển từ "Đang kết nối" sang "Đã lưu"; lần in sau tự kết nối lại.
            device.addEventListener('gattserverdisconnected', () => {
                bleChannels.delete(device);
                window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: {} }));
            });
        }
        if (device.gatt.connected) return;
        bleChannels.delete(device);
        try {
            await device.gatt.connect();
        } catch (error) {
            await waitForAdvertisement(device, 8000);
            try {
                await device.gatt.connect();
            } catch (retryError) {
                throw new Error('Không kết nối được máy in Bluetooth LE. Kiểm tra máy in đã bật, ở gần và không kết nối với thiết bị khác.');
            }
        }
    };

    const openBle = async (device) => {
        await connectBle(device);
        let characteristic = bleChannels.get(device);
        if (!characteristic) {
            const services = await device.gatt.getPrimaryServices();
            for (const service of services) {
                const chars = await service.getCharacteristics();
                characteristic = chars.find((c) => c.properties.writeWithoutResponse || c.properties.write);
                if (characteristic) break;
            }
            if (!characteristic) throw new Error('Không tìm thấy kênh in trên thiết bị Bluetooth LE này.');
            bleChannels.set(device, characteristic);
        }
        let chunkSize = 180;
        const send = (part) => (characteristic.properties.writeWithoutResponse
            ? characteristic.writeValueWithoutResponse(part)
            : characteristic.writeValueWithResponse(part));
        return {
            write: async (bytes) => {
                for (let i = 0; i < bytes.length;) {
                    const part = bytes.slice(i, i + chunkSize);
                    try {
                        await send(part);
                    } catch (error) {
                        // MTU nhỏ: lùi về gói 20 byte (mức tối thiểu của BLE).
                        if (chunkSize === 20) throw error;
                        chunkSize = 20;
                        continue;
                    }
                    i += part.length;
                    if (characteristic.properties.writeWithoutResponse) await sleep(8);
                }
            },
            throttleMs: 20,
        };
    };

    const OPENERS = { usb: openUsb, serial: openSerial, ble: openBle };

    // --- Trạng thái máy in: đèn trong khối chọn máy in và trên nút mở Thiết lập ------------------

    const STATUS = {
        none: 'Chưa chọn',
        live: 'Đang kết nối',
        ready: 'Đã lưu, chưa kết nối',
        lost: 'Cần dò lại',
        error: 'Lần in gần nhất bị lỗi',
    };
    const STATUS_ORDER = ['error', 'lost', 'ready', 'live']; // xấu nhất trước, dùng cho đèn gộp nhiều vai trò
    const lastErrors = new Map(); // savedId -> thông báo lỗi lần in / kết nối gần nhất
    const emitChange = () => window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: {} }));
    const isConnected = (kind, device) => {
        if (kind === 'serial') return serialWriters.has(device);
        if (kind === 'ble') return Boolean(device.gatt && device.gatt.connected);
        if (kind === 'usb') return Boolean(device.opened);
        return false;
    };

    const STYLE = `
        .dp-badge { display: inline-flex; align-items: center; gap: .35rem; font-size: .72rem; font-weight: 700;
            border-radius: 999px; padding: .12rem .55rem; vertical-align: middle; white-space: nowrap; }
        .dp-badge::before { content: ''; width: .5rem; height: .5rem; border-radius: 50%; background: currentColor; }
        .dp-badge.dp-none { color: #64748b; background: #f1f5f9; }
        .dp-badge.dp-ready { color: #15803d; background: #f0fdf4; }
        .dp-badge.dp-live { color: #15803d; background: #dcfce7; }
        .dp-badge.dp-lost { color: #b45309; background: #fef3c7; }
        .dp-badge.dp-error { color: #b91c1c; background: #fee2e2; }
        .dp-badge.dp-live::before, .dp-dot.dp-live { animation: dp-pulse 1.6s ease-out infinite; }
        .dp-indicator { position: relative; }
        .dp-dot { position: absolute; top: 3px; right: 3px; width: .62rem; height: .62rem; border-radius: 50%;
            border: 2px solid #fff; pointer-events: none; }
        .dp-dot.dp-live, .dp-dot.dp-ready { background: #22c55e; }
        .dp-dot.dp-lost { background: #f59e0b; }
        .dp-dot.dp-error { background: #ef4444; }
        @keyframes dp-pulse {
            0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, .55); }
            70% { box-shadow: 0 0 0 .45rem rgba(34, 197, 94, 0); }
            100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
        }
    `;
    let styleInjected = false;
    const injectStyle = () => {
        if (styleInjected) return;
        styleInjected = true;
        const el = document.createElement('style');
        el.textContent = STYLE;
        document.head.appendChild(el);
    };

    if (navigator.usb) {
        navigator.usb.addEventListener('connect', emitChange);
        navigator.usb.addEventListener('disconnect', emitChange);
    }

    // --- Chọn / khôi phục thiết bị -------------------------------------------------------------

    const devices = new Map(); // savedId -> device (thiết bị đã có trong phiên này)

    const scan = async (kind, role = 'receipt') => {
        let device;
        if (kind === 'usb') {
            device = await navigator.usb.requestDevice({ filters: [] });
        } else if (kind === 'serial') {
            // allowedBluetoothServiceClassIds: Chrome 117+ liệt kê cả máy in Bluetooth SPP chưa có cổng COM.
            device = await navigator.serial.requestPort({ allowedBluetoothServiceClassIds: [SPP_SERVICE] });
        } else if (kind === 'ble') {
            device = await navigator.bluetooth.requestDevice({ acceptAllDevices: true, optionalServices: BLE_SERVICES });
        } else {
            throw new Error('Kiểu kết nối không hợp lệ.');
        }
        const saved = { kind, name: deviceName(kind, device), key: deviceKey(kind, device) };
        devices.set(savedId(saved), device);
        writeRole(role, saved);
        return saved;
    };

    const matches = (key, candidate) => Object.keys(key).every((k) => !key[k] || candidate[k] === key[k]);

    const findDevice = async (saved) => {
        const id = savedId(saved);
        if (devices.has(id)) return devices.get(id);
        let list = [];
        if (saved.kind === 'usb' && navigator.usb) list = await navigator.usb.getDevices();
        else if (saved.kind === 'serial' && navigator.serial) list = await navigator.serial.getPorts();
        else if (saved.kind === 'ble' && bleRemembered()) list = await navigator.bluetooth.getDevices();
        const key = saved.key || {};
        const device = list.find((item) => matches(key, saved.kind === 'serial' ? (item.getInfo ? item.getInfo() : {}) : item));
        if (device) devices.set(id, device);
        return device || null;
    };

    // Trả về { kind, device, id } hoặc null khi chưa chọn / trình duyệt không còn nhớ thiết bị.
    const restore = async (role = 'receipt') => {
        const resolved = resolveSaved(role);
        if (!resolved) return null;
        const device = await findDevice(resolved.saved);
        return device ? { kind: resolved.saved.kind, device, id: savedId(resolved.saved) } : null;
    };

    const status = async (role = 'receipt') => {
        const resolved = resolveSaved(role);
        if (!resolved) return { state: 'none', text: STATUS.none };
        const device = await findDevice(resolved.saved).catch(() => null);
        if (!device) return { state: 'lost', text: STATUS.lost };
        const id = savedId(resolved.saved);
        if (lastErrors.has(id)) return { state: 'error', text: STATUS.error, detail: lastErrors.get(id) };
        const state = isConnected(resolved.saved.kind, device) ? 'live' : 'ready';
        return { state, text: STATUS[state] };
    };

    // Ghi nhận kết quả lần in / kết nối để đèn trạng thái đổi màu.
    const track = async (active, work) => {
        try {
            const result = await work();
            lastErrors.delete(active.id);
            return result;
        } catch (error) {
            lastErrors.set(active.id, (error && error.message) || 'Không in được.');
            throw error;
        } finally {
            emitChange();
        }
    };

    let jobs = Promise.resolve();
    // Xếp hàng mọi thao tác ghi: hoá đơn và phiếu bếp in liền nhau, hay hai khối chọn máy in cùng kết nối sẵn
    // một máy, không được mở / ghi xen vào cùng một kết nối.
    const enqueue = (work) => {
        const job = jobs.then(work);
        jobs = job.catch(() => null);
        return job;
    };

    // Kết nối sẵn (không in) để lần in đầu nhanh hơn và đèn hiện "Đang kết nối".
    const connect = async (role = 'receipt') => {
        const active = await requireDevice(role);
        return enqueue(() => track(active, () => OPENERS[active.kind](active.device)));
    };

    const rename = (role, name) => {
        const own = readRole(role);
        if (!own) return;
        own.name = String(name || '').trim().slice(0, 40) || own.name;
        writeRole(role, own);
    };

    const current = (role = 'receipt') => {
        const resolved = resolveSaved(role);
        if (!resolved) return null;
        const { saved, inherited } = resolved;
        return { kind: saved.kind, name: saved.name, kindLabel: KIND_LABEL[saved.kind] || saved.kind, inherited };
    };

    const forget = async (role = 'receipt') => {
        const own = readRole(role);
        writeRole(role, null);
        if (!own) return;
        const id = savedId(own);
        lastErrors.delete(id);
        // Vai trò khác vẫn dùng máy này (VD máy in bếp = máy in hoá đơn) thì giữ kết nối và quyền truy cập.
        if (ROLES.some((other) => other !== role && readRole(other) && savedId(readRole(other)) === id)) return;
        const device = devices.get(id);
        devices.delete(id);
        if (!device) return;
        try {
            if (own.kind === 'serial') await dropSerial(device);
            if (own.kind === 'ble' && device.gatt.connected) device.gatt.disconnect();
            if (device.forget) await device.forget();
        } catch (error) { /* bỏ qua */ }
    };

    const requireDevice = async (role) => {
        const active = await restore(role);
        if (active) return active;
        const resolved = resolveSaved(role);
        let message = 'Chưa chọn máy in hoặc trình duyệt đã quên quyền truy cập. Bấm Dò máy in để chọn lại.';
        if (resolved && resolved.saved.kind === 'ble') {
            message = bleRemembered()
                ? 'Không tìm thấy máy in Bluetooth LE đã chọn. Bấm Dò Bluetooth LE để chọn lại.'
                : 'Máy in Bluetooth LE cần được chọn lại sau khi tải trang (bấm Dò Bluetooth LE).';
        }
        const error = new Error(message);
        error.code = 'NO_DEVICE';
        throw error;
    };

    // --- Dựng ảnh và lệnh ESC/POS ---------------------------------------------------------------

    const readPaper = () => {
        try { return window.localStorage.getItem(PAPER_STORAGE_KEY) === '58' ? '58' : '80'; } catch (error) { return '80'; }
    };
    const formatMoney = (value) => `${Math.round(value).toLocaleString('vi-VN')} đ`;

    const renderSample = ({ paper, storeName, title }) => {
        const width = DOTS[paper] || DOTS[80];
        const scale = width / 384;
        const pad = Math.round(6 * scale);
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = Math.round(900 * scale);
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#fff';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#000';
        ctx.textBaseline = 'top';
        let y = pad;
        const font = (size, bold) => { ctx.font = `${bold ? '700 ' : ''}${Math.round(size * scale)}px Arial, Helvetica, sans-serif`; return Math.round(size * scale); };
        const text = (value, align) => {
            const w = ctx.measureText(value).width;
            const x = align === 'center' ? (width - w) / 2 : (align === 'right' ? width - pad - w : pad);
            ctx.fillText(value, x, y);
        };
        const line = (value, size, bold, align, gap = 4) => { const h = font(size, bold); text(value, align); y += h + gap; };
        const row = (left, right, size, bold, gap = 4) => { const h = font(size, bold); text(left, 'left'); text(right, 'right'); y += h + gap; };
        const sep = (dashed = true) => {
            y += 3;
            ctx.fillRect(pad, y, width - 2 * pad, dashed ? 0 : 2);
            if (dashed) for (let x = pad; x < width - pad; x += 8) ctx.fillRect(x, y, 4, 1);
            y += 8;
        };

        line(String(storeName || 'eApp FnB').toUpperCase(), 26, true, 'center', 6);
        sep();
        line(title || 'PHIẾU IN MẪU', 24, true, 'center', 2);
        line('Không phải hoá đơn', 17, false, 'center', 6);
        row('Giờ in:', new Date().toLocaleString('vi-VN', { hour12: false }), 17, false);
        sep();
        let total = 0;
        [['Cà phê sữa đá', 2, 29000], ['Trà đào cam sả', 1, 45000], ['Bánh mì ốp la', 1, 35000]].forEach(([name, qty, price]) => {
            total += qty * price;
            line(name, 20, true, 'left', 2);
            row(`  ${qty} x ${price.toLocaleString('vi-VN')}`, (qty * price).toLocaleString('vi-VN'), 20, false);
        });
        sep(false);
        row('TỔNG CỘNG', formatMoney(total), 24, true, 6);
        sep();
        line('Tiếng Việt: ăâđêôơư ỨỪỬỮỰ', 18, false, 'center', 2);
        row('|< Trái', 'Phải >|', 18, false, 2);
        line('Xin cảm ơn quý khách!', 20, true, 'center', 2);
        y += pad;

        return ctx.getImageData(0, 0, width, Math.min(y, canvas.height));
    };

    // Ảnh -> các lệnh GS v 0, mỗi lệnh một dải STRIP_ROWS dòng để máy in bộ đệm nhỏ không bị tràn.
    const rasterStrips = (image) => {
        const { width, height, data } = image;
        const bytesPerRow = Math.ceil(width / 8);
        const strips = [];
        for (let top = 0; top < height; top += STRIP_ROWS) {
            const rows = Math.min(STRIP_ROWS, height - top);
            const out = new Uint8Array(8 + bytesPerRow * rows);
            out.set([0x1d, 0x76, 0x30, 0x00, bytesPerRow & 0xff, bytesPerRow >> 8, rows & 0xff, rows >> 8]);
            for (let r = 0; r < rows; r += 1) {
                for (let x = 0; x < width; x += 1) {
                    const i = ((top + r) * width + x) * 4;
                    const lum = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
                    if (lum < 160) out[8 + r * bytesPerRow + (x >> 3)] |= 0x80 >> (x & 7);
                }
            }
            strips.push(out);
        }
        return strips;
    };

    const ascii = (value) => new TextEncoder().encode(value);

    const sendImage = (active, image, header) => enqueue(() => track(active, async () => {
        const conn = await OPENERS[active.kind](active.device);
        await conn.write(new Uint8Array([0x1b, 0x40])); // ESC @: khởi tạo lại máy in
        if (header) await conn.write(ascii(header));
        for (const strip of rasterStrips(image)) {
            await conn.write(strip);
            if (conn.throttleMs) await sleep(conn.throttleMs);
        }
        await conn.write(new Uint8Array([0x0a, 0x0a, 0x0a, 0x0a, 0x1d, 0x56, 0x42, 0x00])); // đẩy giấy + cắt (máy không có dao cắt sẽ bỏ qua)
    }));

    const printSample = async ({ role = 'receipt', paper, storeName } = {}) => {
        const active = await requireDevice(role);
        const title = role === 'kitchen' ? 'IN MẪU MÁY BẾP' : 'PHIẾU IN MẪU';
        // Dòng chữ thường in trước ảnh: ra được dòng này mà không ra ảnh là máy in không hỗ trợ in ảnh GS v 0.
        await sendImage(active, renderSample({ paper: paper || readPaper(), storeName, title }), 'eApp FnB - in mau nhanh\n');
    };

    // --- In trang in của app (hoá đơn, tạm tính, phiếu bếp) -----------------------------------

    const HTML2CANVAS_SRC = 'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js';
    const HTML2CANVAS_SRI = 'sha384-ZZ1pncU3bQe8y31yfZdMFdSpttDoPmOZg2wguVK9almUodir1PghgT0eY7Mrty8H';
    let html2canvasLoading = null;
    const loadHtml2canvas = () => {
        if (window.html2canvas) return Promise.resolve(window.html2canvas);
        html2canvasLoading = html2canvasLoading || new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = HTML2CANVAS_SRC;
            script.integrity = HTML2CANVAS_SRI;
            script.crossOrigin = 'anonymous';
            script.onload = () => resolve(window.html2canvas);
            script.onerror = () => {
                html2canvasLoading = null;
                script.remove();
                reject(new Error('Không tải được thư viện dựng phiếu in. Kiểm tra kết nối mạng.'));
            };
            document.head.appendChild(script);
        });
        return html2canvasLoading;
    };

    // Tải trang in với autoprint=1 (máy chủ đếm lần in như in qua hộp thoại) và direct=1 (trang không gọi window.print()).
    const loadPrintFrame = (url) => new Promise((resolve, reject) => {
        const target = new URL(url, window.location.origin);
        target.searchParams.set('autoprint', '1');
        target.searchParams.set('direct', '1');
        const frame = document.createElement('iframe');
        frame.setAttribute('aria-hidden', 'true');
        frame.tabIndex = -1;
        frame.style.cssText = 'position:fixed;left:-10000px;top:0;width:640px;height:2400px;border:0;';
        const timer = setTimeout(() => {
            frame.remove();
            reject(new Error('Tải phiếu in quá lâu.'));
        }, 20000);
        frame.addEventListener('load', () => {
            clearTimeout(timer);
            resolve(frame);
        }, { once: true });
        frame.src = target.pathname + target.search;
        document.body.appendChild(frame);
    });

    // Trả về true khi đã in, false khi máy khác đã in trước (trang "skipped", không có .paper).
    const printUrl = async (url, role = 'receipt') => {
        const active = await requireDevice(role);
        const h2c = await loadHtml2canvas();
        const frame = await loadPrintFrame(url);
        try {
            const doc = frame.contentDocument;
            if (doc && doc.querySelector('[data-print-skipped]')) return false;
            const paper = doc && doc.querySelector('.paper');
            // Trang lỗi (403/500, mất mạng): báo lỗi thay vì im lặng như phiếu đã in ở máy khác.
            if (!paper) throw new Error('Không tải được phiếu in. Kiểm tra kết nối mạng rồi in lại.');
            const dots = DOTS[doc.body.classList.contains('paper-58') ? 58 : 80];
            const shot = await h2c(paper, {
                backgroundColor: '#ffffff',
                scale: dots / paper.getBoundingClientRect().width,
                logging: false,
            });
            const canvas = document.createElement('canvas');
            canvas.width = dots;
            canvas.height = Math.round((shot.height * dots) / shot.width);
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#fff';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(shot, 0, 0, canvas.width, canvas.height);
            await sendImage(active, ctx.getImageData(0, 0, canvas.width, canvas.height));
            return true;
        } finally {
            frame.remove();
        }
    };

    // --- Khối chọn máy in (templates/App_Sales/print/_direct_printer_picker.html) ---------------

    const bindPicker = (root, { storeName = () => '' } = {}) => {
        injectStyle();
        const role = root.dataset.directPrinter;
        const statusEl = root.querySelector('[data-dp-status]');
        const badge = root.querySelector('[data-dp-badge]');
        const hint = root.querySelector('[data-dp-hint]');
        const message = root.querySelector('[data-dp-message]');
        const sampleBtn = root.querySelector('[data-dp-sample]');
        const forgetBtn = root.querySelector('[data-dp-forget]');
        const renameBtn = root.querySelector('[data-dp-rename]');
        const connectBtn = root.querySelector('[data-dp-connect]');
        const scanButtons = root.querySelectorAll('[data-dp-scan]');
        const supported = support();

        const say = (text, tone) => {
            message.textContent = text || '';
            message.className = `small mt-2 ${tone === 'danger' ? 'text-danger' : 'text-success'}`;
            message.hidden = !text;
        };
        const errorText = (error) => {
            if (error && error.name === 'NotFoundError') return ''; // người dùng đóng hộp thoại chọn
            if (error && error.name === 'SecurityError') return 'Trình duyệt chặn truy cập thiết bị trên trang này.';
            return (error && error.message) || 'Không kết nối được máy in.';
        };

        scanButtons.forEach((button) => { button.hidden = !supported[button.dataset.dpScan]; });
        if (!supported.usb && !supported.serial && !supported.ble) {
            statusEl.textContent = 'Trình duyệt này không kết nối trực tiếp được với máy in. Dùng Chrome hoặc Edge trên máy tính / Android, hoặc in qua hộp thoại.';
            sampleBtn.hidden = true;
            badge.hidden = true;
            return;
        }

        let renderSeq = 0;
        const render = async () => {
            const seq = ++renderSeq;
            const printer = current(role);
            const state = await status(role);
            if (seq !== renderSeq) return;
            badge.className = `dp-badge dp-${state.state}`;
            badge.textContent = state.text;
            badge.title = state.detail || '';
            forgetBtn.classList.toggle('d-none', !printer || printer.inherited);
            renameBtn.classList.toggle('d-none', !printer || printer.inherited);
            connectBtn.classList.toggle('d-none', !['ready', 'error'].includes(state.state));
            sampleBtn.disabled = !printer;
            hint.hidden = true;
            if (!printer) {
                statusEl.textContent = 'Chưa chọn máy in: in qua hộp thoại của trình duyệt.';
                return;
            }
            const label = `${printer.name} (${printer.kindLabel})`;
            statusEl.textContent = printer.inherited ? `Dùng chung máy in hoá đơn: ${label}` : label;
            if (state.state === 'lost' && printer.kind === 'ble' && !bleRemembered()) {
                hint.textContent = `Chrome chưa nhớ máy in Bluetooth LE qua lần tải trang. Để nhớ: mở ${BLE_FLAG}, chọn Enabled, khởi động lại Chrome rồi Dò Bluetooth LE một lần.`;
                hint.hidden = false;
            }
        };
        const tryConnect = async (quiet) => {
            try {
                await connect(role);
                if (!quiet) say('Đã kết nối máy in.');
            } catch (error) {
                if (!quiet) say(errorText(error), 'danger');
            }
        };

        scanButtons.forEach((button) => {
            button.addEventListener('click', async () => {
                try {
                    const printer = await scan(button.dataset.dpScan, role);
                    say(`Đã chọn ${printer.name}.`);
                } catch (error) {
                    say(errorText(error), 'danger');
                }
            });
        });
        sampleBtn.addEventListener('click', async () => {
            sampleBtn.disabled = true;
            say('Đang gửi phiếu mẫu…');
            try {
                await printSample({ role, storeName: storeName() });
                say('Đã gửi phiếu mẫu tới máy in.');
            } catch (error) {
                say(errorText(error), 'danger');
            } finally {
                render();
            }
        });
        forgetBtn.addEventListener('click', async () => {
            await forget(role);
            say('');
        });
        connectBtn.addEventListener('click', () => tryConnect(false));
        // Đặt tên ngay trong khối (không mở hộp thoại chồng lên modal Thiết lập: Bootstrap trả focus về nút
        // đóng của modal bên dưới, Enter khi đó đóng luôn Thiết lập).
        const renameForm = root.querySelector('[data-dp-rename-form]');
        const renameInput = root.querySelector('[data-dp-rename-input]');
        const toggleRename = (open) => {
            renameForm.classList.toggle('d-none', !open);
            statusEl.classList.toggle('d-none', open);
            if (open) {
                renameInput.value = (current(role) || {}).name || '';
                renameInput.focus();
                renameInput.select();
            }
        };
        renameBtn.addEventListener('click', () => toggleRename(renameForm.classList.contains('d-none')));
        root.querySelector('[data-dp-rename-cancel]').addEventListener('click', () => toggleRename(false));
        renameInput.addEventListener('keydown', (event) => {
            if (event.key !== 'Escape') return;
            event.stopPropagation(); // Esc chỉ huỷ đặt tên, không đóng modal Thiết lập
            toggleRename(false);
        });
        renameForm.addEventListener('submit', (event) => {
            event.preventDefault();
            if (renameInput.value.trim()) rename(role, renameInput.value);
            toggleRename(false);
        });
        window.addEventListener(CHANGE_EVENT, render);
        render().then(async () => {
            // Máy in đã lưu và trình duyệt còn nhớ: kết nối sẵn để đèn sáng "Đang kết nối" và lần in đầu nhanh hơn.
            if ((await status(role)).state === 'ready') tryConnect(true);
        });
    };

    // Đèn nhỏ trên nút mở Thiết lập: xanh nhấp nháy = đang kết nối, xanh = đã lưu, vàng = cần dò lại, đỏ = lỗi in.
    const bindIndicator = (el, roles = ROLES) => {
        injectStyle();
        el.classList.add('dp-indicator');
        const baseTitle = el.getAttribute('title') || '';
        const dot = document.createElement('span');
        dot.className = 'dp-dot';
        dot.hidden = true;
        dot.setAttribute('aria-hidden', 'true');
        el.appendChild(dot);
        const update = async () => {
            const states = (await Promise.all(roles.map((role) => status(role)))).filter((s) => s.state !== 'none');
            if (!states.length) {
                dot.hidden = true;
                el.setAttribute('title', baseTitle);
                return;
            }
            const worst = states.reduce((a, b) => (STATUS_ORDER.indexOf(b.state) < STATUS_ORDER.indexOf(a.state) ? b : a));
            dot.className = `dp-dot dp-${worst.state}`;
            dot.hidden = false;
            el.setAttribute('title', `${baseTitle} · Máy in: ${worst.text}`);
        };
        window.addEventListener(CHANGE_EVENT, update);
        update();
    };

    window.eappDirectPrint = {
        support, scan, current, status, connect, rename, forget, restore, printSample, printUrl, bindPicker, bindIndicator,
    };
})();
