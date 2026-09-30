/* PagePilot — Proxy Management page */
let proxies = [], groups = [];
let fQ = "", fGroup = "", fStatus = "";
let selected = new Set();

document.addEventListener("DOMContentLoaded", () => {
  el("addBtn").onclick = openImportModal;
  el("delBtn").onclick = deleteSelected;
  el("checkBtn").onclick = checkSelected;
  el("groupsBtn").onclick = openGroupsModal;
  el("selAll").onchange = (e) => {
    document.querySelectorAll(".rowSel").forEach(c => { c.checked = e.target.checked; });
    syncSelected();
  };
  let deb;
  el("search").oninput = (e) => {
    clearTimeout(deb);
    deb = setTimeout(() => { fQ = e.target.value.trim(); load(); }, 300);
  };
  el("groupFilter").onchange = (e) => { fGroup = e.target.value; load(); };
  el("statusFilter").onchange = (e) => { fStatus = e.target.value; load(); };
  load();
});

async function load() {
  const r = await api("GET", "/api/proxies?q=" + encodeURIComponent(fQ) +
                      "&group_id=" + encodeURIComponent(fGroup) +
                      "&status=" + encodeURIComponent(fStatus));
  if (!r.ok) return;
  proxies = r.data.proxies || [];
  groups = r.data.groups || [];
  renderGroupFilter();
  renderRows();
}

function renderGroupFilter() {
  const cur = el("groupFilter").value;
  el("groupFilter").innerHTML = '<option value="">All Groups</option>' +
    groups.map(g => '<option value="' + g.id + '">' + esc(g.name) + "</option>").join("");
  el("groupFilter").value = cur;
  el("grpCount").textContent = groups.length;
}

