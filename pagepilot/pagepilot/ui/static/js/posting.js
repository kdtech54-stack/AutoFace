/* Posting — Reel Post task builder */
let PST = { pages: [], accounts: {}, acctStatus: {}, categories: [],
            presets: [], sel: new Set(), liveOnly: false, catFilter: "" };

function debounce(fn, ms){
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

document.addEventListener("DOMContentLoaded", () => {
  el("pq").addEventListener("input", debounce(renderPages, 250));
  el("pCatFilter").addEventListener("change", e => { PST.catFilter = e.target.value; renderPages(); });
  el("chipAll").onclick = () => setLive(false);
  el("chipLive").onclick = () => setLive(true);
  el("pSelAll").onchange = onSelAll;
  el("startTaskBtn").onclick = startTask;
  el("reloadTasks").onclick = loadTasks;
  loadAll();
});

function setLive(v){
  PST.liveOnly = v;
  el("chipAll").classList.toggle("on", !v);
  el("chipLive").classList.toggle("on", v);
  renderPages();
}

async function loadAll(){
  const r = await api("GET", "/api/pages");
  if(r.ok && r.data){
    PST.pages = r.data.pages || [];
    PST.categories = r.data.categories || [];
    (r.data.accounts || []).forEach(a => { PST.accounts[a.id] = a.label; });
    renderCatFilter();
  }
  await loadAccountStatus();  /* silent: accounts module may not exist yet */
  await loadPresets();        /* silent: presets module may not exist yet */
  renderPages();
  loadTasks();
}

async function loadAccountStatus(){
  try{
    const r = await fetch("/api/accounts");
    const j = await r.json();
    let list = [];
    if(j.ok){
      list = Array.isArray(j.data) ? j.data : (j.data.accounts || j.data.items || []);
    }
    list.forEach(a => { PST.acctStatus[a.id] = a.status; });
  }catch(e){ /* fall back to page status for the Live Only filter */ }
}

function isLivePage(p){
  const st = PST.acctStatus[p.account_id];
  if(st) return st === "live" || st === "logged_in";
  return p.status === "active";
}

async function loadPresets(){
  try{
    const r = await fetch("/api/presets");
    const j = await r.json();
    let list = [];
    if(j.ok){
      list = Array.isArray(j.data) ? j.data : (j.data.presets || j.data.items || []);
    }
    PST.presets = list.filter(p => !p.type || p.type === "reel");
  }catch(e){ PST.presets = []; }
  renderPresets();
}

function renderPresets(){
  const box = el("presetList");
  if(!PST.presets.length){
    box.innerHTML = '<div class="empty">No reel presets yet — create them under Content Presets.<br>' +
      'Task bina preset ke bhi queue ho sakta hai.</div>';
    return;
  }
  box.innerHTML = PST.presets.map(p =>
    '<label style="display:flex;gap:10px;align-items:center;padding:8px 0;' +
    'border-bottom:1px solid #131e38;cursor:pointer">' +
    '<input type="checkbox" value="' + p.id + '">' +
    '<span><b>' + esc(p.title) + '</b> ' + (p.type ? statusBadge(p.type) : "") + '</span></label>'
  ).join("");
}

function renderCatFilter(){
  el("pCatFilter").innerHTML = '<option value="">All Categories</option>' +
    PST.categories.map(c => '<option value="' + c.id + '">' + esc(c.name) + '</option>').join("");
}

function visiblePages(){
  const q = el("pq").value.trim().toLowerCase();
  return PST.pages.filter(p => {
    if(PST.catFilter && String(p.category_id) !== PST.catFilter) return false;
    if(PST.liveOnly && !isLivePage(p)) return false;
    if(q && !((p.name || "").toLowerCase().includes(q) ||
              (p.slug || "").toLowerCase().includes(q))) return false;
    return true;
  });
}

function renderPages(){
  const rows = visiblePages();
  const tb = el("pPagesBody");
  if(!rows.length){
    tb.innerHTML = '<tr><td colspan="5" class="empty">No pages match. Add pages under Pages &amp; Groups.</td></tr>';
  } else {
    tb.innerHTML = rows.map((p, i) =>
      '<tr><td><input type="checkbox" data-pid="' + p.id + '"' +
        (PST.sel.has(p.id) ? " checked" : "") + '></td>' +
      '<td>' + (i + 1) + '</td>' +
      '<td><b>' + esc(p.name) + '</b>' +
        (p.slug ? '<div class="muted" style="font-size:11px">' + esc(p.slug) + '</div>' : "") + '</td>' +
      '<td>' + esc(p.account) + '</td>' +
      '<td>' + esc(p.category) + '</td></tr>'
    ).join("");
  }
  tb.querySelectorAll("input[data-pid]").forEach(cb => {
    cb.onchange = () => {
      const id = +cb.dataset.pid;
      if(cb.checked) PST.sel.add(id); else PST.sel.delete(id);
      updateSel();
    };
  });
  el("chipAll").classList.toggle("on", !PST.liveOnly);
  el("chipLive").classList.toggle("on", PST.liveOnly);
  updateSel(rows);
}

function onSelAll(e){
  const rows = visiblePages();
  const on = e.target.checked;
  rows.forEach(p => { if(on) PST.sel.add(p.id); else PST.sel.delete(p.id); });
  renderPages();
}

function updateSel(rows){
  rows = rows || visiblePages();
  el("pSelInfo").textContent = "Selected: " + PST.sel.size + " of " + rows.length;
  el("pSelAll").checked = rows.length > 0 && rows.every(p => PST.sel.has(p.id));
  el("builderStatus").textContent = PST.sel.size ? "READY" : "IDLE";
  el("builderStatus").className = "badge " + (PST.sel.size ? "b-cyan" : "b-gray");
}

async function startTask(){
  const pageIds = [...PST.sel];
  if(!pageIds.length){ toast("Select at least one page", "err"); return; }
  const presetIds = [...document.querySelectorAll("#presetList input:checked")]
    .map(c => +c.value);
  const body = {
    name: el("taskName").value.trim(),
    kind: "reel_post",
    page_ids: pageIds,
    preset_ids: presetIds,
    config: {
      min_spacing: +el("cfgMin").value || 3,
      max_spacing: +el("cfgMax").value || 10,
      switch_on_errors: +el("cfgSwitch").value || 10,
      loop: el("cfgLoop").checked
    }
  };
  const r = await api("POST", "/api/tasks", body);
  if(r.ok){
    toast("Task queued — execution starts with the automation engine milestone", "okk");
    PST.sel.clear();
    el("taskName").value = "";
    renderPages();
    loadTasks();
  }
}

async function loadTasks(){
  const r = await api("GET", "/api/tasks");
  const tb = el("tasksBody");
  if(!r.ok || !r.data){
    tb.innerHTML = '<tr><td colspan="9" class="empty">Could not load tasks.</td></tr>';
    return;
  }
  const tasks = r.data;
  if(!tasks.length){
    tb.innerHTML = '<tr><td colspan="9" class="empty">No tasks yet — build one above.</td></tr>';
    return;
  }
  tb.innerHTML = tasks.map(t => {
    const c = t.counts || {};
    const cancellable = t.status === "idle" || t.status === "running";
    return '<tr><td>' + t.id + '</td>' +
      '<td><b>' + esc(t.name) + '</b></td>' +
      '<td>' + esc(t.kind) + '</td>' +
      '<td>' + statusBadge(t.status) + '</td>' +
      '<td>' + (c.queued || 0) + '</td>' +
      '<td>' + (c.done || 0) + '</td>' +
      '<td>' + (c.failed || 0) + '</td>' +
      '<td class="muted">' + fmtDT(t.created_at) + '</td>' +
      '<td style="white-space:nowrap">' +
      '<button class="btn btn-sm" data-view="' + t.id + '">View</button>' +
      (cancellable ? ' <button class="btn btn-sm btn-danger" data-cancel="' + t.id + '">Cancel</button>' : "") +
      '</td></tr>';
  }).join("");
  tb.querySelectorAll("[data-view]").forEach(b => { b.onclick = () => viewTask(+b.dataset.view); });
  tb.querySelectorAll("[data-cancel]").forEach(b => { b.onclick = () => cancelTask(+b.dataset.cancel); });
}

async function viewTask(id){
  const r = await api("GET", "/api/tasks/" + id);
  if(!r.ok || !r.data) return;
  const t = r.data;
  const rows = (t.items || []).map((it, i) =>
    '<tr><td>' + (i + 1) + '</td>' +
    '<td>' + esc(it.page) + '</td>' +
    '<td>' + esc(it.preset) + '</td>' +
    '<td>' + statusBadge(it.status) + '</td>' +
    '<td class="muted">' + fmtDT(it.executed_at) + '</td></tr>'
  ).join("");
  openModal(
    '<div class="modal-head"><h3>Task #' + t.id + ' — ' + esc(t.name) + '</h3>' +
    '<button class="modal-x" onclick="closeModal()">×</button></div>' +
    '<div class="modal-body"><div class="table-wrap"><table class="table">' +
    '<thead><tr><th>STT</th><th>PAGE</th><th>PRESET</th><th>STATUS</th><th>EXECUTED</th></tr></thead>' +
    '<tbody>' + (rows || '<tr><td colspan="5" class="empty">No items.</td></tr>') + '</tbody>' +
    '</table></div></div>' +
    '<div class="modal-foot"><button class="btn btn-ghost" onclick="closeModal()">Close</button></div>',
    true);
}

async function cancelTask(id){
  if(!await confirmDialog("Pause task #" + id + "? Queued items will be skipped.")) return;
  const r = await api("POST", "/api/tasks/" + id + "/cancel");
  if(r.ok){
    toast("Task paused — " + r.data.cancelled + " item(s) skipped", "okk");
    loadTasks();
  }
}
