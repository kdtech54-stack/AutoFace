/* Accounts module: fleet hub, import, live check, bulk actions */
const A = {
  page: 1, perPage: 100, q: "", status: "all", catId: "all",
  selected: new Set(), items: []
};

function accUser(a){
  return "@" + (a.username || a.uid || "");
}

async function loadStats(){
  const r = await api("GET", "/api/accounts/stats");
  if(!r.ok) return;
  const d = r.data;
  el("stTotal").textContent = d.total;
  el("stLive").textContent = d.live;
  el("stLoggedIn").textContent = d.logged_in;
  el("stCheckpoint").textContent = d.checkpoint;
  el("stDead").textContent = d.dead;
  el("tabLoggedIn").textContent = d.logged_in;
}

async function loadCategories(){
  const r = await api("GET", "/api/account-categories/stats");
  if(!r.ok) return;
  const d = r.data, box = el("catList");
  const q = (el("catSearch").value || "").toLowerCase();
  let html = '<div data-cat="all" style="display:flex;align-items:center;gap:8px;padding:9px 10px;border-radius:9px;cursor:pointer;border:1px solid ' +
    (A.catId === "all" ? "#16455a;background:#0e2a33" : "transparent") + ';margin-bottom:6px">' +
    '<input type="checkbox" ' + (A.catId === "all" ? "checked" : "") +
    ' tabindex="-1"> <b>All Accounts</b> <span style="flex:1"></span><span class="badge b-cyan">' +
    d.all.total + "</span></div>";
  for(const c of d.categories){
    if(q && !c.name.toLowerCase().includes(q)) continue;
    const on = String(A.catId) === String(c.id);
    html += '<div data-cat="' + c.id + '" style="display:flex;align-items:center;gap:8px;padding:9px 10px;border-radius:9px;cursor:pointer;border:1px solid ' +
      (on ? "#16455a;background:#0e2a33" : "transparent") + ';margin-bottom:6px">' +
      '<input type="checkbox" ' + (on ? "checked" : "") + ' tabindex="-1"> ' +
      esc(c.name) + ' <span style="flex:1"></span><span class="badge b-gray">' + c.total + "</span>" +
      ' <button data-delcat="' + c.id + '" title="Delete category" style="background:none;border:none;color:#f87171;cursor:pointer;font-size:15px;padding:0 2px">×</button></div>';
  }
  box.innerHTML = html;
  box.querySelectorAll("[data-cat]").forEach(row => {
    row.onclick = (e) => {
      const del = e.target.closest("[data-delcat]");
      if(del){ e.stopPropagation(); deleteCategory(del.dataset.delcat); return; }
      A.catId = row.dataset.cat; A.page = 1;
      loadCategories(); loadAccounts();
    };
  });
  // import modal category select refresh
  const sel = el("impCat");
  if(sel){
    sel.innerHTML = '<option value="">Uncategorized</option>' +
      d.categories.map(c => '<option value="' + c.id + '">' + esc(c.name) + "</option>").join("");
  }
}

async function loadTags(){
  const r = await api("GET", "/api/accounts?per_page=500");
  if(!r.ok) return;
  const tags = new Set();
  for(const a of r.data.items){
    (a.tags || "").split(",").map(t => t.trim()).filter(Boolean).forEach(t => tags.add(t));
  }
  const sel = el("tagFilter");
  const cur = sel.value;
  sel.innerHTML = '<option value="">Tags: All</option>' +
    [...tags].sort().map(t => '<option value="' + esc(t) + '">' + esc(t) + "</option>").join("");
  sel.value = cur;
}

