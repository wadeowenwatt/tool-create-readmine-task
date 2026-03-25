/**
 * Redmine Issue Creator – Frontend Logic v2
 * Upload markdown → AI trích xuất nhiều issues → review từng cái → tạo
 */

"use strict";

// ──────────────────────────────────────────
// State
// ──────────────────────────────────────────
let selectedFile = null;
let currentUser  = null;
let extractedIssues = []; // [{subject, description}]

// ──────────────────────────────────────────
// DOM helpers
// ──────────────────────────────────────────
const $  = (id) => document.getElementById(id);
const qs = (sel) => document.querySelector(sel);

function showBanner(msg, type = "info") {
  const el = $("status-banner");
  el.textContent = msg;
  el.className = `status-banner ${type}`;
  el.classList.remove("hidden");
  if (type === "success" || type === "info") {
    setTimeout(() => el.classList.add("hidden"), 6000);
  }
}
function hideBanner() { $("status-banner").classList.add("hidden"); }

// ──────────────────────────────────────────
// Bootstrap – load config from server
// ──────────────────────────────────────────
async function loadConfig() {
  try {
    showBanner("Đang kết nối Redmine...", "info");
    const res = await fetch("/api/config");
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Không thể tải cấu hình");
    }
    const data = await res.json();

    currentUser = data.user;
    $("user-name").textContent = currentUser.name || currentUser.login;
    $("user-badge").classList.remove("hidden");
    $("assign-display").textContent = `${currentUser.name} (chính mình)`;

    const trackerSel = $("tracker-id");
    data.trackers.forEach((t) => trackerSel.add(new Option(t.name, t.id)));

    const projectSel = $("project-id");
    data.projects.forEach((p) => projectSel.add(new Option(p.name, p.identifier)));

    hideBanner();
  } catch (e) {
    showBanner(`⚠ ${e.message}`, "error");
  }
}

// ──────────────────────────────────────────
// File handling
// ──────────────────────────────────────────
function handleFile(file) {
  if (!file) return;
  const allowed = [".md", ".markdown", ".txt"];
  const ext = "." + file.name.split(".").pop().toLowerCase();
  if (!allowed.includes(ext)) {
    showBanner("Chỉ hỗ trợ file .md, .markdown, .txt", "warning");
    return;
  }
  selectedFile = file;
  $("file-name").textContent = file.name;
  $("file-info").classList.remove("hidden");
  $("drop-zone").classList.add("hidden");
  $("btn-analyze").disabled = false;
  hideBanner();
}

function removeFile() {
  selectedFile = null;
  $("file-input").value = "";
  $("file-info").classList.add("hidden");
  $("drop-zone").classList.remove("hidden");
  $("btn-analyze").disabled = true;
  clearIssueCards();
}

