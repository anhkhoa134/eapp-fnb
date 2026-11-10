/*! eapp-pwa.js — nút Cài app / Có bản cập nhật / Tải lại + icon Live dùng chung cho các app eApp.
 * Bản gốc: repo hạ tầng Shared-UI/pwa/ — đồng bộ bằng sync-pwa.py, KHÔNG sửa trực tiếp trong app.
 *
 * Nhúng trong <head> (không defer, để bắt kịp beforeinstallprompt):
 *   <link rel="stylesheet" href="{% static 'eapp-pwa/eapp-pwa.css' %}">
 *   <script src="{% static 'eapp-pwa/eapp-pwa.js' %}" data-app-name="eApp POS" data-sw-url="/sw.js"></script>
 *
 * data-app-name   tên app trong hướng dẫn cài (mặc định: document.title)
 * data-sw-url     có → file này đăng ký Service Worker (scope "/", kiểm bản mới mỗi giờ);
 *                 bỏ trống → app tự đăng ký, file này chỉ theo dõi bản cập nhật qua serviceWorker.ready
 * data-sw-scope   scope khi đăng ký (mặc định "/")
 * data-health-url URL kiểm Live/Offline (mặc định "/healthz/", gọi HEAD)
 *
 * Gắn vào phần tử của app (giao diện nút giữ nguyên theo app):
 *   [data-pwa-install]               nút Cài app: hiện khi trình duyệt cho cài, hoặc iOS / Safari Mac (mở hướng dẫn)
 *     [data-pwa-install-item]        phần tử bọc ngoài (vd. <li>) ẩn/hiện cùng nút
 *     [data-pwa-install-label]       con của nút: chữ đổi "Cài ứng dụng" / "Hướng dẫn cài đặt"
 *                                    (đổi chữ bằng data-label-install, data-label-guide trên nút)
 *   [data-pwa-update]                nút Có bản cập nhật mới: hiện khi Service Worker mới đang chờ ([data-pwa-update-item] bọc ngoài)
 *   [data-account-reload]            nút Tải lại trang
 *   [data-account-live-indicator]    chấm Live/Offline (data-live-title, data-offline-title;
 *                                    con [data-account-live-text] với data-live-text, data-offline-text)
 *   [data-account-live-probe]        bấm vào phần tử này (vd. nút mở menu tài khoản) thì kiểm lại Live
 * Ẩn/hiện bằng thuộc tính hidden. Menu Bootstrap chứa chấm Live tự kiểm lại khi mở (show.bs.dropdown).
 *
 * Sự kiện trên window: pwa:installpromptavailable, pwa:installed, pwa:updateavailable, eapp-pwa:change.
 * API: window.eAppPWA = { install, update, showHelp, checkLive, sync, isStandalone, state }.
 */
