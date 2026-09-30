/* PagePilot — Content Presets page */
let presets = [], categories = [];
let fType = "", fCat = "All", fQ = "";
let selected = new Set();
const MACROS = ["$number", "$timespan", "$time", "$date", "$text", "$smile"];

document.addEventListener("DOMContentLoaded", () => {
  el("addBtn").onclick = () => openComposer(null);
  el("delBtn").onclick = deleteSelected;
  el("selAll").onchange = (e) => {
    document.querySelectorAll(".rowSel").forEach(c => { c.checked = e.target.checked; });
    syncSelected();
  };
  let deb;
  el("search").oninput = (e) => {
    clearTimeout(deb);
    deb = setTimeout(() => { fQ = e.target.value.trim(); load(); }, 300);
  };
  el("typeTabs").querySelectorAll(".tab").forEach(b => {
    b.onclick = () => {
      el("typeTabs").querySelectorAll(".tab").forEach(x => x.classList.remove("on"));
      b.classList.add("on");
      fType = b.dataset.t;
      load();
    };
  });
  load();
});

async function load() {
  const r = await api("GET", "/api/presets?type=" + encodeURIComponent(fType) +
                      "&q=" + encodeURIComponent(fQ));
  if (!r.ok) return;
  presets = r.data.presets || [];
  categories = r.data.categories || [];
  renderCats();
  renderRows();
}

function renderCats() {
  const counts = {};
  presets.forEach(p => { counts[p.category] = (counts[p.category] || 0) + 1; });
  const all = [{ n: "All", c: presets.length }].concat(
    categories.map(c => ({ n: c, c: counts[c] || 0 })));
  el("catList").innerHTML = all.map(x =>
    '<div class="cat-item' + (fCat === x.n ? " on" : "") + '" data-c="' + esc(x.n) + '">' +
    '<span>' + esc(x.n === "All" ? "All Categories" : x.n) + '</span>' +
    '<span class="badge b-gray">' + x.c + '</span></div>').join("");
  el("catList").querySelectorAll(".cat-item").forEach(d => {
    d.onclick = () => { fCat = d.dataset.c; renderCats(); renderRows(); };
  });
}

function visible() {
  return presets.filter(p => fCat === "All" || p.category === fCat);
}

function typeBadge(t) {
  const map = { post: "b-blue", reel: "b-cyan", comment: "b-amber" };
  return '<span class="badge ' + (map[t] || "b-gray") + '">' + esc(t).toUpperCase() + "</span>";
}

function renderRows() {
  const rows = visible();
  el("presetCount").textContent = presets.length;
  if (!rows.length) {
    el("rows").innerHTML = '<tr><td colspan="9" class="empty">No presets yet — click "+ Add content" to create one.</td></tr>';
  } else {
    el("rows").innerHTML = rows.map((p, i) =>
      "<tr>" +
      '<td><input type="checkbox" class="rowSel" data-id="' + p.id + '"' +
        (selected.has(p.id) ? " checked" : "") + "></td>" +
      "<td class='muted'>" + (i + 1) + "</td>" +
      "<td><b>" + esc(p.title) + "</b></td>" +
      "<td>" + typeBadge(p.type) + "</td>" +
      '<td class="muted" style="max-width:320px">' + esc(p.preview || "—") + "</td>" +
      "<td>" + p.media_count + " file(s)</td>" +
      "<td>" + esc(p.category) + "</td>" +
      '<td class="muted">' + fmtDT(p.created_at) + "</td>" +
      '<td><button class="btn btn-sm btn-ghost" onclick="openComposer(' + p.id + ')">Edit</button></td>' +
      "</tr>").join("");
  }
  el("rows").querySelectorAll(".rowSel").forEach(c => { c.onchange = syncSelected; });
  syncSelected();
}

function syncSelected() {
  selected = new Set();
  document.querySelectorAll(".rowSel").forEach(c => {
    if (c.checked) selected.add(parseInt(c.dataset.id, 10));
  });
  el("delBtn").disabled = selected.size === 0;
  el("delBtn").textContent = selected.size ? "Delete (" + selected.size + ")" : "Delete";
}

async function deleteSelected() {
  if (!selected.size) return;
  if (!await confirmDialog("Delete " + selected.size + " preset(s)? Media files and captions will be removed too.")) return;
  const r = await api("DELETE", "/api/presets", { ids: [...selected] });
  if (r.ok) { selected.clear(); el("selAll").checked = false; toast("Deleted", "okk"); load(); }
}

/* ---------------- composer ---------------- */
let comp = null; // {editing, id, type, staged:[File], media:[], captions}

function splitCaptions(text) {
  const blocks = [], cur = [];
  String(text || "").split("\n").forEach(line => {
    if (line.trim() === "") { if (cur.length) { blocks.push(cur.join("\n").trim()); cur.length = 0; } }
    else cur.push(line);
  });
  if (cur.length) blocks.push(cur.join("\n").trim());
  return blocks.filter(b => b);
}

