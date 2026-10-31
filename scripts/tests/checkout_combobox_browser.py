"""Async checkout picker regression checks, without a server or database.

Run: python3 scripts/tests/checkout_combobox_browser.py
BROWSER=webkit selects WebKit; CHROMIUM_EXECUTABLE optionally selects Chromium.
"""
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]


class CheckoutComboboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        engine = os.environ.get('BROWSER', 'chromium')
        cls.browser = getattr(cls.playwright, engine).launch(
            executable_path=os.environ.get('CHROMIUM_EXECUTABLE') if engine == 'chromium' else None,
            headless=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page(viewport={'width': 393, 'height': 700})
        self.errors = []
        self.page.on('pageerror', lambda err: self.errors.append(str(err)))
        self.page.set_content('''
            <style>
                .modal {position:fixed; top:100px; left:20px; width:350px; height:140px;
                        overflow:hidden; transform:translate(0); background:white; padding:8px;box-sizing:border-box;}
                input {width:110px;font-size:16px;} button {min-width:35px;min-height:35px;}
                #cover {position:fixed;top:240px;left:0;right:0;bottom:0;background:#ddd;z-index:1090;}
            </style>
            <div class="modal"><label for="customer">Khách hàng</label><input id="customer"><button id="recent">▼</button>
                <label for="promo">Khuyến mãi</label><input id="promo"><button id="promos">▼</button></div>
            <button id="outside">Ngoài dropdown</button><div id="cover"></div>
        ''')
        self.page.add_style_tag(path=str(ROOT/'static/css/dropdowns.css'))
        self.page.add_style_tag(path=str(ROOT/'static/css/checkout-combobox.css'))
        self.page.add_script_tag(path=str(ROOT/'static/js/checkout-combobox.js'))
        self.page.evaluate('''() => {
            window.pending = []; window.picked = []; window.applied = [];
            window.picker = EAPPCheckoutCombobox.create({input:document.querySelector('#customer'),
                toggle:document.querySelector('#recent'), load:q=>new Promise((resolve,reject)=>pending.push({q,resolve,reject})),
                select:row=>picked.push(row.label)});
            window.promoPicker = EAPPCheckoutCombobox.create({input:document.querySelector('#promo'),
                toggle:document.querySelector('#promos'), load:async q=>[{label:q || 'SALE10'}],
                select:row=>picked.push(row.label), apply:code=>applied.push(code)});
        }''')
        self.popup = self.page.locator('.checkout-combobox-popup:not([hidden])')

    def tearDown(self):
        self.assertEqual(self.errors, [])
        self.page.close()

    def resolve(self, index, labels):
        self.page.evaluate('args=>pending[args[0]].resolve(args[1].map(label=>({label})))', [index, labels])

    def test_recent_scroll_keyboard_and_top_layer(self):
        self.page.locator('#recent').click()
        self.resolve(0, [f'Khách {i}' for i in range(30)])
        expect(self.popup.get_by_role('option')).to_have_count(30)
        self.assertTrue(self.popup.evaluate('el=>el.scrollHeight>el.clientHeight'))
        self.assertTrue(self.popup.evaluate('el=>{const r=el.getBoundingClientRect();return el.contains(document.elementFromPoint(r.x+20,r.bottom-20))}'))
        # Focusing the input makes a new search; resolve it before using keyboard navigation.
        self.page.locator('#customer').focus()
        self.resolve(1, ['Khách A', 'Khách B'])
        self.page.locator('#customer').press('ArrowDown')
        self.page.locator('#customer').press('ArrowDown')
        self.page.locator('#customer').press('Enter')
        self.assertEqual(self.page.evaluate('picked'), ['Khách B'])
        expect(self.popup).to_have_count(0)

    def test_old_response_cannot_replace_new_query_or_reopen_closed_menu(self):
        self.page.locator('#customer').focus()
        self.page.locator('#customer').fill('new')
        self.page.wait_for_function('pending.length === 2')
        self.resolve(1, ['New result'])
        expect(self.popup).to_contain_text('New result')
        self.resolve(0, ['Old result'])
        expect(self.popup).not_to_contain_text('Old result')
        self.page.locator('#customer').fill('later')
        self.page.wait_for_function('pending.length === 3')
        self.page.locator('#customer').press('Escape')
        self.resolve(2, ['Late result'])
        expect(self.popup).to_have_count(0)
        # Closing also cancels the debounce, so no query opens after Escape.
        self.page.locator('#customer').fill('cancel')
        self.page.locator('#customer').press('Escape')
        self.page.wait_for_timeout(250)
        self.assertEqual(self.page.evaluate('pending.length'), 3)

    def test_only_one_menu_and_enter_applies_typed_code(self):
        self.page.locator('#recent').click()
        self.resolve(0, ['Khách'])
        self.page.locator('#promo').focus()
        expect(self.popup).to_have_count(1)
        expect(self.popup).to_contain_text('SALE10')
        self.page.locator('#promo').fill('OTHER')
        self.page.locator('#promo').press('Enter')
        self.assertEqual(self.page.evaluate('applied'), ['OTHER'])
        expect(self.popup).to_have_count(0)

    def test_error_retry_and_outside_close(self):
        self.page.locator('#recent').click()
        self.page.evaluate("pending[0].reject(new Error('Mất kết nối'))")
        expect(self.popup).to_contain_text('Mất kết nối')
        self.page.locator('#recent').click()
        self.page.locator('#recent').click()
        self.resolve(1, ['Đã kết nối'])
        expect(self.popup).to_contain_text('Đã kết nối')
        self.page.locator('#outside').click()
        expect(self.popup).to_have_count(0)

    def test_legacy_browser_fallback_escapes_modal_clipping(self):
        self.page.evaluate('''() => {
            HTMLElement.prototype.showPopover = undefined;
            window.fallback = EAPPCheckoutCombobox.create({input:document.querySelector('#promo'),
                load:async()=>Array.from({length:20},(_,i)=>({label:'Item '+i})), select:()=>{}});
            fallback.refresh();
        }''')
        expect(self.popup.get_by_role('option')).to_have_count(20)
        self.assertTrue(self.popup.evaluate('el=>el.parentElement === document.body'))
        self.assertTrue(self.popup.evaluate('el=>{const r=el.getBoundingClientRect();return el.contains(document.elementFromPoint(r.x+20,r.bottom-20))}'))


if __name__ == '__main__':
    unittest.main()
