/* Schemes catalogue: filters kept in the URL (shareable), deadline pills, voice on every card */
(async () => {
  await Chrome.boot("/schemes.html", [["/schemes.html", "Schemes"]]);
  const $ = (id) => document.getElementById(id);
  const P = new URLSearchParams(location.search);
  const state = { q: P.get("q") || "", level: P.get("level") || "", state: P.get("state") || "", tag: P.get("tag") || "",
                  deadline: P.get("deadline") || "", sort: P.get("sort") || "relevance", verified: P.get("verified") === "1" };
  let data = null;
  const L = (k, fb) => App.t(k, fb);
  const opt = (v, label, cur) => `<option value="${App.esc(v)}" ${v === cur ? "selected" : ""}>${App.esc(label)}</option>`;

  function sync() {
    const q = new URLSearchParams();
    Object.entries({ ...state, verified: state.verified ? "1" : "" }).forEach(([k, v]) => { if (v && !(k === "sort" && v === "relevance")) q.set(k, v); });
    history.replaceState(null, "", location.pathname + (q.toString() ? "?" + q : ""));
  }

  async function load() {
    const qs = new URLSearchParams();
    ["q", "level", "state", "tag", "deadline", "sort"].forEach((k) => state[k] && qs.set(k, state[k]));
    if (state.verified) qs.set("verified", "true");
    data = await App.api("/api/schemes?" + qs);
    sync(); draw();
  }

  function drawControls() {
    $("f-level").innerHTML = opt("", L("filter_all", "All"), state.level) + data.levels.map((l) => opt(l, L("level_" + l, l), state.level)).join("");
    $("f-state").innerHTML = opt("", L("filter_all", "All"), state.state) + data.states.map((s) => opt(s, s, state.state)).join("");
    $("f-deadline").innerHTML = [["", "filter_all", "All"], ["open", "dl_f_open", "Still open"], ["closing_soon", "dl_f_soon", "Closing soon"],
      ["closed", "dl_f_closed", "Closed"], ["no_deadline", "dl_f_none", "No last date"]].map(([v, k, fb]) => opt(v, L(k, fb), state.deadline)).join("");
    $("f-sort").innerHTML = [["relevance", "sort_rel", "Best first"], ["deadline", "sort_deadline", "Last date (soonest)"],
      ["recent", "sort_recent", "Newly added"], ["name", "sort_name", "Name A-Z"]].map(([v, k, fb]) => opt(v, L(k, fb), state.sort)).join("");
    $("f-tags").innerHTML = data.tags.map((t) => `<button type="button" class="chip-btn ${state.tag === t ? "on" : ""}" data-t="${t}">${App.esc(L("tag_" + t, t))}</button>`).join("");
    $("f-tags").querySelectorAll("button").forEach((b) => b.onclick = () => { state.tag = state.tag === b.dataset.t ? "" : b.dataset.t; load(); });
    $("f-verified").checked = state.verified;
    $("q").value = state.q;
  }

  function drawActive() {
    const a = [];
    if (state.q) a.push(["q", `“${state.q}”`]);
    if (state.level) a.push(["level", L("level_" + state.level, state.level)]);
    if (state.state) a.push(["state", state.state]);
    if (state.tag) a.push(["tag", L("tag_" + state.tag, state.tag)]);
    if (state.deadline) a.push(["deadline", $("f-deadline").selectedOptions[0].textContent]);
    if (state.verified) a.push(["verified", L("f_only_verified", "Only verified")]);
    $("active").innerHTML = a.map(([k, v]) => `<span class="x-chip">${App.esc(v)}<button type="button" aria-label="Remove" data-k="${k}">×</button></span>`).join("");
    $("active").querySelectorAll("button").forEach((b) => b.onclick = () => { state[b.dataset.k] = b.dataset.k === "verified" ? false : ""; load(); });
  }

  function cardHtml(s) {
    return `<article class="card hover stack ${s.deadline.state === "closed" ? "is-closed" : ""}">
      <div class="row" style="justify-content:space-between">
        <span class="badge b-info">${App.esc(s.category || "")}</span>
        <span class="badge ${s.verified ? "b-ok" : "b-warn"}">${s.verified ? "✓ " + App.esc(L("badge_verified")) : "⚠ " + App.esc(L("badge_unverified"))}</span>
      </div>
      <h3>${App.esc(s.name)}</h3>
      <p class="muted">${App.esc(s.benefit)}</p>
      <div class="row">${DeadlineUI.pill(s.deadline)}</div>
      ${s.deadline.quote ? `<p class="dl-quote">“${App.esc(s.deadline.quote)}”</p>` : ""}
      <div class="chips">${s.tags.map((t) => `<span class="chip">${App.esc(L("tag_" + t, t))}</span>`).join("")}</div>
      <div class="row" style="justify-content:space-between">
        <a class="btn btn-sm" href="/scheme.html?id=${encodeURIComponent(s.scheme_id)}">${App.esc(L("view_details"))} →</a>
        <span data-voice="${App.esc(s.scheme_id)}"></span>
      </div></article>`;
  }

  function draw() {
    drawControls(); drawActive();
    $("count").textContent = `${data.schemes.length} / ${data.total} ${L("f_schemes", "schemes")}`;
    $("list").innerHTML = data.schemes.map(cardHtml).join("")
      || `<div class="card empty" style="grid-column:1/-1"><div class="big">🔍</div><p>${App.esc(L("none_yet"))}</p></div>`;
    $("list").querySelectorAll("[data-voice]").forEach((slot) => {
      const s = data.schemes.find((x) => x.scheme_id === slot.dataset.voice);
      slot.appendChild(Voice.button(() => DeadlineUI.spoken(s), L("listen", "Listen")));
    });
  }

  let timer; $("q").oninput = () => { clearTimeout(timer); timer = setTimeout(() => { state.q = $("q").value.trim(); load(); }, 250); };
  [["f-level", "level"], ["f-state", "state"], ["f-deadline", "deadline"], ["f-sort", "sort"]].forEach(([id, key]) => { $(id).onchange = () => { state[key] = $(id).value; load(); }; });
  $("f-verified").onchange = () => { state.verified = $("f-verified").checked; load(); };
  $("clear").onclick = () => { Object.assign(state, { q: "", level: "", state: "", tag: "", deadline: "", sort: "relevance", verified: false }); load(); };

  Voice.bar($("voice-slot"), () => (data ? data.schemes.flatMap(DeadlineUI.spoken) : []));
  load().catch((e) => App.toast(e.message, "err"));
})();
