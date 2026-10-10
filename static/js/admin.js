/* Admin dashboard logic */
(async () => {
  await Chrome.boot("/admin.html", [["/admin.html","Admin"]]);
  const $ = (id) => document.getElementById(id);
  let current = null; // rule version being reviewed

  async function load() {
    try {
      const [st, dash, tk, au] = await Promise.all([
        App.api("/api/admin/stats"), App.api("/api/admin/dashboard"),
        App.api("/api/admin/change-tickets"), App.api("/api/admin/audit")]);
      $("denied").classList.add("hidden");
      $("kpis").innerHTML = [["Schemes", st.schemes], ["Drafts waiting", st.drafts_waiting], ["Open tickets", st.open_tickets],
        ["People", st.people], ["Submissions", st.submissions]].map(([k, v]) => `<div class="card kpi"><b>${v}</b><span>${k}</span></div>`).join("");
      const B = { approved: "b-ok", draft: "b-gray", in_review: "b-info", needs_update: "b-bad" };
      $("schemes").innerHTML = `<tr><th>Scheme</th><th>Status</th><th>Last verified</th><th></th></tr>` + dash.schemes.map((s) => `
        <tr><td><b>${App.esc(s.name)}</b><div class="muted">${App.esc(s.scheme_id)}</div></td>
        <td><span class="badge ${B[s.status] || "b-gray"}">${App.esc(s.status)}</span></td><td>${App.esc(s.last_verified || "—")}</td>
        <td><button class="btn-sm" data-r="${App.esc(s.scheme_id)}">Review rules</button></td></tr>`).join("");
      $("schemes").querySelectorAll("[data-r]").forEach((b) => b.onclick = () => openReview(b.dataset.r));
      $("tickets").innerHTML = tk.change_tickets.length ? tk.change_tickets.map((t) =>
        `<div>• ${App.esc(t.scheme_id)} — ${App.esc(t.status)} <span class="muted">(${App.esc(t.created_at.slice(0, 10))})</span></div>`).join("") : "None";
      $("audit").innerHTML = au.entries.slice(0, 8).map((a) => `<div>${App.esc(a.at.slice(0, 16).replace("T", " "))} · ${App.esc(a.action)} · ${App.esc(a.target || "")}</div>`).join("") || "No actions yet";
    } catch (e) {
      if (e.status === 401 || e.status === 403) $("denied").classList.remove("hidden"); else App.toast(e.message, "err");
    }
  }

  async function openReview(schemeId) {
    try {
      const [rules, src] = await Promise.all([App.api(`/api/admin/rules/${schemeId}`), App.api(`/api/admin/source/${schemeId}`).catch(() => ({ text: "(no source file)" }))]);
      // Latest first; prefer a pending draft if there is one.
      current = rules.rule_versions.find((r) => r.status === "draft") || rules.rule_versions[0];
      if (!current) { App.toast("No rule versions yet. Use Ingest source.", "err"); return; }
      $("rtitle").textContent = `Rule review — ${schemeId} v${current.version} (${current.status})`;
      $("src").textContent = src.text;
      $("json").value = JSON.stringify(current.rule_json, null, 2);
      const text = src.text;
      $("conds").innerHTML = current.rule_json.conditions.map((c) => {
        const q = (c.source && c.source.exact_quote) || "";
        const found = q && text.includes(q);
        return `<div class="cond"><span>${found ? "✅" : "❌"}</span><span class="badge ${c.type === "hard" ? "b-info" : "b-warn"}">${App.esc(c.type)}</span>
          <code>${App.esc(c.field)} ${App.esc(c.op)} ${App.esc(JSON.stringify(c.value))}</code>
          <blockquote style="flex-basis:100%">${App.esc(q)}</blockquote></div>`;
      }).join("");
      $("review").classList.remove("hidden"); $("review").scrollIntoView({ behavior: "smooth" });
    } catch (e) { App.toast(e.message, "err"); }
  }

  async function decide(approve) {
    let edited = null;
    try { edited = JSON.parse($("json").value); } catch (e) { App.toast("Rule JSON is not valid JSON", "err"); return; }
    try {
      await App.api("/api/admin/rules/review", { method: "POST", json: { rule_version_id: current.id, approve, edited_rule_json: approve ? edited : null } });
      App.toast(approve ? "Rule approved" : "Rule rejected", "ok"); $("review").classList.add("hidden"); load();
    } catch (e) { App.toast(e.message, "err"); }
  }
  async function loadStaff() {
    try {
      const d = await App.api("/api/admin/roles");
      $("staff").innerHTML = d.staff.map((s) => `<div>• ${App.esc(s.phone)} — ${App.esc(s.role)}</div>`).join("") || "No staff added yet.";
    } catch (e) { /* denied handled by load() */ }
  }
  $("s-add").onclick = async () => {
    try {
      await App.api("/api/admin/roles", { method: "POST", json: { phone: $("s-phone").value, role: $("s-role").value } });
      App.toast("Access granted", "ok"); $("s-phone").value = ""; loadStaff();
    } catch (e) { App.toast(e.message, "err"); }
  };
  loadStaff();
  $("approve").onclick = () => decide(true);
  $("reject").onclick = () => decide(false);
  $("close").onclick = () => $("review").classList.add("hidden");

  $("refresh").onclick = async () => {
    try { const d = await App.api("/api/admin/run-refresh", { method: "POST" }); App.toast(`Refresh done: ${d.summary.filter((x) => x.changed).length} changed`, "ok"); load(); }
    catch (e) { App.toast(e.message, "err"); }
  };
  load();
})();