async function loadAccounts(){
  const p = new URLSearchParams({
    q: A.q, status: A.status, category_id: A.catId,
    page: A.page, per_page: A.perPage
  });
  const r = await api("GET", "/api/accounts?" + p.toString());
  if(!r.ok) return;
  A.items = r.data.items;
  const tb = el("accBody");
  if(!A.items.length){
    tb.innerHTML = '<tr><td colspan="7" class="empty">No accounts yet. Click "＋ Add Account" to import.</td></tr>';
  } else {
    tb.innerHTML = A.items.map((a, i) =>
      "<tr><td><input type='checkbox' data-acc='" + a.id + "'" +
        (A.selected.has(a.id) ? " checked" : "") + "></td>" +
      "<td class='muted'>" + ((r.data.page - 1) * r.data.per_page + i + 1) + "</td>" +
      "<td>" + esc(accUser(a)) + "</td>" +
      "<td class='muted'>" + esc(a.uid || "—") + "</td>" +
      "<td>" + esc(a.display_name || "—") + "</td>" +
      "<td>" + statusBadge(a.status) + "</td>" +
      "<td class='muted'>" + esc(fmtDT(a.last_check)) + "</td></tr>"
    ).join("");
    tb.querySelectorAll("[data-acc]").forEach(cb => {
      cb.onchange = () => {
        const id = +cb.dataset.acc;
        cb.checked ? A.selected.add(id) : A.selected.delete(id);
        updateSelected();
      };
    });
  }
  el("pgInfo").textContent = "Displaying " + A.items.length + " of " + r.data.total + " Accounts";
  el("pgNum").textContent = r.data.page + " / " + r.data.pages;
  A.page = r.data.page;
  el("selAll").checked = A.items.length > 0 && A.items.every(a => A.selected.has(a.id));
  updateSelected();
}

function updateSelected(){
  el("stSelected").textContent = A.selected.size;
  el("btnBulkDelete").disabled = A.selected.size === 0;
}

function refreshAll(){
  loadStats(); loadCategories(); loadAccounts(); loadTags();
}

/* ---------------- live check (engine pending, honest) ---------------- */
async function checkLive(ids){
  let j;
  try{
    const res = await fetch("/api/accounts/check-live", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ids})
    });
    j = await res.json().catch(() => ({ok: false, error: "Bad server response"}));
  }catch(e){
    toast("Cannot reach local server: " + e.message, "err");
    return;
  }
  if(j.ok) return;
  if(j.error === "engine_pending"){
    toast("Live-check automation engine abhi bana nahi hai — milestone me aayega. Last-check time update ho gaya.", "okk");
    loadStats(); loadAccounts();
  } else {
    toast(j.error || "Request failed", "err");
  }
}

/* ---------------- bulk delete ---------------- */
async function bulkDelete(){
  if(!await confirmDialog("Delete " + A.selected.size + " selected account(s)? Their pages will be kept but unlinked.")) return;
  const r = await api("DELETE", "/api/accounts", {ids: [...A.selected]});
  if(!r.ok) return;
  toast("Deleted " + r.data.deleted + " account(s).", "okk");
  A.selected.clear();
  refreshAll();
}

/* ---------------- import modal ---------------- */
function countDetectable(text){
  let n = 0;
  for(const raw of text.split("\n")){
    const line = raw.trim();
    if(!line) continue;
    if(line.startsWith("{")){ try{ JSON.parse(line); n++; }catch(e){} continue; }
    if(line.includes("c_user=")){ n++; continue; }
    const parts = line.includes("|") ? line.split("|") : line.split("\t");
    if(parts[0] && parts[0].trim()) n++;
  }
  return n;
}

function openImportModal(){
  openModal(
    '<div class="modal-head"><h3>＋ Import Facebook Accounts <span class="badge b-cyan">INGESTION MATRIX</span></h3>' +
    '<button class="modal-x" onclick="closeModal()">×</button></div>' +
    '<div class="modal-body">' +
    '<div class="card-sub" style="margin-bottom:14px">Bulk import profiles, credentials &amp; session cookies into fleet repository</div>' +
    '<div class="row2">' +
      '<div class="field"><label>TARGET CATEGORY</label><select class="input select" id="impCat"><option value="">Uncategorized</option></select></div>' +
      '<div class="field"><label>INPUT FORMAT</label><select class="input select" id="impFmt">' +
        '<option value="auto">Auto-Detect</option>' +
        '<option value="uid|pass|2fa">UID | Pass | 2FA</option>' +
        '<option value="uid|pass">UID | Pass</option>' +
        '<option value="cookies">Cookies</option>' +
      "</select></div>" +
    "</div>" +
    '<div class="field"><label>PRESETS</label><div class="chiprow">' +
      '<span class="chip" data-fmt="uid|pass|2fa">UID | Pass | 2FA</span>' +
      '<span class="chip" data-fmt="uid|pass">UID | Pass</span>' +
      '<span class="chip" data-fmt="cookies">Cookies</span>' +
      '<span class="chip" data-fmt="auto">Auto-Detect</span>' +
    "</div></div>" +
    '<div class="field"><label>ACCOUNTS BUFFER (ONE PER LINE)</label>' +
    '<textarea class="input" id="impText" rows="7" placeholder="100084928819|MyPass123|JBSWY3DPEHPK3PXP\nc_user=10008...; xs=abc..."></textarea></div>' +
    '<div class="toolbar"><span class="badge b-cyan" id="impCount">0 accounts detected</span>' +
    '<span class="spacer"></span><span class="card-sub">Delimiter: | or tab. Duplicates skipped.</span></div>' +
    "</div>" +
    '<div class="modal-foot"><button class="btn btn-ghost" onclick="closeModal()">Cancel</button>' +
    '<button class="btn btn-primary" id="impGo">＋ Import Accounts</button></div>'
  );
  loadCategories();
  el("impText").addEventListener("input", () => {
    el("impCount").textContent = countDetectable(el("impText").value) + " accounts detected";
  });
  document.querySelectorAll(".chip[data-fmt]").forEach(ch => {
    ch.onclick = () => { el("impFmt").value = ch.dataset.fmt; };
  });
  el("impGo").onclick = async () => {
    const text = el("impText").value;
    if(!text.trim()){ toast("Paste at least one account line.", "err"); return; }
    const r = await api("POST", "/api/accounts/import", {
      category_id: el("impCat").value || null,
      format: el("impFmt").value,
      text
    });
    if(!r.ok) return;
    closeModal();
    toast("Imported " + r.data.imported + ", skipped " + r.data.skipped + ".", "okk");
    refreshAll();
  };
}

