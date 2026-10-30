"""Browser regression tests. Run: python3 scripts/tests/dropdowns_browser.py

Requires Python Playwright and Chromium (or BROWSER=webkit for mobile WebKit).
Set CHROMIUM_EXECUTABLE to use an existing Chromium installation.
Fixtures are local; no server/database required.
"""
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


class DropdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        browser_name = os.environ.get('BROWSER', 'chromium')
        cls.browser = getattr(cls.playwright, browser_name).launch(
            executable_path=os.environ.get('CHROMIUM_EXECUTABLE') if browser_name == 'chromium' else None,
            headless=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page(viewport={'width': 1000, 'height': 720})
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.set_content('''
            <style>
              body { padding: 30px; font: 16px Arial; }
              select, input { display: block; box-sizing: border-box; width: 300px; padding: 10px; }
              .quanly-page .form-select:focus { border-color: blue; box-shadow: 0 0 0 4px blue; }
              .modal { position: fixed; top: 120px; left: 100px; width: 420px; height: 150px;
                       overflow: hidden; transform: translate(0); background: white; }
            </style>
            <form id="form" class="quanly-page">
              <label for="category">Danh mục</label>
              <select class="form-select" id="category" name="category" required>
                <option value="">Tất cả danh mục</option>
                <option value="tools">Dụng cụ thiết bị</option>
                <option value="food" disabled>Thực phẩm</option>
                <optgroup label="Nhóm khác"><option value="drink">Đồ uống</option></optgroup>
                <optgroup label="Ngừng bán" disabled><option value="old">Hàng cũ</option></optgroup>
              </select>
              <input id="next" name="next">
              <label for="suggest">Đơn vị</label>
              <input id="suggest" name="unit" list="units">
              <datalist id="units"><option value="Hộp"></option><option value="Cái"></option></datalist>
              <button type="reset" id="reset-button">Reset</button>
            </form>
            <div id="dynamic"></div>
            <button id="outside">Ngoài dropdown</button>
            <script>
              window.events = [];
              for (const type of ['input', 'change']) document.querySelector('#form')
                .addEventListener(type, e => window.events.push([type, e.target.name, e.target.value]));
            </script>
        ''')
        self.page.add_style_tag(path=str(ROOT / 'static/css/dropdowns.css'))
        self.page.add_style_tag(path=str(ROOT / 'static/css/dropdowns-fnb.css'))
        self.page.add_script_tag(path=str(ROOT / 'static/js/dropdowns.js'))

    def tearDown(self):
        self.page.close()
        self.assertEqual(self.errors, [])

    def test_selection_events_validation_reset_and_programmatic_values(self):
        self.assertFalse(self.page.locator('#category').evaluate('(el) => el.checkValidity()'))
        self.page.locator('#category').click()
        self.page.locator('.eapp-dropdown-list').get_by_role('option', name='Dụng cụ thiết bị').click()
        self.assertEqual(self.page.locator('#category').input_value(), 'tools')
        self.assertEqual(self.page.evaluate('window.events'), [['input', 'category', 'tools'], ['change', 'category', 'tools']])
        self.assertTrue(self.page.locator('#category').evaluate('(el) => el.checkValidity()'))
        self.assertEqual(self.page.evaluate("new FormData(document.querySelector('form')).get('category')"), 'tools')
        self.page.locator('#category').evaluate("el => el.value = 'drink'")
        self.page.locator('#category').click()
        self.assertEqual(self.page.locator('[role=option][aria-selected=true]').inner_text(), 'Đồ uống')
        self.page.locator('#form').evaluate('form => form.reset()')
        self.assertEqual(self.page.locator('#category').input_value(), '')
        self.assertEqual(self.page.locator('.eapp-dropdown-popup').count(), 0)

    def test_keyboard_disabled_options_escape_and_tab(self):
        self.page.locator('#category').focus()
        self.page.keyboard.press('ArrowDown')
        self.page.keyboard.press('ArrowDown')
        self.page.keyboard.press('ArrowDown')  # skips disabled food
        self.page.keyboard.press('Enter')
        self.assertEqual(self.page.locator('#category').input_value(), 'drink')
        self.page.keyboard.press('Space')
        self.page.locator('.eapp-dropdown-list').get_by_role('option', name='Hàng cũ').click(force=True)
        self.assertEqual(self.page.locator('#category').input_value(), 'drink')
        self.page.keyboard.press('Escape')
        self.assertEqual(self.page.locator('.eapp-dropdown-popup').count(), 0)
        self.page.keyboard.press('Space')
        self.page.keyboard.press('Tab')
        self.assertEqual(self.page.locator(':focus').get_attribute('id'), 'next')

    def test_search_vietnamese_empty_results_and_safe_text(self):
        self.page.locator('#category').evaluate('''el => {
          for (let i = 0; i < 10; i++) el.add(new Option('Mặt hàng ' + i, String(i)));
          el.add(new Option('<img src=x onerror=alert(1)>', 'safe'));
        }''')
        self.page.locator('#category').click()
        search = self.page.get_by_role('combobox', name='Tìm kiếm: Danh mục')
        search.fill('do uong')
        self.assertEqual(self.page.locator('.eapp-dropdown-list').get_by_role('option').all_text_contents(), ['Đồ uống'])
        search.press('Enter')
        self.assertEqual(self.page.locator('#category').input_value(), 'drink')
        self.page.locator('#category').click()
        search.fill('zzzz')
        self.assertEqual(self.page.locator('.eapp-dropdown-list').get_by_role('option').count(), 0)
        self.assertTrue(self.page.get_by_role('status').is_visible())
        search.fill('<img')
        self.assertEqual(self.page.locator('.eapp-dropdown-popup img').count(), 0)
        self.assertIn('<img', self.page.locator('.eapp-dropdown-list').get_by_role('option').inner_text())
        search.press('Tab')
        self.assertEqual(self.page.locator(':focus').get_attribute('id'), 'next')

    def test_option_swatch_renders_colour_dot_and_rejects_invalid_colour(self):
        self.page.locator('#category').evaluate('''el => {
          el.options[1].dataset.swatch = '#10b981';
          el.options[3].dataset.swatch = 'url(javascript:alert(1))';
        }''')
        self.page.locator('#category').click()
        swatches = self.page.locator('.eapp-dropdown-list .eapp-dropdown-swatch')
        self.assertEqual(swatches.count(), 1)
        self.assertEqual(swatches.first.evaluate('el => getComputedStyle(el).backgroundColor'), 'rgb(16, 185, 129)')
        self.assertEqual(swatches.first.get_attribute('aria-hidden'), 'true')
        option = self.page.locator('.eapp-dropdown-list').get_by_role('option', name='Dụng cụ thiết bị')
        self.assertEqual(option.inner_text().strip(), 'Dụng cụ thiết bị')
        option.click()
        self.assertEqual(self.page.locator('#category').input_value(), 'tools')

    def test_datalist_keeps_free_text_and_emits_selection_events(self):
        self.page.locator('#suggest').fill('hop')
        self.assertEqual(self.page.locator('.eapp-dropdown-list').get_by_role('option').all_text_contents(), ['Hộp'])
        self.page.locator('.eapp-dropdown-list').get_by_role('option', name='Hộp').click()
        self.assertEqual(self.page.locator('#suggest').input_value(), 'Hộp')
        self.assertEqual(self.page.locator('.eapp-dropdown-popup').count(), 0)
        self.page.locator('#suggest').fill('Thùng tự nhập')
        self.page.keyboard.press('Escape')
        self.assertEqual(self.page.locator('#suggest').input_value(), 'Thùng tự nhập')
        self.assertEqual(self.page.evaluate("new FormData(document.querySelector('form')).get('unit')"), 'Thùng tự nhập')

    def test_dynamic_controls_options_disabled_and_removal(self):
        self.page.locator('#dynamic').evaluate('''el => {
          el.innerHTML = '<select id="ajax"><option>A</option><option>B</option></select>';
        }''')
        self.page.locator('#ajax.eapp-dropdown-control').wait_for()
        self.page.locator('#ajax').click()
        self.page.locator('#ajax').evaluate("el => el.innerHTML = '<option>C</option><option>D</option>'")
        self.page.locator('.eapp-dropdown-list').get_by_role('option', name='D', exact=True).click()
        self.assertEqual(self.page.locator('#ajax').input_value(), 'D')
        self.page.locator('#ajax').click()
        self.page.locator('#ajax').evaluate('el => el.disabled = true')
        self.page.locator('.eapp-dropdown-popup').wait_for(state='detached')
        self.page.locator('#ajax').evaluate('el => el.disabled = false')
        self.page.locator('#ajax').click()
        self.page.locator('#dynamic').evaluate('el => el.replaceChildren()')
        self.page.locator('.eapp-dropdown-popup').wait_for(state='detached')

    def test_modal_clipping_and_small_viewport(self):
        self.page.locator('#dynamic').evaluate('''el => {
          el.innerHTML = '<div class="modal"><label for="modalSelect">Bộ lọc</label>' +
            '<select id="modalSelect" data-dropdown-search="true"><option>A</option><option>B</option></select></div>';
        }''')
        self.page.locator('#modalSelect').click()
        self.assertEqual(self.page.locator('.modal .eapp-dropdown-popup').count(), 1)
        self.assertEqual(self.page.locator('.eapp-dropdown-popup:popover-open').count(), 1)
        self.page.locator('.eapp-dropdown-list').get_by_role('option', name='B', exact=True).click()
        self.assertEqual(self.page.locator('#modalSelect').input_value(), 'B')
        self.page.set_viewport_size({'width': 375, 'height': 667})
        self.page.locator('.modal').evaluate("el => { el.style.left = '16px'; el.style.top = '530px'; el.style.width = '340px'; }")
        self.page.locator('#modalSelect').click()
        box = self.page.locator('.eapp-dropdown-popup').bounding_box()
        control = self.page.locator('#modalSelect').bounding_box()
        self.assertGreaterEqual(box['x'], 0)
        self.assertLessEqual(box['x'] + box['width'], 375)
        self.assertLess(box['y'], control['y'])
        self.page.evaluate("document.querySelector('.modal').dispatchEvent(new Event('hide.bs.modal', {bubbles: true}))")
        self.assertEqual(self.page.locator('.eapp-dropdown-popup').count(), 0)

    def test_fnb_theme_changes_without_reinitialization(self):
        self.page.locator('#category').click()
        row = self.page.locator('.eapp-dropdown-option[aria-selected=true]')
        self.page.evaluate("document.documentElement.style.setProperty('--primary-hover', '#7c3aed')")
        self.page.evaluate("document.documentElement.style.setProperty('--primary-color', '#a855f7')")
        self.assertEqual(self.page.locator('#category').evaluate('el => getComputedStyle(el).borderTopColor'), 'rgb(168, 85, 247)')
        self.assertEqual(row.evaluate('el => getComputedStyle(el).color'), 'rgb(124, 58, 237)')
        self.page.evaluate("document.documentElement.style.setProperty('--primary-hover', '#059669')")
        self.assertEqual(row.evaluate('el => getComputedStyle(el).color'), 'rgb(5, 150, 105)')

    def test_print_does_not_include_open_popup(self):
        self.page.locator('#category').click()
        self.page.emulate_media(media='print')
        self.assertFalse(self.page.locator('.eapp-dropdown-popup').is_visible())

    def test_touch_and_outside_dismissal(self):
        context = self.browser.new_context(has_touch=True, is_mobile=True, viewport={'width': 375, 'height': 667})
        page = context.new_page()
        page.set_content('''
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>select, button { min-height: 44px; font-size: 16px; } select { width: 240px; }</style>
            <select><option>A</option><option>B</option></select><button>Outside</button>
        ''')
        page.add_style_tag(path=str(ROOT / 'static/css/dropdowns.css'))
        page.add_script_tag(path=str(ROOT / 'static/js/dropdowns.js'))
        page.evaluate('''() => {
          window.selectFocusCount = 0;
          window.touchEnds = [];
          const select = document.querySelector('select');
          select.addEventListener('focus', () => window.selectFocusCount++);
          select.addEventListener('touchend', e => window.touchEnds.push(e.defaultPrevented));
        }''')
        page.locator('select').tap()
        self.assertEqual(page.locator('.eapp-dropdown-popup').count(), 1)
        self.assertEqual(page.evaluate('window.touchEnds'), [True])
        page.locator('.eapp-dropdown-list').get_by_role('option', name='B', exact=True).tap()
        self.assertEqual(page.locator('select').input_value(), 'B')
        self.assertEqual(page.locator('.eapp-dropdown-popup').count(), 0)
        self.assertEqual(page.evaluate('window.selectFocusCount'), 0)
        page.locator('select').tap()
        page.locator('select').tap()
        self.assertEqual(page.locator('.eapp-dropdown-popup').count(), 0)
        page.locator('select').tap()
        page.locator('button').tap()
        self.assertEqual(page.locator('.eapp-dropdown-popup').count(), 0)
        page.locator('select').evaluate('''select => {
          const touch = {clientX: 20, clientY: 20};
          const moved = {clientX: 20, clientY: 80};
          for (const [type, touches] of [
            ['touchstart', [touch]], ['touchmove', [moved]], ['touchend', []],
          ]) {
            const event = new Event(type, {bubbles: true, cancelable: true});
            Object.defineProperty(event, 'touches', {value: touches});
            select.dispatchEvent(event);
          }
        }''')
        self.assertEqual(page.locator('.eapp-dropdown-popup').count(), 0, 'Swiping must not open the dropdown')
        page.locator('select').evaluate("select => select.dataset.dropdownSearch = 'true'")
        page.locator('select').tap()
        page.locator('.eapp-dropdown-search').press('a')
        page.locator('.eapp-dropdown-list').get_by_role('option', name='A', exact=True).tap()
        self.assertEqual(page.locator('select').input_value(), 'A')
        self.assertEqual(page.evaluate('window.selectFocusCount'), 0, 'Typing a search must not restore native select focus')
        self.assertEqual(page.locator('.eapp-dropdown-popup').count(), 0)
        context.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
