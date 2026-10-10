(async () => {
  await Chrome.boot("/track.html", [["/track.html","Track application"],["/receipt.html","Receipt"]]);
  const raw = sessionStorage.getItem("ss_receipt");
  if (!raw) { location.href = "/track.html"; return; }
  const r = JSON.parse(raw), $ = (id) => document.getElementById(id);
  $("arn").textContent = r.arn; $("rs").textContent = r.scheme_name || r.scheme_id; $("rb").textContent = r.benefit || "";
  $("rt").textContent = new Date(r.timestamp).toLocaleString();
  $("track").href = "/track.html?arn=" + encodeURIComponent(r.arn);
  $("print").onclick = () => window.print();
  const speech = () => App.t("receipt_speak") + " " + r.arn.replace(/-/g, " ");
  $("speak-slot").appendChild(App.speakerButton(speech));
  App.speak(speech());
})();
