(async () => {
  await Chrome.boot("/language.html");
  const langs = await App.api("/api/languages");
  const grid = document.getElementById("lang-grid");
  const cur = App.lang();
  const slot = document.getElementById("speak-slot");

  async function choose(code) {
    localStorage.setItem("ss_lang", code);
    location.href = new URLSearchParams(location.search).get("next") || "/";
  }
  langs.forEach((l) => {
    const c = document.createElement("div");
    c.className = "lang-card" + (l.code === cur ? " sel" : "");
    c.tabIndex = 0; c.setAttribute("role", "button");
    c.innerHTML = `<div class="native">${App.esc(l.native_name)}</div><div class="eng">${App.esc(l.name)}</div>
      <span class="badge ${l.support === "preview" ? "b-warn" : "b-ok"}">${l.support === "preview" ? "Preview" : "✓ Reviewed"}</span>`;
    c.onclick = () => choose(l.code);
    c.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choose(l.code); } };
    grid.appendChild(c);
  });
  slot.appendChild(App.speakerButton(() => App.t("lang_title") + ". " + App.t("lang_sub")));
  document.getElementById("title").textContent = App.t("lang_title", "Choose your language");
  document.getElementById("sub").textContent = App.t("lang_sub", "Tap your language");
})();
