/* Voice helper for people who cannot read well.
 *
 * Uses ONLY the browser's speech engine, and only when a voice exists for the chosen
 * language. If not, the speaker buttons are hidden and a short note is shown.
 * Nothing is recorded and no audio is sent anywhere.
 *
 * Usage:
 *   Voice.button(() => "text to read")       -> a small 🔊 button element
 *   Voice.readAll(["line 1", "line 2"])      -> reads a list one after another
 *   Voice.bar(container, () => [...lines])   -> "Listen to everything" + speed + stop controls
 */
const Voice = (() => {
  const rate = () => Number(localStorage.getItem("ss_rate") || 0.85);   // a little slower than normal
  let queue = [], playing = false;

  const voices = () => ("speechSynthesis" in window ? speechSynthesis.getVoices() : []);
  const hasVoice = () => voices().some((v) => (v.lang || "").toLowerCase().startsWith(App.lang().toLowerCase()));

  function pick() {
    const want = App.lang().toLowerCase();
    const list = voices().filter((v) => (v.lang || "").toLowerCase().startsWith(want));
    return list.find((v) => v.localService) || list[0] || null;
  }

  function speakOne(text, done) {
    const u = new SpeechSynthesisUtterance(text);
    u.lang = App.lang(); u.rate = rate(); u.pitch = 1;
    const v = pick();
    if (v) u.voice = v;
    u.onend = done; u.onerror = done;
    speechSynthesis.speak(u);
  }

  function next() {
    if (!queue.length) { playing = false; document.dispatchEvent(new Event("voice-end")); return; }
    playing = true;
    speakOne(queue.shift(), next);
  }

  function stop() { queue = []; playing = false; if ("speechSynthesis" in window) speechSynthesis.cancel(); document.dispatchEvent(new Event("voice-end")); }

  function readAll(lines) {
    if (!hasVoice()) return false;
    stop();
    queue = lines.filter((l) => l && String(l).trim()).map(String);
    next();
    return true;
  }

  function button(getText, label) {
    const wrap = document.createElement("span");
    const b = document.createElement("button");
    b.type = "button"; b.className = "speaker speaker-sm";
    b.setAttribute("aria-label", App.t("listen", "Listen"));
    b.textContent = "🔊" + (label ? " " + label : "");
    b.onclick = (e) => { e.preventDefault(); e.stopPropagation(); const t = typeof getText === "function" ? getText() : getText; readAll(Array.isArray(t) ? t : [t]); };
    wrap.appendChild(b);
    const refresh = () => { b.classList.toggle("hidden", !hasVoice()); };
    refresh();
    if ("speechSynthesis" in window) speechSynthesis.addEventListener("voiceschanged", refresh);
    return wrap;
  }

  function bar(container, getLines) {
    const el = document.createElement("div");
    el.className = "voicebar no-print";
    const note = `<span class="muted voice-note">${App.esc(App.t("no_voice", "Voice is not available for this language on this device. Please read the text."))}</span>`;
    el.innerHTML = `
      <button type="button" class="btn-accent" data-v="all">🔊 ${App.esc(App.t("listen_all", "Listen to everything"))}</button>
      <button type="button" class="btn-ghost btn-sm" data-v="stop">⏹ ${App.esc(App.t("stop", "Stop"))}</button>
      <label class="rate">${App.esc(App.t("speed", "Speed"))}
        <select data-v="rate"><option value="0.7">🐢 ${App.esc(App.t("slow", "Slow"))}</option><option value="0.85">${App.esc(App.t("normal", "Normal"))}</option><option value="1.05">🐇 ${App.esc(App.t("fast", "Fast"))}</option></select></label>
      ${note}`;
    const sel = el.querySelector("[data-v=rate]");
    sel.value = String(rate());
    if (![...sel.options].some((o) => o.value === sel.value)) sel.value = "0.85";
    sel.onchange = () => localStorage.setItem("ss_rate", sel.value);
    el.querySelector("[data-v=all]").onclick = () => readAll(getLines());
    el.querySelector("[data-v=stop]").onclick = stop;
    const refresh = () => {
      const ok = hasVoice();
      el.querySelectorAll("[data-v]").forEach((x) => x.closest("label") ? x.closest("label").classList.toggle("hidden", !ok) : x.classList.toggle("hidden", !ok));
      el.querySelector(".voice-note").classList.toggle("hidden", ok);
    };
    refresh();
    if ("speechSynthesis" in window) speechSynthesis.addEventListener("voiceschanged", refresh);
    container.appendChild(el);
    return el;
  }

  return { button, bar, readAll, stop, hasVoice, isPlaying: () => playing };
})();