(() => {
  "use strict";
  if (window.eAppPWA) return;

  const config = (document.currentScript && document.currentScript.dataset) || {};
  const healthUrl = config.healthUrl || "/healthz/";
  const appName = () => config.appName || document.title || "eApp";

  const STRINGS = {
    vi: {
      helpTitle: "Cài {app}",
      close: "Đã hiểu",
      install: "Cài ứng dụng",
      guide: "Hướng dẫn cài đặt",
      ios: [
        "Mở trang này bằng <b>Safari</b>.",
        "Nhấn nút <b>Chia sẻ</b> (ô vuông có mũi tên) → <b>Thêm vào Màn hình chính</b>.",
        "Bật <b>Mở dưới dạng ứng dụng web</b> nếu có, rồi nhấn <b>Thêm</b>.",
        "Mở {app} bằng biểu tượng mới trên Màn hình chính.",
      ],
      "mac-safari": ["Trên thanh menu Safari chọn <b>Tệp</b> → <b>Thêm vào Dock…</b>", "Mở {app} từ Dock hoặc Launchpad."],
      android: ["Mở menu <b>⋮</b> của trình duyệt.", "Chọn <b>Cài đặt ứng dụng</b> hoặc <b>Thêm vào màn hình chính</b>."],
      desktop: [
        "Nhấn biểu tượng <b>Cài đặt</b> ở cuối thanh địa chỉ (Chrome, Edge).",
        "Hoặc mở menu <b>⋮</b> → <b>Truyền, lưu và chia sẻ</b> → <b>Cài đặt trang dưới dạng ứng dụng</b>.",
      ],
      live: "Live",
      offline: "Offline",
    },
    en: {
      helpTitle: "Install {app}",
      close: "Got it",
      install: "Install app",
      guide: "How to install",
      ios: [
        "Open this page in <b>Safari</b>.",
        "Tap <b>Share</b> → <b>Add to Home Screen</b>.",
        "Turn on <b>Open as Web App</b> if shown, then tap <b>Add</b>.",
        "Open {app} from the new Home Screen icon.",
      ],
      "mac-safari": ["In the Safari menu bar choose <b>File</b> → <b>Add to Dock…</b>", "Open {app} from the Dock or Launchpad."],
      android: ["Open the browser <b>⋮</b> menu.", "Choose <b>Install app</b> or <b>Add to Home screen</b>."],
      desktop: [
        "Click the <b>Install</b> icon at the end of the address bar (Chrome, Edge).",
        "Or open the <b>⋮</b> menu → <b>Cast, save and share</b> → <b>Install page as app</b>.",
      ],
      live: "Live",
      offline: "Offline",
    },
  };
  const lang = (document.documentElement.lang || "vi").toLowerCase().startsWith("vi") ? "vi" : "en";
  const t = STRINGS[lang];

  const ua = navigator.userAgent || "";
  const platform = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
    ? "ios"
    : /Macintosh/.test(ua) && /Safari/.test(ua) && !/Chrome|Chromium|CriOS|Edg|OPR|Firefox/.test(ua)
      ? "mac-safari"
      : /Android/i.test(ua) ? "android" : "desktop";
  // Safari không có beforeinstallprompt: nút Cài app mở hướng dẫn thủ công thay vì ẩn hẳn.
  const manualInstall = platform === "ios" || platform === "mac-safari";

  const standaloneQuery = window.matchMedia("(display-mode: standalone)");
  const isStandalone = () => standaloneQuery.matches || navigator.standalone === true;

  const state = {
    installPrompt: window.__pwaInstallPrompt || null, // app nào đã bắt sẵn trong <head> thì dùng lại
    installing: false,
    installed: false,
    updateAvailable: false,
    registration: null,
    online: navigator.onLine,
  };

  const emit = (name, detail) => window.dispatchEvent(new CustomEvent(name, { detail }));
  const all = (selector) => document.querySelectorAll(selector);

  const setHidden = (el, hidden) => {
    if (el && el.hidden !== hidden) el.hidden = hidden;
  };

  let lastChange = "";
  function sync() {
    const showInstall = !isStandalone() && !state.installed && (Boolean(state.installPrompt) || manualInstall);
    all("[data-pwa-install]").forEach((el) => {
      setHidden(el, !showInstall);
      setHidden(el.closest("[data-pwa-install-item]"), !showInstall); // vd. <li> bọc nút trong dropdown
      if ("disabled" in el && el.disabled !== state.installing) el.disabled = state.installing;
      const label = el.querySelector("[data-pwa-install-label]");
      if (label) {
        // Có hộp thoại cài của trình duyệt → "Cài ứng dụng"; iOS / Safari Mac → "Hướng dẫn cài đặt".
        const text = state.installPrompt ? el.dataset.labelInstall || t.install : el.dataset.labelGuide || t.guide;
        if (label.textContent !== text) label.textContent = text;
        el.title = text;
        el.setAttribute("aria-label", text);
      }
    });
    all("[data-pwa-update]").forEach((el) => {
      setHidden(el, !state.updateAvailable);
      setHidden(el.closest("[data-pwa-update-item]"), !state.updateAvailable);
    });
    const change = `${showInstall}|${state.updateAvailable}`;
    if (change !== lastChange) {
      lastChange = change;
      emit("eapp-pwa:change", { canInstall: showInstall, updateAvailable: state.updateAvailable });
    }
  }

  // ---------- Cài app ----------
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    state.installPrompt = event;
    window.__pwaInstallPrompt = event;
    emit("pwa:installpromptavailable", { promptEvent: event });
    sync();
  });
  window.addEventListener("appinstalled", () => {
    state.installed = true;
    state.installPrompt = null;
    window.__pwaInstallPrompt = null;
    emit("pwa:installed");
    sync();
  });
  if (standaloneQuery.addEventListener) standaloneQuery.addEventListener("change", sync);

  let dialog = null;
  function showHelp() {
    const name = appName().replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
    const fill = (text) => text.replace(/\{app\}/g, name);
    if (!dialog) {
      dialog = document.createElement("dialog");
      dialog.className = "eapp-pwa-dialog";
      dialog.setAttribute("aria-labelledby", "eappPwaDialogTitle");
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog || event.target.closest("[data-eapp-pwa-close]")) dialog.close();
      });
      document.body.appendChild(dialog);
    }
    dialog.innerHTML = `<div class="eapp-pwa-dialog__body">
        <h2 class="eapp-pwa-dialog__title" id="eappPwaDialogTitle">${fill(t.helpTitle)}</h2>
        <ol>${t[platform].map((step) => `<li>${fill(step)}</li>`).join("")}</ol>
        <div class="eapp-pwa-dialog__actions"><button type="button" data-eapp-pwa-close>${t.close}</button></div>
      </div>`;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else window.alert(dialog.textContent.replace(/\s+/g, " ").trim());
  }

  async function install() {
    if (isStandalone() || state.installing) return;
    const prompt = state.installPrompt;
    if (!prompt) {
      showHelp();
      return;
    }
    // Sự kiện chỉ dùng được một lần: bỏ trước khi await để không bấm hai lần.
    state.installPrompt = null;
    window.__pwaInstallPrompt = null;
    state.installing = true;
    sync();
    try {
      await prompt.prompt();
      const choice = await prompt.userChoice;
      if (choice && choice.outcome === "accepted") state.installed = true;
    } catch (error) {
      console.warn("[eApp PWA] Không mở được hộp thoại cài:", error);
    } finally {
      state.installing = false;
      sync();
    }
  }

  // ---------- Bản cập nhật (Service Worker) ----------
  function markUpdate() {
    if (state.updateAvailable) return;
    state.updateAvailable = true;
    emit("pwa:updateavailable", { registration: state.registration });
    sync();
  }

  function update() {
    const waiting = state.registration && state.registration.waiting;
    if (waiting) waiting.postMessage({ type: "SKIP_WAITING" });
    window.location.reload();
  }

  function watchWorker(worker) {
    if (!worker || !navigator.serviceWorker.controller || worker === navigator.serviceWorker.controller) return;
    const check = () => {
      if (worker.state === "installed" || worker.state === "activated") markUpdate();
    };
    worker.addEventListener("statechange", check);
    check();
  }

  function track(registration) {
    if (!registration || state.registration === registration) return;
    state.registration = registration;
    watchWorker(registration.waiting);
    watchWorker(registration.installing);
    registration.addEventListener("updatefound", () => watchWorker(registration.installing));
  }

  if ("serviceWorker" in navigator && window.isSecureContext) {
    let controller = navigator.serviceWorker.controller;
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (controller) markUpdate();
      controller = navigator.serviceWorker.controller;
    });
    window.addEventListener("load", async () => {
      try {
        if (config.swUrl) {
          const registration = await navigator.serviceWorker.register(config.swUrl, {
            scope: config.swScope || "/",
            updateViaCache: "none",
          });
          track(registration);
          const checkForUpdate = () => registration.update().catch(() => {});
          checkForUpdate();
          window.setInterval(checkForUpdate, 60 * 60 * 1000);
        } else {
          track(await navigator.serviceWorker.ready);
        }
      } catch (error) {
        console.warn("[eApp PWA] Service Worker:", error);
      }
    });
  }

  // ---------- Tải lại + Live / Offline ----------
  function setLive(online) {
    state.online = Boolean(online);
    all("[data-account-live-indicator]").forEach((indicator) => {
      indicator.classList.toggle("is-live", state.online);
      indicator.classList.toggle("is-offline", !state.online);
      const title = state.online ? indicator.dataset.liveTitle : indicator.dataset.offlineTitle;
      if (title) indicator.setAttribute("title", title);
      const label = indicator.querySelector("[data-account-live-text]");
      if (label) {
        label.textContent = state.online ? label.dataset.liveText || t.live : label.dataset.offlineText || t.offline;
      }
    });
  }

  let probing = null;
  function checkLive() {
    if (!navigator.onLine) {
      setLive(false);
      return Promise.resolve(false);
    }
    if (!probing) {
      probing = fetch(healthUrl, { method: "HEAD", cache: "no-store", credentials: "same-origin" })
        .then((response) => response.ok)
        .catch(() => false)
        .then((ok) => {
          setLive(ok);
          probing = null;
          return ok;
        });
    }
    return probing;
  }

  window.addEventListener("online", () => setLive(true));
  window.addEventListener("offline", () => setLive(false));
  document.addEventListener("show.bs.dropdown", (event) => {
    const menu = event.target.closest(".dropdown, .dropup, .dropstart, .dropend, .btn-group") || event.target.parentElement;
    if (menu && menu.querySelector("[data-account-live-indicator]")) checkLive();
  });

  document.addEventListener("click", (event) => {
    const reload = event.target.closest("[data-account-reload]");
    if (reload) {
      event.preventDefault();
      reload.classList.add("is-loading", "is-spinning");
      window.setTimeout(() => window.location.reload(), 150);
      return;
    }
    if (event.target.closest("[data-pwa-update]")) {
      event.preventDefault();
      update();
      return;
    }
    if (event.target.closest("[data-pwa-install]")) {
      event.preventDefault();
      install();
      return;
    }
    if (event.target.closest("[data-account-live-probe]")) checkLive();
  });

  // Menu do JS dựng sau khi tải trang (SPA, dropdown tự vẽ): áp lại trạng thái khi có nút mới chèn vào DOM.
  const WATCHED = "[data-pwa-install], [data-pwa-update], [data-account-live-indicator]";
  let pending = false;
  function refreshSoon() {
    if (pending) return;
    pending = true;
    window.requestAnimationFrame(() => {
      pending = false;
      sync();
      setLive(state.online);
    });
  }

  function start() {
    setLive(navigator.onLine);
    sync();
    if (!window.MutationObserver) return;
    new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType === 1 && (node.matches(WATCHED) || node.querySelector(WATCHED))) {
            refreshSoon();
            return;
          }
        }
      }
    }).observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();

  window.eAppPWA = { install, update, showHelp, checkLive, sync, isStandalone, state, platform };
})();
