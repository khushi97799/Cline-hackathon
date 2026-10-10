(async () => {
  // First visit: let the person pick a language before anything else.
  if (!localStorage.getItem("ss_lang")) { location.replace("/language.html"); return; }
  await Chrome.boot("/");
  document.getElementById("speak-slot").appendChild(
    App.speakerButton(() => App.t("hero_title") + ". " + App.t("hero_sub")));
  try {
    const d = await App.api("/api/schemes");
    document.getElementById("n-schemes").textContent = d.schemes.length;
  } catch (e) { /* keep default */ }
})();
