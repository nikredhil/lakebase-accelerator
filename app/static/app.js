/* Lakebase Accelerator UI — manages Lakebase (Postgres) database instances */

const $ = (id) => document.getElementById(id);
const REFRESH_MS = 10000;

let pendingDestroy = null;
const expanded = new Set(); // use cases whose card is expanded (survives refresh)

/* ── helpers ─────────────────────────────────────────────── */

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
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

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}

function pillClass(state) {
  if (state === "AVAILABLE") return "pill-running";
  if (["STARTING", "UPDATING", "DELETING", "FAILING_OVER"].includes(state)) return "pill-pending";
  if (state === "STOPPED") return "pill-stopped";
  return "pill-error";
}

function parseTags(raw) {
  const tags = {};
  for (const pair of (raw || "").split(",")) {
    const i = pair.indexOf("=");
    if (i > 0) tags[pair.slice(0, i).trim()] = pair.slice(i + 1).trim();
  }
  return tags;
}

function slug(usecase) {
  return "lakebase-" + usecase.toLowerCase().replace(/_/g, "-");
}

/* ── modal ───────────────────────────────────────────────── */

function openModal(usecase) {
  pendingDestroy = usecase;
  $("modal-usecase").textContent = usecase;
  $("modal").hidden = false;
}

function closeModal() {
  $("modal").hidden = true;
  pendingDestroy = null;
}

$("modal-cancel").addEventListener("click", closeModal);
$("modal").addEventListener("click", (ev) => {
  if (ev.target === $("modal")) closeModal();
});
document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape") closeModal();
});

$("modal-confirm").addEventListener("click", async () => {
  const usecase = pendingDestroy;
  closeModal();
  if (!usecase) return;
  toast(`Destroying '${usecase}'…`, true);
  try {
    await api("/api/destroy", { method: "POST", body: JSON.stringify({ usecase }) });
    expanded.delete(usecase);
    toast(`'${usecase}' destroyed — billing stopped`, true);
  } catch (e) {
    toast("Destroy failed: " + e.message);
  }
  await refresh();
});

/* ── config ──────────────────────────────────────────────── */

async function loadConfig() {
  try {
    const cfg = await api("/api/config");
    $("host-chip").textContent = new URL(cfg.host).hostname;
    if (cfg.user) {
      $("user-chip").textContent = cfg.user;
      $("user-chip").hidden = false;
    }
    // Agent Backbone link stays hidden for the demo (not part of the retail twin flow).
  } catch (e) {
    toast("Could not load workspace config: " + e.message);
  }
}

/* ── deployments list ────────────────────────────────────── */

