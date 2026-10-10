(async () => {
  await Chrome.boot("/start.html", [["/start.html","Check eligibility"]]);
  if (!App.requireLogin()) return;
  Chrome.stepper(document.getElementById("stepper"), 0);
  const role = localStorage.getItem("ss_role");
  const isCsc = role === "csc_operator";
  const choice = { find: null, save: false, notify: false };

  if (isCsc) {
    if (!App.personId()) { location.href = "/csc.html"; return; }
    document.getElementById("who").textContent = (localStorage.getItem("ss_person_name") || "") + " — " + App.t("login_tab_csc");
  }
  document.getElementById("speak-slot").appendChild(App.speakerButton(
    () => [App.t("consent_title"), App.t("consent_find_schemes"), App.t("consent_save_profile"), App.t("consent_notifications")].join(". ")));

  document.querySelectorAll(".tick-cross").forEach((g) => {
    g.querySelectorAll("button").forEach((b) => b.onclick = () => {
      const v = b.dataset.v === "1";
      choice[g.dataset.key] = v;
      g.querySelectorAll("button").forEach((x) => x.className = "");
      b.className = v ? "on-yes" : "on-no";
      document.getElementById("go").disabled = choice.find !== true;
      if (g.dataset.key === "find" && !v) App.toast(App.t("consent_need_find"), "err");
    });
  });

  document.getElementById("go").onclick = async () => {
    try {
      // A new person for every session; CSC operators pick/create one on their desk.
      if (!isCsc) {
        const p = await App.api("/api/persons", { method: "POST", json: { language: App.lang() } });
        localStorage.setItem("ss_person_id", p.person_id);
      }
      await App.api("/api/persons/consent", { method: "POST",
        json: { person_id: App.personId(), find_schemes: true, save_profile: !!choice.save, notifications: !!choice.notify } });
      location.href = "/upload.html";
    } catch (e) { App.toast(e.message, "err"); }
  };
})();
