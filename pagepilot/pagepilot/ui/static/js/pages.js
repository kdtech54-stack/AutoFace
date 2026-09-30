/* Pages & Groups module */
let PP = { pages: [], categories: [], accounts: [], sel: new Set(),
           catFilter: null, unassigned: 0 };

function debounce(fn, ms){
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

document.addEventListener("DOMContentLoaded", () => {
  el("q").addEventListener("input", debounce(loadPages, 300));
  el("accountFilter").addEventListener("change", loadPages);
  el("fetchBtn").onclick = fetchNow;
  el("addPageBtn").onclick = openAddPage;
  el("addCatBtn").onclick = openAddCategory;
  el("selAll").onchange = onSelAll;
  el("chgCatBtn").onclick = openChangeCategory;
  el("copyUrlsBtn").onclick = copyUrls;
  el("delBtn").onclick = deleteSelected;
  el("tabPages").onclick = () => setTab("pages");
  el("tabGroups").onclick = () => setTab("groups");
  loadAll();
});

function setTab(t){
  el("tabPages").classList.toggle("on", t === "pages");
  el("tabGroups").classList.toggle("on", t === "groups");
  el("pagesPane").style.display = t === "pages" ? "" : "none";
  el("groupsPane").style.display = t === "groups" ? "" : "none";
}

async function loadAll(){
  await loadCategories();
  await loadPages();
}

async function loadCategories(){
  const r = await api("GET", "/api/page-categories");
  if(r.ok && r.data){
    PP.categories = r.data.categories || [];
    PP.unassigned = r.data.unassigned || 0;
    renderCategories();
  }
}

function renderCategories(){
  const box = el("catList");
  const total = PP.categories.reduce((a, c) => a + (c.pages || 0), 0) + PP.unassigned;
  let h = '<div class="cat-row' + (PP.catFilter === null ? " on" : "") + '" data-cat="">' +
    '<span>All Categories</span><span class="badge b-blue">' + total + '</span></div>';
  for(const c of PP.categories){
    h += '<div class="cat-row' + (PP.catFilter === c.id ? " on" : "") + '" data-cat="' + c.id + '">' +
      '<span>' + esc(c.name) + '</span>' +
      '<span style="display:flex;gap:6px;align-items:center">' +
      '<span class="badge b-gray">' + (c.pages || 0) + '</span>' +
      '<button class="cat-x" data-del="' + c.id + '" title="Delete category">×</button></span></div>';
  }
  box.innerHTML = h;
  box.querySelectorAll(".cat-row").forEach(row => {
    row.onclick = e => {
      if(e.target.dataset.del){ deleteCategory(+e.target.dataset.del); return; }
      PP.catFilter = row.dataset.cat === "" ? null : +row.dataset.cat;
      renderCategories();
      loadPages();
    };
  });
}

async function loadPages(){
  const params = new URLSearchParams();
  const q = el("q").value.trim();
  if(q) params.set("q", q);
  if(el("accountFilter").value) params.set("account_id", el("accountFilter").value);
  if(PP.catFilter !== null) params.set("category_id", PP.catFilter);
  const r = await api("GET", "/api/pages?" + params.toString());
  if(r.ok && r.data){
    PP.pages = r.data.pages || [];
    PP.accounts = r.data.accounts || [];
    renderAccountFilter();
    renderTable();
  }
}

function renderAccountFilter(){
  const sel = el("accountFilter");
  const cur = sel.value;
  sel.innerHTML = '<option value="">All accounts</option>' +
    PP.accounts.map(a => '<option value="' + a.id + '">' + esc(a.label) + '</option>').join("");
  sel.value = cur;
}

function renderTable(){
  const tb = el("pagesBody");
  el("pagesCount").textContent = PP.pages.length;
  if(!PP.pages.length){
    tb.innerHTML = '<tr><td colspan="6" class="empty">No pages yet — use “Fetch Now” (engine) or “＋ Add Page”.</td></tr>';
  } else {
    tb.innerHTML = PP.pages.map((p, i) =>
      '<tr><td><input type="checkbox" data-pid="' + p.id + '"' +
        (PP.sel.has(p.id) ? " checked" : "") + '></td>' +
      '<td>' + (i + 1) + '</td>' +
      '<td>' + esc(p.account) + '</td>' +
      '<td>' + esc(p.category) + '</td>' +
      '<td><b>' + esc(p.name) + '</b>' +
        (p.slug ? '<div class="muted" style="font-size:11px">' + esc(p.slug) + '</div>' : "") + '</td>' +
      '<td class="muted">' + esc(p.page_uid || p.slug || "—") + '</td></tr>'
    ).join("");
  }
  tb.querySelectorAll("input[data-pid]").forEach(cb => {
    cb.onchange = () => {
      const id = +cb.dataset.pid;
      if(cb.checked) PP.sel.add(id); else PP.sel.delete(id);
      updateFoot();
    };
  });
  updateFoot();
}

function onSelAll(e){
  const on = e.target.checked;
  PP.pages.forEach(p => { if(on) PP.sel.add(p.id); else PP.sel.delete(p.id); });
  renderTable();
}

function updateFoot(){
  el("footInfo").textContent = "Total " + PP.pages.length + " · Selected " + PP.sel.size;
  el("selAll").checked = PP.pages.length > 0 && PP.pages.every(p => PP.sel.has(p.id));
}

async function fetchNow(){
  el("fetchBtn").disabled = true;
  try{
    const r = await fetch("/api/pages/fetch", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({account_ids: "all"})
    });
    const j = await r.json().catch(() => ({ok: false}));
    if(!j.ok && j.error === "engine_pending"){
      toast("Real Facebook page fetch automation engine milestone me aayega", "err");
    } else if(j.ok){
      toast("Pages fetched", "okk");
      loadAll();
    } else {
      toast(j.error || "Fetch failed", "err");
    }
  }catch(e){
    toast("Cannot reach local server", "err");
  }
  el("fetchBtn").disabled = false;
}