function renderDeployment(d) {
  const open = expanded.has(d.usecase);
  const stoppable = d.state === "AVAILABLE";
  const startable = d.state === "STOPPED";
  const cap = (d.capacity || "").replace("CU_", "") + " CU";
  const isBackbone = (d.tags || {}).blueprint === "stateful-agent-backbone";
  const tags = Object.entries(d.tags || {})
    .map(([k, v]) => `<span class="tag">${esc(k)}=${esc(v)}</span>`)
    .join("");
  const nextSteps = isBackbone ? `
      <div class="bp-nextsteps">
        <h4>Next steps</h4>
        <ol class="bp-next">
          <li>Open the <b>Agent Backbone</b> app (link in the top nav) and click <b>Apply schema</b> to create the <code>agent.*</code> memory + eval tables.</li>
          <li>Chat with the agent there — every turn is logged to <code>agent.interactions</code> with its <code>cost_usd</code>.</li>
          <li>Register this instance in Unity Catalog and sync <code>agent.interactions</code> to Delta for zero-ETL eval.</li>
        </ol>
      </div>` : "";
  return `
  <div class="dep-card${open ? " open" : ""}" data-card="${esc(d.usecase)}">
    <button type="button" class="dep-head" data-toggle="${esc(d.usecase)}"
            title="${open ? "Collapse" : "Expand to manage"}">
      <svg class="chev" viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
        <path d="M6 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span class="dep-name">${esc(d.usecase)}</span>
      ${isBackbone ? `<span class="badge bp-badge">backbone</span>` : ""}
      <span class="dep-sub">${esc(cap)}${d.pg_version ? " &middot; Postgres " + esc(d.pg_version) : ""}</span>
      <span class="pill ${pillClass(d.state)}">${esc(d.state)}</span>
    </button>
    <div class="dep-body">
      <div class="dep-meta">
        <span>instance <b>${esc(d.name)}</b></span>
        <span>size <b>${esc(cap)}</b></span>
        ${d.pg_version ? `<span>postgres <b>${esc(d.pg_version)}</b></span>` : ""}
        ${d.retention_days ? `<span>restore window <b>${esc(String(d.retention_days))}d</b></span>` : ""}
      </div>
      ${d.endpoint ? `
      <div class="endpoint" title="Postgres endpoint (port 5432, sslmode=require)">
        <span>${esc(d.endpoint)}</span>
        <button type="button" data-copy="${esc(d.endpoint)}">copy</button>
      </div>` : ""}
      ${tags ? `<div class="dep-tags">${tags}</div>` : ""}
      ${nextSteps}
      <div class="dep-actions">
        ${startable ? `<button class="btn btn-ghost" data-start="${esc(d.name)}">&#9654; Start</button>` : ""}
        ${stoppable ? `<button class="btn btn-ghost" data-stop="${esc(d.name)}">&#9632; Stop</button>` : ""}
        <a class="btn btn-ghost" href="${esc(d.url)}" target="_blank" rel="noopener">Open in workspace &#8599;</a>
        <button class="btn btn-outline-danger" data-destroy="${esc(d.usecase)}">Destroy&hellip;</button>
      </div>
    </div>
  </div>`;
}

// usecase -> JSON of the last-rendered deployment, so a poll only touches the DOM
// for cards whose data actually changed (no full re-render → no flicker / animation restart).
let lastByUsecase = {};

async function refresh() {
  let deps;
  try {
    deps = await api("/api/deployments");
  } catch (e) {
    toast("Refresh failed: " + e.message);
    return;
  }
  $("empty-state").hidden = deps.length > 0;

  const list = $("deployments-list");
  const next = {};
  const seen = new Set();

  // Upsert: create new cards, re-render changed ones, leave unchanged cards alone.
  for (const d of deps) {
    seen.add(d.usecase);
    const json = JSON.stringify(d);
    next[d.usecase] = json;
    const node = list.querySelector(`[data-card="${d.usecase}"]`);
    if (node && lastByUsecase[d.usecase] === json) continue; // unchanged → don't touch the DOM
    if (node) node.outerHTML = renderDeployment(d);          // changed → re-render just this card
    else list.insertAdjacentHTML("beforeend", renderDeployment(d)); // new card
  }

  // Remove cards for deployments that no longer exist.
  for (const node of list.querySelectorAll("[data-card]")) {
    if (!seen.has(node.getAttribute("data-card"))) node.remove();
  }

  // Order the DOM to match `deps`, moving ONLY misplaced nodes. Re-inserting a node
  // restarts its CSS animation, so in-place (unchanged) cards must never be touched —
  // a stable list does zero moves here, which is what kills the per-poll flicker.
  let ref = list.firstElementChild;
  for (const d of deps) {
    const node = list.querySelector(`[data-card="${d.usecase}"]`);
    if (!node) continue;
    if (node === ref) ref = ref.nextElementSibling; // already in place
    else list.insertBefore(node, ref);              // move only if out of order
  }

  lastByUsecase = next;
}

/* ── deployment interactions (expand / start / stop / destroy / copy) ── */

$("deployments-list").addEventListener("click", async (ev) => {
  const head = ev.target.closest("[data-toggle]");
  if (head) {
    const usecase = head.dataset.toggle;
    const card = head.closest(".dep-card");
    if (expanded.has(usecase)) {
      expanded.delete(usecase);
      card.classList.remove("open");
    } else {
      expanded.add(usecase);
      card.classList.add("open");
    }
    return;
  }

  const btn = ev.target.closest("button");
  if (!btn) return;

  if (btn.dataset.copy) {
    try {
      await navigator.clipboard.writeText(btn.dataset.copy);
      btn.textContent = "copied!";
      setTimeout(() => { btn.textContent = "copy"; }, 1500);
    } catch (_) {
      toast("Copy failed — select the text manually");
    }
    return;
  }
  if (btn.dataset.destroy) {
    openModal(btn.dataset.destroy);
    return;
  }
  const action = btn.dataset.start ? "start" : btn.dataset.stop ? "stop" : null;
  if (!action) return;
  const name = btn.dataset.start || btn.dataset.stop;
  btn.disabled = true;
  try {
    await api(`/api/instances/${encodeURIComponent(name)}/${action}`, { method: "POST" });
    toast(`Database ${action === "start" ? "starting" : "stopping — billing paused, data kept"}…`, true);
    await refresh();
  } catch (e) {
    toast(`${action} failed: ` + e.message);
    btn.disabled = false;
  }
});

$("refresh-btn").addEventListener("click", refresh);

/* ── deploy form ─────────────────────────────────────────── */

let capacity = "CU_1";
$("f-capacity").addEventListener("click", (ev) => {
  const opt = ev.target.closest(".seg-opt");
  if (!opt) return;
  capacity = opt.dataset.cap;
  for (const el of $("f-capacity").querySelectorAll(".seg-opt")) {
    el.classList.toggle("selected", el === opt);
  }
});

$("f-usecase").addEventListener("input", () => {
  const v = $("f-usecase").value.trim();
  $("name-preview").textContent = v ? slug(v) : "lakebase-…";
});

$("deploy-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const btn = $("deploy-btn");
  btn.disabled = true;
  btn.querySelector(".spinner").hidden = false;
  btn.querySelector(".btn-label").textContent = "Deploying…";
  try {
    const retention = $("f-retention").value.trim();
    const body = {
      usecase: $("f-usecase").value.trim(),
      capacity,
      retention_days: retention ? parseInt(retention, 10) : null,
      custom_tags: parseTags($("f-tags").value),
    };
    const res = await api("/api/deploy", { method: "POST", body: JSON.stringify(body) });
    toast(`Deployed '${body.usecase}' — database ${res.name} is provisioning`, true);
    expanded.add(body.usecase); // show the new deployment expanded
    $("f-usecase").value = "";
    $("name-preview").textContent = "lakebase-…";
    await refresh();
  } catch (e) {
    toast("Deploy failed: " + e.message);
  } finally {
    btn.disabled = false;
    btn.querySelector(".spinner").hidden = true;
    btn.querySelector(".btn-label").textContent = "Deploy";
  }
});

/* ════════════════════════════════════════════════════════════
   View switching (Deploy | Cost center)
   ════════════════════════════════════════════════════════════ */
let costsLoaded = false;

function showView(view) {
  $("view-deploy").hidden = view !== "deploy";
  $("view-costs").hidden = view !== "costs";
  for (const el of $("subnav").querySelectorAll(".seg-opt")) {
    el.classList.toggle("selected", el.dataset.view === view);
  }
  if (view === "costs" && !costsLoaded) { costsLoaded = true; loadCosts(); }
}
$("subnav").addEventListener("click", (ev) => {
  const opt = ev.target.closest(".seg-opt");
  if (opt) showView(opt.dataset.view);
});

/* ════════════════════════════════════════════════════════════
   Blueprint card
   ════════════════════════════════════════════════════════════ */
let blueprint = null;
let bpSchemaLoaded = false;

async function loadBlueprints() {
  try {
    const list = await api("/api/blueprints");
    blueprint = list[0];
    if (!blueprint) return;
    $("bp-name").textContent = blueprint.name;
    $("bp-tagline").textContent = blueprint.tagline;
    $("bp-detail").innerHTML = renderBlueprintDetail(blueprint);
    $("blueprint-card").hidden = false;
  } catch (_) { /* blueprint card is optional */ }
}

function renderBlueprintDetail(bp) {
  const props = bp.value_props.map((p) => `<li>${esc(p)}</li>`).join("");
  const diff = bp.differentiation
    .map((d) => `<tr><td>${esc(d.vs)}</td><td>${esc(d.why)}</td></tr>`).join("");
  return `
    <h4>What you get</h4>
    <ul class="bp-props">${props}</ul>
    <h4>Why Lakebase</h4>
    <table class="bp-diff"><tbody>${diff}</tbody></table>
    <div class="bp-deploy-row">
      <label class="field">
        <span>Cost center</span>
        <input id="bp-cost-center" type="text" placeholder="e.g. ml-platform" value="ml-platform">
      </label>
      <button class="btn btn-primary" id="bp-deploy-btn">
        <span class="btn-label">Deploy backbone</span><span class="spinner" hidden></span>
      </button>
    </div>
    <h4>Agent schema module</h4>
    <p class="hint">Applied to the instance from the Agent tab; also available here to run yourself.</p>
    <div class="bp-schema-tools">
      <button class="btn btn-ghost btn-xs" id="bp-schema-copy">Copy SQL</button>
      <a class="btn btn-ghost btn-xs" id="bp-schema-download" download="lakebase_agent_schema.sql">Download .sql</a>
    </div>
    <pre class="bp-schema" id="bp-schema">Loading schema…</pre>
    <h4>Next steps</h4>
    <ol class="bp-next">${bp.next_steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>`;
}

$("bp-toggle").addEventListener("click", async () => {
  const card = $("blueprint-card");
  const open = card.classList.toggle("open");
  $("bp-detail").hidden = !open;
  if (open && !bpSchemaLoaded) {
    bpSchemaLoaded = true;
    try {
      const { sql } = await api(`/api/blueprints/${blueprint.slug}/schema`);
      $("bp-schema").textContent = sql;
      const a = $("bp-schema-download");
      a.href = "data:text/plain;charset=utf-8," + encodeURIComponent(sql);
    } catch (_) { $("bp-schema").textContent = "(schema unavailable)"; }
  }
});

$("bp-detail").addEventListener("click", async (ev) => {
  const t = ev.target.closest("button, a");
  if (!t) return;
  if (t.id === "bp-schema-copy") {
    try { await navigator.clipboard.writeText($("bp-schema").textContent); t.textContent = "Copied!"; setTimeout(() => t.textContent = "Copy SQL", 1500); }
    catch (_) { toast("Copy failed"); }
    return;
  }
  if (t.id === "bp-deploy-btn") {
    const cc = ($("bp-cost-center").value || "").trim();
    t.disabled = true;
    t.querySelector(".spinner").hidden = false;
    t.querySelector(".btn-label").textContent = "Deploying…";
    try {
      const res = await api(`/api/blueprints/${blueprint.slug}/deploy`,
        { method: "POST", body: JSON.stringify({ cost_center: cc }) });
      toast(`Backbone deploying — ${res.name}. Open the Agent tab once it's available.`, true);
      expanded.add(blueprint.usecase);
      await refresh();
    } catch (e) {
      toast("Blueprint deploy failed: " + e.message);
    } finally {
      t.disabled = false;
      t.querySelector(".spinner").hidden = true;
      t.querySelector(".btn-label").textContent = "Deploy backbone";
    }
  }
});

