(async () => {
  await Chrome.boot("/login.html");
  let role = "citizen";
  const $ = (id) => document.getElementById(id);

  document.querySelectorAll("#tabs button").forEach((b) => b.onclick = () => {
    document.querySelectorAll("#tabs button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active"); role = b.dataset.role;
  });

  $("send").onclick = async () => {
    const phone = $("phone").value.trim();
    if (phone.replace(/\D/g, "").length < 10) { App.toast("Enter a valid 10-digit number", "err"); return; }
    $("send").disabled = true;
    try {
      const d = await App.api("/api/auth/send-otp", { method: "POST", json: { phone, role } });
      if (d.test_mode) { const b = $("test-banner"); b.classList.remove("hidden"); b.textContent = App.t("test_mode_banner") + " — " + d.message; }
      $("phone-step").classList.add("hidden"); $("otp-step").classList.remove("hidden"); $("otp").focus(); startCooldown(d.resend_in || 30);
    } catch (e) { App.toast(e.message, "err"); }
    $("send").disabled = false;
  };

  let cdTimer;
  function startCooldown(n) {
    const b = $("resend"); clearInterval(cdTimer); b.disabled = true;
    const tick = () => { b.textContent = n > 0 ? App.t("resend_in", "Resend code in") + " " + n + "s" : App.t("resend", "Resend code"); b.disabled = n > 0; n--; if (n < -1) clearInterval(cdTimer); };
    tick(); cdTimer = setInterval(tick, 1000);
  }
  $("resend").onclick = () => $("send").click();
  $("change").onclick = () => { $("otp-step").classList.add("hidden"); $("phone-step").classList.remove("hidden"); };

  $("verify").onclick = async () => {
    $("verify").disabled = true;
    try {
      const d = await App.api("/api/auth/verify-otp", { method: "POST", json: { phone: $("phone").value.trim(), code: $("otp").value.trim(), role } });
      localStorage.setItem("ss_in", "1"); localStorage.setItem("ss_role", d.role);   // the real token is an HttpOnly cookie
      const next = new URLSearchParams(location.search).get("next");
      if (next) location.href = next;
      else if (d.role === "admin") location.href = "/admin.html";
      else if (d.role === "csc_operator") location.href = "/csc.html";
      else location.href = "/start.html";
    } catch (e) { App.toast(e.message, "err"); }
    $("verify").disabled = false;
  };
  $("otp").addEventListener("keydown", (e) => { if (e.key === "Enter") $("verify").click(); });
})();
