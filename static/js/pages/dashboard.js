/* My data: see, edit, remove, withdraw consent, download, delete. Everything goes through /api/me. */
(async () => {
  await Chrome.boot("/dashboard.html", [["/dashboard.html", "My data"]]);
  if (!App.requireLogin()) return;
  const $ = (id) => document.getElementById(id);
  const L = (k, fb) => App.t(k, fb);
  let me = null;
  const fail = (e) => App.toast(e.message, "err");
  const ok = (k, fb) => App.toast(L(k, fb), "ok");

  async function loadApps() {
    const pid = App.personId() || (me.people[0] && me.people[0].id);
    const none = `<p class="muted">${App.esc(L("md_no_apps", "No applications yet."))}</p>`;
    if (!pid) { $("subs").innerHTML = none; return; }
    try {
      const s = await App.api(`/api/submissions/person/${pid}`);
      $("subs").innerHTML = s.submissions.map((x) => `<div class="row" style="justify-content:space-between;border-bottom:1px solid var(--line);padding:.5rem 0">
        <span><b>${App.esc(x.scheme_id)}</b><div class="muted" style="font-size:.85rem">${App.esc(x.arn)}</div></span>
        <span><span class="badge b-info">${App.esc(L("st_" + x.status, x.status))}</span> <a class="btn btn-sm btn-ghost" href="/track.html?arn=${encodeURIComponent(x.arn)}">${App.esc(L("receipt_track", "Track"))}</a></span></div>`).join("") || none;
    } catch (e) { $("subs").innerHTML = none; }
  }

  async function load() {
    me = await App.api("/api/me/people");
    $("people").innerHTML = me.people.length ? me.people.map((p) => MyDataView.person(p, me.role)).join("")
      : `<div class="card empty"><div class="big">📭</div><p>${App.esc(L("md_none", "No details are saved."))}</p><a class="btn" href="/start.html">${App.esc(L("nav_check", "Check eligibility"))}</a></div>`;
    $("danger").classList.toggle("hidden", me.role !== "citizen");
    document.querySelectorAll("[data-person]").forEach(bind);
    loadApps();
  }

  function bindRow(card, pid, row) {
    const f = row.dataset.f, person = me.people.find((x) => x.id === pid);
    row.querySelector("[data-act=del]").onclick = async () => {
      if (!confirm(L("md_confirm_rm", "Remove this value?"))) return;
      try { await App.api(`/api/me/people/${pid}/fields/${f}`, { method: "DELETE" }); ok("md_removed", "Removed"); load(); } catch (e) { fail(e); }
    };
    row.querySelector("[data-act=edit]").onclick = () => {
      row.querySelector("[data-show]").innerHTML = MyDataView.input(f, person.profile[f]);
      row.querySelector(".acts").innerHTML = `<button class="btn-sm" data-act="save">${App.esc(L("save", "Save"))}</button><button class="btn-sm btn-ghost" data-act="cancel">${App.esc(L("md_cancel", "Cancel"))}</button>`;
      row.querySelector("[data-act=cancel]").onclick = load;
      row.querySelector("[data-act=save]").onclick = async () => {
        try { await App.api(`/api/me/people/${pid}/fields/${f}`, { method: "PUT", json: { value: row.querySelector("[data-input]").value } }); ok("md_saved", "Saved"); load(); }
        catch (e) { fail(e); }
      };
    };
  }

  function bind(card) {
    const pid = card.dataset.person, person = me.people.find((x) => x.id === pid);
    card.querySelectorAll(".field-edit").forEach((row) => bindRow(card, pid, row));
    card.querySelector("[data-pick]").onclick = () => localStorage.setItem("ss_person_id", pid);
    card.querySelector("[data-act=rename]").onclick = async () => {
      const name = prompt(L("field_name_ask", "Name"), person.display_name || "");
      if (name === null) return;
      try { await App.api(`/api/me/people/${pid}/name`, { method: "PUT", json: { name } }); load(); } catch (e) { fail(e); }
    };
    const dp = card.querySelector("[data-act=delperson]");
    if (dp) dp.onclick = async () => {
      if (!confirm(L("delete_confirm"))) return;
      try { await App.api(`/api/me/people/${pid}`, { method: "DELETE" }); if (App.personId() === pid) localStorage.removeItem("ss_person_id"); load(); } catch (e) { fail(e); }
    };
    card.querySelectorAll(".tick-cross").forEach((g) => g.querySelectorAll("button").forEach((b) => b.onclick = async () => {
      const on = b.dataset.v === "1";
      const save = g.dataset.c === "save" ? on : person.consent.save_profile;
      const notify = g.dataset.c === "notify" ? on : person.consent.notifications;
      try { await App.api(`/api/me/people/${pid}/consent`, { method: "PUT", json: { save_profile: save, notifications: notify } }); ok("md_saved", "Saved"); load(); }
      catch (e) { fail(e); }
    }));
  }

  $("export").onclick = async () => {
    try {
      const data = await App.api("/api/me/export");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      a.download = "my-scheme-sniper-data.json"; a.click(); URL.revokeObjectURL(a.href);
    } catch (e) { fail(e); }
  };
  $("erase").onclick = async () => {
    if (!confirm(L("md_confirm_erase", "Delete your account and ALL your data? This cannot be undone."))) return;
    try { await App.api("/api/me/account", { method: "DELETE" }); localStorage.clear(); ok("deleted", "Deleted"); setTimeout(() => (location.href = "/"), 900); }
    catch (e) { fail(e); }
  };

  Voice.bar($("voice-slot"), () => [L("md_title", "My data"), L("md_promise")]);
  load().catch(fail);
})();
