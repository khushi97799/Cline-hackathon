/* Scheme Sniper shared runtime (part 1): i18n, API, toast, speech */
const App = (() => {
  let strings = {}, preview = false;
  let lang = localStorage.getItem("ss_lang") || "en";

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const t = (k, fb) => strings[k] || fb || k;

  async function loadI18n(code) {
    lang = code || lang;
    const r = await fetch(`/api/i18n/${lang}`);
    const d = await r.json();
    strings = d.strings; preview = d.preview;
    localStorage.setItem("ss_lang", lang);
    document.documentElement.lang = lang;
  }

  function applyDom(root = document) {
    root.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n, el.textContent); });
    root.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh, el.placeholder); });
  }

  async function api(path, opts = {}) {
    const headers = { ...(opts.headers || {}) };
    const o = { ...opts };
    if (o.json !== undefined) { headers["Content-Type"] = "application/json"; o.body = JSON.stringify(o.json); delete o.json; }
    // The login token lives in an HttpOnly cookie (scripts cannot read it). This header proves the
    // request comes from our own pages, which blocks cross-site forgery.
    headers["X-Requested-With"] = "SchemeSniper";
    const res = await fetch(path, { ...o, headers, credentials: "same-origin" });
    let data = null;
    try { data = await res.json(); } catch (e) { /* empty body */ }
    if (res.status === 401 && localStorage.getItem("ss_in")) {      // session ended: clear the flag
      ["ss_in", "ss_role"].forEach((k) => localStorage.removeItem(k));
    }
    if (!res.ok) {
      const d = data && data.detail;
      const err = new Error(typeof d === "string" ? d : "Something went wrong");
      err.status = res.status; throw err;
    }
    return data;
  }

  function toast(msg, kind = "") {
    let box = document.getElementById("toasts");
    if (!box) { box = document.createElement("div"); box.id = "toasts"; document.body.appendChild(box); }
    const el = document.createElement("div");
    el.className = `toast ${kind}`; el.textContent = msg; box.appendChild(el);
    setTimeout(() => el.remove(), 4200);
  }

  // Speech uses the browser API only when a voice exists for the language.
  function hasVoice() {
    if (!("speechSynthesis" in window)) return false;
    return speechSynthesis.getVoices().some((v) => (v.lang || "").toLowerCase().startsWith(lang.toLowerCase()));
  }
  function speak(text) {
    if (!hasVoice()) return false;
    const u = new SpeechSynthesisUtterance(text); u.lang = lang;
    speechSynthesis.cancel(); speechSynthesis.speak(u); return true;
  }
  function speakerButton(getText) {
    const b = document.createElement("button");
    b.className = "speaker"; b.type = "button"; b.textContent = "🔊 " + t("listen", "Listen");
    const note = document.createElement("span");
    note.className = "muted"; note.style.fontSize = ".8rem";
    note.textContent = t("no_voice", "Voice not available for this language on this device. Please read the text.");
    b.onclick = () => speak(typeof getText === "function" ? getText() : getText);
    const wrap = document.createElement("span"); wrap.append(b, note);
    const refresh = () => { b.classList.toggle("hidden", !hasVoice()); note.classList.toggle("hidden", hasVoice()); };
    refresh();
    if ("speechSynthesis" in window) speechSynthesis.addEventListener("voiceschanged", refresh);
    return wrap;
  }

  const personId = () => localStorage.getItem("ss_person_id");
  const requireLogin = () => {
    if (!localStorage.getItem("ss_in")) { location.href = "/login.html?next=" + encodeURIComponent(location.pathname + location.search); return false; }
    return true;
  };

  return { t, api, toast, esc, speak, speakerButton, hasVoice, applyDom, loadI18n, personId, requireLogin,
           lang: () => lang, isPreview: () => preview };
})();
