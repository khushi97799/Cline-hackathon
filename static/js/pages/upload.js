(async () => {
  await Chrome.boot("/upload.html", [["/start.html","Check eligibility"],["/upload.html","Documents"]]);
  if (!App.requireLogin()) return;
  if (!App.personId()) { location.href = "/start.html"; return; }
  Chrome.stepper(document.getElementById("stepper"), 1);
  const $ = (id) => document.getElementById(id);
  document.getElementById("speak-slot").appendChild(App.speakerButton(() => App.t("upload_title") + ". " + App.t("upload_hint")));

  let picked = [];
  const extracted = {};

  function showChosen() {
    $("chosen").innerHTML = picked.map((f) => `<span class="chip">📎 ${App.esc(f.name)}</span>`).join("");
    $("read").classList.toggle("hidden", !picked.length);
  }
  $("files").onchange = (e) => { picked = [...e.target.files]; showChosen(); };
  ["dragover", "dragenter"].forEach((ev) => $("drop").addEventListener(ev, (e) => { e.preventDefault(); $("drop").classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) => $("drop").addEventListener(ev, (e) => { e.preventDefault(); $("drop").classList.remove("drag"); }));
  $("drop").addEventListener("drop", (e) => { picked = [...e.dataTransfer.files].filter((f) => f.type.startsWith("image/")); showChosen(); });

  $("read").onclick = async () => {
    $("read").disabled = true; $("read").innerHTML = `<span class="spinner"></span> ${App.esc(App.t("upload_reading"))}`;
    for (const f of picked) {
      const fd = new FormData(); fd.append("file", f);
      try { const d = await App.api("/api/documents/extract", { method: "POST", body: fd }); Object.assign(extracted, d.fields); }
      catch (e) { App.toast(f.name + ": " + e.message, "err"); }
    }
    picked = []; $("files").value = "";
    renderConfirm();
  };

  function renderConfirm() {
    $("upload-card").classList.add("hidden"); $("confirm-card").classList.remove("hidden");
    Chrome.stepper(document.getElementById("stepper"), 2);
    const keys = Object.keys(extracted);
    $("empty").classList.toggle("hidden", keys.length > 0);
    $("fields").innerHTML = keys.map((k) => `
      <div class="field-row" data-k="${App.esc(k)}">
        <div><label>${App.esc(App.t("f_" + k, k))}</label><span class="badge b-ok">✓ ${App.esc(App.t("src_verified"))}</span></div>
        <input type="text" value="${App.esc(extracted[k])}" aria-label="${App.esc(k)}" />
        <button type="button" class="btn-ghost btn-sm" data-rm="${App.esc(k)}">✘ ${App.esc(App.t("confirm_remove"))}</button>
      </div>`).join("");
    $("fields").querySelectorAll("[data-rm]").forEach((b) => b.onclick = () => { delete extracted[b.dataset.rm]; renderConfirm(); });
  }

  $("save").onclick = async () => {
    const verified = {};
    $("fields").querySelectorAll(".field-row").forEach((r) => { verified[r.dataset.k] = r.querySelector("input").value; });
    try {
      await App.api("/api/documents/confirm", { method: "POST", json: { person_id: App.personId(), verified_fields: verified, user_stated_fields: {} } });
      location.href = "/questions.html";
    } catch (e) { App.toast(e.message, "err"); }
  };
})();
