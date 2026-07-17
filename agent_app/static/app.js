/* Lakebase Agent Backbone — standalone chat UI */

const $ = (id) => document.getElementById(id);

let agState = { instance: "", model: "", thread: null, branch: "main" };

/* ── helpers ─────────────────────────────────────────────── */
async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}
function toast(msg, ok = false) {
  const el = document.createElement("div");
  el.className = "toast" + (ok ? " ok" : "");
  el.textContent = msg;
  $("toasts").appendChild(el);
  setTimeout(() => el.remove(), 6000);
}
function esc(s) { const d = document.createElement("div"); d.textContent = s ?? ""; return d.innerHTML; }
function money(v) { return v == null ? "—" : "$" + Number(v).toFixed(v < 1 ? 5 : 2); }

/* ── config / instance + model pickers ───────────────────── */
async function loadConfig() {
  try {
    const cfg = await api("/api/config");
    $("host-chip").textContent = new URL(cfg.host).hostname;
    if (cfg.user) { $("user-chip").textContent = cfg.user; $("user-chip").hidden = false; }
    const pool = [...(cfg.backbones || []), ...(cfg.others || [])];
    const sel = $("ag-instance");
    sel.innerHTML = pool.map((d) =>
      `<option value="${esc(d.name)}">${esc(d.usecase)}${(d.tags||{}).blueprint ? " ⭐" : ""} (${esc(d.state)})</option>`
    ).join("") || `<option value="">— deploy the backbone in the control plane —</option>`;
    agState.instance = sel.value;
  } catch (e) { toast("Config failed: " + e.message); }

  try {
    const models = await api("/api/agent/models");
    $("ag-model").innerHTML = models.map((m) =>
      `<option value="${esc(m)}">${esc(m.replace("databricks-", ""))}</option>`).join("");
    agState.model = $("ag-model").value;
  } catch (_) {}

  if (agState.instance) { loadThreads(); loadCost(); }
}

$("ag-instance").addEventListener("change", (e) => {
  agState.instance = e.target.value; agState.thread = null; agState.branch = "main";
  renderMessages([]); loadThreads(); loadCost();
});
$("ag-model").addEventListener("change", (e) => { agState.model = e.target.value; });

$("ag-setup-btn").addEventListener("click", async () => {
  if (!agState.instance) return toast("Pick a backbone instance first");
  const btn = $("ag-setup-btn"); btn.disabled = true; const orig = btn.textContent; btn.textContent = "Applying…";
  try {
    const r = await api("/api/agent/setup", { method: "POST", body: JSON.stringify({ instance: agState.instance }) });
    toast(`Schema applied: ${(r.applied || []).join(", ")}`, true);
    loadThreads();
  } catch (e) { toast("Apply schema failed: " + e.message); }
  finally { btn.disabled = false; btn.textContent = orig; }
});

/* ── cost strip (this agent's per-turn ledger) ───────────── */
async function loadCost() {
  if (!agState.instance) return;
  try {
    const c = await api(`/api/agent/cost?instance=${encodeURIComponent(agState.instance)}&days=30`);
    if (c.usd != null) {
      $("ag-cost").hidden = false;
      const turns = (c.breakdown || []).reduce((a, b) => a + (b.turns || 0), 0);
      const toks = (c.breakdown || []).reduce((a, b) => a + (b.tokens || 0), 0);
      $("ag-cost").innerHTML = `<span class="ag-cost-usd">${money(c.usd)}</span><span class="ag-cost-sub">${turns} turns · ${toks.toLocaleString()} tokens · 30d · metered from agent.interactions</span>`;
    }
  } catch (_) { $("ag-cost").hidden = true; }
}

/* ── threads ─────────────────────────────────────────────── */
async function loadThreads() {
  if (!agState.instance) return;
  try {
    const threads = await api(`/api/agent/threads?instance=${encodeURIComponent(agState.instance)}`);
    $("ag-threads").innerHTML = threads.map((t) => `
      <button type="button" class="ag-thread${t.thread_id === agState.thread && t.branch === agState.branch ? " active" : ""}"
              data-thread="${esc(t.thread_id)}" data-branch="${esc(t.branch)}">
        <span class="t-id">${esc(t.thread_id)}</span>
        ${t.branch && t.branch !== "main" ? `<span class="t-branch">⎇ ${esc(t.branch)}</span>` : ""}
        <div class="t-meta">${esc(t.agent_version || "")} · ${esc((t.last_active_at || "").slice(0, 16))}</div>
      </button>`).join("") || `<p class="hint">No threads yet — say hello below.</p>`;
  } catch (e) {
    $("ag-threads").innerHTML = `<p class="hint">Threads need the schema applied. ${esc(e.message)}</p>`;
  }
}