// ──────────────────────────────────────────
// Analyze markdown → render issue cards
// ──────────────────────────────────────────
async function analyzeMarkdown() {
  if (!selectedFile) return;

  const btnAnalyze = $("btn-analyze");
  const spinner = $("analyze-spinner");
  const btnText = $("btn-analyze-text");

  btnAnalyze.disabled = true;
  spinner.classList.remove("hidden");
  btnText.textContent = "Đang phân tích...";
  hideBanner();
  clearIssueCards();

  try {
    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("extra_context", $("extra-context").value.trim());

    const res = await fetch("/api/analyze", { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Lỗi phân tích");
    }

    const data = await res.json();
    extractedIssues = data.issues;
    renderIssueCards(extractedIssues);
    showBanner(`✅ AI trích xuất được ${extractedIssues.length} issue! Kiểm tra và nhấn Tạo từng cái.`, "success");
  } catch (e) {
    showBanner(`⚠ ${e.message}`, "error");
  } finally {
    btnAnalyze.disabled = false;
    spinner.classList.add("hidden");
    btnText.textContent = "✨ Phân tích bằng AI";
  }
}

// ──────────────────────────────────────────
// Render issue cards
// ──────────────────────────────────────────
function clearIssueCards() {
  extractedIssues = [];
  const container = $("issues-container");
  // Xóa tất cả issue cards, giữ lại placeholder
  container.querySelectorAll(".issue-card").forEach(el => el.remove());
  $("issues-placeholder").classList.remove("hidden");
  $("issue-count-badge").classList.add("hidden");
  $("btn-create-all").classList.add("hidden");
}

function renderIssueCards(issues) {
  $("issues-placeholder").classList.add("hidden");

  const badge = $("issue-count-badge");
  badge.textContent = `${issues.length} issues`;
  badge.classList.remove("hidden");

  $("btn-create-all").classList.remove("hidden");

  const container = $("issues-container");
  issues.forEach((issue, idx) => {
    const card = buildIssueCard(issue, idx);
    container.appendChild(card);
  });
}

function buildIssueCard(issue, idx) {
  const card = document.createElement("div");
  card.className = "issue-card";
  card.id = `issue-card-${idx}`;

  card.innerHTML = `
    <div class="issue-card-header">
      <span class="issue-card-num">#${idx + 1}</span>
      <span class="issue-card-status" id="issue-status-${idx}"></span>
    </div>
    <div class="field">
      <label class="field-label">Subject <span class="required">*</span></label>
      <input type="text" class="field-input issue-subject" id="issue-subject-${idx}"
             value="${escapeHtml(issue.subject)}" maxlength="255" />
      <span class="field-hint char-count">
        <span id="issue-subject-count-${idx}">${issue.subject.length}</span>/255
      </span>
    </div>
    <div class="field">
      <label class="field-label">Description</label>
      <textarea class="field-input issue-description" id="issue-desc-${idx}"
                rows="4">${escapeHtml(issue.description)}</textarea>
    </div>
    <div class="issue-card-actions">
      <button class="btn btn-success btn-sm" onclick="createSingleIssue(${idx})" id="issue-btn-${idx}">
        <svg class="btn-icon-left spin hidden" id="issue-spinner-${idx}"
             viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
        </svg>
        <span id="issue-btn-text-${idx}">🚀 Tạo issue</span>
      </button>
    </div>
  `;

  // Char count
  card.querySelector(`#issue-subject-${idx}`).addEventListener("input", (e) => {
    $(`issue-subject-count-${idx}`).textContent = e.target.value.length;
  });

  return card;
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ──────────────────────────────────────────
// Shared config helpers
// ──────────────────────────────────────────
function getSharedConfig() {
  const projectId = $("project-id").value;
  const trackerId = $("tracker-id").value;
  const startDate = $("start-date").value;
  const dueDate   = $("due-date").value;

  if (!projectId || !trackerId || !startDate || !dueDate) {
    showBanner("⚠ Vui lòng chọn đầy đủ Project, Tracker và Dates trước khi tạo issue", "warning");
    [$("project-id"), $("tracker-id"), $("start-date"), $("due-date")].forEach(el => {
      if (!el.value) el.classList.add("error");
    });
    return null;
  }

  if (dueDate < startDate) {
    showBanner("⚠ Due date phải sau Start date", "warning");
    $("due-date").classList.add("error");
    return null;
  }

  const parentId = $("parent-issue-id").value;
  return {
    project_id:      projectId,
    tracker_id:      parseInt(trackerId),
    start_date:      startDate,
    due_date:        dueDate,
    priority_id:     parseInt($("priority-id").value),
    parent_issue_id: parentId ? parseInt(parentId) : null,
  };
}

// ──────────────────────────────────────────
// Create single issue
// ──────────────────────────────────────────
async function createSingleIssue(idx) {
  const config = getSharedConfig();
  if (!config) return;

  const subject     = $(`issue-subject-${idx}`).value.trim();
  const description = $(`issue-desc-${idx}`).value.trim();

  if (!subject) {
    showBanner(`⚠ Issue #${idx + 1}: Subject không được để trống`, "warning");
    $(`issue-subject-${idx}`).classList.add("error");
    return;
  }

  const btn     = $(`issue-btn-${idx}`);
  const spinner = $(`issue-spinner-${idx}`);
  const btnText = $(`issue-btn-text-${idx}`);
  const status  = $(`issue-status-${idx}`);

  btn.disabled = true;
  spinner.classList.remove("hidden");
  btnText.textContent = "Đang tạo...";

  try {
    const res = await fetch("/api/issues", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...config, subject, description }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Lỗi tạo issue");
    }

    const issue = await res.json();
    markCardCreated(idx, issue);
  } catch (e) {
    btn.disabled = false;
    spinner.classList.add("hidden");
    btnText.textContent = "🚀 Tạo issue";
    status.textContent = `❌ ${e.message}`;
    status.className = "issue-card-status error";
  }
}

function markCardCreated(idx, issue) {
  const card   = $(`issue-card-${idx}`);
  const btn    = $(`issue-btn-${idx}`);
  const status = $(`issue-status-${idx}`);

  card.classList.add("issue-card-done");
  btn.disabled = true;
  $(`issue-spinner-${idx}`).classList.add("hidden");
  $(`issue-btn-text-${idx}`).textContent = "✅ Đã tạo";

  status.innerHTML = `✅ <a href="${issue.url}" target="_blank" rel="noopener">#${issue.id} – Mở issue</a>`;
  status.className = "issue-card-status success";
}

// ──────────────────────────────────────────
// Create ALL issues
// ──────────────────────────────────────────
async function createAllIssues() {
  const config = getSharedConfig();
  if (!config) return;

  $("btn-create-all").disabled = true;

  let created = 0;
  for (let idx = 0; idx < extractedIssues.length; idx++) {
    const card = $(`issue-card-${idx}`);
    if (card.classList.contains("issue-card-done")) continue;
    await createSingleIssue(idx);
    created++;
  }

  $("btn-create-all").disabled = false;
  showBanner(`🎉 Đã tạo ${created} issue thành công!`, "success");
}

// ──────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────
function setDefaultDates() {
  const today = new Date().toISOString().split("T")[0];
  $("start-date").value = today;
  const due = new Date();
  due.setDate(due.getDate() + 7);
  $("due-date").value = due.toISOString().split("T")[0];
}

// ──────────────────────────────────────────
// Event wiring
// ──────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  setDefaultDates();
  loadConfig();

  $("file-input").addEventListener("change", (e) => handleFile(e.target.files[0]));
  $("btn-remove-file").addEventListener("click", removeFile);

  const dz = $("drop-zone");
  dz.addEventListener("click", () => $("file-input").click());
  dz.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") $("file-input").click();
  });
  ["dragenter", "dragover"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag-over"); })
  );
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag-over"); })
  );
  dz.addEventListener("drop", (e) => handleFile(e.dataTransfer.files[0]));

  $("btn-analyze").addEventListener("click", analyzeMarkdown);
  $("btn-create-all").addEventListener("click", createAllIssues);

  document.querySelectorAll(".field-input").forEach((el) => {
    el.addEventListener("input", () => el.classList.remove("error"));
  });
});
