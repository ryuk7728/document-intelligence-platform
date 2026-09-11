const form = document.querySelector("#upload-form");
const fileInput = document.querySelector("#document-file");
const fileLabel = document.querySelector("#file-label");
const dropZone = document.querySelector("#drop-zone");
const processButton = document.querySelector("#process-button");
const uploadStatus = document.querySelector("#upload-status");
const historyBody = document.querySelector("#history-body");
const historyEmpty = document.querySelector("#history-empty");
const resultSection = document.querySelector("#result-section");
const apiBase = String(window.RUNTIME_CONFIG?.API_BASE_URL || "").replace(/\/$/, "");

const typeLabels = {
  invoice: "Invoice",
  balance_sheet: "Balance sheet",
  profit_and_loss: "Profit & loss",
  cash_flow_statement: "Cash flow",
};

function statusClass(status) {
  return String(status).toLowerCase().replaceAll("_", "-");
}

function pill(status) {
  const node = document.createElement("span");
  node.className = `status-pill ${statusClass(status)}`;
  node.textContent = String(status).replaceAll("_", " ");
  return node;
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") return "Not available";
  if (typeof value === "object") return JSON.stringify(value);
  if (typeof value === "number") return new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(value);
  return String(value);
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

async function api(path, options) {
  const response = await fetch(`${apiBase}${path}`, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload?.error?.message || "The request could not be completed.");
  return payload;
}

async function loadHistory() {
  historyBody.replaceChildren(document.querySelector("#loading-row-template").content.cloneNode(true));
  historyEmpty.hidden = true;
  try {
    const data = await api("/api/v1/documents?limit=25");
    historyBody.replaceChildren();
    historyEmpty.hidden = data.items.length !== 0;
    for (const item of data.items) {
      const row = document.createElement("tr");
      row.tabIndex = 0;
      row.setAttribute("aria-label", `Open ${item.document_name}`);
      for (const value of [item.document_name, typeLabels[item.document_type] || item.document_type]) {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      }
      const validationCell = document.createElement("td");
      validationCell.append(pill(item.validation_status));
      row.append(validationCell);
      const timeCell = document.createElement("td");
      timeCell.textContent = formatDate(item.created_at);
      row.append(timeCell);
      const open = () => loadRecord(item.id);
      row.addEventListener("click", open);
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); }
      });
      historyBody.append(row);
    }
  } catch (error) {
    historyBody.replaceChildren();
    historyEmpty.hidden = false;
    historyEmpty.querySelector("strong").textContent = "History is unavailable";
    historyEmpty.querySelector("span").textContent = error.message;
  }
}

function metric(label, value) {
  const node = document.createElement("div");
  node.className = "metric";
  const name = document.createElement("span");
  name.textContent = label;
  const strong = document.createElement("strong");
  strong.textContent = value;
  node.append(name, strong);
  return node;
}

function renderRecord(record) {
  const result = record.result;
  document.querySelector("#result-title").textContent = result.document_name;
  document.querySelector("#result-meta").textContent = `${typeLabels[result.document_type]} · ${formatDate(record.created_at)} · ${result.processing_metadata.processing_time_ms} ms`;
  const statusTarget = document.querySelector("#result-status");
  statusTarget.className = `status-pill ${statusClass(result.validation.overall_status)}`;
  statusTarget.textContent = result.validation.overall_status.replaceAll("_", " ");

  const overview = document.querySelector("#overview-panel");
  overview.replaceChildren();
  const metrics = document.createElement("div");
  metrics.className = "metric-grid";
  metrics.append(
    metric("Fields", Object.keys(result.extracted_data.fields).length),
    metric("Line items", result.extracted_data.line_items.length + result.extracted_data.financial_line_items.length),
    metric("Pages", result.file_validation.page_count ?? "—"),
    metric("OCR", result.processing_metadata.ocr_used ? "Used" : "Native text")
  );
  overview.append(metrics);

  const fieldsPanel = document.querySelector("#fields-panel");
  fieldsPanel.replaceChildren();
  const fieldGrid = document.createElement("dl");
  fieldGrid.className = "field-grid";
  for (const [name, entry] of Object.entries(result.extracted_data.fields)) {
    const card = document.createElement("div");
    card.className = "field-card";
    const term = document.createElement("dt");
    term.textContent = name.replaceAll("_", " ");
    const definition = document.createElement("dd");
    definition.textContent = formatValue(entry.value);
    card.append(term, definition);
    if (entry.evidence) {
      const evidence = document.createElement("small");
      evidence.textContent = `Page ${entry.evidence.page_number}: “${entry.evidence.source_text}”`;
      card.append(evidence);
    }
    fieldGrid.append(card);
  }
  if (!fieldGrid.children.length) fieldGrid.append(metric("Extracted fields", "No reliable canonical fields"));
  fieldsPanel.append(fieldGrid);

  const checksPanel = document.querySelector("#checks-panel");
  checksPanel.replaceChildren();
  const checkList = document.createElement("div");
  checkList.className = "check-list";
  for (const check of result.validation.checks) {
    const card = document.createElement("div");
    card.className = "check-card";
    const identity = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = check.name.replaceAll("_", " ");
    const period = document.createElement("p");
    period.textContent = check.period ? `Period ${check.period}` : "Document-level check";
    identity.append(name, period);
    const formula = document.createElement("code");
    formula.textContent = check.formula;
    card.append(identity, formula, pill(check.status));
    checkList.append(card);
  }
  if (!checkList.children.length) checkList.append(metric("Validation", "No checks available"));
  checksPanel.append(checkList);

  document.querySelector("#raw-json").textContent = JSON.stringify(record, null, 2);
  resultSection.hidden = false;
  resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadRecord(id) {
  try {
    renderRecord(await api(`/api/v1/documents/${id}`));
  } catch (error) {
    uploadStatus.className = "form-status error";
    uploadStatus.textContent = error.message;
  }
}

fileInput.addEventListener("change", () => {
  fileLabel.textContent = fileInput.files[0]?.name || "Drop a document here";
});
for (const eventName of ["dragenter", "dragover"]) {
  dropZone.addEventListener(eventName, (event) => { event.preventDefault(); dropZone.classList.add("dragging"); });
}
for (const eventName of ["dragleave", "drop"]) {
  dropZone.addEventListener(eventName, (event) => { event.preventDefault(); dropZone.classList.remove("dragging"); });
}
dropZone.addEventListener("drop", (event) => {
  if (event.dataTransfer.files.length) {
    fileInput.files = event.dataTransfer.files;
    fileInput.dispatchEvent(new Event("change"));
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!fileInput.files.length) return;
  processButton.disabled = true;
  uploadStatus.className = "form-status";
  uploadStatus.textContent = "Reading, extracting and reconciling the document…";
  try {
    const body = new FormData(form);
    const record = await api("/api/v1/documents/process", { method: "POST", body });
    uploadStatus.textContent = "Processing complete. The result was saved.";
    renderRecord(record);
    await loadHistory();
  } catch (error) {
    uploadStatus.className = "form-status error";
    uploadStatus.textContent = error.message;
  } finally {
    processButton.disabled = false;
  }
});

document.querySelector("#refresh-button").addEventListener("click", loadHistory);
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => {
      const active = item === tab;
      item.classList.toggle("active", active);
      item.setAttribute("aria-selected", String(active));
    });
    document.querySelectorAll(".tab-panel").forEach((panel) => { panel.hidden = panel.id !== tab.dataset.panel; });
  });
});

loadHistory();
