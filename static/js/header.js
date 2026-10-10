/* Header parts: utility bar, navbar with search, back button + breadcrumb */
const Header = (() => {
  const { t, esc } = App;
  const loggedIn = () => !!localStorage.getItem("ss_in");
  const role = () => localStorage.getItem("ss_role");

  function applyFontSize() {
    document.documentElement.style.fontSize = Number(localStorage.getItem("ss_fs") || 17) + "px";
  }
  const dashboardHref = () => ({ admin: "/admin.html", csc_operator: "/csc.html" }[role()] || "/dashboard.html");

  function topbar() {
    const el = document.createElement("div");
    el.className = "topbar";
    el.innerHTML = `<div class="container">
      <span>${esc(t("topbar_tag", "Free service · Guidance only · Confirm at the office"))}</span>
      <span class="fs-ctl">
        <button type="button" id="fs-minus" aria-label="Smaller text">A−</button>
        <button type="button" id="fs-reset" aria-label="Normal text">A</button>
        <button type="button" id="fs-plus" aria-label="Larger text">A+</button>
        <span class="sep">|</span><a href="/language.html">🌐 ${esc(App.lang().toUpperCase())}</a>
      </span></div>`;
    const set = (n) => { localStorage.setItem("ss_fs", Math.min(24, Math.max(14, n))); applyFontSize(); };
    const cur = () => Number(localStorage.getItem("ss_fs") || 17);
    el.querySelector("#fs-minus").onclick = () => set(cur() - 1);
    el.querySelector("#fs-plus").onclick = () => set(cur() + 1);
    el.querySelector("#fs-reset").onclick = () => set(17);
    return el;
  }

  /* Search box with live suggestions: starts at the first letter, keyboard friendly, highlights the match. */
  function highlight(text, q) {
    const safe = App.esc(text);
    const word = q.trim().split(/\s+/).filter(Boolean).sort((x, y) => y.length - x.length)[0];
    if (!word) return safe;
    const i = text.toLowerCase().indexOf(word.toLowerCase());
    if (i < 0) return safe;
    return App.esc(text.slice(0, i)) + "<mark>" + App.esc(text.slice(i, i + word.length)) + "</mark>" + App.esc(text.slice(i + word.length));
  }

  function searchBox() {
    const w = document.createElement("div");
    w.className = "nav-search";
    w.style.width = "100%";
    w.innerHTML = `<span class="mag">🔍</span><input type="search" autocomplete="off" role="combobox" aria-expanded="false" aria-label="${esc(t("search_ph", "Search schemes"))}" placeholder="${esc(t("search_ph", "Search schemes"))}" />`;
    const input = w.querySelector("input");
    let box = null, timer, items = [], cur = -1, seq = 0;
    const close = () => { if (box) { box.remove(); box = null; } items = []; cur = -1; input.setAttribute("aria-expanded", "false"); };
    const go = (href) => { location.href = href; };
    const allHref = () => "/schemes.html?q=" + encodeURIComponent(input.value.trim());
    const mark = () => items.forEach((a, i) => a.classList.toggle("on", i === cur));

    async function show() {
      const q = input.value.trim();
      if (!q) { close(); return; }                        // from the very first letter
      const mine = ++seq;
      try {
        const d = await App.api("/api/schemes/suggest?q=" + encodeURIComponent(q));
        if (mine !== seq) return;                         // a newer keystroke already replaced this answer
        close();
        box = document.createElement("div"); box.className = "sugg"; box.setAttribute("role", "listbox");
        const why = { name: "", tag: App.t("sg_tag", "matches who it is for"), text: App.t("sg_text", "matches the description") };
        box.innerHTML = d.suggestions.length
          ? d.suggestions.map((s) => `<a role="option" href="/scheme.html?id=${encodeURIComponent(s.scheme_id)}"><b>${highlight(s.name, q)}</b>` +
              `<small>${esc(s.benefit)}</small>${why[s.match] ? `<em>${esc(why[s.match])}</em>` : ""}</a>`).join("") +
            `<a class="all" href="${allHref()}">${esc(t("sg_all", "See all results for"))} \u201c${esc(q)}\u201d \u2192</a>`
          : `<div class="none">${esc(t("sg_none", "No scheme found. Try another word, or"))} <a href="/schemes.html">${esc(t("sg_browse", "browse all schemes"))}</a></div>`;
        w.appendChild(box);
        items = [...box.querySelectorAll("a")];
        input.setAttribute("aria-expanded", "true");
      } catch (e) { close(); }
    }

    input.oninput = () => { clearTimeout(timer); timer = setTimeout(show, 120); };
    input.onfocus = () => { if (input.value.trim() && !box) show(); };
    input.onkeydown = (e) => {
      if (e.key === "ArrowDown" && items.length) { e.preventDefault(); cur = (cur + 1) % items.length; mark(); }
      else if (e.key === "ArrowUp" && items.length) { e.preventDefault(); cur = (cur - 1 + items.length) % items.length; mark(); }
      else if (e.key === "Enter") { e.preventDefault(); if (cur >= 0 && items[cur]) go(items[cur].href); else if (input.value.trim()) go(allHref()); }
      else if (e.key === "Escape") close();
    };
    document.addEventListener("click", (e) => { if (!w.contains(e.target)) close(); });
    return w;
  }

  function navbar(active) {
    const links = [["/", "nav_home", "Home"], ["/schemes.html", "nav_schemes", "Schemes"], ["/start.html", "nav_check", "Check eligibility"],
      ["/track.html", "nav_track", "Track"], ["/faq.html", "nav_faq", "FAQ"]];
    const nav = document.createElement("header");
    nav.className = "nav";
    nav.innerHTML = `<div class="container nav-inner">
      <a class="logo" href="/"><span class="logo-mark">🎯</span>Scheme Sniper</a>
      <span id="search-slot" style="flex:1;display:flex;justify-content:center"></span>
      <button class="menu-btn" aria-label="Menu" id="menu-btn">☰</button>
      <nav class="nav-links" id="nav-links">
        <span class="m-search" id="m-search"></span>
        ${links.map(([h, k, fb]) => `<a class="link ${active === h ? "active" : ""}" href="${h}">${esc(t(k, fb))}</a>`).join("")}
        ${loggedIn()
          ? `<a class="user-pill" href="${dashboardHref()}">👤 ${esc(t("nav_account", "My account"))}</a><a href="#" id="logout">${esc(t("logout", "Logout"))}</a>`
          : `<a class="btn btn-sm" href="/login.html">${esc(t("nav_login", "Login"))}</a>`}
      </nav></div>`;
    nav.querySelector("#search-slot").appendChild(searchBox());
    nav.querySelector("#m-search").appendChild(searchBox());
    nav.querySelector("#menu-btn").onclick = () => nav.querySelector("#nav-links").classList.toggle("open");
    const lo = nav.querySelector("#logout");
    if (lo) lo.onclick = async (e) => {
      e.preventDefault();
      try { await App.api("/api/auth/logout", { method: "POST" }); } catch (err) { /* cookie expires anyway */ }
      localStorage.clear();            // nothing about the person stays in this browser
      location.href = "/";
    };
    return nav;
  }

  function subbar(crumbs) {
    if (!crumbs || !crumbs.length) return null;
    const el = document.createElement("div");
    el.className = "subbar";
    const trail = [["/", t("nav_home", "Home")], ...crumbs].map((c, i, a) =>
      i === a.length - 1 ? `<b>${esc(c[1])}</b>` : `<a href="${c[0]}">${esc(c[1])}</a>`).join(" › ");
    el.innerHTML = `<div class="container"><button type="button" class="back-btn" id="back">← ${esc(t("back", "Back"))}</button><span class="crumbs">${trail}</span></div>`;
    el.querySelector("#back").onclick = () => {
      if (history.length > 1 && document.referrer.startsWith(location.origin)) history.back(); else location.href = "/";
    };
    return el;
  }

  return { topbar, navbar, subbar, applyFontSize };
})();
