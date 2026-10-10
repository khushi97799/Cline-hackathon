/* Deadline text + a spoken summary of a scheme card, shared by several pages. */
const DeadlineUI = (() => {
  const L = (k, fb) => App.t(k, fb);

  function dateText(iso) {
    return new Date(iso + "T00:00:00").toLocaleDateString(App.lang(), { day: "numeric", month: "short", year: "numeric" });
  }

  function label(d) {
    if (!d || d.state === "open_ended") return L("dl_none", "No last date announced");
    if (d.state === "closed") return L("dl_closed", "Closed on") + " " + dateText(d.date);
    if (d.state === "closing_soon") {
      return d.days_left === 0 ? L("dl_today", "Last day is today!") : `${d.days_left} ${L("dl_days_left", "days left")} · ${dateText(d.date)}`;
    }
    return L("dl_last", "Last date") + ": " + dateText(d.date);
  }

  function pill(d) {
    const st = d ? d.state : "open_ended";
    return `<span class="dl dl-${st}">⏰ ${App.esc(label(d))}</span>`;
  }

  /* What the speaker reads for one scheme: short, plain sentences. */
  function spoken(s) {
    const parts = [s.name + ".", L("benefit_label", "Benefit") + ": " + s.benefit + ".", label(s.deadline) + "."];
    parts.push(s.verified ? L("badge_verified", "Verified by admin") : L("badge_unverified", "Not yet verified, confirm at the office before you go"));
    return parts;
  }

  return { label, pill, spoken, dateText };
})();
