/* Remote datalist UI shared by checkout customer and promotion pickers. */
(function () {
    'use strict';
    let sequence = 0;
    let opened = null;
    function create({ input, toggle, load, select, apply, onInput, emptyText = 'Không có kết quả phù hợp.' }) {
        if (!input) return null;
        const menu = document.createElement('div');
        menu.id = 'checkout-options-' + (++sequence);
        menu.className = 'eapp-dropdown-menu checkout-combobox-popup';
        menu.setAttribute('role', 'listbox');
        menu.setAttribute('aria-label', input.getAttribute('aria-label') || input.placeholder);
        menu.hidden = true;
        if (typeof menu.showPopover === 'function') menu.setAttribute('popover', 'manual');
        // Preserve the modal's focus trap while escaping overflow clipping via the top layer.
        (menu.hasAttribute('popover') ? input.closest('.modal') || document.body : document.body).append(menu);
        input.setAttribute('role', 'combobox');
        input.setAttribute('aria-autocomplete', 'list');
        input.setAttribute('aria-expanded', 'false');
        input.setAttribute('aria-controls', menu.id);
        input.setAttribute('autocomplete', 'off');
        toggle?.setAttribute('aria-controls', menu.id);
        toggle?.setAttribute('aria-expanded', 'false');
        let revision = 0, timer = null, items = [], active = -1;
        function position() {
            if (menu.hidden) return;
            if (!input.isConnected || !input.getClientRects().length || input.disabled) return close();
            const rect = input.getBoundingClientRect();
            const viewport = window.visualViewport;
            const left = viewport?.offsetLeft || 0, top = viewport?.offsetTop || 0;
            const width = viewport?.width || innerWidth, height = viewport?.height || innerHeight;
            if (rect.bottom <= top || rect.top >= top + height) return close();
            const below = top + height - rect.bottom - 12, above = rect.top - top - 12;
            const up = below < 200 && above > below;
            menu.style.width = Math.min(Math.max(rect.width, 280), width - 16) + 'px';
            menu.style.maxHeight = Math.max(48, Math.min(300, up ? above : below)) + 'px';
            menu.style.left = Math.max(left + 8, Math.min(rect.left, left + width - menu.offsetWidth - 8)) + 'px';
            menu.style.top = (up ? rect.top - menu.offsetHeight - 4 : rect.bottom + 4) + 'px';
        }
        function close() {
            revision++;
            clearTimeout(timer);
            if (menu.hasAttribute('popover') && menu.matches(':popover-open')) menu.hidePopover();
            menu.hidden = true;
            input.setAttribute('aria-expanded', 'false');
            input.removeAttribute('aria-activedescendant');
            toggle?.setAttribute('aria-expanded', 'false');
            if (opened === api) opened = null;
        }
        function show() {
            if (input.disabled || !input.getClientRects().length) return false;
            if (opened && opened !== api) opened.close();
            opened = api;
            menu.hidden = false;
            if (menu.hasAttribute('popover') && !menu.matches(':popover-open')) menu.showPopover();
            input.setAttribute('aria-expanded', 'true');
            toggle?.setAttribute('aria-expanded', 'true');
            position();
            return true;
        }
        function status(text) {
            menu.replaceChildren();
            const row = document.createElement('div');
            row.className = 'checkout-combobox-status';
            row.setAttribute('role', 'status');
            row.textContent = text;
            menu.append(row);
            items = []; active = -1;
            input.removeAttribute('aria-activedescendant');
            position();
        }
        function activate(index) {
            active = index;
            menu.querySelectorAll('[role="option"]').forEach((row, i) => {
                row.classList.toggle('is-active', i === index);
                row.setAttribute('aria-selected', String(i === index));
                if (i === index) {
                    input.setAttribute('aria-activedescendant', row.id);
                    row.scrollIntoView({block: 'nearest'});
                }
            });
        }
        function choose(index) {
            const item = items[index];
            if (!item) return;
            close();
            select(item);
        }
        async function refresh(query = '') {
            clearTimeout(timer);
            const current = ++revision;
            if (!show()) return;
            status(query ? 'Đang tìm…' : 'Đang tải danh sách gần đây…');
            try {
                const rows = await load(query);
                if (current !== revision || menu.hidden) return;
                items = rows;
                if (!rows.length) return status(emptyText);
                menu.replaceChildren(); active = -1;
                const heading = document.createElement('div');
                heading.className = 'checkout-combobox-status';
                heading.setAttribute('role', 'presentation');
                heading.textContent = query ? 'Kết quả tìm kiếm' : 'Gần đây';
                menu.append(heading);
                rows.forEach((item, index) => {
                    const row = document.createElement('div');
                    row.id = menu.id + '-' + index;
                    row.className = 'eapp-dropdown-option checkout-combobox-option';
                    row.setAttribute('role', 'option');
                    row.setAttribute('aria-selected', 'false');
                    const label = document.createElement('div');
                    label.className = 'fw-semibold';
                    label.textContent = item.label;
                    row.append(label);
                    if (item.meta) {
                        const meta = document.createElement('div');
                        meta.className = 'checkout-combobox-meta';
                        meta.textContent = item.meta;
                        row.append(meta);
                    }
                    row.addEventListener('mousedown', event => event.preventDefault());
                    row.addEventListener('click', () => choose(index));
                    menu.append(row);
                });
                position();
            } catch (error) {
                if (current === revision && !menu.hidden) status(error.message || 'Không tải được danh sách. Vui lòng thử lại.');
            }
        }
        input.addEventListener('focus', () => refresh(input.value.trim()));
        input.addEventListener('click', () => {
            if (menu.hidden) refresh(input.value.trim());
        });
        input.addEventListener('input', event => {
            revision++; // Invalidate in-flight responses before the debounce, not afterwards.
            clearTimeout(timer);
            onInput?.();
            if (event.isComposing) return;
            if (show()) status('Đang tìm…');
            timer = setTimeout(() => refresh(input.value.trim()), 200);
        });
        input.addEventListener('keydown', event => {
            if (event.isComposing) return;
            if (event.key === 'Escape' && !menu.hidden) { event.preventDefault(); event.stopPropagation(); close(); }
            else if (event.key === 'Tab') close();
            else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                if (menu.hidden) refresh(input.value.trim());
                else if (items.length) activate(Math.max(0, Math.min(items.length - 1,
                    active < 0 ? (event.key === 'ArrowDown' ? 0 : items.length - 1) : active + (event.key === 'ArrowDown' ? 1 : -1))));
            } else if (event.key === 'Enter') {
                event.preventDefault();
                if (!menu.hidden && active >= 0) choose(active);
                else if (apply) { close(); apply(input.value.trim()); }
                else if (!menu.hidden && items.length === 1) choose(0);
                else refresh(input.value.trim());
            }
        });
        toggle?.addEventListener('click', () => menu.hidden ? refresh('') : close());
        document.addEventListener('pointerdown', event => {
            if (event.target !== input && !toggle?.contains(event.target) && !menu.contains(event.target)) close();
        }, true);
        document.addEventListener('focusin', event => {
            if (event.target !== input && !toggle?.contains(event.target) && !menu.contains(event.target)) close();
        });
        input.closest('.modal')?.addEventListener('hide.bs.modal', close);
        document.addEventListener('scroll', position, true);
        window.addEventListener('resize', position);
        window.visualViewport?.addEventListener('resize', position);
        window.visualViewport?.addEventListener('scroll', position);
        const api = {close, refresh};
        return api;
    }
    window.EAPPCheckoutCombobox = {create};
})();