/* ---------------- categories ---------------- */
function openAddCategory(){
  openModal(
    '<div class="modal-head"><h3>New Category</h3><button class="modal-x" onclick="closeModal()">×</button></div>' +
    '<div class="modal-body"><div class="field"><label>NAME</label>' +
    '<input class="input" id="newCatName" placeholder="e.g. Clients, Test…"></div></div>' +
    '<div class="modal-foot"><button class="btn btn-ghost" onclick="closeModal()">Cancel</button>' +
    '<button class="btn btn-primary" id="newCatGo">＋ Add</button></div>'
  );
  el("newCatName").focus();
  el("newCatGo").onclick = async () => {
    const name = el("newCatName").value.trim();
    if(!name){ toast("Name required.", "err"); return; }
    const r = await api("POST", "/api/account-categories", {name});
    if(!r.ok) return;
    closeModal(); toast("Category added.", "okk"); loadCategories();
  };
}

async function deleteCategory(id){
  if(!await confirmDialog("Delete this category? Accounts inside it will become uncategorized.")) return;
  const r = await api("DELETE", "/api/account-categories", {ids: [+id]});
  if(!r.ok) return;
  if(String(A.catId) === String(id)) A.catId = "all";
  toast("Category deleted.", "okk");
  loadCategories(); loadAccounts();
}

/* ---------------- init ---------------- */
document.addEventListener("DOMContentLoaded", () => {
  let deb;
  el("qSearch").addEventListener("input", e => {
    clearTimeout(deb);
    deb = setTimeout(() => { A.q = e.target.value.trim(); A.page = 1; loadAccounts(); }, 350);
  });
  el("tagFilter").onchange = e => {
    el("qSearch").value = e.target.value; A.q = e.target.value; A.page = 1; loadAccounts();
  };
  el("statusTabs").querySelectorAll(".tab").forEach(t => {
    t.onclick = () => {
      el("statusTabs").querySelectorAll(".tab").forEach(x => x.classList.remove("on"));
      t.classList.add("on");
      A.status = t.dataset.st; A.page = 1; loadAccounts();
    };
  });
  el("selAll").onchange = e => {
    A.items.forEach(a => e.target.checked ? A.selected.add(a.id) : A.selected.delete(a.id));
    loadAccounts();
  };
  el("perPage").onchange = e => { A.perPage = +e.target.value; A.page = 1; loadAccounts(); };
  el("pgPrev").onclick = () => { if(A.page > 1){ A.page--; loadAccounts(); } };
  el("pgNext").onclick = () => { A.page++; loadAccounts(); };
  el("catSearch").addEventListener("input", loadCategories);
  el("btnCheckLive").onclick = () => checkLive("all");
  el("btnBulkDelete").onclick = bulkDelete;
  el("btnAddAccount").onclick = openImportModal;
  el("btnAddCat").onclick = openAddCategory;
  refreshAll();
});
