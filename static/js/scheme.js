/* Scheme detail page: checklist, rule transparency, packet, simulated submit */
(async () => {
  await Chrome.boot("/schemes.html", [["/schemes.html","Schemes"],[location.href,"Details"]]);
  const $ = (id) => document.getElementById(id);
  const id = new URLSearchParams(location.search).get("id");
  if (!id) { location.href = "/schemes.html"; return; }
  const pid = App.personId();
  let d;
  try { d = await App.api(`/api/schemes/${encodeURIComponent(id)}` + (pid ? `?person_id=${pid}` : "")); }
  catch (e) { App.toast(e.message, "err"); return; }

  $("name").textContent = d.name; $("benefit").textContent = d.benefit; $("cat").textContent = d.category || "";
  document.title = d.name + " - Scheme Sniper";
  const ok = d.status === "approved";
  $("meta").innerHTML = `<span class="badge ${ok ? "b-ok" : "b-warn"}">${ok ? "✓ " + App.esc(App.t("badge_verified")) : "⚠ " + App.esc(App.t("badge_unverified"))}</span>
    <span class="muted">${App.esc(App.t("last_verified"))}: ${App.esc(d.last_verified || "—")}</span>`;
  if (d.official_link) { const a = $("official"); a.href = d.official_link; a.textContent = "↗ " + App.t("official_site"); }
  else $("official").classList.add("hidden");
  const L = (k, fb) => App.t(k, fb);
  $("deadline").innerHTML = DeadlineUI.pill(d.deadline) + (d.deadline.quote ? `<p class="dl-quote">${App.esc(L("quote_label", "Official text"))}: “${App.esc(d.deadline.quote)}”</p>` : "") +
    (d.deadline.state === "closed" ? `<div class="notice n-warn" style="margin-top:.5rem">${App.esc(L("dl_closed_note", "The last date has passed. Please check the official website for a new date before you go."))}</div>` : "") +
    (d.deadline.state === "open_ended" ? `<div class="muted" style="font-size:.85rem;margin-top:.3rem">${App.esc(L("dl_none_note", "The official source does not give a last date. Please ask at the office."))}</div>` : "");
  $("tags").innerHTML = (d.tags || []).map((x) => `<span class="chip">${App.esc(L("tag_" + x, x))}</span>`).join("");
  const spokenPage = () => {
    const lines = [d.name + ".", L("benefit_label", "Benefit") + ": " + d.benefit + ".", DeadlineUI.label(d.deadline) + "."];
    lines.push(L("detail_checklist", "Documents checklist") + ".");
    d.documents.forEach((x) => {
      lines.push(x.name + ": " + L(x.have ? "doc_have" : "doc_missing") + ".");
      if (!x.have) {
        if (x.office) lines.push(L("detail_office", "Where to go") + ": " + x.office.name + ".");
        (x.steps || []).forEach((st, i) => lines.push((i + 1) + ". " + st + "."));
      }
    });
    lines.push(L("confirm_before_you_go", "Confirm timings and location before you go."));
    return lines;
  };
  Voice.bar($("voice-slot"), spokenPage);

  const haveN = d.documents.filter((x) => x.have).length;
  $("have-sum").textContent = `${haveN} / ${d.documents.length} ${App.t("have_count")}`;
  $("docs").innerHTML = d.documents.map((x) => `
    <div class="doc-item ${x.have ? "have" : ""} stack">
      <div class="row" style="justify-content:space-between"><b>${x.have ? "✅" : "⬜"} ${App.esc(x.name)}</b>
      <span class="badge ${x.have ? "b-ok" : "b-warn"}">${App.esc(App.t(x.have ? "doc_have" : "doc_missing"))}</span></div>
      ${x.have ? "" : `
        <div><b>${App.esc(App.t("detail_office"))}:</b> ${App.esc(x.office ? x.office.name : "—")}
          ${x.office ? `<div class="muted" style="font-size:.9rem">${App.esc(x.office.address || "")} · ${App.esc(x.office.hours || "")}</div>` : ""}</div>
        <div><b>${App.esc(App.t("detail_carry"))}:</b> ${App.esc((x.what_to_carry || []).join(", "))}</div>
        <div><b>${App.esc(App.t("detail_form"))}:</b> ${App.esc(x.form || "—")}</div>
        ${x.official_link ? `<div><a href="${App.esc(x.official_link)}" target="_blank" rel="noopener">↗ ${App.esc(App.t("detail_link"))}</a></div>` : ""}
        <div><b>${App.esc(App.t("detail_steps"))}:</b><ol class="steps-list">${(x.steps || []).map((s) => `<li>${App.esc(s)}</li>`).join("")}</ol></div>`}
    </div>`).join("");

  try {
    const r = await App.api(`/api/schemes/${encodeURIComponent(id)}/rule`);
    $("rules").innerHTML = r.conditions.map((c) => `
      <div class="cond"><span class="badge ${c.type === "hard" ? "b-info" : "b-warn"}">${App.esc(App.t(c.type === "hard" ? "cond_hard" : "cond_ambiguous"))}</span>
        <code>${App.esc(c.field)} ${App.esc(c.op)} ${App.esc(JSON.stringify(c.value))}</code>
        ${c.quote ? `<blockquote style="flex-basis:100%"><b>${App.esc(App.t("quote_label"))}:</b> “${App.esc(c.quote)}”</blockquote>` : ""}
      </div>`).join("");
  } catch (e) { $("rules").innerHTML = `<p class="muted">—</p>`; }

  $("print").onclick = async () => {
    if (pid) {
      try {
        const p = await App.api(`/api/persons/${pid}`);
        $("values").innerHTML = Object.entries(p.profile).map(([k, v]) => `<div class="row"><b>${App.esc(App.t("f_" + k, k))}:</b> ${App.esc(v)}
          <span class="badge ${p.field_sources[k] === "verified" ? "b-ok" : "b-gray"}">${App.esc(App.t(p.field_sources[k] === "verified" ? "src_verified" : "src_user"))}</span></div>`).join("") || "—";
        $("packet-values").classList.remove("hidden");
      } catch (e) { /* print without values */ }
    }
    setTimeout(() => window.print(), 150);
  };

  const delay = (ms) => new Promise((r) => setTimeout(r, ms));
  $("apply").onclick = async () => {
    if (!App.requireLogin()) return;
    if (!pid) { location.href = "/start.html"; return; }
    $("submit-card").classList.remove("hidden"); $("submit-card").scrollIntoView({ behavior: "smooth" });
    try { const p = await App.api(`/api/persons/${pid}`); if (!p.profile.name) $("name-ask").classList.remove("hidden"); }
    catch (e) { App.toast(e.message, "err"); }
    sendCode();
  };

  // A fresh confirmation code goes to the logged-in user's own phone.
  async function sendCode() {
    try {
      const d = await App.api("/api/submissions/request-code", { method: "POST" });
      $("code-msg").textContent = d.test_mode ? d.message : App.t("code_sent", "A code was sent to your phone.");
      $("code-msg").classList.remove("hidden");
    } catch (e) { App.toast(e.message, "err"); }
  }
  $("resend-code").onclick = sendCode;

  $("go").onclick = async () => {
    const pname = $("pname").value.trim();
    try {
      if (!$("name-ask").classList.contains("hidden")) {
        if (!pname) { App.toast(App.t("field_name_ask"), "err"); return; }
        await App.api("/api/documents/confirm", { method: "POST", json: { person_id: pid, verified_fields: {}, user_stated_fields: { name: pname } } });
      }
      $("go").disabled = true; $("otp-wrap").classList.add("hidden");
      const prog = $("prog"); prog.classList.remove("hidden");
      const lis = prog.querySelectorAll("li");
      ["submit_step1", "submit_step2", "submit_step3"].forEach((k, i) => { lis[i].className = ""; lis[i].dataset.t = App.t(k); lis[i].textContent = "○ " + App.t(k); });
      const mark = (i) => { lis[i].className = "done"; lis[i].textContent = "✔ " + lis[i].dataset.t; };
      lis[0].className = "cur"; await delay(700); mark(0);
      lis[1].className = "cur";
      const receipt = await App.api("/api/submissions", { method: "POST", json: { person_id: pid, scheme_id: id, otp_code: $("otp").value.trim() } });
      await delay(600); mark(1); lis[2].className = "cur"; await delay(600); mark(2);
      sessionStorage.setItem("ss_receipt", JSON.stringify({ ...receipt, scheme_name: d.name, benefit: d.benefit }));
      location.href = "/receipt.html";
    } catch (e) {
      App.toast(e.message, "err"); $("go").disabled = false; $("otp-wrap").classList.remove("hidden"); $("prog").classList.add("hidden");
    }
  };
})();
