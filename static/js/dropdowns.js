/* Keep the real form controls (values, validation, labels, reset and change handlers).
 * Only their OS popup is replaced. No dependency and no duplicate form fields.
 * data-dropdown-search="true|false" overrides automatic search for >= 8 options.
 * data-dropdown-native opts out; multiple/size>1 listboxes retain native behavior.
 */
(function () {
    'use strict';
    const states = new WeakMap();
    const selector = 'select, input[list], input[data-dropdown-list]';
    let opened = null;
    let sequence = 0;
    const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase();

    function focusControl(state) {
        // Focusing a select during a touch gesture can bring up iOS's native picker.
        if (!state.touchSelect) state.control.focus({ preventScroll: true });
    }

    function options(state) {
        const source = state.isSelect ? state.control : document.getElementById(state.control.dataset.dropdownList);
        return source ? Array.from(source.querySelectorAll('option')) : [];
    }

    function close() {
        if (!opened) return;
        const state = opened;
        opened = null;
        state.control.setAttribute('aria-expanded', 'false');
        state.control.removeAttribute('aria-activedescendant');
        state.control.removeAttribute('aria-controls');
        if (state.menu.hasAttribute('popover')) state.menu.hidePopover();
        state.menu.remove();
        state.menu = null;
    }

    function position() {
        if (!opened) return;
        const { control, menu } = opened;
        if (!control.isConnected || !control.getClientRects().length || control.matches(':disabled') || control.readOnly) {
            close();
            return;
        }
        const rect = control.getBoundingClientRect();
        const viewport = window.visualViewport;
        const left = viewport ? viewport.offsetLeft : 0;
        const top = viewport ? viewport.offsetTop : 0;
        const width = viewport ? viewport.width : window.innerWidth;
        const height = viewport ? viewport.height : window.innerHeight;
        const below = top + height - rect.bottom - 12;
        const above = rect.top - top - 12;
        const upward = below < 220 && above > below;
        menu.style.width = Math.min(Math.max(rect.width, 220), width - 16) + 'px';
        menu.style.maxHeight = Math.max(48, Math.min(340, upward ? above : below)) + 'px';
        menu.style.left = Math.max(left + 8, Math.min(rect.left, left + width - menu.offsetWidth - 8)) + 'px';
        menu.style.top = (upward ? rect.top - menu.offsetHeight - 5 : rect.bottom + 5) + 'px';
    }

    function activate(state, index, scroll) {
        state.active = index;
        state.rows.forEach((row, i) => row.classList.toggle('is-active', i === index));
        const row = state.rows[index];
        const focus = state.search || state.control;
        if (row) {
            focus.setAttribute('aria-activedescendant', row.id);
            if (scroll) row.scrollIntoView({ block: 'nearest' });
        } else {
            focus.removeAttribute('aria-activedescendant');
        }
    }

    function choose(state, option) {
        if (state.control.matches(':disabled') || state.control.readOnly || option.disabled || option.parentElement.disabled) return;
        const previous = state.control.value;
        if (state.isSelect) state.control.selectedIndex = option.index;
        else state.control.value = option.value;
        close();
        focusControl(state);
        if (previous !== state.control.value) {
            state.choosing = true;
            state.control.dispatchEvent(new Event('input', { bubbles: true }));
            state.control.dispatchEvent(new Event('change', { bubbles: true }));
            state.choosing = false;
        }
    }

    function render(state) {
        const query = normalize(state.search ? state.search.value : state.isSelect ? '' : state.control.value);
        state.list.replaceChildren();
        state.rows = [];
        state.visibleOptions = [];
        let lastGroup = null;
        options(state).forEach(option => {
            const group = option.parentElement.tagName === 'OPTGROUP' ? option.parentElement : null;
            if (option.hidden || (group && group.hidden) || (!state.isSelect && !option.value)) return;
            const label = option.label || option.textContent || option.value;
            if (query && !normalize(label + ' ' + option.value).includes(query)) return;
            if (group && group !== lastGroup) {
                const heading = document.createElement('div');
                heading.className = 'eapp-dropdown-group';
                heading.setAttribute('role', 'presentation');
                heading.textContent = group.label;
                state.list.append(heading);
            }
            lastGroup = group;
            const row = document.createElement('div');
            row.className = 'eapp-dropdown-option';
            row.id = state.list.id + '-' + state.rows.length;
            row.setAttribute('role', 'option');
            row.setAttribute('aria-selected', String(state.isSelect ? option.selected : option.value === state.control.value));
            row.setAttribute('aria-disabled', String(option.disabled || !!(group && group.disabled)));
            row.textContent = !state.isSelect && label !== option.value ? option.value + ' — ' + label : label;
            // data-swatch on <option>: colour dot before the label (e.g. theme picker). Only valid CSS colours.
            const swatch = option.dataset.swatch;
            if (swatch && window.CSS && CSS.supports('color', swatch)) {
                const dot = document.createElement('span');
                dot.className = 'eapp-dropdown-swatch';
                dot.setAttribute('aria-hidden', 'true');
                dot.style.background = swatch;
                row.prepend(dot);
            }
            row.addEventListener('pointerdown', event => event.preventDefault());
            row.addEventListener('click', event => { event.stopPropagation(); choose(state, option); });
            const index = state.rows.length;
            row.addEventListener('pointermove', () => { if (row.getAttribute('aria-disabled') !== 'true') activate(state, index); });
            state.rows.push(row);
            state.visibleOptions.push(option);
            state.list.append(row);
        });
        if (!state.rows.length) {
            const empty = document.createElement('div');
            empty.className = 'eapp-dropdown-empty';
            empty.setAttribute('role', 'status');
            empty.textContent = 'Không có kết quả phù hợp';
            state.list.append(empty);
        }
        const selected = state.rows.findIndex(row => row.getAttribute('aria-selected') === 'true' && row.getAttribute('aria-disabled') !== 'true');
        activate(state, selected >= 0 ? selected : state.rows.findIndex(row => row.getAttribute('aria-disabled') !== 'true'));
        position();
    }

    function open(state) {
        if (state.control.matches(':disabled') || state.control.readOnly) return;
        if (opened === state) return;
        close();
        opened = state;
        const menu = document.createElement('div');
        menu.className = 'eapp-dropdown-menu eapp-dropdown-popup';
        // Top layer avoids clipped tables/modals; DOM ancestry preserves Bootstrap's focus trap.
        if (typeof menu.showPopover === 'function') menu.setAttribute('popover', 'manual');
        const list = document.createElement('div');
        list.className = 'eapp-dropdown-list';
        list.id = 'eapp-dropdown-list-' + (++sequence);
        list.setAttribute('role', 'listbox');
        const label = state.control.getAttribute('aria-label') || Array.from(state.control.labels || []).map(item => item.textContent.trim()).join(' ') || state.control.name || 'Lựa chọn';
        list.setAttribute('aria-label', label);
        state.menu = menu;
        state.list = list;
        state.search = null;
        if (state.isSelect && (state.control.dataset.dropdownSearch === 'true' || (state.control.dataset.dropdownSearch !== 'false' && options(state).length >= 8))) {
            const search = document.createElement('input');
            search.type = 'search';
            search.className = 'eapp-dropdown-search';
            search.placeholder = 'Tìm kiếm…';
            search.setAttribute('aria-label', 'Tìm kiếm: ' + label);
            search.setAttribute('role', 'combobox');
            search.setAttribute('aria-autocomplete', 'list');
            search.setAttribute('aria-expanded', 'true');
            search.setAttribute('aria-controls', list.id);
            search.addEventListener('input', () => render(state));
            search.addEventListener('keydown', event => keydown(event, state));
            state.search = search;
            menu.append(search);
        }
        menu.append(list);
        menu.tabIndex = -1;
        menu.addEventListener('keydown', event => {
            if (event.target === menu) keydown(event, state);
        });
        // Keep a nested select's parent Bootstrap dropdown open during selection/search.
        menu.addEventListener('click', event => event.stopPropagation());
        (state.control.closest('.flatpickr-calendar, .modal, dialog, .dropdown-menu') || document.body).append(menu);
        if (menu.hasAttribute('popover')) menu.showPopover();
        state.control.setAttribute('aria-expanded', 'true');
        state.control.setAttribute('aria-controls', list.id);
        render(state);
        if (state.search) state.search.focus({ preventScroll: true });
        else if (state.touchSelect) menu.focus({ preventScroll: true });
        else focusControl(state);
        activate(state, state.active, true);
    }

    function keydown(event, state) {
        if (event.isComposing) return;
        if (event.target === state.control) state.touchSelect = false;
        const isOpen = opened === state;
        if (event.key === 'Escape' && isOpen) {
            event.preventDefault();
            event.stopPropagation();
            close();
            focusControl(state);
            return;
        }
        if (event.key === 'Tab') {
            if (isOpen && (state.search === event.target || state.menu === event.target)) state.control.focus({ preventScroll: true });
            close();
            return;
        }
        const arrow = event.key === 'ArrowDown' || event.key === 'ArrowUp';
        const edge = event.key === 'Home' || event.key === 'End';
        const commit = event.key === 'Enter' || (event.key === ' ' && (event.target === state.control || event.target === state.menu) && state.isSelect);
        if (arrow || (isOpen && edge && event.target === state.control && state.isSelect) || commit && (state.isSelect || isOpen)) {
            event.preventDefault();
            event.stopPropagation();
            if (!isOpen) { open(state); return; }
            if (commit) {
                if (state.active >= 0) choose(state, state.visibleOptions[state.active]);
                return;
            }
            const enabled = state.rows.map((row, index) => row.getAttribute('aria-disabled') === 'true' ? -1 : index).filter(index => index >= 0);
            const current = enabled.indexOf(state.active);
            const next = edge ? (event.key === 'Home' ? 0 : enabled.length - 1) : Math.max(0, Math.min(enabled.length - 1, current + (event.key === 'ArrowDown' ? 1 : -1)));
            activate(state, enabled[next] ?? -1, true);
        } else if (state.isSelect && event.target === state.control && event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
            event.preventDefault();
            open(state);
            if (state.search) {
                state.search.value += event.key;
                render(state);
            } else {
                state.typed = (Date.now() - (state.typedAt || 0) < 700 ? state.typed || '' : '') + event.key;
                state.typedAt = Date.now();
                const index = state.visibleOptions.findIndex((option, i) => state.rows[i].getAttribute('aria-disabled') !== 'true' && normalize(option.label).startsWith(normalize(state.typed)));
                if (index >= 0) activate(state, index, true);
            }
        } else if (state.isSelect && event.key === 'F4') {
            event.preventDefault();
            if (isOpen) close(); else open(state);
        }
    }

    function enhance(control) {
        if (states.has(control) || control.hasAttribute('data-dropdown-native')) return;
        if (control.tagName === 'SELECT' && (control.multiple || control.size > 1)) return;
        const state = { control, isSelect: control.tagName === 'SELECT' };
        if (!state.isSelect) {
            const listId = control.getAttribute('list') || control.dataset.dropdownList;
            if (!listId) return;
            control.dataset.dropdownList = listId;
            control.removeAttribute('list');
            control.setAttribute('role', 'combobox');
            control.setAttribute('aria-autocomplete', 'list');
            control.setAttribute('autocomplete', 'off');
            control.addEventListener('input', () => {
                if (state.choosing) return;
                open(state);
                if (opened === state) render(state);
            });
        }
        states.set(control, state);
        control.classList.add('eapp-dropdown-control');
        control.setAttribute('aria-haspopup', 'listbox');
        control.setAttribute('aria-expanded', 'false');
        if (state.isSelect) {
            // iOS also activates its picker from touchend, independently of mouse defaults.
            // Leave touchstart/move alone so a swipe over a select can still scroll the page.
            let touch = null;
            control.addEventListener('touchstart', event => {
                state.touchSelect = true;
                touch = event.touches.length === 1 ? {
                    x: event.touches[0].clientX, y: event.touches[0].clientY,
                } : null;
            }, { passive: true });
            control.addEventListener('touchmove', event => {
                if (touch && (event.touches.length !== 1 ||
                    Math.abs(event.touches[0].clientX - touch.x) > 10 ||
                    Math.abs(event.touches[0].clientY - touch.y) > 10)) touch = null;
            }, { passive: true });
            control.addEventListener('touchcancel', () => { touch = null; });
            control.addEventListener('touchend', event => {
                event.preventDefault();
                if (!touch) return;
                touch = null;
                event.stopPropagation();
                if (opened === state) close(); else open(state);
            }, { passive: false });
            control.addEventListener('pointerdown', event => {
                state.touchSelect = event.pointerType === 'touch';
                if (event.button === 0) event.preventDefault();
            });
            control.addEventListener('mousedown', event => event.preventDefault());
        }
        control.addEventListener('click', event => {
            event.preventDefault();
            event.stopPropagation();
            if (opened === state && state.isSelect) close(); else open(state);
        });
        control.addEventListener('keydown', event => keydown(event, state));
        control.addEventListener('change', () => { if (opened === state) render(state); });
    }

    function init(root) {
        if (root.matches && root.matches(selector)) enhance(root);
        root.querySelectorAll(selector).forEach(enhance);
    }

    function start() {
        init(document);
        new MutationObserver(mutations => {
            mutations.forEach(mutation => {
                mutation.addedNodes.forEach(node => { if (node.nodeType === 1) init(node); });
                if (mutation.type === 'attributes' && mutation.target.matches(selector)) enhance(mutation.target);
            });
            if (!opened) return;
            const source = opened.isSelect ? opened.control : document.getElementById(opened.control.dataset.dropdownList);
            if (!opened.control.isConnected || opened.control.matches(':disabled') || opened.control.readOnly) close();
            else if (mutations.some(mutation => source && (source === mutation.target || source.contains(mutation.target)))) render(opened);
        }).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['disabled', 'readonly', 'selected', 'label', 'value', 'hidden', 'list'] });
        document.addEventListener('pointerdown', event => {
            if (opened && event.target !== opened.control && !opened.menu.contains(event.target)) close();
        }, true);
        document.addEventListener('focusin', event => {
            if (opened && event.target !== opened.control && !opened.menu.contains(event.target)) close();
        });
        document.addEventListener('reset', close, true);
        document.addEventListener('hide.bs.modal', close);
        document.addEventListener('hide.bs.dropdown', close);
        window.addEventListener('resize', position);
        document.addEventListener('scroll', position, true);
        if (window.visualViewport) {
            window.visualViewport.addEventListener('resize', position);
            window.visualViewport.addEventListener('scroll', position);
        }
    }
    window.EAPPDropdowns = { init: (root = document) => init(root), close };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
})();
