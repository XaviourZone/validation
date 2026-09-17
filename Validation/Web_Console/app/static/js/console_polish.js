/* Minimal operational UI and robust folder-picker overrides. */
(function () {
  "use strict";
  const style=document.createElement("style"); style.id="validation-console-polish"; style.textContent=`
    .radar-logo{box-shadow:none!important}.status-pill.running::before{box-shadow:none!important}
    .module-card:hover{transform:none!important}.module-card,.kpi-card,.panel,.router-header-panel{box-shadow:none!important}
    .btn:hover,.refresh-btn:hover{transform:none!important;box-shadow:none!important}
    .router-status-row{display:none!important}#btn-start-router,#btn-new-parser{display:none!important}
    #router-page-status-pill,#router-uptime{display:none!important}
    .pans-config-row{display:flex;gap:16px;align-items:flex-end}.pans-config-field{flex:1;min-width:0}
    .pans-folder-line{display:flex;gap:8px}.pans-folder-line .form-input{flex:1}
    .panel-subtitle{font-size:11px;color:var(--text-muted);margin-top:3px}
    @media(max-width:760px){.pans-config-row{flex-direction:column;align-items:stretch}}
  `; document.head.appendChild(style);

  const api=(url,options)=>fetch(url,Object.assign({headers:{"Content-Type":"application/json"}},options||{})).then(async r=>{const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.error||d.message||`HTTP ${r.status}`);return d;});

  function clean(){
    const addParser=document.getElementById("btn-new-parser"); if(addParser)addParser.remove();
    const routerStatus=document.querySelector("#view-router .router-status-row"); if(routerStatus)routerStatus.remove();
    const routerKpi=document.getElementById("kpi-router-status"); if(routerKpi){const card=routerKpi.closest(".kpi-card");if(card)card.remove();}
    const badge=document.getElementById("sidebar-router-badge");if(badge){badge.textContent="Sources";badge.className="mini-badge";}
    const fw=document.querySelector("[data-tab='forwarder'] .mini-badge");if(fw&&/not impl/i.test(fw.textContent)){fw.textContent="Live";fw.className="mini-badge running";}
  }

  function installRobustRouterBrowse(){
    const old=document.getElementById("router-browse-folder"),target=document.getElementById("src-folder");
    if(!old||!target||old.dataset.robust==="1")return; old.dataset.robust="1"; old.onclick=()=>openBrowser(target);
  }

  function openBrowser(target){
    let modal=document.getElementById("router-folder-browser");
    if(!modal){
      modal=document.createElement("div");modal.id="router-folder-browser";modal.className="modal-backdrop active";modal.style.zIndex="10050";
      modal.innerHTML=`<div class="modal-container" style="max-width:780px"><div class="modal-header"><div class="modal-title">Select input folder</div><button class="modal-close-btn" id="rpb-close">✕</button></div><div class="modal-body"><div class="form-group"><label class="form-label">Selected folder</label><input id="rpb-path" class="form-input" readonly></div><div style="display:flex;gap:8px;margin-bottom:10px"><button class="btn btn-secondary" id="rpb-up">Up</button><button class="btn btn-primary" id="rpb-select">Select this folder</button></div><div id="rpb-list" style="max-height:420px;overflow:auto;border:1px solid var(--border-color);border-radius:6px"></div><div id="rpb-error" style="color:var(--accent-rose);margin-top:8px"></div></div></div>`;
      document.body.appendChild(modal);
      document.getElementById("rpb-close").onclick=()=>modal.remove();
      document.getElementById("rpb-select").onclick=()=>{const p=document.getElementById("rpb-path").value;if(p){target.value=p;target.dispatchEvent(new Event("change",{bubbles:true}));}modal.remove();};
      document.getElementById("rpb-up").onclick=async()=>{const p=document.getElementById("rpb-path").value;if(p){const d=await browse(p);if(d.parent)await browse(d.parent);}};
    }
    browse(target.value.trim());
    async function browse(path){try{const d=await api(`/api/router/filesystem/browse${path?`?path=${encodeURIComponent(path)}`:""}`);if(d.roots){document.getElementById("rpb-path").value="";render(d.roots);}else{document.getElementById("rpb-path").value=d.path;render(d.entries||[]);}document.getElementById("rpb-error").textContent="";return d;}catch(e){document.getElementById("rpb-error").textContent=e.message;return {};}}
    function render(entries){const list=document.getElementById("rpb-list");list.innerHTML="";if(!entries.length){list.innerHTML=`<div style="padding:12px;color:var(--text-muted)">No readable folders</div>`;return;}entries.forEach(e=>{const b=document.createElement("button");b.type="button";b.className="btn btn-secondary";b.style.cssText="display:block;width:100%;text-align:left;margin:3px 0";b.disabled=e.readable===false;b.textContent=`📁 ${e.name}`;b.onclick=()=>browse(e.path);list.appendChild(b);});}
  }

  function boot(){clean();installRobustRouterBrowse();setTimeout(()=>{clean();installRobustRouterBrowse();},300);setTimeout(()=>{clean();installRobustRouterBrowse();},1000);setTimeout(()=>{clean();installRobustRouterBrowse();},2000);}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);else boot();
})();
