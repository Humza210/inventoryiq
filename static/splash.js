/* InventoryIQ splash controller */
(function () {
  // CONFIG
  const KEY = "inventoryiq_splash_seen";  // session key (per tab)
  const SHOW_ON_INDEX_RELOAD = true;       // show on hard refresh of index page

  function isReload() {
    try {
      const nav = performance.getEntriesByType("navigation")[0];
      return nav && nav.type === "reload";
    } catch (_) {
      // Older browsers
      return performance.navigation && performance.navigation.type === 1;
    }
  }

  function onDomReady(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn, { once: true });
    } else {
      fn();
    }
  }

  onDomReady(() => {
    const el = document.getElementById("splash");
    if (!el) return; // no splash in this page

    // If you want this only on the home page, uncomment the next line:
    // if (!document.body.matches('[data-page="index"]')) { el.remove(); return; }

    const seenThisTab = sessionStorage.getItem(KEY) === "1";
    const shouldShow = SHOW_ON_INDEX_RELOAD ? (!seenThisTab || isReload()) : !seenThisTab;

    if (!shouldShow) {
      el.remove();
      return;
    }

    const hide = () => {
      try { sessionStorage.setItem(KEY, "1"); } catch (_) {}
      el.classList.add("hide");
      setTimeout(() => el.remove(), 500);
    };

    // Wait for full load so big assets don’t flash behind the splash
    window.addEventListener("load", () => setTimeout(hide, 500), { once: true });
  });
})();
