/* Deterministic UI loader. Prevents extension-order races and browser cache confusion. */
(function () {
  "use strict";
  const files = [
    ["/static/js/forwarder.js","forwarder"],
    ["/static/js/router_admin.js","router-admin"],
    ["/static/js/database_admin.js","database-admin"],
    ["/static/js/console_polish.js","minimal-ui"]
  ];

  function loadOne(url, key) {
    if (window.__validationLoadedScripts && window.__validationLoadedScripts[key]) return;
    window.__validationLoadedScripts = window.__validationLoadedScripts || {};
    const s = document.createElement("script");
    s.src = url + "?v=20260918";
    s.async = false;
    s.dataset.validationExtension = key;
    s.onload = () => { window.__validationLoadedScripts[key] = true; };
    s.onerror = () => { console.error("Validation UI extension failed:", url); };
    document.body.appendChild(s);
  }

  function boot() {
    for (const [url,key] of files) loadOne(url,key);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