function openAddPage(){
  const accOpts = PP.accounts.map(a =>
    '<option value="' + a.id + '">' + esc(a.label) + '</option>').join("");
  const catOpts = '<option value="">Unassigned</option>' + PP.categories.map(c =>
    '<option value="' + c.id + '">' + esc(c.name) + '</option>').join("");
  openModal(
    '<div class="modal-head"><h3>Add Page (manual)</h3>' +
    '<button class="modal-x" onclick="closeModal()">×</button></div>' +
    '<div class="modal-body">' +
    '<div class="field"><label>Owning account</label>' +
    '<select class="select" id="mAccount"><option value="">— none —</option>' + accOpts + '</select></div>' +
    '<div class="field"><label>Page name *</label>' +
    '<input class="input" id="mName" placeholder="e.g. ToonBrew"></div>' +
    '<div class="row2">' +
    '<div class="field"><label>Page UID</label><input class="input" id="mUid"></div>' +
    '<div class="field"><label>Slug</label><input class="input" id="mSlug"></div>' +
    '</div>' +
    '<div class="field"><label>URL</label>' +
    '<input class="input" id="mUrl" placeholder="https://facebook.com/..."></div>' +
    '<div class="field"><label>Category</label>' +
    '<select class="select" id="mCat">' + catOpts + '</select></div>' +
    '</div>' +
    '<div class="modal-foot"><button class="btn btn-ghost" onclick="closeModal()">Cancel</button>' +
    '<button class="btn btn-primary" id="mSave">Add Page</button></div>');
  el("mSave").onclick = async () => {
    const name = el("mName").value.trim();
    if(!name){ toast("Page name is required", "err"); return; }
    const body = {
      name: name,
      account_id: el("mAccount").value ? +el("mAccount").value : null,
      page_uid: el("mUid").value.trim(),
      slug: el("mSlug").value.trim(),
      url: el("mUrl").value.trim(),
      category_id: el("mCat").value ? +el("mCat").value : null
    };
    const r = await api("POST", "/api/pages", body);
    if(r.ok){ closeModal(); toast("Page added", "okk"); loadAll(); }
  };
}

