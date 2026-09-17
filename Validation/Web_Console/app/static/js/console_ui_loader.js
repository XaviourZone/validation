/* Deterministic UI loader. Core console.js owns lifecycle/navigation;
   these extensions provide Router/Forwarder/PANS operator features. */
(function () {
  "use strict";

  const files = [
    ["/static/js/forwarder.js", "forwarder"],
    ["/static/js/router_admin.js", "router-admin"],
    ["/static/js/database_admin.js", "database-admin"],
    ["/static/js/console_polish.js", "minimal-ui"]
  ];

  function loadOne(url, key) {
    window.__validationLoadedScripts = window.__validationLoadedScripts || {};
    if (window.__validationLoadedScripts[key]) return Promise.resolve();

    return new Promise(resolve => {
      const s = document.createElement("script");
      s.src = url + "?v=20260918-r2";
      s.async = false;
      s.dataset.validationExtension = key;
      s.onload = () => { window.__validationLoadedScripts[key] = true; resolve(); };
      s.onerror = () => {
        console.error("Validation UI extension failed:", url);
        resolve();
      };
      document.body.appendChild(s);
    });
  }

  async function boot() {
    for (const [url, key] of files) {
      await loadOne(url, key);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, {once:true});
  } else {
    boot();
  }
})();