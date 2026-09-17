/* Router administration extension: filesystem folder selection, file-pattern presets,
   parser mapping editor and automatic Router reload after source configuration changes. */
(function () {
  "use strict";

  const esc = v => String(v == null ? "" : v).replace(/[&<>\"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]));
  const api = (url, options) => fetch(url, Object.assign({headers:{"Content-Type":"application/json"}}, options || {})).then(async r => {
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || d.message || `HTTP ${r.status}`);
    return d;
  });

  function installFetchReload() {
    if (window.__validationRouterReloadPatch) return;
    window.__validationRouterReloadPatch = true;
    const original = window.fetch.bind(window);
    window.fetch = async function (input, init) {
      const response = await original(input, init);
      let url = typeof input === "string" ? input : (input && input.url) || "";
      if (response.ok && /^\/api\/router\/sources\/.+\/(save|delete|enable|disable)$/.test(url)) {
        // Existing console source actions write YAML. Apply them immediately to the
        // continuously-running Router without adding a Stop/Start workflow.
        original("/api/router/reload", {method:"POST", headers:{"Content-Type":"application/json"}, body:"{}"}).catch(() => {});
      }
      if (response.ok && url === "/api/router/sources/save") {
        original("/api/router/reload", {method:"POST", headers:{"Content-Type":"application/json"}, body:"{}"}).catch(() => {});
      }
      return response;
    };
  }

  function ensureBrowseButton() {
    const folder = document.getElementById("src-folder");
    if (!folder || document.getElementById("router-browse-folder")) return;
    const wrapper = folder.parentElement;
    if (!wrapper) return;
    const button = document.createElement("button");
    button.type = "button";
    button.id = "router-browse-folder";
    button.className = "btn btn-secondary";
    button.style.cssText = "margin-top:6px;padding:5px 10px;";
    button.textContent = "Browse…";
    button.onclick = () => openFolderBrowser(folder);
    wrapper.appendChild(button);

    const patterns = document.getElementById("src-patterns");
    if (patterns && !document.getElementById("router-pattern-presets")) {
      const select = document.createElement("select");
      select.id = "router-pattern-presets";
      select.className = "form-input";
      select.style.cssText = "margin-top:6px;";
      ["CSV (*.csv)","XML (*.xml)","JSON (*.json)","Text (*.txt)","NMEA (*.nmea)","All (*)","Custom"].forEach((label, i) => {
        const o = document.createElement("option"); o.value = ["*.csv","*.xml","*.json","*.txt","*.nmea","*",""][i]; o.textContent = label; select.appendChild(o);
      });
      select.onchange = () => { if (select.value) patterns.value = select.value; };
      patterns.parentElement && patterns.parentElement.appendChild(select);
    }
  }

  function openFolderBrowser(target) {
    let modal = document.getElementById("router-folder-browser");
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "router-folder-browser";
      modal.className = "modal-backdrop active";
      modal.style.zIndex = "10050";
      modal.innerHTML = `
        <div class="modal-container" style="max-width:780px;">
          <div class="modal-header"><div class="modal-title">Select input folder</div><button class="modal-close-btn" id="rfb-close">✕</button></div>
          <div class="modal-body">
            <div class="form-group"><label class="form-label">Current folder</label><input id="rfb-path" class="form-input" value="/"></div>
            <div style="display:flex;gap:8px;margin-bottom:10px;"><button class="btn btn-secondary" id="rfb-up">Up</button><button class="btn btn-primary" id="rfb-select">Select this folder</button></div>
            <div id="rfb-list" style="max-height:420px;overflow:auto;border:1px solid var(--border-color);border-radius:6px;"></div>
            <div id="rfb-error" style="color:var(--accent-rose);margin-top:8px;"></div>
          </div>
        </div>`;
      document.body.appendChild(modal);
      document.getElementById("rfb-close").onclick = () => modal.remove();
      document.getElementById("rfb-select").onclick = () => { target.value = document.getElementById("rfb-path").value; modal.remove(); target.dispatchEvent(new Event("change", {bubbles:true})); };
      document.getElementById("rfb-up").onclick = () => browse(document.getElementById("rfb-path").value).then(d => d.parent && browse(d.parent));
    }
    browse(document.getElementById("rfb-path").value);

    async function browse(path) {
      try {
        const d = await api(`/api/router/filesystem/browse?path=${encodeURIComponent(path)}`);
        document.getElementById("rfb-path").value = d.path;
        const list = document.getElementById("rfb-list"); list.innerHTML = "";
        (d.entries || []).forEach(e => {
          const b = document.createElement("button");
          b.className = "btn btn-secondary";
          b.style.cssText = "display:block;width:100%;text-align:left;margin:3px 0;";
          b.disabled = e.readable === false;
          b.textContent = `📁 ${e.name}`;
          b.onclick = () => browse(e.path);
          list.appendChild(b);
        });
        if (!d.entries || !d.entries.length) list.innerHTML = `<div style="padding:12px;color:var(--text-muted);">No readable subfolders</div>`;
        return d;
      } catch (e) {
        document.getElementById("rfb-error").textContent = e.message;
        return {};
      }
    }
  }

  function installMappingPanel() {
    const parserView = document.getElementById("view-parser");
    if (!parserView || document.getElementById("btn-parser-mapping")) return;
    const firstPanel = parserView.querySelector(".kpi-grid") || parserView.firstElementChild;
    const holder = document.createElement("div");
    holder.style.cssText = "margin:0 0 20px 0;display:flex;justify-content:flex-end;";
    holder.innerHTML = `<button class="btn btn-primary" id="btn-parser-mapping">⚙ Parser Mapping — 41 XML Fields</button>`;
    if (firstPanel) parserView.insertBefore(holder, firstPanel); else parserView.appendChild(holder);
    document.getElementById("btn-parser-mapping").onclick = openMapping;
  }

  async function openMapping() {
    let modal = document.getElementById("parser-mapping-modal");
    if (!modal) {
      modal = document.createElement("div"); modal.id = "parser-mapping-modal"; modal.className = "modal-backdrop active"; modal.style.zIndex = "10040";
      modal.innerHTML = `
        <div class="modal-container" style="max-width:1200px;width:96vw;max-height:92vh;">
          <div class="modal-header"><div class="modal-title">Parser Mapping — 41 Canonical XML Fields</div><button class="modal-close-btn" id="pm-close">✕</button></div>
          <div class="modal-body" style="overflow:auto;">
            <div class="form-row" style="align-items:end;">
              <div class="form-group"><label class="form-label">Parser</label><select id="pm-parser" class="form-input"></select></div>
              <div class="form-group"><label class="form-label">Input format</label><select id="pm-format" class="form-input"><option>auto</option><option>csv</option><option>json</option><option>xml</option><option>text</option></select></div>
            </div>
            <div style="font-size:11px;color:var(--text-muted);margin:8px 0 12px;">For each XML field enter candidates in priority order. Example: incoming:mmsi → ais_state:mmsi → wrs:wrs_mmsi → default:UNKNOWN.</div>
            <div style="overflow:auto;"><table class="data-table"><thead><tr><th>#</th><th>XML Tag</th><th>Priority 1</th><th>Priority 2</th><th>Priority 3</th><th>Priority 4</th><th>Priority 5</th></tr></thead><tbody id="pm-body"></tbody></table></div>
          </div>
          <div class="modal-footer"><button class="btn btn-secondary" id="pm-cancel">Cancel</button><button class="btn btn-success" id="pm-save">Save Mapping</button></div>
        </div>`;
      document.body.appendChild(modal);
      document.getElementById("pm-close").onclick = () => modal.remove();
      document.getElementById("pm-cancel").onclick = () => modal.remove();
    }
    const parserSelect = document.getElementById("pm-parser");
    const p = await api("/api/parser/mapping/parsers");
    parserSelect.innerHTML = "";
    (p.parsers || []).forEach(name => { const o=document.createElement("option"); o.value=name; o.textContent=name; parserSelect.appendChild(o); });
    parserSelect.onchange = loadMapping;
    if (!parserSelect.value) parserSelect.value = (p.parsers || ["GENERIC"])[0];
    await loadMapping();

    async function loadMapping() {
      const name = parserSelect.value || "GENERIC";
      const d = await api(`/api/parser/mapping?parser=${encodeURIComponent(name)}`);
      document.getElementById("pm-format").value = d.mapping.format || "auto";
      const body = document.getElementById("pm-body"); body.innerHTML = "";
      const fields = await api("/api/parser/mapping/fields");
      (fields.fields || []).forEach((field, idx) => {
        const candidates = ((d.mapping.fields || {})[field] || []).slice(0,5);
        while (candidates.length < 5) candidates.push("");
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${idx+1}</td><td class="mono" style="min-width:230px;">${esc(field)}</td>` + candidates.map((v,i)=>`<td><input class="form-input pm-candidate" data-field="${esc(field)}" data-priority="${i}" value="${esc(v)}" placeholder="incoming:field"></td>`).join("");
        body.appendChild(tr);
      });
    }

    document.getElementById("pm-save").onclick = async () => {
      const name = parserSelect.value;
      const fields = {};
      document.querySelectorAll(".pm-candidate").forEach(input => {
        const field = input.dataset.field; const value = input.value.trim();
        fields[field] = fields[field] || []; if (value) fields[field].push(value);
      });
      try {
        await api("/api/parser/mapping/save", {method:"POST", body:JSON.stringify({parser:name,mapping:{format:document.getElementById("pm-format").value,fields}})});
        alert(`Mapping for ${name} saved successfully.`);
        modal.remove();
      } catch (e) { alert(e.message); }
    };
  }

  function boot() {
    installFetchReload();
    ensureBrowseButton();
    installMappingPanel();
    setTimeout(() => { ensureBrowseButton(); installMappingPanel(); }, 1000);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
