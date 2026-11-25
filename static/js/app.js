const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

const pageTitles = {
  overview: "Your farm intelligence, evolving.",
  assistant: "Ask. Understand. Grow.",
  memory: "Your knowledge, under your control.",
  research: "A research-oriented memory framework"
};

function go(page) {
  $$(".page").forEach(p => p.classList.toggle("active", p.id === "page-" + page));
  $$(".nav").forEach(n => n.classList.toggle("active", n.dataset.page === page));
  $("#heading").textContent = pageTitles[page] || "EvoMindAgri";
  $("#crumb").textContent = page.toUpperCase();
  if (page === "memory") loadMemory();
  if (page === "assistant") loadChatMemory();
}

$$(".nav").forEach(b => b.addEventListener("click", () => go(b.dataset.page)));
$$("[data-go]").forEach(b => b.addEventListener("click", () => go(b.dataset.go)));

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[c]));
}

function date(v) {
  if (!v) return "Date not recorded";
  try {
    return new Date(v).toLocaleString();
  } catch {
    return "";
  }
}

async function api(url, opts = {}) {
  const r = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts
  });
  let d = {};
  try {
    d = await r.json();
  } catch {}
  if (!r.ok) throw Error(d.error || d.message || "Request failed");
  return d;
}

async function loadHealth() {
  try {
    const d = await api("/health");
    $("#db-status").textContent = d.mongodb === "Connected" ? "● MongoDB connected" : "● MongoDB disconnected";
    $("#db-status").style.color = d.mongodb === "Connected" ? "#34754a" : "#a34d4d";
  } catch {
    $("#db-status").textContent = "● API unavailable";
  }
}

async function loadStats() {
  try {
    const d = await api("/api/memory/stats");
    $("#stat-approved").textContent = d.approved ?? 0;
    $("#stat-pending").textContent = d.pending ?? 0;
    $("#stat-general").textContent = d.general ?? 0;
    $("#pending-pill").textContent = d.pending ?? 0;
    $("#tab-pending").textContent = d.pending ?? 0;
    $("#tab-approved").textContent = d.approved ?? 0;
  } catch (e) {
    console.warn(e);
  }
}

function memoryMarkup(m, mode) {
  const title = (m.key || m.category || "Agricultural memory").replaceAll("_", " ");
  const hasHistory = mode === "approved" && (m.version || 1) > 1;

  return `<article class="memory-card">
    <div class="memory-symbol">◈</div>
    <div class="memory-info">
      <strong>${esc(title)}</strong>
      <p>${esc(m.content)}</p>
      <div class="meta">${esc(m.category || "General")} · ${esc(m.scope || "farmer")} · ${esc(date(m.updated_at || m.created_at))}${m.version ? ` · Version ${m.version}` : ""}</div>
      ${mode === "pending" ? `
        <div class="actions">
          <button class="approve" data-approve="${esc(m._id)}">✓ Approve & save</button>
          <button class="reject" data-reject="${esc(m._id)}">Decline</button>
        </div>` : ""}
      ${hasHistory ? `
        <div class="actions">
          <button class="outline" data-versions="${esc(m._id)}">↻ View version history (${m.version - 1} prior)</button>
        </div>
        <div class="mini-list" id="versions-${esc(m._id)}" hidden></div>` : ""}
    </div>
    ${mode === "approved" ? '<span class="approved-tag">✓ Approved</span>' : ""}
  </article>`;
}

async function loadMemory() {
  loadStats();
  try {
    const [p, a, l] = await Promise.all([
      api("/api/memory/proposals"),
      api("/api/memory/approved"),
      api("/api/memory/audit")
    ]);

    const archivedCount = a.memories.reduce((sum, m) => sum + Math.max(0, (m.version || 1) - 1), 0);
    $("#stat-versions").textContent = archivedCount;

    $("#pending-list").innerHTML = p.proposals.length
      ? p.proposals.map(m => memoryMarkup(m, "pending")).join("")
      : '<div class="panel empty">No memories are waiting for review. Share personal farm information in the assistant to create a proposal.</div>';

    $("#approved-list").innerHTML = a.memories.length
      ? a.memories.map(m => memoryMarkup(m, "approved")).join("")
      : '<div class="panel empty">No approved memories yet. Approve a proposal and it will be saved permanently in your MongoDB database.</div>';

    $("#audit-list").innerHTML = l.logs.length
      ? l.logs.map(x => `<article class="memory-card"><div class="memory-symbol">↻</div><div class="memory-info"><strong>${esc((x.action || "memory event").replaceAll("_", " "))}</strong><p>${esc(JSON.stringify(x.details || {}))}</p><div class="meta">${esc(date(x.timestamp))}</div></div></article>`).join("")
      : '<div class="panel empty">No activity recorded yet.</div>';

    $("#recent-memories").innerHTML = a.memories.slice(0, 4)
      .map(m => `<div class="recent-item"><strong>${esc((m.key || "memory").replaceAll("_", " "))}</strong><small>${esc(m.content)} · ${esc(date(m.updated_at))}</small></div>`)
      .join("") || '<div class="empty">Your approved records will appear here.</div>';

    $("#chat-memory-count").textContent = a.memories.length;
    $("#chat-memory-preview").innerHTML = a.memories.slice(0, 4)
      .map(m => `• ${esc(m.content)}`)
      .join("<br>") || "No approved memories yet.";
  } catch (e) {
    $("#pending-list").innerHTML = `<div class="panel empty">Could not load memory records: ${esc(e.message)}. Check MongoDB connection.</div>`;
  }
}

