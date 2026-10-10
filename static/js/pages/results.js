(async () => {
  await Chrome.boot("/results.html", [["/start.html","Check eligibility"],["/results.html","Results"]]);
  if (!App.requireLogin()) return;
  if (!App.personId()) { location.href = "/start.html"; return; }
  Chrome.stepper(document.getElementById("stepper"), 4);
  const $ = (id) => document.getElementById(id);
  const ORDER = ["likely_qualifies", "maybe_confirm_at_office", "cant_tell", "likely_not_eligible"];
  const BADGE = { likely_qualifies: "b-ok", maybe_confirm_at_office: "b-warn", cant_tell: "b-gray", likely_not_eligible: "b-bad" };
  let results = [], filter = "all";

  const data = await App.api(`/api/results/${App.personId()}`);
  results = data.results.sort((a, b) => ORDER.indexOf(a.outcome) - ORDER.indexOf(b.outcome));

  const spoken = (r) => [r.name + ".", App.t("outcome_" + r.outcome) + ".", DeadlineUI.label(r.deadline) + ".",
    r.verified_badge ? App.t("badge_verified") : App.t("badge_unverified")];
  Voice.bar($("voice-slot"), () => results.flatMap(spoken));

  function draw() {
    const present = ORDER.filter((o) => results.some((r) => r.outcome === o));
    $("filters").innerHTML = ["all", ...present].map((o) =>
      `<button type="button" class="${filter === o ? "active" : ""}" data-f="${o}">${App.esc(o === "all" ? App.t("filter_all") : App.t("outcome_" + o))}</button>`).join("");
    $("filters").querySelectorAll("button").forEach((b) => b.onclick = () => { filter = b.dataset.f; draw(); });
    setTimeout(() => $("list").querySelectorAll("[data-voice]").forEach((slot) => {
      const r = results.find((x) => x.scheme_id === slot.dataset.voice);
      slot.appendChild(Voice.button(() => spoken(r), App.t("listen", "Listen")));
    }), 0);

    const shown = results.filter((r) => filter === "all" || r.outcome === filter);
    $("none").classList.toggle("hidden", shown.length > 0);
    $("list").innerHTML = shown.map((r) => `
      <article class="card outcome ${r.outcome} stack">
        <div class="row" style="justify-content:space-between">
          <span class="badge ${BADGE[r.outcome]}">${App.esc(App.t("outcome_" + r.outcome))}</span>
          <span class="badge ${r.verified_badge ? "b-ok" : "b-warn"}">${r.verified_badge ? "✓ " + App.esc(App.t("badge_verified")) : "⚠ " + App.esc(App.t("badge_unverified"))}</span>
        </div>
        <h3>${App.esc(r.name)}</h3>
        <p><b>${App.esc(App.t("benefit_label"))}:</b> ${App.esc(r.benefit)}</p>
        ${r.almost_eligible ? `<div class="notice n-warn">${App.esc(App.t("almost_eligible_note"))}</div>` : ""}
        <div>${DeadlineUI.pill(r.deadline)}</div>
        ${r.deadline && r.deadline.state === "closed" ? `<div class="notice n-warn">${App.esc(App.t("dl_closed_note", "The last date has passed."))}</div>` : ""}
        ${r.needs_update ? `<div class="notice n-warn">${App.esc(App.t("needs_update_note", "The official page changed. Please confirm at the office."))}</div>` : ""}
        <p class="muted" style="font-size:.85rem">${App.esc(App.t("last_verified"))}: ${App.esc(r.last_verified || "—")}</p>
        <div class="row" style="justify-content:space-between"><a class="btn" href="/scheme.html?id=${encodeURIComponent(r.scheme_id)}">${App.esc(App.t("view_details"))} →</a><span data-voice="${App.esc(r.scheme_id)}"></span></div>
      </article>`).join("");
  }
  draw();

  $("print").onclick = () => window.print();
  $("del").onclick = async () => {
    if (!confirm(App.t("delete_confirm"))) return;
    try {
      await App.api(`/api/me/people/${App.personId()}`, { method: "DELETE" });
      localStorage.removeItem("ss_person_id"); App.toast(App.t("deleted"), "ok");
      setTimeout(() => (location.href = "/"), 900);
    } catch (e) { App.toast(e.message, "err"); }
  };
})();
