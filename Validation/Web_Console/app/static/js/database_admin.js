/* Database administration UI. PANS is a live XML folder watcher. */
(function () {
  "use strict";
  const api=(url,options)=>fetch(url,Object.assign({headers:{"Content-Type":"application/json"}},options||{}))
    .then(async r=>{const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.error||d.message||`HTTP ${r.status}`);return d;});

  function view(){return document.getElementById("view-database");}

  function makePanel(){
    const v=view(); if(!v||document.getElementById("pans-live-config"))return;
    const panel=document.createElement("div");panel.id="pans-live-config";panel.className="panel";
    panel.innerHTML=`
      <div class="panel-header"><span class="panel-title">PANS XML Source</span><span id="pans-watch-status" class="status-pill stopped">NOT CONFIGURED</span></div>
      <div class="panel-body"><div class="pans-config-row">
        <div class="pans-config-field"><label class="form-label">Source Folder</label>
          <div class="pans-folder-line"><input id="pans-input-folder" class="form-input" type="text" readonly><button type="button" class="btn btn-secondary" id="pans-browse">Browse</button></div>
        </div>
        <button type="button" class="btn btn-primary" id="pans-save">Save</button>
      </div><div id="pans-config-message" class="form-hint" style="margin-top:8px"></div></div>`;
    v.insertBefore(panel,v.firstElementChild||null);
    document.getElementById("pans-browse").onclick=()=>openBrowser(document.getElementById("pans-input-folder"));
    document.getElementById("pans-save").onclick=saveFolder;
    loadConfig();
  }

  async function loadConfig(){
    try{
      const d=await api("/api/database/pans/config");
      const input=document.getElementById("pans-input-folder"),pill=document.getElementById("pans-watch-status");
      if(input)input.value=d.input_dir||"";
      if(pill){pill.textContent=d.input_dir?"CONFIGURED":"NOT CONFIGURED";pill.className=`status-pill ${d.input_dir?"running":"stopped"}`;}
    }catch(e){setMessage(e.message,true);}
  }

  async function saveFolder(){
    const folder=document.getElementById("pans-input-folder").value.trim();
    if(!folder)return setMessage("Select a PANS source folder first.",true);
    try{const d=await api("/api/database/pans/config",{method:"POST",body:JSON.stringify({input_dir:folder})});setMessage(d.restart&&d.restart.message?d.restart.message:"PANS source folder saved.");loadConfig();}
    catch(e){setMessage(e.message,true);}
  }

  function setMessage(message,error){const el=document.getElementById("pans-config-message");if(el){el.textContent=message;el.style.color=error?"var(--accent-rose)":"var(--text-secondary)";}}

  function openBrowser(target){
    const old=document.getElementById("validation-pans-folder-browser");if(old)old.remove();
    const modal=document.createElement("div");modal.id="validation-pans-folder-browser";modal.className="modal-backdrop open";modal.style.zIndex="10100";
    modal.innerHTML=`
      <div class="modal-container" style="max-width:760px;">
        <div class="modal-header"><div class="modal-title">Select PANS XML Folder</div><button class="modal-close-btn" id="pfb-close">✕</button></div>
        <div class="modal-body">
          <div class="form-group"><label class="form-label">Selected Folder</label><input id="pfb-path" class="form-input" readonly></div>
          <div style="display:flex;gap:8px;margin-bottom:10px"><button class="btn btn-secondary" id="pfb-up">Up</button><button class="btn btn-primary" id="pfb-select">Select Folder</button></div>
          <div id="pfb-list" style="max-height:430px;overflow:auto;border:1px solid var(--border-color);border-radius:4px"></div>
          <div id="pfb-error" style="color:var(--accent-rose);margin-top:8px"></div>
        </div>
      </div>`;
    document.body.appendChild(modal);
    const p=document.getElementById("pfb-path"),list=document.getElementById("pfb-list"),err=document.getElementById("pfb-error");
    document.getElementById("pfb-close").onclick=()=>modal.remove();
    document.getElementById("pfb-select").onclick=()=>{if(p.value){target.value=p.value;target.dispatchEvent(new Event("input",{bubbles:true}));target.dispatchEvent(new Event("change",{bubbles:true}));}modal.remove();};
    document.getElementById("pfb-up").onclick=async()=>{const cur=p.value;if(!cur)return;const d=await browse(cur);if(d.parent&&d.parent!==cur)await browse(d.parent);};
    browse(target.value.trim());

    async function browse(path){
      try{
        const d=await api(path?"/api/database/filesystem/browse?path="+encodeURIComponent(path):"/api/database/filesystem/browse");
        if(d.roots){p.value="";render(d.roots);}else{p.value=d.path||"";render(d.entries||[]);}
        err.textContent="";return d;
      }catch(e){err.textContent=e.message;list.innerHTML="";return {};}
    }
    function render(entries){
      list.innerHTML="";
      if(!entries.length){list.innerHTML='<div style="padding:12px;color:var(--text-muted)">No readable folders</div>';return;}
      entries.forEach(e=>{const b=document.createElement("button");b.type="button";b.className="btn btn-secondary";b.style.cssText="display:block;width:100%;text-align:left;margin:3px 0";b.disabled=e.readable===false;b.textContent="📁 "+e.name;b.onclick=()=>browse(e.path);list.appendChild(b);});
    }
  }

  function boot(){makePanel();setTimeout(makePanel,300);setTimeout(makePanel,1000);}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);else boot();
})();