function openComposer(pid) {
  comp = { editing: !!pid, id: pid || null, type: "post", staged: [], media: [] };
  const macroChips = MACROS.map(m =>
    '<span class="chip" onclick="insMacro(\'' + m + '\')">' + m + "</span>").join("");
  openModal(
    '<div class="modal-head"><h3>' + (pid ? "Edit" : "Create") + ' Content Preset ' +
    '<span class="badge b-cyan">STUDIO COMPOSER</span></h3>' +
    '<button class="modal-x" onclick="closeModal()">×</button></div>' +
    '<div class="modal-body">' +
      '<div class="card-title" style="margin-bottom:10px">PRESET INFORMATION</div>' +
      '<div class="field"><label>Title *</label>' +
        '<input class="input" id="cTitle" placeholder="e.g. funny cats reel"></div>' +
      '<div class="row2">' +
        '<div class="field"><label>Category</label>' +
          '<select class="select" id="cCatSel"></select></div>' +
        '<div class="field"><label>New category</label>' +
          '<input class="input" id="cCatNew" placeholder="optional — overrides select"></div>' +
      '</div>' +
      '<div class="field"><label>Preset Type</label>' +
        '<div class="seg" id="cType">' +
          '<button data-t="post" class="on">Post</button>' +
          '<button data-t="reel">Reel</button>' +
          '<button data-t="comment">Comment</button>' +
        '</div></div>' +
      '<div class="card-title" style="margin:18px 0 10px">CONTENT &amp; SPINTAX COMPOSER</div>' +
      '<div class="field"><textarea class="input" id="cTemplate" rows="4" ' +
        'placeholder="{Amazing|Incredible|Check out this} new video! $smile"></textarea></div>' +
      '<div class="field"><label>CLICK TO INSERT DYNAMIC MACRO</label>' +
        '<div class="chiprow">' + macroChips + "</div></div>" +
      '<div style="display:flex;gap:10px;align-items:center;margin-bottom:10px">' +
        '<button class="btn btn-sm" id="cSpin">Test Spin Preview</button>' +
        '<button class="btn btn-sm" id="cAI">✨ AI Captions</button>' +
        '<span class="muted" style="font-size:12px">Syntax: {opt1|opt2|opt3}</span></div>' +
      '<div class="card" id="cSpinBox" style="display:none;margin-bottom:6px">' +
        '<div id="cSpinOut" style="font-size:13px"></div></div>' +
      '<div class="card-title" style="margin:18px 0 10px">MEDIA ASSETS ' +
        '<span class="badge b-gray" id="cMediaCount">0 file(s)</span></div>' +
      '<div class="field"><input type="file" id="cFiles" multiple accept="image/*,video/*"></div>' +
      '<div id="cMediaList" class="chiprow" style="margin-bottom:6px"></div>' +
      '<div class="card-title" style="margin:18px 0 10px">CAPTIONS POOL ' +
        '<span class="badge b-green" id="cCapCount">0 Caption(s) Ready</span></div>' +
      '<div class="field"><textarea class="input" id="cCaptions" rows="4" ' +
        'placeholder="Paste multiple distinct captions separated by an empty line..."></textarea></div>' +
      '<div class="card-sub" id="cSummary" style="margin:6px 0 0"></div>' +
    "</div>" +
    '<div class="modal-foot"><button class="btn btn-ghost" onclick="closeModal()">Cancel</button>' +
    '<button class="btn btn-primary" id="cSave">Save Preset</button></div>',
    true);

  el("cCatSel").innerHTML = categories.map(c =>
    '<option value="' + esc(c) + '">' + esc(c) + "</option>").join("") +
    '<option value="Default">Default</option>';
  el("cType").querySelectorAll("button").forEach(b => {
    b.onclick = () => {
      el("cType").querySelectorAll("button").forEach(x => x.classList.remove("on"));
      b.classList.add("on"); comp.type = b.dataset.t; updateSummary();
    };
  });
  el("cSpin").onclick = testSpin;
  el("cAI").onclick = aiCaptions;
  el("cTemplate").oninput = updateSummary;
  el("cCaptions").oninput = () => {
    el("cCapCount").textContent = splitCaptions(el("cCaptions").value).length + " Caption(s) Ready";
    updateSummary();
  };
  el("cFiles").onchange = (e) => {
    [...e.target.files].forEach(f => comp.staged.push(f));
    e.target.value = "";
    renderMediaList(); updateSummary();
  };
  el("cSave").onclick = saveComposer;
  if (pid) loadComposerData(pid);
  updateSummary();
}

async function aiCaptions() {
  const topic = (el("cTemplate").value.trim() || el("cTitle").value.trim());
  if (!topic) { toast("Pehle template ya title me topic likho", "err"); return; }
  toast("AI captions ban rahe hain...");
  const r = await api("POST", "/api/ai/captions", { topic, count: 5 });
  if (!r.ok) return;
  const caps = (r.data && r.data.captions) || [];
  if (!caps.length) return;
  const ta = el("cCaptions");
  ta.value = (ta.value.trim() ? ta.value.trim() + "\n\n" : "") + caps.join("\n\n");
  ta.oninput();
  toast(caps.length + " AI captions added");
}

