/* My data page: how a person card, a value row and the inputs are drawn. */
const MyDataView = (() => {
  const L = (k, fb) => App.t(k, fb);
  const ORDER = ["name", "date_of_birth", "age", "gender", "state", "district", "occupation", "income_band", "income_amount",
                 "caste_category", "marital_status", "family_size", "land_holding", "disability_status", "document_type"];
  const CHOICES = {
    gender: ["female", "male", "other"], occupation: ["farmer", "laborer", "self_employed", "salaried", "student", "homemaker", "other"],
    income_band: ["BPL", "APL"], caste_category: ["general", "obc", "sc", "st"], marital_status: ["single", "married", "widowed", "divorced"],
    disability_status: ["yes", "no"],
  };
  const NUMERIC = new Set(["age", "family_size", "land_holding", "income_amount"]);

  const shown = (k, v) => (CHOICES[k] ? L("opt_" + String(v).toLowerCase().replace("bpl", "BPL").replace("apl", "APL"), v) : String(v));

  function input(k, v) {
    if (CHOICES[k]) {
      return `<select data-input>${CHOICES[k].map((o) => `<option value="${App.esc(o)}" ${String(v).toLowerCase() === o.toLowerCase() ? "selected" : ""}>${App.esc(L("opt_" + o, o))}</option>`).join("")}</select>`;
    }
    const num = NUMERIC.has(k);
    return `<input data-input type="${num ? "number" : "text"}" ${num ? 'inputmode="decimal" min="0"' : ""} value="${App.esc(v)}" maxlength="120" />`;
  }

  function row(p, k) {
    const ver = p.field_sources[k] === "verified";
    return `<div class="field-edit" data-f="${App.esc(k)}">
      <div><b>${App.esc(L("f_" + k, k))}</b><div><span class="badge ${ver ? "b-ok" : "b-gray"}">${App.esc(L(ver ? "src_verified" : "src_user"))}</span></div></div>
      <div class="val" data-show>${App.esc(shown(k, p.profile[k]))}</div>
      <div class="acts"><button class="btn-sm btn-ghost" data-act="edit">✏️ ${App.esc(L("confirm_edit", "Edit"))}</button>
        <button class="btn-sm btn-ghost" data-act="del">🗑 ${App.esc(L("confirm_remove", "Remove"))}</button></div></div>`;
  }

  function consentRow(label, key, on) {
    return `<div class="switch-row"><span>${App.esc(label)}</span><span class="tick-cross" data-c="${key}">
      <button type="button" data-v="1" class="${on ? "on-yes" : ""}" aria-label="Yes">✔</button>
      <button type="button" data-v="0" class="${on ? "" : "on-no"}" aria-label="No">✘</button></span></div>`;
  }

  function person(p, role) {
    const rows = ORDER.filter((k) => p.profile[k] !== undefined).map((k) => row(p, k)).join("");
    return `<section class="card stack" data-person="${App.esc(p.id)}">
      <div class="row" style="justify-content:space-between"><h2>${App.esc(p.display_name || L("md_unnamed", "My details"))}</h2>
        <span class="row"><button class="btn-sm btn-ghost" data-act="rename">✏️ ${App.esc(L("md_rename", "Change name"))}</button>
        ${role === "csc_operator" ? `<button class="btn-sm btn-danger" data-act="delperson">🗑 ${App.esc(L("md_del_person", "Delete this person"))}</button>` : ""}</span></div>
      ${rows || `<p class="muted">${App.esc(L("md_empty", "Nothing is saved yet."))}</p>`}
      ${consentRow(L("consent_save_profile"), "save", p.consent.save_profile)}
      ${consentRow(L("consent_notifications"), "notify", p.consent.notifications)}
      <a class="btn btn-sm" href="/questions.html" data-pick="${App.esc(p.id)}">${App.esc(L("edit_answers", "Edit my answers"))}</a>
    </section>`;
  }

  return { person, input };
})();
