const FAQ = [
  ["Does Scheme Sniper tell me that I qualify?", "No. It tells you whether you are likely to qualify, may need to confirm at the office, are likely not eligible, or whether more information is needed. The final decision is always made by the government office."],
  ["Who decides the result?", "Fixed rules written from official government text. An admin approves each rule and checks every quote against the source. AI never decides eligibility."],
  ["What does 'Not yet verified' mean?", "The rule has not been checked by an admin yet, so we never show a confident result. Please confirm at the office before you go."],
  ["Do you keep my documents or Aadhaar number?", "No. Photos are read once and deleted immediately. Aadhaar, PAN, voter ID, passport and bank account numbers are never read or stored."],
  ["Is my data saved?", "Only if you choose to save your profile. You can delete everything at any time with the Delete my data button on the results page."],
  ["Why do I need a phone number?", "To log you in with a one-time code. Phone numbers are kept in a separate table from your profile details."],
  ["Can a CSC operator help me?", "Yes. A CSC operator can fill the form with you. Each person has their own consent, and operators see only the people they created."],
  ["Does the app really submit my application to the government?", "No. The online submit and receipt screens are a clearly labelled simulation. Use the documents checklist, office details and official link to apply."],
  ["Which languages are supported?", "All 22 Eighth Schedule languages plus English. English and Hindi are fully reviewed. The others show English text with a Preview label until a native speaker reviews them."],
  ["The speaker button is missing. Why?", "Your device has no voice for the chosen language. The text is still shown, and you can try another browser or device."],
];
(async () => {
  await Chrome.boot("/faq.html", [["/faq.html", "FAQ"]]);
  const draw = () => {
    const q = document.getElementById("f").value.toLowerCase();
    document.getElementById("list").innerHTML = FAQ.filter(([a, b]) => (a + b).toLowerCase().includes(q))
      .map(([a, b]) => `<details class="faq"><summary>${App.esc(a)}</summary><p>${App.esc(b)}</p></details>`).join("")
      || `<p class="muted">No matching question.</p>`;
  };
  document.getElementById("f").oninput = draw; draw();
})();
