/* PagePilot — Comments & Engagement page */
document.addEventListener("DOMContentLoaded", () => {
  el("wuStart").onclick = startWarmup;
  el("crStart").onclick = startReplies;
  loadAll();
});

function checkedIds(boxId) {
  return [...document.querySelectorAll("#" + boxId + " input:checked")]
    .map(c => parseInt(c.value, 10));
}

async function loadAll() {
  const [ar, pr, tr] = await Promise.all([
    api("GET", "/api/accounts?per_page=500"),
    api("GET", "/api/pages"),
    api("GET", "/api/tasks"),
  ]);
  if (ar.ok) {
    el("wuAccounts").innerHTML = (ar.data.items || []).map(a =>
      '<label class="check"><input type="checkbox" value="' + a.id + '"><span>' +
      esc(a.display_name || a.username || a.uid || ("#" + a.id)) + "</span></label>").join("") ||
      '<div class="empty">No accounts yet.</div>';
  }
  if (pr.ok) {
    el("crPages").innerHTML = (pr.data.pages || []).map(p =>
      '<label class="check"><input type="checkbox" value="' + p.id + '"><span>' +
      esc(p.name) + ' <span class="muted">(' + esc(p.account || "") + ")</span></span></label>").join("") ||
      '<div class="empty">No pages yet.</div>';
  }
  if (tr.ok) renderTasks((tr.data || []).filter(t =>
    t.kind === "warmup" || t.kind === "comment_reply"));
}

function renderTasks(tasks) {
  const tb = el("taskRows");
  if (!tasks.length) {
    tb.innerHTML = '<tr><td colspan="9" class="empty">No engagement tasks yet.</td></tr>';
    return;
  }
  tb.innerHTML = tasks.map(t => {
    const c = t.counts || {};
    return "<tr><td>" + t.id + "</td><td>" + esc(t.name) + "</td>" +
      "<td>" + esc(t.kind) + "</td><td>" + statusBadge(t.status) + "</td>" +
      "<td>" + (c.queued || 0) + "</td><td>" + (c.done || 0) + "</td>" +
      "<td>" + (c.failed || 0) + "</td><td>" + fmtDT(t.created_at) + "</td>" +
      '<td><button class="btn btn-sm btn-ghost" onclick="cancelTask(' + t.id + ')">Cancel</button></td></tr>';
  }).join("");
}

async function cancelTask(id) {
  if (!await confirmDialog("Cancel this task?")) return;
  const r = await api("POST", "/api/tasks/" + id + "/cancel");
  if (r.ok) { toast("Task cancelled"); loadAll(); }
}

async function startWarmup() {
  const ids = checkedIds("wuAccounts");
  if (!ids.length) { toast("Select at least one account", "err"); return; }
  const r = await api("POST", "/api/tasks/warmup",
    { account_ids: ids, minutes: parseInt(el("wuMinutes").value, 10) || 10 });
  if (r.ok) { toast("Warm-up task queued — run the scheduler to start"); loadAll(); }
}

async function startReplies() {
  const ids = checkedIds("crPages");
  if (!ids.length) { toast("Select at least one page", "err"); return; }
  const replies = el("crReplies").value.trim();
  if (!replies) { toast("Add at least one reply text", "err"); return; }
  const r = await api("POST", "/api/tasks/engagement", {
    page_ids: ids, replies,
    max_replies: parseInt(el("crMax").value, 10) || 10,
  });
  if (r.ok) { toast("Comment-reply task queued — run the scheduler to start"); loadAll(); }
}
