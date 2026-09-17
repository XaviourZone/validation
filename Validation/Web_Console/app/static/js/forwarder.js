/* Validation Data Forwarder operator panel. Loaded as an extension by the existing console. */
(function () {
  "use strict";

  const api = (path, options) => fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, options || {})).then(async (r) => {
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || data.message || `HTTP ${r.status}`);
    return data;
  });

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>\"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[c]));
  }

  function buildPanel() {
    const view = document.getElementById("view-forwarder");
    if (!view) return;
    view.innerHTML = `
      <div class="router-header-panel">
        <div class="router-header-title-row">
          <h2>DATA FORWARDER</h2>
          <span id="fw-status" class="status-pill stopped">● STOPPED</span>
        </div>
        <div class="router-status-row" style="gap:8px; flex-wrap:wrap;">
          <button class="btn btn-success" id="fw-start">▶ Start</button>
          <button class="btn btn-danger" id="fw-stop">■ Stop</button>
          <button class="btn btn-secondary" id="fw-restart">↻ Restart</button>
          <button class="btn btn-secondary" id="fw-reload">⟳ Reload Configuration</button>
          <span style="font-size:11px;color:var(--text-muted);margin-left:8px;">Final XML → enabled destinations</span>
        </div>
      </div>

      <div class="kpi-grid">
        <div class="kpi-card highlight"><div class="kpi-title">Pending XML</div><div class="kpi-value" id="fw-pending">0</div><div class="kpi-subtext">Waiting for downstream delivery</div></div>
        <div class="kpi-card"><div class="kpi-title">Delivered</div><div class="kpi-value" id="fw-delivered">0</div><div class="kpi-subtext">Confirmed deliveries</div></div>
        <div class="kpi-card"><div class="kpi-title">Retrying</div><div class="kpi-value" id="fw-retrying">0</div><div class="kpi-subtext">Temporary delivery failures</div></div>
        <div class="kpi-card"><div class="kpi-title">Failed</div><div class="kpi-value" id="fw-failed">0</div><div class="kpi-subtext" id="fw-last-error">No errors</div></div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div><span class="panel-title">DOWNSTREAM DESTINATIONS</span><span style="font-size:11px;color:var(--text-muted);margin-left:8px;">Secure copy / SFTP delivery targets</span></div>
          <button class="btn btn-primary" id="fw-add">+ Add Forward Destination</button>
        </div>
        <div class="panel-body" style="padding:0;overflow-x:auto;">
          <table class="data-table">
            <thead><tr><th>Name</th><th>Enabled</th><th>Protocol</th><th>Destination</th><th>Remote Folder</th><th>SSH User</th><th>Password</th><th>Actions</th></tr></thead>
            <tbody id="fw-destinations-body"></tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header"><span class="panel-title">RECENT DELIVERY ACTIVITY</span></div>
        <div class="panel-body" style="padding:0;overflow-x:auto;">
          <table class="data-table"><thead><tr><th>Time</th><th>File</th><th>Destination</th><th>State</th><th>Attempts</th><th>Error</th></tr></thead><tbody id="fw-delivery-body"></tbody></table>
        </div>
      </div>

      <div class="modal-backdrop" id="fw-modal">
        <div class="modal-container" style="max-width:760px;">
          <div class="modal-header"><div class="modal-title"><span>⇢</span><span id="fw-modal-title">Add Forward Destination</span></div><button class="modal-close-btn" id="fw-close">✕</button></div>
          <div class="modal-body">
            <input type="hidden" id="fw-editing-name">
            <div class="form-section-title">1. Destination</div>
            <div class="form-row">
              <div class="form-group"><label class="form-label">Destination Name <span class="required">*</span></label><input id="fw-name" class="form-input" placeholder="e.g. DDIODE_PRIMARY"></div>
              <div class="form-group"><label class="form-label">Protocol</label><select id="fw-protocol" class="form-input"><option value="sftp">SFTP / SSH Secure Copy</option><option value="filesystem">Local Filesystem</option></select></div>
            </div>
            <div class="form-group"><label style="display:flex;align-items:center;gap:8px;font-size:13px;"><input type="checkbox" id="fw-enabled"> Enable destination</label></div>
            <div class="form-section-title">2. SFTP / SSH Connection</div>
            <div class="form-row">
              <div class="form-group"><label class="form-label">Destination IP / Host <span class="required">*</span></label><input id="fw-host" class="form-input" placeholder="40.1.1.1"></div>
              <div class="form-group"><label class="form-label">SSH Port</label><input id="fw-port" type="number" min="1" max="65535" class="form-input" value="22"></div>
            </div>
            <div class="form-row">
              <div class="form-group"><label class="form-label">SSH Username <span class="required">*</span></label><input id="fw-user" class="form-input" placeholder="ddiode"></div>
              <div class="form-group"><label class="form-label">SSH Password</label><input id="fw-password" type="password" class="form-input" autocomplete="new-password" placeholder="Leave blank to keep existing password"></div>
            </div>
            <div class="form-group"><label class="form-label">Folder Location for Secure Copy to Destination <span class="required">*</span></label><input id="fw-path" class="form-input" placeholder="/home/ddiode/txserver/in/"></div>
            <div class="form-group"><label class="form-label">Private Key File (optional)</label><input id="fw-key" class="form-input" placeholder="Leave empty to use password authentication"></div>
            <div class="form-row">
              <div class="form-group"><label class="form-label">Connection Timeout (seconds)</label><input id="fw-timeout" type="number" min="1" class="form-input" value="10"></div>
              <div class="form-group"><label style="display:flex;align-items:center;gap:8px;font-size:13px;margin-top:25px;"><input type="checkbox" id="fw-verify" checked> Verify transferred file size</label></div>
            </div>
            <div id="fw-form-error" style="display:none;margin-top:12px;padding:10px;border:1px solid var(--accent-rose);border-radius:6px;color:var(--accent-rose);"></div>
          </div>
          <div class="modal-footer"><button class="btn btn-secondary" id="fw-cancel">Cancel</button><button class="btn btn-primary" id="fw-test">Test Connection</button><button class="btn btn-success" id="fw-save">Save Destination</button></div>
        </div>
      </div>`;

    bindControls();
    refresh();
  }

  function setStatus(status) {
    const el = document.getElementById("fw-status");
    if (!el) return;
    const running = status === "RUNNING";
    el.textContent = `● ${status}`;
    el.className = `status-pill ${running ? "running" : (status === "STARTING" ? "degraded" : "stopped")}`;
    const badge = document.getElementById("sidebar-forwarder-badge");
    if (badge) { badge.textContent = running ? "Live" : status; badge.className = `mini-badge ${running ? "running" : "stopped"}`; }
  }

  async function refreshStatus() {
    try { const d = await api("/api/forwarder/status"); setStatus(d.status || "UNKNOWN"); } catch (_) { setStatus("OFFLINE"); }
  }

  async function refreshMetrics() {
    try {
      const d = await api("/api/forwarder/metrics");
      const states = d.states || {};
      document.getElementById("fw-pending").textContent = d.pending_files || 0;
      document.getElementById("fw-delivered").textContent = states.DELIVERED || 0;
      document.getElementById("fw-retrying").textContent = states.RETRYING || 0;
      document.getElementById("fw-failed").textContent = states.FAILED || 0;
      document.getElementById("fw-last-error").textContent = d.last_error ? String(d.last_error).substring(0, 55) : "No errors";
    } catch (_) {}
  }

  async function refreshDestinations() {
    try {
      const d = await api("/api/forwarder/destinations");
      const body = document.getElementById("fw-destinations-body");
      body.innerHTML = "";
      (d.destinations || []).forEach(dest => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td><strong>${esc(dest.name)}</strong></td><td><span class="status-pill ${dest.enabled ? "running" : "stopped"}" style="font-size:9px;">${dest.enabled ? "ENABLED" : "DISABLED"}</span></td><td>${esc(dest.protocol.toUpperCase())}</td><td class="mono">${esc(dest.host)}:${esc(dest.port)}</td><td class="mono">${esc(dest.remote_path)}</td><td>${esc(dest.username)}</td><td>${dest.password_configured ? "● Configured" : "○ Not configured"}</td><td><div class="btn-group"><button class="btn btn-secondary fw-edit" data-name="${esc(dest.name)}">Edit</button><button class="btn btn-secondary fw-test-row" data-name="${esc(dest.name)}">Test</button><button class="btn ${dest.enabled ? "btn-danger" : "btn-success"} fw-toggle" data-name="${esc(dest.name)}">${dest.enabled ? "Disable" : "Enable"}</button><button class="btn btn-danger fw-delete" data-name="${esc(dest.name)}">Delete</button></div></td>`;
        body.appendChild(tr);
      });
      body.querySelectorAll(".fw-edit").forEach(b => b.onclick = () => openModal((d.destinations || []).find(x => x.name === b.dataset.name)));
      body.querySelectorAll(".fw-test-row").forEach(b => b.onclick = () => testDestination(b.dataset.name));
      body.querySelectorAll(".fw-toggle").forEach(b => b.onclick = () => toggleDestination(b.dataset.name, b.textContent.trim() === "Enable"));
      body.querySelectorAll(".fw-delete").forEach(b => b.onclick = () => deleteDestination(b.dataset.name));
    } catch (_) {}
  }

  async function refreshDeliveries() {
    try {
      const d = await api("/api/forwarder/deliveries");
      const body = document.getElementById("fw-delivery-body"); body.innerHTML = "";
      (d.deliveries || []).forEach(x => { const tr = document.createElement("tr"); tr.innerHTML = `<td class="mono">${esc(x.updated_at)}</td><td class="mono">${esc(x.filename)}</td><td>${esc(x.destination)}</td><td>${esc(x.state)}</td><td>${esc(x.attempts)}</td><td>${esc(x.last_error || "")}</td>`; body.appendChild(tr); });
    } catch (_) {}
  }

  function refresh() { refreshStatus(); refreshMetrics(); refreshDestinations(); refreshDeliveries(); }

  function bindControls() {
    document.getElementById("fw-add").onclick = () => openModal(null);
    document.getElementById("fw-close").onclick = closeModal;
    document.getElementById("fw-cancel").onclick = closeModal;
    document.getElementById("fw-save").onclick = saveDestination;
    document.getElementById("fw-test").onclick = testCurrent;
    document.getElementById("fw-start").onclick = () => serviceAction("start");
    document.getElementById("fw-stop").onclick = () => serviceAction("stop");
    document.getElementById("fw-restart").onclick = () => serviceAction("restart");
    document.getElementById("fw-reload").onclick = () => serviceAction("reload");
    document.getElementById("fw-protocol").onchange = () => { const s = document.getElementById("fw-protocol").value === "sftp"; ["fw-host","fw-port","fw-user","fw-password","fw-path","fw-key"].forEach(id => document.getElementById(id).disabled = !s); };
  }

  async function serviceAction(action) {
    try { await api(`/api/forwarder/${action}`, { method: "POST", body: "{}" }); refresh(); } catch (e) { alert(e.message); }
  }

  function openModal(dest) {
    const modal = document.getElementById("fw-modal"); modal.classList.add("active");
    document.getElementById("fw-modal-title").textContent = dest ? "Edit Forward Destination" : "Add Forward Destination";
    document.getElementById("fw-editing-name").value = dest ? dest.name : "";
    document.getElementById("fw-name").value = dest ? dest.name : "";
    document.getElementById("fw-name").disabled = !!dest;
    document.getElementById("fw-enabled").checked = dest ? !!dest.enabled : false;
    document.getElementById("fw-protocol").value = dest ? dest.protocol : "sftp";
    document.getElementById("fw-host").value = dest ? dest.host : "";
    document.getElementById("fw-port").value = dest ? dest.port : 22;
    document.getElementById("fw-user").value = dest ? dest.username : "";
    document.getElementById("fw-password").value = "";
    document.getElementById("fw-path").value = dest ? dest.remote_path : "";
    document.getElementById("fw-key").value = dest ? dest.private_key_file : "";
    document.getElementById("fw-timeout").value = dest ? dest.connect_timeout_seconds : 10;
    document.getElementById("fw-verify").checked = dest ? !!dest.verify_remote_size : true;
    document.getElementById("fw-form-error").style.display = "none";
  }

  function closeModal() { document.getElementById("fw-modal").classList.remove("active"); }

  function formPayload() {
    return {
      name: document.getElementById("fw-name").value.trim(), enabled: document.getElementById("fw-enabled").checked,
      protocol: document.getElementById("fw-protocol").value, host: document.getElementById("fw-host").value.trim(),
      port: Number(document.getElementById("fw-port").value), username: document.getElementById("fw-user").value.trim(),
      password: document.getElementById("fw-password").value, remote_path: document.getElementById("fw-path").value.trim(),
      private_key_file: document.getElementById("fw-key").value.trim(), connect_timeout_seconds: Number(document.getElementById("fw-timeout").value),
      verify_remote_size: document.getElementById("fw-verify").checked
    };
  }

  async function saveDestination() {
    const payload = formPayload();
    const err = document.getElementById("fw-form-error");
    if (!payload.name || !payload.host || !payload.remote_path || !payload.username) { err.textContent = "Name, host, remote folder and SSH username are required."; err.style.display = "block"; return; }
    try { await api("/api/forwarder/destinations/save", { method: "POST", body: JSON.stringify(payload) }); closeModal(); refresh(); }
    catch (e) { err.textContent = e.message; err.style.display = "block"; }
  }

  async function testCurrent() {
    const name = document.getElementById("fw-name").value.trim();
    const err = document.getElementById("fw-form-error");
    if (!name) { err.textContent = "Save the destination before testing it."; err.style.display = "block"; return; }
    try { await api("/api/forwarder/test", { method: "POST", body: JSON.stringify({ name }) }); err.textContent = "Connection and remote folder test succeeded."; err.style.display = "block"; err.style.color = "var(--accent-emerald)"; }
    catch (e) { err.textContent = `Connection test failed: ${e.message}`; err.style.display = "block"; }
  }

  async function testDestination(name) { try { const d = await api("/api/forwarder/test", { method: "POST", body: JSON.stringify({ name }) }); alert(d.message || "Connection test succeeded"); } catch (e) { alert(`Connection test failed: ${e.message}`); } }
  async function toggleDestination(name, enable) { try { await api(`/api/forwarder/destinations/${encodeURIComponent(name)}/${enable ? "enable" : "disable"}`, { method: "POST", body: "{}" }); refresh(); } catch (e) { alert(e.message); } }
  async function deleteDestination(name) { if (!confirm(`Delete Forward Destination '${name}'?`)) return; try { await api(`/api/forwarder/destinations/${encodeURIComponent(name)}/delete`, { method: "POST", body: "{}" }); refresh(); } catch (e) { alert(e.message); } }

  function init() {
    buildPanel();
    setInterval(() => { if (!document.hidden) refresh(); }, 3000);
    const nav = document.querySelector('.nav-item[data-tab="forwarder"]');
    if (nav) { const badge = nav.querySelector('.mini-badge'); if (badge) badge.id = "sidebar-forwarder-badge"; }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