async function deleteSelected(){
  if(!PP.sel.size){ toast("Select at least one page", "err"); return; }
  if(!await confirmDialog("Delete " + PP.sel.size + " page(s)? Linked task items will be removed too.")) return;
  const r = await api("DELETE", "/api/pages", {ids: [...PP.sel]});
  if(r.ok){ PP.sel.clear(); toast("Deleted " + r.data.deleted + " page(s)", "okk"); loadAll(); }
}

function openChangeCategory(){
  if(!PP.sel.size){ toast("Select at least one page", "err"); return; }
  const opts = '<option value="">Unassigned</option>' + PP.categories.map(c =>
    '<option value="' + c.id + '">' + esc(c.name) + '</option>').join("");
  openModal(
    '<div class="modal-head"><h3>Change Category (' + PP.sel.size + ')</h3>' +
    '<button class="modal-x" onclick="closeModal()">×</button></div>' +
    '<div class="modal-body"><div class="field"><label>Category</label>' +
    '<select class="select" id="cCat">' + opts + '</select></div></div>' +
    '<div class="modal-foot"><button class="btn btn-ghost" onclick="closeModal()">Cancel</button>' +
    '<button class="btn btn-primary" id="cApply">Apply</button></div>');
  el("cApply").onclick = async () => {
    const r = await api("PUT", "/api/pages/category", {
      ids: [...PP.sel],
      category_id: el("cCat").value ? +el("cCat").value : null
    });
    if(r.ok){ closeModal(); toast("Updated " + r.data.updated + " page(s)", "okk"); loadAll(); }
  };
}

function copyUrls(){
  if(!PP.sel.size){ toast("Select at least one page", "err"); return; }
  const urls = PP.pages
    .filter(p => PP.sel.has(p.id))
    .map(p => p.url || (p.page_uid ? "https://facebook.com/" + p.page_uid : ""))
    .filter(Boolean);
  if(!urls.length){ toast("Selected pages have no URLs", "err"); return; }
  const text = urls.join("\n");
  const done = () => toast("Copied " + urls.length + " URL(s)", "okk");
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(done, () => fallbackCopy(text, done));
  } else {
    fallbackCopy(text, done);
  }
}

function fallbackCopy(text, done){
  const ta = document.createElement("textarea");
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  try{ document.execCommand("copy"); done(); }
  catch(e){ toast("Copy failed", "err"); }
  ta.remove();
}

function openAddCategory(){
  openModal(
    '<div class="modal-head"><h3>New Category</h3>' +
    '<button class="modal-x" onclick="closeModal()">×</button></div>' +
    '<div class="modal-body"><div class="field"><label>Category name *</label>' +
    '<input class="input" id="nCat" placeholder="e.g. Cartoon"></div></div>' +
    '<div class="modal-foot"><button class="btn btn-ghost" onclick="closeModal()">Cancel</button>' +
    '<button class="btn btn-primary" id="nSave">Create</button></div>');
  el("nSave").onclick = async () => {
    const name = el("nCat").value.trim();
    if(!name){ toast("Name is required", "err"); return; }
    const r = await api("POST", "/api/page-categories", {name: name});
    if(r.ok){ closeModal(); toast("Category created", "okk"); loadCategories(); }
  };
}

async function deleteCategory(id){
  if(!await confirmDialog("Delete this category? Its pages become Unassigned.")) return;
  const r = await api("DELETE", "/api/page-categories", {id: id});
  if(r.ok){
    if(PP.catFilter === id) PP.catFilter = null;
    toast("Category deleted", "okk");
    loadAll();
  }
}
