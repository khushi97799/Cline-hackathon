/* Page chrome: header + footer + stepper. Call: Chrome.boot("/path", [[href, label], ...crumbs]) */
const Chrome = (() => {
  const { t, esc } = App;

  function footer() {
    const f = document.createElement("footer");
    f.className = "footer";
    f.innerHTML = `<div class="container">
      <div class="foot-grid">
        <div><b style="color:#fff;font-size:1.2rem">🎯 Scheme Sniper</b>
          <p>${esc(t("footer_note", "Results are guidance only, decided by fixed rules from official sources. Always confirm timings and location at the office before you go."))}</p></div>
        <div><h4>${esc(t("foot_explore", "Explore"))}</h4><ul>
          <li><a href="/schemes.html">${esc(t("nav_schemes", "Schemes"))}</a></li>
          <li><a href="/start.html">${esc(t("nav_check", "Check eligibility"))}</a></li>
          <li><a href="/track.html">${esc(t("nav_track", "Track application"))}</a></li>
          <li><a href="/language.html">${esc(t("lang_title", "Language"))}</a></li></ul></div>
        <div><h4>${esc(t("foot_help", "Help"))}</h4><ul>
          <li><a href="/faq.html">${esc(t("nav_faq", "FAQ"))}</a></li>
          <li><a href="/privacy.html">${esc(t("nav_privacy", "Privacy"))}</a></li>
          <li><a href="/about.html">${esc(t("nav_about", "About"))}</a></li></ul></div>
        <div><h4>${esc(t("foot_for", "For staff"))}</h4><ul>
          <li><a href="/login.html">${esc(t("login_tab_csc", "CSC Operator"))}</a></li>
          <li><a href="/login.html">${esc(t("login_tab_admin", "Admin"))}</a></li></ul></div>
      </div>
      <div class="foot-bottom"><span>© ${new Date().getFullYear()} Scheme Sniper</span>
        <span>${esc(t("footer_sim", "Online submission here is a simulation and does not reach any government system."))}</span></div></div>`;
    const up = document.createElement("button");
    up.className = "to-top hidden"; up.setAttribute("aria-label", "Back to top"); up.textContent = "↑";
    up.onclick = () => window.scrollTo({ top: 0, behavior: "smooth" });
    window.addEventListener("scroll", () => up.classList.toggle("hidden", window.scrollY < 400));
    document.body.appendChild(up);
    return f;
  }

  function mount(active, crumbs) {
    Header.applyFontSize();
    const prev = document.createElement("div");
    prev.className = "banner" + (App.isPreview() ? "" : " hidden");
    prev.textContent = t("preview_label", "Preview translation, not yet reviewed");
    [Header.topbar(), Header.navbar(active), Header.subbar(crumbs), prev].filter(Boolean).reverse()
      .forEach((p) => document.body.prepend(p));
    document.body.appendChild(footer());
  }

  async function boot(active, crumbs) {
    await App.loadI18n();
    mount(active, crumbs);
    App.applyDom();
  }

  const STEPS = ["step_consent", "step_docs", "step_confirm", "step_questions", "step_results"];
  const STEP_FB = ["Consent", "Documents", "Confirm", "Questions", "Results"];
  function stepper(el, current) {
    el.className = "stepper";
    el.innerHTML = STEPS.map((k, i) =>
      `<div class="step ${i < current ? "done" : i === current ? "cur" : ""}"><div class="bar"></div><span>${esc(t(k, STEP_FB[i]))}</span></div>`).join("");
  }

  return { boot, stepper };
})();