function renderRows() {
  if (!proxies.length) {
    el("rows").innerHTML = '<tr><td colspan="12" class="empty">' +
      'No proxies added yet — click "+ Add Proxy" to import HTTP or SOCKS5 proxies in bulk.</td></tr>';
  } else {
    el("rows").innerHTML = proxies.map((p, i) =>
      "<tr>" +
      '<td><input type="checkbox" class="rowSel" data-id="' + p.id + '"' +
        (selected.has(p.id) ? " checked" : "") + "></td>" +
      "<td class='muted'>" + (i + 1) + "</td>" +
      "<td><b>" + esc(p.proxy) + "</b></td>" +
      "<td class='muted'>" + esc(p.host) + "</td>" +
      "<td>" + p.profiles + "</td>" +
      '<td><span class="badge b-blue">' + esc(p.protocol.toUpperCase()) + "</span></td>" +
      '<td><span class="badge b-gray">' + esc(p.protocol.toUpperCase()) + "</span></td>" +
      "<td>" + esc(p.group || "—") + "</td>" +
      "<td class='muted'>" + esc(p.location || "—") + "</td>" +
      "<td class='muted'>" + esc(p.timezone || "—") + "</td>" +
      "<td class='muted'>" + (p.latency_ms == null ? "—" : p.latency_ms + " ms") + "</td>" +
      "<td>" + statusBadge(p.status) + "</td>" +
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
  el("checkBtn").textContent = selected.size ? "Check Selected (" + selected.size + ")" : "Check All";
}

async function deleteSelected() {
  if (!selected.size) return;
  if (!await confirmDialog("Delete " + selected.size + " proxie(s)? Accounts using them will be unassigned.")) return;
  const r = await api("DELETE", "/api/proxies", { ids: [...selected] });
  if (r.ok) { selected.clear(); el("selAll").checked = false; toast("Deleted", "okk"); load(); }
}

async function checkSelected() {
  const ids = selected.size ? [...selected] : "all";
  let j;
  try {
    const res = await fetch("/api/proxies/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids })
    });
    j = await res.json().catch(() => ({ ok: false, error: "Bad server response" }));
  } catch (e) {
    toast("Cannot reach local server: " + e.message, "err");
    return;
  }
  if (j.ok) { toast("Check complete", "okk"); load(); return; }
  if (j.error === "engine_pending") {
    toast("Proxy check engine automation milestone me aayega — abhi sirf import & assignment working hai", "err");
  } else {
    toast(j.error || "Check failed", "err");
  }
}

/* ---------------- bulk import ---------------- */
function openImportModal() {
  openModal(
    '<div class="modal-head"><h3>Add Proxies (Bulk Import)</h3>' +
    '<button class="modal-x" onclick="closeModal()">×</button></div>' +
    '<div class="modal-body">' +
      '<div class="card" style="margin-bottom:14px">' +
        '<div class="card-title" style="margin-bottom:8px">SUPPORTED PROXY FORMATS</div>' +
        '<div style="font-family:monospace;font-size:12px;color:var(--muted);line-height:1.9">' +
          "host:port:user:pass<br>host:port<br>" +
          "socks5://host:port<br>socks5://host:port:user:pass<br>socks4://host:port:user:pass" +
        "</div></div>" +
      '<div class="row2">' +
        '<div class="field"><label>Format</label>' +
          '<div style="padding:10px 0"><span class="badge b-cyan">Auto Detect</span></div></div>' +
        '<div class="field"><label>Protocol (when line has no scheme)</label>' +
          '<select class="select" id="imProto">' +
            '<option value="http">HTTP</option><option value="socks4">SOCKS4</option>' +
            '<option value="socks5">SOCKS5</option></select></div>' +
      "</div>" +
      '<div class="field"><label>Proxy Group</label>' +
        '<select class="select" id="imGroup">' +
          groups.map(g => '<option value="' + g.id + '">' + esc(g.name) + "</option>").join("") +
        "</select></div>" +
      '<div class="field"><label>Proxy List (one per line) ' +
        '<span class="badge b-gray" id="imCount" style="margin-left:8px">0 line(s)</span></label>' +
        '<textarea class="input" id="imText" rows="8" style="font-family:monospace" ' +
          'placeholder="203.0.113.7:8080:user:pass\nsocks5://198.51.100.23:1080"></textarea></div>' +
    "</div>" +
    '<div class="modal-foot"><button class="btn btn-ghost" onclick="closeModal()">Cancel</button>' +
    '<button class="btn btn-primary" id="imAdd">+ Add Proxies</button></div>');

  el("imText").oninput = () => {
    const n = el("imText").value.split("\n").filter(l => l.trim()).length;
    el("imCount").textContent = n + " line(s)";
  };
  el("imAdd").onclick = async () => {
    const text = el("imText").value;
    if (!text.trim()) { toast("Paste at least one proxy line", "err"); return; }
    const r = await api("POST", "/api/proxies/import", {
      text,
      protocol: el("imProto").value,
      group_id: el("imGroup").value || null
    });
    if (r.ok) {
      closeModal();
      toast("Imported " + r.data.imported + ", skipped " + r.data.skipped, "okk");
      load();
    }
  };
}

/* ---------------- proxy groups ---------------- */
function openGroupsModal() {
  openModal(
    '<div class="modal-head"><h3>Proxy Groups</h3>' +
    '<button class="modal-x" onclick="closeModal()">×</button></div>' +
    '<div class="modal-body">' +
      '<div style="display:flex;gap:10px;margin-bottom:14px">' +
        '<input class="input" id="ngName" placeholder="New group name...">' +
        '<button class="btn btn-primary btn-sm" id="ngAdd">+ Add</button></div>' +
      '<div id="ngList"></div>' +
    "</div>" +
    '<div class="modal-foot"><button class="btn btn-ghost" onclick="closeModal()">Close</button></div>');

  const render = () => {
    el("ngList").innerHTML = groups.length
      ? groups.map(g =>
          '<div class="kv"><b>' + esc(g.name) + '</b>' +
          '<button class="btn btn-sm btn-danger" onclick="delGroup(' + g.id + ')">Delete</button></div>').join("")
      : '<div class="empty">No groups yet.</div>';
  };
  render();

  el("ngAdd").onclick = async () => {
    const name = el("ngName").value.trim();
    if (!name) { toast("Group name is required", "err"); return; }
    const r = await api("POST", "/api/proxy-groups", { name });
    if (r.ok) {
      const g = await api("GET", "/api/proxy-groups");
      if (g.ok) groups = g.data;
      el("ngName").value = "";
      render(); renderGroupFilter();
      toast("Group added", "okk");
    }
  };
}

async function delGroup(id) {
  if (!await confirmDialog("Delete this proxy group? Proxies in it will become ungrouped.")) return;
  const r = await api("DELETE", "/api/proxy-groups", { ids: [id] });
  if (r.ok) {
    const g = await api("GET", "/api/proxy-groups");
    if (g.ok) groups = g.data;
    openGroupsModal();
    renderGroupFilter();
    toast("Group deleted", "okk");
  }
}
