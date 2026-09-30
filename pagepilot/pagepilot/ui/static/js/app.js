/* PagePilot shared frontend helpers */
function el(id){ return document.getElementById(id); }

function esc(s){
  return String(s == null ? "" : s)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function fmtDT(iso){
  if(!iso) return "—";
  try{
    const d = new Date(iso);
    return d.toLocaleString("en-GB",{day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"});
  }catch(e){ return iso; }
}

async function api(method, url, body){
  try{
    const r = await fetch(url, {
      method,
      headers: {"Content-Type":"application/json"},
      body: body !== undefined ? JSON.stringify(body) : undefined
    });
    const j = await r.json().catch(()=>({ok:false, error:"Bad server response"}));
    if(!j.ok) toast(j.error || "Request failed", "err");
    return j;
  }catch(e){
    toast("Cannot reach local server: " + e.message, "err");
    return {ok:false, error:String(e)};
  }
}

function toast(msg, kind){
  const box = el("toasts");
  const t = document.createElement("div");
  t.className = "toast" + (kind==="err" ? " err" : kind==="okk" ? " okk" : "");
  t.textContent = msg;
  box.appendChild(t);
  setTimeout(()=>{ t.style.opacity="0"; t.style.transition="opacity .4s";
    setTimeout(()=>t.remove(), 400); }, 3600);
}

function statusBadge(s){
  const map = {live:"b-green", logged_in:"b-green", active:"b-green", ok:"b-green", done:"b-green",
    checkpoint:"b-amber", unknown:"b-gray", queued:"b-blue", running:"b-cyan",
    dead:"b-red", failed:"b-red", paused:"b-amber"};
  return '<span class="badge '+(map[s]||"b-gray")+'">'+esc(s)+"</span>";
}

function openModal(html, wide){
  const root = el("modal-root");
  root.innerHTML = '<div class="modal-backdrop" onclick="if(event.target===this)closeModal()">'+
    '<div class="modal'+(wide?" wide":"")+'">'+html+"</div></div>";
}
function closeModal(){ el("modal-root").innerHTML = ""; }

function confirmDialog(msg){
  return new Promise(resolve => {
    openModal(
      '<div class="modal-head"><h3>Confirm</h3><button class="modal-x" onclick="closeModal()">×</button></div>'+
      '<div class="modal-body"><p>'+esc(msg)+'</p></div>'+
      '<div class="modal-foot"><button class="btn btn-ghost" onclick="closeModal()">Cancel</button>'+
      '<button class="btn btn-danger" id="cfYes">Yes, do it</button></div>'
    );
    el("cfYes").onclick = ()=>{ closeModal(); resolve(true); };
    const bd = document.querySelector(".modal-backdrop");
    const cancel = ()=>resolve(false);
    bd.addEventListener("click", function h(e){ if(e.target===bd){ bd.removeEventListener("click",h); cancel(); } });
  });
}

/* scheduler pill (graceful until scheduler API lands) */
document.addEventListener("DOMContentLoaded", async ()=>{
  const btn = el("schedBtn");
  if(btn) btn.onclick = async ()=>{
    const r = await api("POST","/api/scheduler/toggle");
    if(r.ok && r.data){
      el("schedState").textContent = r.data.running ? "RUNNING" : "IDLE";
      el("schedDot").className = "dot " + (r.data.running ? "dot-green" : "dot-gray");
      btn.innerHTML = r.data.running ? "⏸ Stop" : "▶ Run";
    }
  };
  const st = await api("GET","/api/scheduler/status").catch(()=>null);
  if(st && st.ok && st.data && el("schedState")){
    el("schedState").textContent = st.data.running ? "RUNNING" : "IDLE";
    el("schedDot").className = "dot " + (st.data.running ? "dot-green" : "dot-gray");
    el("schedBtn").innerHTML = st.data.running ? "⏸ Stop" : "▶ Run";
  }
});
