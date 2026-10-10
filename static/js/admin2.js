/* Admin part 2a: add a scheme from an official page, and watch pages for changes */
const AdminAdd = (() => {
  const $ = (id) => document.getElementById(id);
  let openMeta = () => {};

  async function loadSources() {
    try {
      const d = await App.api("/api/admin/sources");
      $("sources").innerHTML = `<tr><th>Page</th><th>For</th><th>Last checked</th><th>Status</th><th></th></tr>` + d.sources.map((s) => `
        <tr><td style="word-break:break-all">${App.esc(s.url)}</td><td>${App.esc(s.scheme_id || "finds new schemes")}</td>
        <td>${App.esc(s.last_checked ? s.last_checked.slice(0, 16).replace("T", " ") : "never")}</td>
        <td>${s.last_error ? `<span class="badge b-bad">${App.esc(s.last_error)}</span>` : `<span class="badge b-ok">OK</span>`}</td>
        <td><button class="btn-sm btn-danger" data-del="${App.esc(s.id)}">Remove</button></td></tr>`).join("");
      $("sources").querySelectorAll("[data-del]").forEach((b) => b.onclick = async () => {
        await App.api("/api/admin/sources/" + b.dataset.del, { method: "DELETE" }); loadSources();
      });
    } catch (e) { /* denied: admin.js shows the login message */ }
  }

  function bind() {
    $("ingest").onclick = async () => {
      const body = { url: $("i-url").value.trim() || null, scheme_id: $("i-id").value.trim() || null,
                     title: $("i-title").value.trim() || null, text: $("i-text").value.trim() || null };
      $("ingest").disabled = true; $("ingest-out").innerHTML = `<span class="spinner"></span>`;
      try {
        const d = await App.api("/api/admin/ingest", { method: "POST", json: body });
        const probs = d.problems.map((p) => `<li>${App.esc(p)}</li>`).join("");
        $("ingest-out").innerHTML = `<div class="notice n-ok">Draft created for <b>${App.esc(d.scheme_id)}</b>. Next: set its filters and last date, then review the rules.</div>` +
          (probs ? `<ul class="muted" style="font-size:.85rem">${probs}</ul>` : "") + `<button class="btn-sm" id="go-meta">Set filters and last date</button>`;
        $("go-meta").onclick = () => openMeta(d.scheme_id);
        loadSources();
      } catch (e) { $("ingest-out").innerHTML = ""; App.toast(e.message, "err"); }
      $("ingest").disabled = false;
    };
    $("w-add").onclick = async () => {
      try {
        await App.api("/api/admin/sources", { method: "POST", json: { url: $("w-url").value.trim(), scheme_id: $("w-id").value.trim() || null, kind: "page" } });
        App.toast("Now watching", "ok"); $("w-url").value = ""; $("w-id").value = ""; loadSources();
      } catch (e) { App.toast(e.message, "err"); }
    };
    $("discover").onclick = async () => {
      $("discover").disabled = true;
      try { const d = await App.api("/api/admin/discover", { method: "POST" }); App.toast(`${d.created.length} new scheme(s) drafted`, "ok"); }
      catch (e) { App.toast(e.message, "err"); }
      $("discover").disabled = false; loadSources();
    };
    loadSources();
  }

  return { bind, setOpenMeta: (fn) => { openMeta = fn; } };
})();
