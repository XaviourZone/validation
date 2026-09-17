/* Minimal operational UI overrides. Keeps the existing offline UI structure but
   removes decorative glow and controls that are not part of operator workflow. */
(function () {
  "use strict";

  const css = `
    .radar-logo { box-shadow: none !important; }
    .status-pill.running::before { box-shadow: none !important; }
    .module-card:hover { transform: none !important; }
    .module-card, .kpi-card, .panel, .router-header-panel { box-shadow: none !important; }
    .btn:hover, .refresh-btn:hover { transform: none !important; box-shadow: none !important; }
    .router-status-row { display: none !important; }
    #btn-start-router, #btn-new-parser { display: none !important; }
    #router-page-status-pill, #router-uptime { display: none !important; }
    .pans-config-row { display:flex; gap:16px; align-items:flex-end; }
    .pans-config-field { flex:1; min-width:0; }
    .pans-folder-line { display:flex; gap:8px; }
    .pans-folder-line .form-input { flex:1; }
    .panel-subtitle { font-size:11px; color:var(--text-muted); margin-top:3px; }
    @media (max-width: 760px) {
      .pans-config-row { flex-direction:column; align-items:stretch; }
    }
  `;
  const style = document.createElement("style"); style.id = "validation-console-polish"; style.textContent = css;
  document.head.appendChild(style);

  function clean() {
    const addParser = document.getElementById("btn-new-parser");
    if (addParser) addParser.remove();
    const routerStatus = document.querySelector(".router-status-row");
    if (routerStatus) routerStatus.remove();
    const routerKpi = document.getElementById("kpi-router-status");
    if (routerKpi) {
      const card = routerKpi.closest(".kpi-card");
      if (card) card.remove();
    }
    const badge = document.getElementById("sidebar-router-badge");
    if (badge) { badge.textContent = "Sources"; badge.className = "mini-badge"; }
    const forwarderBadge = document.querySelector("[data-tab='forwarder'] .mini-badge");
    if (forwarderBadge && /not impl/i.test(forwarderBadge.textContent)) {
      forwarderBadge.textContent = "Live"; forwarderBadge.className = "mini-badge running";
    }
  }

  function boot() {
    clean();
    setTimeout(clean, 300);
    setTimeout(clean, 1000);
    setTimeout(clean, 2000);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
