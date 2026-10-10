(async () => {
  await Chrome.boot("/csc.html", [["/csc.html","CSC desk"]]);
  const $ = (id) => document.getElementById(id);

  async function people() {
    try {
      const d = await App.api("/api/csc/people");
      $("denied").classList.add("hidden");
      $("people").innerHTML = d.people.map((p) => `
        <div class="row" style="justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:.5rem">
          <span><b>${App.esc(p.display_name || "(unnamed)")}</b></span>
          <span><button class="btn-sm" data-open="${App.esc(p.id)}" data-name="${App.esc(p.display_name || "")}">Continue</button>
          <button class="btn-sm btn-danger" data-del="${App.esc(p.id)}">Delete</button></span></div>`).join("") || `<p class="muted">No people yet.</p>`;
      $("people").querySelectorAll("[data-open]").forEach((b) => b.onclick = () => {
        localStorage.setItem("ss_person_id", b.dataset.open); localStorage.setItem("ss_person_name", b.dataset.name); location.href = "/start.html";
      });
      $("people").querySelectorAll("[data-del]").forEach((b) => b.onclick = async () => {
        if (!confirm(App.t("delete_confirm"))) return;
        try { await App.api("/api/persons/" + b.dataset.del, { method: "DELETE" }); people(); queue(); } catch (e) { App.toast(e.message, "err"); }
      });
    } catch (e) { if (e.status === 401 || e.status === 403) $("denied").classList.remove("hidden"); else App.toast(e.message, "err"); }
  }

  async function queue() {
    try {
      const d = await App.api("/api/submissions/queue");
      $("queue").innerHTML = `<tr><th>Reference</th><th>Scheme</th><th>Status</th><th></th></tr>` + d.submissions.map((s) => `
        <tr><td><b>${App.esc(s.arn)}</b></td><td>${App.esc(s.scheme_id)}</td>
        <td><span class="badge b-info">${App.esc(App.t("st_" + s.status, s.status))}</span></td>
        <td><button class="btn-sm" data-adv="${App.esc(s.id)}">Advance</button></td></tr>`).join("");
      $("queue").querySelectorAll("[data-adv]").forEach((b) => b.onclick = async () => {
        try { await App.api(`/api/submissions/${b.dataset.adv}/advance`, { method: "POST" }); queue(); } catch (e) { App.toast(e.message, "err"); }
      });
    } catch (e) { /* denied handled above */ }
  }

  $("add").onclick = async () => {
    const name = $("pn").value.trim();
    if (!name) { App.toast("Enter a name", "err"); return; }
    try {
      const d = await App.api("/api/persons", { method: "POST", json: { display_name: name, language: App.lang() } });
      localStorage.setItem("ss_person_id", d.person_id); localStorage.setItem("ss_person_name", name); location.href = "/start.html";
    } catch (e) { App.toast(e.message, "err"); }
  };
  people(); queue();
})();
