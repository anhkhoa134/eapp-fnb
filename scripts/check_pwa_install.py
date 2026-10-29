"""Chrome regression of PWA button lifecycle using synthetic browser events.

Run: python scripts/check_pwa_install.py (requires Playwright and Chrome).
No user profile, server, database, or actual installation is used.
PWA_PROJECT_ROOT can point at a staged project tree.
"""
import os,re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(os.environ.get('PWA_PROJECT_ROOT',Path(__file__).resolve().parents[1]))
APP=ROOT.name.removeprefix('eapp-')
STYLE='<style>.d-none,[hidden]{display:none!important}</style>'
HTMLS={
 'reader':'<button id="pwaInstallButton" hidden>Cài đặt</button>',
 'prompt':'<div id="colorThemeDropdown"><div hidden></div><div class="ctd-install" hidden><button id="pwaInstallBtn">Cài đặt App</button></div></div>',
 'fnb':'<li class="js-pwa-install-action d-none"><button><span data-pwa-install-label>Cài ứng dụng</span></button></li>',
 'equiptrack':'<button id="install">Cài ứng dụng</button>',
 'pos':'<li data-pwa-install-item hidden><button data-pwa-install hidden><span data-pwa-install-label>Cài ứng dụng</span></button></li>',
 'lms':'<button data-pwa-install hidden><span data-pwa-install-label>Cài ứng dụng</span></button>',
}
SELECTORS={'reader':'#pwaInstallButton','prompt':'#pwaInstallBtn','fnb':'.js-pwa-install-action button','equiptrack':'#install','pos':'[data-pwa-install]','lms':'[data-pwa-install]'}
if APP=='fnb':
 SOURCE=(ROOT/'templates/App_Core/_pwa_register.html').read_text().removeprefix('<script>').strip().removesuffix('</script>')
 SOURCE=re.sub(r'\{%.*?%\}','/sw.js',SOURCE)
elif APP=='equiptrack':
 raw=(ROOT/'static/js/app.js').read_text()
 SOURCE="const state={showAccountMenu:true};function renderApp(){document.getElementById('install').hidden=!shouldShowPwaInstallButton()}function showToast(){}\n"+raw[raw.index('        function isPwaStandalone()'):raw.index('        let debtChartInstance')]+"\nsetupPwaInstallPrompt();document.getElementById('install').addEventListener('click',promptPwaInstall);renderApp();"
else:
 SOURCE=(ROOT/('static/js/pwa-register.js' if APP=='reader' else 'static/js/pwa-install.js')).read_text()

with sync_playwright() as p:
 browser=p.chromium.launch(channel='chrome',headless=True)
 def open_page(apple=False,standalone=False):
  page=browser.new_page();page.set_default_timeout(5000);errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
  page.set_content(STYLE+HTMLS[APP])
  page.evaluate('''() => {
   window.promptCalls=0;window.standalone=false;window.modeListeners=[];
   window.matchMedia=()=>({get matches(){return window.standalone},addEventListener:(name,fn)=>modeListeners.push(fn)});
   window.setStandalone=(value)=>{window.standalone=value;modeListeners.forEach(fn=>fn())};
   delete Navigator.prototype.serviceWorker;
   window.bootstrap={Modal:{getOrCreateInstance:el=>({show:()=>{el.hidden=false;window.guideShown=true}})}};
  }''')
  if apple:page.evaluate("Object.defineProperty(navigator,'platform',{value:'MacIntel'});Object.defineProperty(navigator,'maxTouchPoints',{value:5});Object.defineProperty(navigator,'userAgent',{value:'Version/18.0 Safari/605.1.15'})")
  if standalone:page.evaluate('window.standalone=true')
  page.add_script_tag(content=SOURCE);return page,errors
 def offer(page,outcome='dismissed',pending=False,fail=None):
  page.evaluate('''({outcome,pending,fail})=>{
   const e=new Event('beforeinstallprompt',{cancelable:true});
   e.prompt=()=>{promptCalls++;if(fail==='choice')e.userChoice=Promise.reject(Error('test choice failure'));return fail==='prompt'?Promise.reject(Error('test failure')):Promise.resolve()};
   e.userChoice=pending?new Promise(resolve=>window.resolveChoice=resolve):Promise.resolve({outcome});
   dispatchEvent(e);
  }''',dict(outcome=outcome,pending=pending,fail=fail))
 def click(page):
  # Prompt hides its parent theme menu when clicked; model the user opening it again.
  if APP=='prompt':page.evaluate('document.getElementById("colorThemeDropdown").hidden=false')
  if APP=='equiptrack':page.evaluate('state.showAccountMenu=true;renderApp()')
  page.locator(SELECTORS[APP]).click()
 def visible(page):
  if APP=='prompt':page.evaluate('document.getElementById("colorThemeDropdown").hidden=false')
  if APP=='equiptrack':page.evaluate('state.showAccountMenu=true;renderApp()')
  expect(page.locator(SELECTORS[APP])).to_be_visible()
 page,errors=open_page();button=page.locator(SELECTORS[APP]);expect(button).to_be_hidden()
 offer(page);visible(page);click(page);expect(button).to_be_hidden();assert page.evaluate('promptCalls')==1
 offer(page,pending=True);click(page)
 page.evaluate('(selector)=>{document.querySelector(selector).click();document.querySelector(selector).click()}',SELECTORS[APP]);assert page.evaluate('promptCalls')==2
 # A fresh browser event arriving while a previous choice is pending must survive.
 offer(page);page.evaluate("resolveChoice({outcome:'dismissed'})");visible(page);click(page);expect(button).to_be_hidden();assert page.evaluate('promptCalls')==3
 for fail in ['prompt','choice']:
  offer(page,fail=fail);click(page);expect(button).to_be_hidden()
 offer(page);visible(page);click(page);assert page.evaluate('promptCalls')==6
 offer(page,outcome='accepted');click(page);expect(button).to_be_hidden()
 offer(page);expect(button).to_be_hidden();page.evaluate("dispatchEvent(new Event('appinstalled'))");expect(button).to_be_hidden()
 assert not errors,errors;page.close()
 page,errors=open_page(standalone=True);offer(page);expect(page.locator(SELECTORS[APP])).to_be_hidden();assert page.evaluate('promptCalls')==0;assert not errors;page.close()
 page,errors=open_page();offer(page);page.evaluate("dispatchEvent(new Event('appinstalled'))");expect(page.locator(SELECTORS[APP])).to_be_hidden();offer(page);expect(page.locator(SELECTORS[APP])).to_be_hidden();assert not errors;page.close()
 if APP in ['fnb','pos','lms']:
  page,errors=open_page(apple=True);visible(page);expect(page.locator('[data-pwa-install-label]')).to_have_text('Hướng dẫn cài đặt');click(page)
  assert page.evaluate("window.guideShown===true || document.querySelector('dialog')?.open===true")
  assert page.evaluate('promptCalls')==0;assert not errors;page.close()
  page,errors=open_page(apple=True,standalone=True);expect(page.locator(SELECTORS[APP])).to_be_hidden();page.close()
 browser.close()
 print(APP+': PASS — unavailable, dismissal/retry, double click, new event while pending, rejected prompt/choice, accepted, appinstalled, standalone'+(', iPad manual guide' if APP in ['fnb','pos','lms'] else ''))