$$(".tab").forEach(b => b.addEventListener("click", () => {
  $$(".tab").forEach(t => t.classList.toggle("active", t === b));
  $$(".memory-content").forEach(x => x.hidden = x.id !== "memory-" + b.dataset.tab);
}));

document.addEventListener("click", async e => {
  const a = e.target.closest("[data-approve]");
  const r = e.target.closest("[data-reject]");
  const v = e.target.closest("[data-versions]");

  if (a) {
    a.disabled = true;
    a.textContent = "Saving…";
    try {
      const d = await api("/api/memory/approve/" + a.dataset.approve, { method: "POST" });
      await loadMemory();
      alert(d.message || "Memory saved.");
    } catch (err) {
      a.disabled = false;
      a.textContent = "✓ Approve & save";
      alert(err.message);
    }
  }

  if (r) {
    if (!confirm("Decline this memory proposal?")) return;
    r.disabled = true;
    try {
      await api("/api/memory/reject/" + r.dataset.reject, {
        method: "POST",
        body: JSON.stringify({ reason: "Declined by farmer" })
      });
      loadMemory();
    } catch (err) {
      r.disabled = false;
      alert(err.message);
    }
  }

  if (v) {
    const box = $("#versions-" + v.dataset.versions);
    if (!box.hidden) {
      box.hidden = true;
      return;
    }
    box.hidden = false;
    box.textContent = "Loading prior versions…";
    try {
      const d = await api("/api/memory/versions/" + v.dataset.versions);
      box.innerHTML = d.versions.length
        ? d.versions.map(ver => `• <b>v${esc(ver.version)}</b>: ${esc(ver.content)} <span class="meta">(${esc(date(ver.archived_at || ver.updated_at))})</span>`).join("<br>")
        : "No prior versions archived.";
    } catch (err) {
      box.textContent = "Could not load versions: " + err.message;
    }
  }
});

function addMessage(role, text) {
  const box = $("#chat-messages");
  const welcome = box.querySelector(".welcome-chat");
  if (welcome) welcome.remove();
  const div = document.createElement("div");
  div.className = "message " + role;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  div.appendChild(bubble);
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

async function sendMessage(text) {
  const input = $("#user-input");
  const message = (text ?? input.value).trim();
  if (!message) return;
  input.value = "";
  addMessage("user", message);
  const btn = $("#send-button");
  btn.disabled = true;
  btn.textContent = "…";
  try {
    const d = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message })
    });
    addMessage("bot", d.response || "No response received.");
    if (d.memory_proposals?.length) {
      addMessage("bot", `${d.memory_proposals.length} memory proposal(s) were created. Open Adaptive memory to review and approve them. They are not saved as approved memories until you approve.`);
      $("#pending-pill").textContent = Number($("#pending-pill").textContent || 0) + d.memory_proposals.length;
    }
    loadStats();
    loadChatMemory();
  } catch (e) {
    addMessage("bot", "I could not process that request. Please check that MongoDB and Ollama are running. Details: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "↑";
    input.focus();
  }
}

$("#chat-form").addEventListener("submit", e => {
  e.preventDefault();
  sendMessage();
});

$("#user-input").addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

document.addEventListener("click", e => {
  const b = e.target.closest(".suggestions button");
  if (b) {
    go("assistant");
    sendMessage(b.textContent);
  }
});

$("#clear-chat").addEventListener("click", () => {
  $("#chat-messages").innerHTML = '<div class="empty">Chat view cleared. Your saved conversation and approved memories are not deleted.</div>';
});

$("#refresh-all").addEventListener("click", () => {
  loadHealth();
  loadStats();
  loadMemory();
});

async function loadChatMemory() {
  try {
    const d = await api("/api/memory/approved");
    $("#chat-memory-count").textContent = d.memories.length;
    $("#chat-memory-preview").innerHTML = d.memories.slice(0, 5)
      .map(m => "• " + esc(m.content))
      .join("<br>") || "No approved memories yet.";
  } catch {
    $("#chat-memory-preview").textContent = "Memory service unavailable.";
  }
}

loadHealth();
loadStats();
loadMemory();