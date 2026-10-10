/* Admin part 2b: filters (tags, level, state) and the last date, with its exact quote */
(() => {
  const $ = (id) => document.getElementById(id);
  let metaId = null, tagList = [], selTags = new Set();

  const wait = setInterval(() => {                // start once admin.js has built the page
    if (!$("ingest") || !$("schemes")) return;
    clearInterval(wait); init();
  }, 100);

  async function init() {
    try { tagList = (await App.api("/api/admin/options")).tags; } catch (e) { return; }
    AdminAdd.setOpenMeta(openMeta);
    AdminAdd.bind();
    $("mclose").onclick = () => $("meta").classList.add("hidden");
    $("msave").onclick = () => save(false);
    $("mclear").onclick = () => save(true);
    new MutationObserver(addButtons).observe($("schemes"), { childList: true });
    addButtons();
  }

  function addButtons() {
    $("schemes").querySelectorAll("[data-r]").forEach((b) => {
      if (b.parentElement.querySelector("[data-m]")) return;
      const m = document.createElement("button");
      m.className = "btn-sm btn-ghost"; m.dataset.m = b.dataset.r; m.style.marginLeft = ".4rem"; m.textContent = "Filters & last date";
      m.onclick = () => openMeta(b.dataset.r);
      b.parentElement.appendChild(m);
    });
  }

  async function openMeta(id) {
    try {
      const d = await App.api(`/api/admin/schemes/${encodeURIComponent(id)}/meta`);
      metaId = id; selTags = new Set(d.tags);
      $("mtitle").textContent = `Filters and last date: ${d.name}`;
      $("m-level").value = d.level || ""; $("m-state").value = d.state || ""; $("m-cat").value = d.category || "";
      $("m-date").value = d.deadline ? d.deadline.date : ""; $("m-quote").value = d.deadline ? d.deadline.quote : "";
      $("m-tags").innerHTML = tagList.map((t) => `<button type="button" class="chip-btn ${selTags.has(t) ? "on" : ""}" data-t="${t}">${App.esc(App.t("tag_" + t, t))}</button>`).join("");
      $("m-tags").querySelectorAll("button").forEach((b) => b.onclick = () => {
        selTags.has(b.dataset.t) ? selTags.delete(b.dataset.t) : selTags.add(b.dataset.t); b.classList.toggle("on");
      });
      $("m-cands").innerHTML = d.deadline_candidates.length
        ? `<div class="muted">Dates the source says about the last day to apply:</div>` + d.deadline_candidates.map((c, i) =>
            `<div class="row"><button type="button" class="btn-sm btn-ghost" data-c="${i}">Use ${App.esc(c.date)}</button><span class="dl-quote">“${App.esc(c.quote)}”</span></div>`).join("")
        : `<div class="muted">${d.has_source ? "The source text has no last date. Leave it empty." : "No source text saved yet for this scheme."}</div>`;
      $("m-cands").querySelectorAll("[data-c]").forEach((b) => b.onclick = () => {
        const c = d.deadline_candidates[Number(b.dataset.c)]; $("m-date").value = c.date; $("m-quote").value = c.quote;
      });
      $("meta").classList.remove("hidden"); $("meta").scrollIntoView({ behavior: "smooth" });
    } catch (e) { App.toast(e.message, "err"); }
  }

  async function save(clearDate) {
    const body = { level: $("m-level").value || null, state: $("m-state").value.trim() || null, category: $("m-cat").value,
                   tags: [...selTags], deadline_date: clearDate ? "" : $("m-date").value.trim(), deadline_quote: clearDate ? "" : $("m-quote").value.trim() };
    try {
      await App.api(`/api/admin/schemes/${encodeURIComponent(metaId)}/meta`, { method: "PUT", json: body });
      App.toast("Saved", "ok"); $("meta").classList.add("hidden");
    } catch (e) { App.toast(e.message, "err"); }
  }
})();
