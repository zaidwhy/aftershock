// Reports as files: one clean, print-ready HTML document per report, saved as a Word file (Word opens HTML saved
// with its MIME type, and every script, Korean included, survives) or printed to PDF through the browser, which
// keeps the text selectable and needs no PDF library.

const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

const STYLE = `
  @page { size: A4; margin: 18mm 16mm; }
  body { font: 10.5pt/1.5 Calibri, "Segoe UI", Arial, sans-serif; color: #15181D; margin: 0; }
  .brand { font: 600 9pt Consolas, monospace; letter-spacing: .2em; color: #C83A20; margin: 0 0 4pt; }
  h1 { font: 700 20pt/1.15 Calibri, "Segoe UI", Arial, sans-serif; margin: 0 0 8pt; }
  h2 { font: 700 12.5pt Calibri, "Segoe UI", Arial, sans-serif; margin: 16pt 0 5pt; padding-top: 6pt; border-top: 1px solid #E2DED5; color: #15181D; }
  p { margin: 0 0 6pt; }
  .lead { font-size: 12pt; }
  .note { color: #5A616C; font-size: 9.5pt; }
  .decision { border-left: 3pt solid #B5670A; padding: 4pt 8pt; background: #FBF5EC; }
  ul { margin: 0 0 6pt 16pt; padding: 0; }
  li { margin: 0 0 2pt; }
  table { border-collapse: collapse; width: 100%; margin: 4pt 0 8pt; }
  th { text-align: left; font: 700 8.5pt Calibri, Arial, sans-serif; text-transform: uppercase; letter-spacing: .05em; color: #5A616C; border-bottom: 1.5pt solid #15181D; padding: 3pt 5pt; }
  td { vertical-align: top; border-bottom: 1px solid #E2DED5; padding: 4pt 5pt; }
  td.gap { color: #8A4F08; }
  .foot { margin-top: 18pt; padding-top: 6pt; border-top: 1px solid #E2DED5; color: #5A616C; font-size: 8.5pt; }`;

/** A report: {title, lead?, blocks: [{heading?, text?, note?, decision?, list?, table?: {head, rows, gapColumn?}}], source}. */
export function reportHtml(report) {
  const block = (b) => [
    b.heading ? `<h2>${esc(b.heading)}</h2>` : "",
    b.decision ? `<p class="decision">${esc(b.decision)}</p>` : "",
    ...(b.text ? [].concat(b.text).map((t) => `<p>${esc(t)}</p>`) : []),
    b.list?.length ? `<ul>${b.list.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "",
    b.table?.rows?.length ? `<table><thead><tr>${b.table.head.map((x) => `<th>${esc(x)}</th>`).join("")}</tr></thead><tbody>${
      b.table.rows.map((r) => `<tr>${r.map((c, i) => `<td${i === b.table.gapColumn ? ' class="gap"' : ""}>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>` : "",
    b.note ? `<p class="note">${esc(b.note)}</p>` : "",
  ].join("");
  const made = new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
  return `<!doctype html><html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word"><head><meta charset="utf-8"><title>${esc(report.title)}</title><style>${STYLE}</style></head><body>
<p class="brand">AFTERSHOCK</p><h1>${esc(report.title)}</h1>${report.lead ? `<p class="lead">${esc(report.lead)}</p>` : ""}
${report.blocks.filter(Boolean).map(block).join("\n")}
<p class="foot">Made ${esc(made)} from ${esc(report.source || "https://aftershock-qloo.vercel.app")}. A hackathon prototype by Team Solstine: forecasts are probabilities, not promises; every output is a shortlist for further research, not a confirmed business opportunity. Netflix Top 10 data credited to Netflix; we have no permission from Netflix and claim none. Audience data from Qloo.</p>
</body></html>`;
}

const slug = (t) => String(t).toLowerCase().normalize("NFKD").replace(/[^\w]+/g, "-").replace(/^-|-$/g, "").slice(0, 60) || "report";

/** Save the report as a .doc file that Word, Pages and Google Docs open with its headings and tables. */
export function downloadWord(report) {
  const blob = new Blob(["﻿", reportHtml(report)], { type: "application/msword" });
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: `${slug(report.title)}.doc`, hidden: true });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

/** Open the browser's print dialog on the clean report, where "Save as PDF" writes the file. */
export function printPdf(report) {
  const frame = Object.assign(document.createElement("iframe"), { title: "Report for printing" });
  frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;";
  document.body.append(frame);
  frame.onload = () => {
    frame.contentWindow.focus();
    frame.contentWindow.print();
    setTimeout(() => frame.remove(), 60000);
  };
  frame.srcdoc = reportHtml({ ...report, title: report.title });
}
