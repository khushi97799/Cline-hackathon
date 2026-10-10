(async () => {
  await Chrome.boot("/track.html", [["/track.html","Track application"]]);
  const $ = (id) => document.getElementById(id);
  async function check() {
    const arn = $("arn").value.trim();
    if (!arn) return;
    try {
      const d = await App.api("/api/submissions/track/" + encodeURIComponent(arn));
      const idx = d.steps.indexOf(d.status);
      $("a").textContent = d.arn;
      $("tl").innerHTML = d.steps.map((s, i) => `<div class="tl ${i <= idx ? "done" : ""}"><i>${i <= idx ? "✓" : i + 1}</i>${App.esc(App.t("st_" + s, s))}</div>`).join("");
      $("when").textContent = App.t("receipt_time") + ": " + new Date(d.updated_at).toLocaleString();
      $("res").classList.remove("hidden");
    } catch (e) { $("res").classList.add("hidden"); App.toast(e.message, "err"); }
  }
  $("go").onclick = check; $("arn").onkeydown = (e) => { if (e.key === "Enter") check(); };
  const q = new URLSearchParams(location.search).get("arn");
  if (q) { $("arn").value = q; check(); }
})();