$("ag-threads").addEventListener("click", async (ev) => {
  const t = ev.target.closest(".ag-thread");
  if (!t) return;
  agState.thread = t.dataset.thread; agState.branch = t.dataset.branch || "main";
  await openThread(); loadThreads();
});
$("ag-new-thread").addEventListener("click", () => {
  agState.thread = null; agState.branch = "main";
  $("ag-thread-label").textContent = "New conversation";
  renderMessages([]); loadThreads();
});

async function openThread() {
  try {
    const msgs = await api(`/api/agent/thread?instance=${encodeURIComponent(agState.instance)}&thread_id=${encodeURIComponent(agState.thread)}&branch=${encodeURIComponent(agState.branch)}`);
    $("ag-thread-label").textContent = `${agState.thread}${agState.branch !== "main" ? " ⎇ " + agState.branch : ""}`;
    renderMessages(msgs);
  } catch (e) { toast("Open thread failed: " + e.message); }
}

function renderMessages(msgs) {
  const box = $("ag-messages");
  if (!msgs.length) {
    box.innerHTML = `<div class="ag-empty"><p>Start a conversation — the agent recalls memory from Lakebase and persists every turn.</p><p class="hint">Resume a thread to see the checkpointer rehydrate state; branch to test a different model on an isolated copy.</p></div>`;
    return;
  }
  box.innerHTML = msgs.map((m) => {
    const meta = m.role === "assistant" && m.cost_usd != null
      ? `<div class="msg-meta">${m.model ? esc(m.model.replace("databricks-", "")) : ""} · ${m.prompt_tokens || 0}+${m.completion_tokens || 0} tok · ${m.latency_ms || 0}ms · ${money(m.cost_usd)}</div>`
      : "";
    return `<div class="msg ${m.role === "assistant" ? "assistant" : "user"}">${esc(m.content)}</div>${meta}`;
  }).join("");
  box.scrollTop = box.scrollHeight;
}

$("ag-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const text = $("ag-text").value.trim();
  if (!text) return;
  if (!agState.instance) return toast("Pick a backbone instance first");
  $("ag-text").value = "";
  const box = $("ag-messages");
  if (box.querySelector(".ag-empty")) box.innerHTML = "";
  box.insertAdjacentHTML("beforeend", `<div class="msg user">${esc(text)}</div>`);
  box.insertAdjacentHTML("beforeend", `<div class="ag-typing" id="ag-typing">agent is thinking…</div>`);
  box.scrollTop = box.scrollHeight;
  try {
    const r = await api("/api/agent/chat", { method: "POST", body: JSON.stringify({
      instance: agState.instance, message: text, thread_id: agState.thread, branch: agState.branch, model: agState.model,
    }) });
    agState.thread = r.thread_id;
    $("ag-typing")?.remove();
    box.insertAdjacentHTML("beforeend", `<div class="msg assistant">${esc(r.reply)}</div><div class="msg-meta">${esc((r.model || "").replace("databricks-", ""))} · ${r.prompt_tokens}+${r.completion_tokens} tok · ${r.latency_ms}ms · ${money(r.cost_usd)} — logged to agent.interactions</div>`);
    box.scrollTop = box.scrollHeight;
    $("ag-thread-label").textContent = `${agState.thread}${agState.branch !== "main" ? " ⎇ " + agState.branch : ""}`;
    loadThreads(); loadCost();
  } catch (e) {
    $("ag-typing")?.remove();
    toast("Chat failed: " + e.message);
  }
});

/* ── branch modal ────────────────────────────────────────── */
$("ag-branch-btn").addEventListener("click", () => {
  if (!agState.thread) return toast("Open a thread to branch it");
  $("branch-modal").hidden = false;
});
$("branch-cancel").addEventListener("click", () => { $("branch-modal").hidden = true; });
$("branch-modal").addEventListener("click", (ev) => { if (ev.target === $("branch-modal")) $("branch-modal").hidden = true; });
document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") $("branch-modal").hidden = true; });
$("branch-confirm").addEventListener("click", async () => {
  const nb = ($("branch-name").value || "").trim();
  if (!nb) return;
  $("branch-modal").hidden = true;
  try {
    await api("/api/agent/branch", { method: "POST", body: JSON.stringify({
      instance: agState.instance, thread_id: agState.thread, new_branch: nb, source_branch: agState.branch,
    }) });
    toast(`Branched to ⎇ ${nb} — pick a different model and re-run.`, true);
    agState.branch = nb; await openThread(); loadThreads();
  } catch (e) { toast("Branch failed: " + e.message); }
});

/* ── init ────────────────────────────────────────────────── */
loadConfig();
