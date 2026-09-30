/* PagePilot — Settings page */
const FIELDS = [
  ["sMin", "min_spacing", "3"], ["sMax", "max_spacing", "10"],
  ["sSwitch", "switch_on_errors", "10"],
  ["sDupDays", "dup_guard_days", "30"],
  ["sAiBase", "ai_base_url", "https://api.openai.com/v1"],
  ["sAiModel", "ai_model", "gpt-4o-mini"],
];
const CHECKS = [
  ["sHeadless", "browser_headless", true], ["sUniq", "uniquify_media", true],
  ["sDup", "dup_guard", true],
];

document.addEventListener("DOMContentLoaded", () => {
  el("saveBtn").onclick = save;
  load();
});

async function load() {
  const r = await api("GET", "/api/settings");
  if (!r.ok) return;
  const d = r.data || {};
  FIELDS.forEach(([id, key, def]) => {
    if (id === "sAiKey") return;
    el(id).value = d[key] !== undefined && d[key] !== "" ? d[key] : def;
  });
  CHECKS.forEach(([id, key, def]) => {
    const v = d[key];
    el(id).checked = v === undefined || v === "" ? def : v !== "0";
  });
  el("sAiKey").placeholder = d["ai_api_key"] ? "•••••••• (saved)" : "sk-...";
}

async function save() {
  const body = {};
  FIELDS.forEach(([id, key]) => {
    if (id === "sAiKey") return;
    body[key] = el(id).value.trim();
  });
  if (el("sAiKey").value.trim()) body["ai_api_key"] = el("sAiKey").value.trim();
  CHECKS.forEach(([id, key]) => { body[key] = el(id).checked ? "1" : "0"; });
  const r = await api("POST", "/api/settings", body);
  if (r.ok) { toast("Settings saved"); el("sAiKey").value = ""; load(); }
}
