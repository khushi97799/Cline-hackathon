(async () => {
  await Chrome.boot("/questions.html", [["/start.html","Check eligibility"],["/questions.html","Questions"]]);
  if (!App.requireLogin()) return;
  if (!App.personId()) { location.href = "/start.html"; return; }
  Chrome.stepper(document.getElementById("stepper"), 3);
  const $ = (id) => document.getElementById(id);
  let spec = null, asked = 0;
  const slot = $("speak-slot");
  slot.appendChild(App.speakerButton(() => $("qtext").textContent));

  async function answer(value) {
    try {
      await App.api("/api/questions/answer", { method: "POST", json: { person_id: App.personId(), field: spec.field, value } });
      next();
    } catch (e) { App.toast(e.message, "err"); }
  }

  function render() {
    $("qtext").textContent = App.t(spec.question_key);
    $("qcount").textContent = App.t("q_progress") + " " + (asked + 1);
    const box = $("qinput");
    if (spec.options) {
      box.innerHTML = `<div class="opt-grid">${spec.options.map((o) => `<button type="button" class="opt" data-v="${App.esc(o)}">${App.esc(App.t("opt_" + o, o))}</button>`).join("")}</div>`;
      box.querySelectorAll(".opt").forEach((b) => b.onclick = () => answer(b.dataset.v));
    } else {
      box.innerHTML = `<div class="stack"><input type="number" id="ans" min="0" inputmode="decimal" autofocus />
        <button id="ok" class="btn-lg btn-block">${App.esc(App.t("question_next", "Next"))}</button></div>`;
      const go = () => { const v = $("ans").value; if (v === "") { App.toast(App.t("q_skip_hint"), "err"); return; } answer(v); };
      $("ok").onclick = go; $("ans").onkeydown = (e) => { if (e.key === "Enter") go(); };
    }
    App.speak($("qtext").textContent);
  }

  async function next() {
    const d = await App.api(`/api/questions/next/${App.personId()}`);
    if (d.done) { $("qcard").classList.add("hidden"); $("done").classList.remove("hidden"); location.href = "/results.html"; return; }
    spec = d.question; render(); asked++;
  }
  next().catch((e) => App.toast(e.message, "err"));
})();