function insMacro(m) {
  const ta = el("cTemplate");
  const s = ta.selectionStart || 0, e = ta.selectionEnd || 0;
  ta.value = ta.value.slice(0, s) + m + ta.value.slice(e);
  ta.selectionStart = ta.selectionEnd = s + m.length;
  ta.focus();
}

async function loadComposerData(pid) {
  const r = await api("GET", "/api/presets/" + pid);
  if (!r.ok) { closeModal(); return; }
  const p = r.data;
  el("cTitle").value = p.title;
  el("cTemplate").value = p.template || "";
  el("cCaptions").value = (p.captions || []).map(c => c.text).join("\n\n");
  comp.type = p.type;
  comp.media = p.media || [];
  el("cType").querySelectorAll("button").forEach(x =>
    x.classList.toggle("on", x.dataset.t === p.type));
  if (![...el("cCatSel").options].some(o => o.value === p.category)) {
    const o = document.createElement("option");
    o.value = o.textContent = p.category;
    el("cCatSel").appendChild(o);
  }
  el("cCatSel").value = p.category;
  el("cCapCount").textContent = p.caption_count + " Caption(s) Ready";
  renderMediaList(); updateSummary();
}

function renderMediaList() {
  const box = el("cMediaList");
  let html = comp.media.map(m =>
    '<span class="chip" title="' + esc(m.filename) + '">' + esc(m.filename) +
    ' <b style="cursor:pointer" onclick="delMedia(' + m.id + ')">×</b></span>').join("");
  html += comp.staged.map((f, i) =>
    '<span class="chip" title="staged — uploads on save">' + esc(f.name) +
    ' <b style="cursor:pointer" onclick="delStaged(' + i + ')">×</b></span>').join("");
  box.innerHTML = html || '<span class="muted" style="font-size:12px">No media attached yet — supports JPG, PNG, MP4, MOV.</span>';
  el("cMediaCount").textContent = (comp.media.length + comp.staged.length) + " file(s)";
}

function delStaged(i) { comp.staged.splice(i, 1); renderMediaList(); updateSummary(); }

async function delMedia(mid) {
  const r = await api("DELETE", "/api/presets/" + comp.id + "/media/" + mid);
  if (r.ok) { comp.media = comp.media.filter(m => m.id !== mid); renderMediaList(); updateSummary(); }
}

function updateSummary() {
  if (!el("cSummary")) return;
  const mc = comp.media.length + comp.staged.length;
  const cc = splitCaptions(el("cCaptions").value).length;
  el("cSummary").innerHTML = "<b>" + esc(comp.type.toUpperCase()) + "</b> · " +
    mc + " media file(s) · " + cc + " caption(s)";
}

async function testSpin() {
  const t = el("cTemplate").value;
  if (!t.trim()) { toast("Template is empty", "err"); return; }
  const r = await api("POST", "/api/presets/test-spin", { template: t });
  if (!r.ok) return;
  el("cSpinBox").style.display = "block";
  el("cSpinOut").innerHTML =
    r.data.variants.map((v, i) =>
      '<div style="padding:6px 0;border-bottom:1px solid #131e38"><span class="muted">#' +
      (i + 1) + "</span> " + esc(v) + "</div>").join("") +
    '<div style="padding-top:8px"><span class="badge b-cyan">RENDERED</span> ' +
    esc(r.data.rendered) + "</div>";
}

async function uploadStaged(pid) {
  if (!comp.staged.length) return true;
  const fd = new FormData();
  comp.staged.forEach(f => fd.append("files", f));
  try {
    const res = await fetch("/api/presets/" + pid + "/media", { method: "POST", body: fd });
    const j = await res.json().catch(() => ({ ok: false }));
    if (!j.ok) { toast(j.error || "Media upload failed", "err"); return false; }
    return true;
  } catch (e) {
    toast("Media upload failed: " + e.message, "err");
    return false;
  }
}

async function saveComposer() {
  const title = el("cTitle").value.trim();
  if (!title) { toast("Title is required", "err"); return; }
  const newCat = el("cCatNew").value.trim();
  const body = {
    title,
    type: comp.type,
    category: newCat || el("cCatSel").value || "Default",
    template: el("cTemplate").value,
    captions: el("cCaptions").value
  };
  let r, pid;
  if (comp.editing) {
    r = await api("PUT", "/api/presets/" + comp.id, body);
    pid = comp.id;
  } else {
    r = await api("POST", "/api/presets", body);
    pid = r.ok && r.data ? r.data.id : null;
  }
  if (!r.ok || !pid) return;
  await uploadStaged(pid);
  closeModal();
  toast("Preset saved", "okk");
  load();
}