/* ════════════════════════════════════════════════════════════
   Cost center view
   ════════════════════════════════════════════════════════════ */
let costData = null;

async function loadCosts() {
  const days = parseInt($("cost-days").value, 10);
  $("cost-buckets").innerHTML = `<div class="cost-empty">Loading costs…</div>`;
  try {
    costData = await api(`/api/costs?days=${days}`);
    renderCosts(costData);
  } catch (e) {
    $("cost-buckets").innerHTML = `<div class="cost-empty">Cost data unavailable: ${esc(e.message)}</div>`;
  }
}
$("cost-refresh").addEventListener("click", loadCosts);
$("cost-days").addEventListener("change", loadCosts);

function money(v) { return v == null ? "—" : "$" + Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

function renderCosts(c) {
  // source badge + note
  const live = c.source === "live";
  const badge = $("cost-source");
  badge.textContent = live ? "live · system.billing" : "rate estimate";
  badge.className = "badge " + (live ? "bp-badge" : "");
  badge.style.background = live ? "#E5F3E6" : "";
  badge.style.color = live ? "#2E7D32" : "";
  const note = $("cost-note");
  if (c.note && !live) { note.hidden = false; note.textContent = c.note; } else { note.hidden = true; }

  // three buckets
  const labels = { agent: "Agent (model serving)", app: "App (Databricks Apps)", lakebase: "Lakebase (database)" };
  const uptimeByBucket = {};
  (c.breakdown || []).forEach((r) => {
    if (r.uptime_hours != null) uptimeByBucket[r.bucket] = (uptimeByBucket[r.bucket] || 0) + r.uptime_hours;
  });
  $("cost-buckets").innerHTML = ["agent", "app", "lakebase"].map((b) => {
    const v = (c.buckets || {})[b] || {};
    let sub;
    if (!live) sub = "projected / mo";
    else if (b === "agent") sub = "metered per turn";
    else sub = `${(uptimeByBucket[b] || 0).toFixed(1)}h up · cost to date`;
    return `<div class="bucket">
      <div class="b-label">${labels[b]}</div>
      <div class="b-usd">${money(v.usd)}</div>
      <div class="b-sub">${esc(sub)}</div>
      ${v.basis ? `<span class="b-basis">${esc(v.basis)}</span>` : ""}
    </div>`;
  }).join("");

  renderSavings(c);
  renderProjection(c.projection);
  renderBreakdown(c.breakdown || []);
}

function renderSavings(c) {
  const s = c.savings || {};
  const diy = (c.projection && c.projection.assumptions) ? null : null;
  const items = DIY_ITEMS;
  const lines = Object.entries(items).map(([k, v]) =>
    `<div class="save-line"><span>${esc(diyLabel(k))}</span><input type="number" data-diy="${k}" value="${v}"></div>`).join("");
  $("savings-card").innerHTML = `
    <h3>Savings vs DIY</h3>
    <p class="hint">A fragmented stack — separate Postgres + cache + vector DB + eval ETL + ops — vs one governed Lakebase. Edit the monthly $ to fit your environment.</p>
    ${lines}
    <div class="save-line total"><span>DIY total / mo</span><span id="diy-total">${money(diyTotal())}</span></div>
    <div class="save-line total"><span>Lakebase total / mo</span><span id="lb-total">${money(s.lakebase_total)}</span></div>
    <div class="save-headline" id="save-headline"></div>`;
  recomputeSavings(s.lakebase_total);
}

function diyLabel(k) {
  return { managed_postgres: "Managed Postgres", redis_cache: "Redis / cache", vector_db: "Vector DB", eval_etl_compute: "Eval ETL compute", ops_overhead: "Ops overhead" }[k] || k;
}
function diyTotal() { return Object.values(DIY_ITEMS).reduce((a, b) => a + Number(b || 0), 0); }
function recomputeSavings(lakebaseMonthly) {
  const diy = diyTotal();
  const lb = Number(lakebaseMonthly || 0);
  const delta = diy - lb;
  const pct = diy > 0 ? Math.round((delta / diy) * 1000) / 10 : 0;
  $("diy-total").textContent = money(diy);
  $("save-headline").textContent = `Save ${money(delta)}/mo — ${pct}% less than DIY`;
}
$("view-costs").addEventListener("input", (ev) => {
  const inp = ev.target.closest("input[data-diy]");
  if (!inp) return;
  DIY_ITEMS[inp.dataset.diy] = Number(inp.value || 0);
  const lb = costData && costData.savings ? costData.savings.lakebase_total : 0;
  recomputeSavings(lb);
});

function renderProjection(p) {
  if (!p) { $("projection-card").innerHTML = ""; return; }
  const a = p.assumptions || {};
  $("projection-card").innerHTML = `
    <h3>Monthly run-rate</h3>
    <p class="hint">Forward projection from published DBU rates (scale-to-zero assumed).</p>
    <div class="proj-line"><span>Agent (model serving)</span><b>${money(p.agent)}</b></div>
    <div class="proj-line"><span>App (Databricks Apps)</span><b>${money(p.app)}</b></div>
    <div class="proj-line"><span>Lakebase (${esc(String(a.cu))} CU · ${esc(String(a.lakebase_hours_per_day))}h/day)</span><b>${money(p.lakebase)}</b></div>
    <div class="proj-line total"><span><b>Total / mo</b></span><b>${money(p.total)}</b></div>
    <p class="proj-assume">Assumes app ${esc(a.apps_size)} ${esc(String(a.apps_hours_per_day))}h/day; agent ${esc(String(a.agent_in_tokens_per_day || 0))} in / ${esc(String(a.agent_out_tokens_per_day || 0))} out tokens/day. Lakebase ≈0.213 DBU/CU-hr.</p>`;
}

function renderBreakdown(rows) {
  if (!rows.length) {
    $("cost-table").innerHTML = `<div class="cost-empty">No running resources yet. Deploy the backbone and chat with the agent — each resource's cost-to-date (uptime × rate) appears here.</div>`;
    return;
  }
  const head = `<tr><th>Resource</th><th>Bucket</th><th>Cost center</th><th>State</th><th class="num">Uptime</th><th class="num">Rate/hr</th><th class="num">Cost to date</th></tr>`;
  const body = rows.map((r) => `<tr>
    <td><b>${esc(r.resource)}</b><div class="r-detail">${esc(r.detail || r.use_case || "")}</div></td>
    <td><span class="b-pill ${esc(r.bucket)}">${esc(r.bucket)}</span></td>
    <td>${esc(r.cost_center)}</td>
    <td>${esc(r.state || "")}</td>
    <td class="num">${r.uptime_hours != null ? Number(r.uptime_hours).toFixed(1) + "h" : "—"}</td>
    <td class="num">${r.rate_per_hour != null ? "$" + Number(r.rate_per_hour).toFixed(4) : "—"}</td>
    <td class="num">${money(r.usd)}</td>
  </tr>`).join("");
  $("cost-table").innerHTML = `<table class="cost-table"><thead>${head}</thead><tbody>${body}</tbody></table>`;
}

let DIY_ITEMS = { managed_postgres: 200, redis_cache: 100, vector_db: 150, eval_etl_compute: 120, ops_overhead: 250 };

/* ── init ────────────────────────────────────────────────── */

loadConfig();
// loadBlueprints();  // disabled for the demo — hides the Stateful Agent Backbone blueprint card
refresh();
setInterval(() => { if (!$("view-deploy").hidden) refresh(); }, REFRESH_MS);
