const state = { mode: "code", samples: [], codeSamples: [], reviews: [], currentReview: null, filter: "All", search: "", selectedFile: 0, toastTimer: null };
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(body.detail) ? body.detail.map((item) => item.msg).join("; ") : body.detail;
    throw new Error(detail || `Request failed (${response.status}).`);
  }
  return body;
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.remove("hidden");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => toast.classList.add("hidden"), 3800);
}

function setView(name) {
  $$(".page-view").forEach((view) => view.classList.toggle("is-visible", view.id === `view-${name}`));
  $$(".nav-link").forEach((link) => link.classList.toggle("is-active", link.dataset.view === name));
  const labels = { dashboard: "Overview", reviews: "Code reviews", settings: "Settings" };
  $("#breadcrumb-current").textContent = labels[name] || "Overview";
  $("#sidebar").classList.remove("is-open");
  if (name === "reviews") renderHistory($("#history-search").value);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function updateDashboard() {
  const reviews = state.reviews;
  $("#metric-total").textContent = reviews.length;
  $("#metric-bugs").textContent = reviews.reduce((total, review) => total + review.findings.length, 0);
  $("#metric-security").textContent = reviews.filter((review) => review.mode === "Python static analysis (AST rules)").length;
  $("#metric-score").textContent = reviews.filter((review) =>
    review.mode === "AI-generated (unverified)" || review.mode === "Demo heuristic (live GitHub diff)"
  ).length;
  $("#demo-banner-copy").textContent = reviews.length
    ? "Dashboard counts reflect saved reviews on this instance. Bundled sample PRs are clearly labeled demo data."
    : "No saved reviews yet. Try the safe Python example or explore a clearly labeled sample PR.";
}

function renderSampleOptions() {
  const select = $("#sample-select");
  select.replaceChildren(...state.samples.map((sample) => {
    const option = document.createElement("option");
    option.value = sample.id;
    option.textContent = `#${sample.number}  ${sample.title}`;
    return option;
  }));
}

function renderCodeSampleOptions() {
  const select = $("#code-sample-select");
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Choose an example or paste your own Python";
  select.replaceChildren(placeholder, ...state.codeSamples.map((sample) => {
    const option = document.createElement("option");
    option.value = sample.id;
    option.textContent = `${sample.title} · ${sample.category}`;
    return option;
  }));
  select.value = "";
  $("#code-snippet").value = "";
  updateCodeEmptyState();
}

function updateCodeEmptyState() {
  $("#code-empty-state").classList.toggle("hidden", Boolean($("#code-snippet").value.trim()));
}

function renderActivity() {
  const list = $("#activity-list");
  list.replaceChildren();
  const recentReviews = state.reviews.slice(0, 5);
  $("#activity-pill").textContent = recentReviews.length ? "SAVED REVIEWS" : "DEMO SAMPLES";
  if (recentReviews.length) {
    recentReviews.forEach((review) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "activity-row";
      row.setAttribute("aria-label", `Open saved review ${review.title}`);
      row.innerHTML = `<span class="activity-icon">⌘</span><span class="activity-main"><span class="activity-title">${escapeHTML(review.title)}</span><span class="activity-repo">${escapeHTML(review.repository)} · ${escapeHTML(review.mode)}</span></span><span class="activity-side"><span class="status-badge">${review.findings.length} finding${review.findings.length === 1 ? "" : "s"}</span><span class="activity-time">${escapeHTML(new Date(review.reviewed_at).toLocaleDateString())}</span></span>`;
      row.addEventListener("click", () => openSavedReview(review));
      list.append(row);
    });
    return;
  }
  state.samples.slice(0, 3).forEach((sample) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "activity-row";
    row.setAttribute("aria-label", `Explore demo review ${sample.title}`);
    row.innerHTML = `<span class="activity-icon">⌘</span><span class="activity-main"><span class="activity-title">${escapeHTML(sample.title)}</span><span class="activity-repo">${escapeHTML(sample.repository)} <span>#${sample.number}</span></span></span><span class="activity-side"><span class="status-badge">Demo sample</span><span class="activity-time">${escapeHTML(sample.updated)}</span></span>`;
    row.addEventListener("click", () => {
      switchMode("demo");
      runReview({ sample_id: sample.id }, "demo");
    });
    list.append(row);
  });
}

function renderHistory(query = "") {
  const body = $("#history-body");
  body.replaceChildren();
  const search = query.trim().toLowerCase();
  const severity = $("#history-severity").value;
  const matches = state.reviews.filter((review) => {
    const matchesSearch = `${review.title} ${review.repository} ${review.author} ${review.mode}`.toLowerCase().includes(search);
    const matchesSeverity = severity === "All"
      || (severity === "None" ? review.findings.length === 0 : review.findings.some((finding) => finding.severity === severity));
    return matchesSearch && matchesSeverity;
  });
  matches.forEach((review) => {
    const row = document.createElement("tr");
    const countLabel = review.findings.length === 0 ? "No issues" : `${review.findings.length} finding${review.findings.length === 1 ? "" : "s"}`;
    row.innerHTML = `<td><div class="history-title">${escapeHTML(review.title)}</div><div class="history-repo">${escapeHTML(review.repository)} · #${review.pull_request_number}</div></td><td>${escapeHTML(review.mode)}</td><td><span class="status-badge">✓ ${escapeHTML(review.status)}</span></td><td><span class="finding-count">${countLabel}</span></td><td>${escapeHTML(new Date(review.reviewed_at).toLocaleString())}</td><td><button class="table-open" aria-label="Open saved review" title="Open saved review">↗</button></td>`;
    $("button", row).addEventListener("click", () => {
      openSavedReview(review);
    });
    body.append(row);
  });
  if (!matches.length) {
    const row = document.createElement("tr");
    row.innerHTML = `<td colspan="6">${state.reviews.length ? "No saved reviews match those filters." : "No reviews yet. Choose Code reviews to submit your first Python snippet."}</td>`;
    body.append(row);
  }
  $("#review-nav-count").textContent = state.reviews.length;
}

async function loadHistory() {
  try {
    state.reviews = await api("/api/reviews");
    updateDashboard();
    renderActivity();
    renderHistory($("#history-search").value);
  } catch (error) {
    showToast(`Could not load review history: ${error.message}`);
  }
}

function openSavedReview(review) {
  state.currentReview = review;
  state.filter = "All";
  state.selectedFile = 0;
  setView("dashboard");
  renderReview(review);
  $("#results-panel").classList.remove("hidden");
  $("#results-panel").scrollIntoView({ behavior: "smooth", block: "start" });
}

function switchMode(mode) {
  if (mode === "demo" && state.mode !== "demo") {
    $("#code-snippet").value = "";
    $("#code-sample-select").value = "";
    updateCodeEmptyState();
  }
  state.mode = mode;
  $$(".mode-tab").forEach((tab) => {
    const selected = tab.dataset.mode === mode;
    tab.classList.toggle("is-selected", selected);
    tab.setAttribute("aria-selected", String(selected));
  });
  $("#sample-field").classList.toggle("hidden", mode !== "demo");
  $("#code-sample-field").classList.toggle("hidden", mode !== "code");
  $("#language-field").classList.toggle("hidden", mode !== "code");
  $("#snippet-field").classList.toggle("hidden", mode === "github");
  $("#repo-field").classList.toggle("hidden", mode !== "github");
  $("#pr-field").classList.toggle("hidden", mode !== "github");
  $("#review-form-title").textContent = mode === "code" ? "Review Python code" : mode === "demo" ? "Explore a sample PR" : "Review a GitHub PR";
  $("#submit-label").textContent = mode === "code" ? "Review Code" : mode === "demo" ? "Run demo review" : "Review GitHub PR";
  $("#code-editor-hint").textContent = mode === "code"
    ? "Python AST rules · code is never executed · no AI provider required"
    : "Sample patterns only · illustrative suggestions · not a full code audit";
  $("#form-error").classList.add("hidden");
}

async function handleReviewSubmit(event) {
  event.preventDefault();
  const snippet = $("#code-snippet").value.trim();
  const errorBox = $("#form-error");
  errorBox.classList.add("hidden");
  if (state.mode === "github") {
    const repositoryUrl = $("#repo-url").value.trim();
    const number = Number($("#pr-number").value);
    if (!repositoryUrl) return showFormError("Enter a GitHub repository URL.");
    if (!Number.isInteger(number) || number < 1) return showFormError("Enter a pull request number greater than zero.");
    try {
      const parsed = new URL(repositoryUrl);
      const parts = parsed.pathname.split("/").filter(Boolean);
      if (parsed.hostname !== "github.com" && parsed.hostname !== "www.github.com") throw new Error("Use a repository URL hosted on github.com.");
      if (parts.length !== 2 || parts.some((part) => part === "." || part === "..")) throw new Error("Use a repository URL in the form https://github.com/owner/repository.");
    } catch (error) {
      return showFormError(error.message || "Enter a valid GitHub repository URL.");
    }
    return runReview({ repository_url: repositoryUrl, pull_request_number: number }, "github");
  }
  if (state.mode === "code") {
    if (!snippet) return showFormError("Paste Python code or select a built-in sample before reviewing.");
    return runReview({ code_snippet: snippet }, "code");
  }
  if (snippet) return runReview({ code_snippet: snippet }, "demo");
  return runReview({ sample_id: $("#sample-select").value }, "demo");
}

function showFormError(message) {
  const box = $("#form-error");
  box.textContent = message;
  box.classList.remove("hidden");
}

async function runReview(payload, mode) {
  const button = $("#review-submit");
  const originalText = mode === "code" ? "Review Code" : mode === "demo" ? "Run demo review" : "Review GitHub PR";
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  $("#submit-label").textContent = mode === "code"
    ? "Analyzing code…"
    : mode === "demo" ? "Loading sample…" : "Reviewing GitHub diff…";
  $(".submit-icon").textContent = "◌";
  try {
    const result = await api(`/api/review/${mode}`, { method: "POST", body: JSON.stringify(payload) });
    state.currentReview = result;
    state.filter = "All";
    state.selectedFile = 0;
    renderReview(result);
    $("#results-panel").classList.remove("hidden");
    $("#results-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    await loadHistory();
  } catch (error) {
    showFormError(error.message);
    showToast(error.message);
  } finally {
    button.disabled = false;
    button.removeAttribute("aria-busy");
    $("#submit-label").textContent = originalText;
    $(".submit-icon").textContent = "✦";
  }
}

function renderReview(review) {
  $("#result-title").textContent = `${review.title} · #${review.pull_request_number}`;
  $("#result-summary").textContent = review.summary;
  $("#result-mode").textContent = review.mode.toUpperCase();
  $("#result-score").textContent = review.score;
  $("#result-score-label").textContent = (review.score_label || "Estimated code quality").toUpperCase();
  $("#result-meta").textContent = `${review.repository}  ·  ${review.author}  ·  ${review.files.length} changed file${review.files.length === 1 ? "" : "s"}  ·  ${new Date(review.reviewed_at).toLocaleString()}`;
  $("#finding-count").textContent = review.findings.length;
  $("#finding-search").value = "";
  state.search = "";
  renderReviewInsights(review);
  renderPullRequestFiles(review);
  $("#diff-toggle").setAttribute("aria-expanded", "false");
  $("#diff-toggle").innerHTML = "Show diff <span>⌄</span>";
  $("#diff-view").classList.add("hidden");
  const fileSelect = $("#file-select");
  fileSelect.replaceChildren(...review.files.map((file, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = file.filename;
    return option;
  }));
  fileSelect.onchange = () => {
    state.selectedFile = Number(fileSelect.value);
    renderDiff();
  };
  renderDiff();
  renderFindings();
}

function diffCounts(file) {
  const lines = (file.patch || "").split("\n");
  return {
    added: lines.filter((line) => line.startsWith("+") && !line.startsWith("+++")).length,
    removed: lines.filter((line) => line.startsWith("-") && !line.startsWith("---")).length,
    hasPatch: Boolean(file.patch)
  };
}

function renderReviewInsights(review) {
  const totals = Object.fromEntries(["Critical", "High", "Medium", "Low"].map((severity) => [
    severity,
    review.findings.filter((finding) => finding.severity === severity).length
  ]));
  const maximum = Math.max(1, ...Object.values(totals));
  const bars = $("#risk-bars");
  bars.replaceChildren();
  Object.entries(totals).forEach(([severity, count]) => {
    const row = document.createElement("div");
    row.className = `risk-row risk-${severity.toLowerCase()}`;
    row.innerHTML = `<span>${severity}</span><span class="risk-track"><span style="width:${count / maximum * 100}%"></span></span><strong>${count}</strong>`;
    bars.append(row);
  });
  $("#risk-legend").textContent = `${review.findings.length} reported finding${review.findings.length === 1 ? "" : "s"} · counts only; no probability or exploitability score`;

  const checklist = $("#check-list");
  checklist.replaceChildren();
  let method;
  let checks;
  let limits;
  if (review.mode === "Python static analysis (AST rules)") {
    method = "DETERMINISTIC AST";
    checks = [
      "Python syntax parsing",
      "Dynamic eval() / exec() calls",
      "pickle.load() / pickle.loads() calls",
      "subprocess shell=True",
      "Interpolated SQL passed to execute()",
      "Mutable function defaults",
      "Bare except handlers"
    ];
    limits = "Only these patterns are checked. No data-flow, dependency, type, or runtime analysis is performed.";
  } else if (review.mode === "Demo heuristic (live GitHub diff)") {
    method = "LIVE DIFF · HEURISTICS";
    checks = [
      "GitHub PR metadata and available file patches retrieved",
      "Changed/context diff text checked for eval(), interpolated execute(), shell=True, and bare except patterns"
    ];
    limits = "Rule matches are illustrative. Diff line locations and full source may be unavailable; unchanged code is not scanned.";
  } else if (review.mode === "AI-generated (unverified)") {
    method = "EXTERNAL AI PROVIDER";
    checks = [
      "GitHub PR metadata and available file patches retrieved",
      "Diff submitted to the configured AI provider",
      "Provider findings labeled as AI-generated and unverified"
    ];
    limits = "The provider does not expose a verifiable checklist or calibrated confidence. Review its privacy policy and verify every suggestion.";
  } else {
    method = "DEMO SAMPLE DATA";
    checks = ["Bundled example findings displayed", "No submitted code or live repository was analyzed"];
    limits = "This is illustrative sample content, not a scan of the sample repository or a real pull request.";
  }
  $("#check-method").textContent = method;
  checks.forEach((check) => {
    const item = document.createElement("li");
    item.textContent = check;
    checklist.append(item);
  });
  const manualChecks = $("#manual-check-list");
  manualChecks.replaceChildren();
  [
    "Validate untrusted inputs at system boundaries",
    "Use parameterized database queries",
    "Keep credentials out of logs and source control",
    "Review authorization for sensitive operations",
    "Set timeouts and resource limits for external work"
  ].forEach((check) => {
    const item = document.createElement("li");
    item.textContent = check;
    manualChecks.append(item);
  });
  $("#check-limits").textContent = limits;

  const counts = review.files.reduce((all, file) => {
    const current = diffCounts(file);
    all.added += current.added;
    all.removed += current.removed;
    all.withPatch += Number(current.hasPatch);
    return all;
  }, { added: 0, removed: 0, withPatch: 0 });
  $("#change-summary").innerHTML = `<span><strong>${review.files.length}</strong> file${review.files.length === 1 ? "" : "s"}</span><span><strong>+${counts.added}</strong> additions</span><span><strong>−${counts.removed}</strong> deletions</span><span><strong>${counts.withPatch}/${review.files.length}</strong> patches available</span>`;
}

function renderPullRequestFiles(review) {
  const isPullRequest = ["AI-generated (unverified)", "Demo heuristic (live GitHub diff)", "Demo data"].includes(review.mode);
  const panel = $("#pr-files-panel");
  panel.classList.toggle("hidden", !isPullRequest);
  $("#pr-files-title").textContent = review.mode === "Demo data"
    ? "Bundled sample files · demo data, not fetched from GitHub"
    : "Files returned by GitHub";
  const list = $("#pr-file-list");
  list.replaceChildren();
  if (!isPullRequest) return;
  review.files.forEach((file, index) => {
    const counts = diffCounts(file);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pr-file-chip";
    button.innerHTML = `<span class="file-chip-name">${escapeHTML(file.filename)}</span><span class="file-chip-diff">+${counts.added} / −${counts.removed}${counts.hasPatch ? "" : " · patch unavailable"}</span>`;
    button.addEventListener("click", () => {
      state.selectedFile = index;
      $("#file-select").value = String(index);
      renderDiff();
      $("#diff-view").classList.remove("hidden");
      $("#diff-toggle").setAttribute("aria-expanded", "true");
      $("#diff-toggle").innerHTML = "Hide diff <span>⌃</span>";
      $("#diff-view").scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
    list.append(button);
  });
}

function renderDiff() {
  const review = state.currentReview;
  const container = $("#diff-view");
  container.replaceChildren();
  const file = review?.files[state.selectedFile];
  if (!file) {
    const empty = document.createElement("div");
    empty.className = "diff-file-title";
    empty.textContent = "No diff available.";
    container.append(empty);
    return;
  }
  const title = document.createElement("div");
  title.className = "diff-file-title";
  title.textContent = file.filename;
  container.append(title);
  const lines = (file.patch || "").split("\n");
  if (!file.patch) {
    const line = document.createElement("div");
    line.className = "diff-line context";
    line.textContent = "GitHub did not provide a patch for this file (binary or large file).";
    container.append(line);
    return;
  }
  let number = 0;
  lines.forEach((content) => {
    if (!content) return;
    const row = document.createElement("div");
    const isAdded = content.startsWith("+") && !content.startsWith("+++");
    const isRemoved = content.startsWith("-") && !content.startsWith("---");
    const isMeta = content.startsWith("@@") || content.startsWith("+++") || content.startsWith("---");
    row.className = `diff-line ${isMeta ? "meta" : isAdded ? "added" : isRemoved ? "removed" : "context"}`;
    if (content.startsWith("@@")) {
      const match = content.match(/\+(\d+)/);
      number = match ? Number(match[1]) - 1 : number;
    }
    if (!isMeta && !isRemoved) number += 1;
    const lineNumber = document.createElement("span");
    lineNumber.className = "line-number";
    lineNumber.textContent = isMeta ? "" : String(number || "");
    const code = document.createElement("span");
    code.className = "diff-content";
    code.textContent = content;
    row.append(lineNumber, code);
    container.append(row);
  });
}

function renderFindings() {
  const findings = state.currentReview?.findings || [];
  const list = $("#findings-list");
  list.replaceChildren();
  const search = state.search.trim().toLowerCase();
  const visible = findings.filter((finding) => {
    const matchesSeverity = state.filter === "All" || finding.severity === state.filter;
    const matchesSearch = `${finding.title} ${finding.category} ${finding.file || ""} ${finding.explanation} ${finding.recommendation} ${finding.source}`.toLowerCase().includes(search);
    return matchesSeverity && matchesSearch;
  }).sort((left, right) => ["Critical", "High", "Medium", "Low"].indexOf(left.severity) - ["Critical", "High", "Medium", "Low"].indexOf(right.severity));
  ["Critical", "High", "Medium", "Low"].forEach((severity) => {
    const count = findings.filter((finding) => finding.severity === severity).length;
    $(`[data-severity-count="${severity}"]`).textContent = count;
  });
  let lastSeverity = "";
  visible.forEach((finding) => {
    if (finding.severity !== lastSeverity) {
      const group = document.createElement("div");
      group.className = `finding-group-label risk-${finding.severity.toLowerCase()}`;
      group.textContent = `${finding.severity} severity`;
      list.append(group);
      lastSeverity = finding.severity;
    }
    const card = document.createElement("article");
    card.className = "finding-card";
    const location = [finding.file, finding.line ? `line ${finding.line}` : null].filter(Boolean).join(" · ") || "Location not available";
    const affectedCode = findAffectedCode(state.currentReview, finding);
    const originalContent = affectedCode
      ? `<pre>${escapeHTML(affectedCode)}</pre>`
      : `<p class="code-unavailable">The response does not include a source excerpt at a verified line. Inspect the available diff above.</p>`;
    const fixContent = finding.suggested_code
      ? `<pre>${escapeHTML(finding.suggested_code)}</pre>`
      : `<p>${escapeHTML(finding.recommendation)}</p>`;
    card.innerHTML = `<div class="finding-main" role="button" tabindex="0" aria-expanded="false"><span class="severity-stripe severity-${escapeHTML(finding.severity)}"></span><span><span class="finding-heading"><span class="finding-title">${escapeHTML(finding.title)}</span><span class="severity-badge ${escapeHTML(finding.severity)}">${escapeHTML(finding.severity)}</span><span class="category-badge">${escapeHTML(finding.category)}</span></span><span class="finding-location">${escapeHTML(location)} · ${escapeHTML(finding.source)} · confidence not provided</span></span><span class="finding-chevron">⌄</span></div><div class="finding-detail"><div class="finding-explanation"><div><div class="detail-label">What we noticed</div><p>${escapeHTML(finding.explanation)}</p><div class="detail-label">Why it matters</div><p>${escapeHTML(finding.why_it_matters)}</p><div class="detail-label">Recommended fix</div><p>${escapeHTML(finding.recommendation)}</p></div><button class="copy-finding button button-secondary" type="button">Copy finding</button></div><div class="fix-comparison"><section class="comparison-pane"><div class="comparison-heading">AFFECTED CODE${finding.line ? ` · LINE ${finding.line}` : ""}</div>${originalContent}</section><section class="comparison-pane fix-pane"><div class="comparison-heading">SUGGESTED FIX · EXAMPLE, NOT APPLIED</div>${fixContent}${finding.suggested_code ? '<button class="copy-fix button button-secondary" type="button">Copy fix</button>' : ""}</section></div></div>`;
    const toggle = () => {
      const expanded = card.classList.toggle("expanded");
      $(".finding-main", card).setAttribute("aria-expanded", String(expanded));
    };
    $(".finding-main", card).addEventListener("click", toggle);
    $(".finding-main", card).addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggle();
      }
    });
    $(".copy-finding", card).addEventListener("click", () => copyText(formatFinding(finding), "Finding copied."));
    const copyFix = $(".copy-fix", card);
    if (copyFix) copyFix.addEventListener("click", () => copyText(finding.suggested_code, "Suggested fix copied."));
    list.append(card);
  });
  $("#empty-filter").textContent = findings.length === 0
    ? "No findings were returned by this review. This is not proof that the code is safe or defect-free."
    : "No findings match the current severity and search filters.";
  $("#empty-filter").classList.toggle("hidden", visible.length > 0);
}

function findAffectedCode(review, finding) {
  if (!finding.file || !finding.line) return null;
  const file = review.files.find((item) => item.filename === finding.file);
  if (!file) return null;
  const source = file.new || "";
  if (!source.includes("@@") && !source.startsWith("--- ")) {
    const lines = source.split(/\r?\n/);
    if (finding.line > lines.length) return null;
    const start = Math.max(0, finding.line - 2);
    const end = Math.min(lines.length, finding.line + 1);
    return lines.slice(start, end).map((line, index) => `${start + index + 1 === finding.line ? "›" : " "} ${start + index + 1}  ${line}`).join("\n");
  }
  const patch = file.patch || source;
  let newLine = 0;
  for (const line of patch.split(/\r?\n/)) {
    const hunk = line.match(/^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
    if (hunk) {
      newLine = Number(hunk[1]);
      continue;
    }
    if (line.startsWith("+") && !line.startsWith("+++")) {
      if (newLine === finding.line) return `› ${newLine}  ${line.slice(1)}`;
      newLine += 1;
    } else if (line.startsWith(" ") && newLine > 0) {
      if (newLine === finding.line) return `  ${newLine}  ${line.slice(1)}`;
      newLine += 1;
    }
  }
  return null;
}

function formatFinding(finding) {
  return [
    `[${finding.severity}] ${finding.title}`,
    `Source: ${finding.source} (confidence not provided)`,
    `Location: ${[finding.file, finding.line ? `line ${finding.line}` : null].filter(Boolean).join(":") || "not provided"}`,
    `Explanation: ${finding.explanation}`,
    `Why it matters: ${finding.why_it_matters}`,
    `Recommendation: ${finding.recommendation}`,
    finding.suggested_code ? `Suggested example:\n${finding.suggested_code}` : ""
  ].filter(Boolean).join("\n");
}

async function copyText(value, successMessage) {
  try {
    await navigator.clipboard.writeText(value);
    showToast(successMessage);
  } catch {
    showToast("Clipboard access is unavailable in this browser context.");
  }
}

function exportReport() {
  const review = state.currentReview;
  if (!review) return;
  const lines = [
    `# Code review: ${review.title}`,
    "",
    `- Repository: ${review.repository}`,
    `- Pull request: #${review.pull_request_number}`,
    `- Method: ${review.mode}`,
    `- Reviewed: ${review.reviewed_at}`,
    `- Summary: ${review.summary}`,
    "",
    "## Files returned",
    ...review.files.map((file) => {
      const counts = diffCounts(file);
      return `- \`${file.filename}\`: +${counts.added} / -${counts.removed}${counts.hasPatch ? "" : " (patch unavailable)"}`;
    }),
    "",
    "## Findings"
  ];
  if (!review.findings.length) lines.push("", "No findings were returned. This does not establish that the code is free of defects.");
  review.findings.forEach((finding) => lines.push("", `### ${finding.severity}: ${finding.title}`, "", formatFinding(finding)));
  lines.push("", "---", "Advisory review only. Findings are not verified vulnerabilities; confidence values are not provided unless explicitly stated.");
  const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `ai-code-review-bot-github-pr-review-${review.id}.md`;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function startNewReview() {
  setView("dashboard");
  switchMode("code");
  $("#review-form-panel").scrollIntoView({ behavior: "smooth", block: "center" });
  $("#code-snippet").focus({ preventScroll: true });
}

function resetReviewForm() {
  $("#form-error").classList.add("hidden");
  $("#code-snippet").value = "";
  updateCodeEmptyState();
  $("#code-sample-select").value = "";
  $("#sample-select").selectedIndex = 0;
  $("#repo-url").value = "";
  $("#pr-number").value = "";
  $("#results-panel").classList.add("hidden");
  state.currentReview = null;
  state.filter = "All";
  state.search = "";
  $("#finding-search").value = "";
  $$(".filter-chip", $("#severity-filters")).forEach((chip) => chip.classList.toggle("active", chip.dataset.filter === "All"));
  showToast("Review form reset.");
}

async function loadSettings() {
  try {
    const health = await api("/api/health");
    $("#connection-label").textContent = "Backend connected";
    $(".connection").classList.add("is-online");
    $("#github-status-dot").classList.toggle("online", health.github_token_configured);
    $("#github-status-label").textContent = health.github_token_configured ? "Token configured on backend" : "Public repositories · no token configured";
    $("#ai-status-dot").classList.toggle("online", health.llm_configured);
    $("#ai-status-label").textContent = health.llm_configured
      ? "LLM key configured for GitHub PR reviews"
      : "GitHub demo heuristic active · Python AST rules available";
  } catch {
    $("#connection-label").textContent = "Backend unavailable";
    $("#github-status-label").textContent = "Backend unavailable — start the FastAPI server.";
    $("#ai-status-label").textContent = "Backend unavailable — start the FastAPI server.";
  }
}

async function init() {
  const now = new Date();
  $("#current-date").textContent = new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "2-digit"
  }).format(now).toUpperCase();
  const greeting = now.getHours() < 12 ? "Good morning" : now.getHours() < 18 ? "Good afternoon" : "Good evening";
  $(".page-heading h1").firstChild.textContent = `${greeting}, `;
  $$(".nav-link,[data-view='settings'],[data-view='reviews'],[data-view='dashboard']").forEach((button) => {
    button.addEventListener("click", () => {
      setView(button.dataset.view);
      if (button.matches("#view-reviews [data-view='dashboard']")) startNewReview();
    });
  });
  $("#mobile-menu").addEventListener("click", () => $("#sidebar").classList.toggle("is-open"));
  $("#new-review-button").addEventListener("click", startNewReview);
  $$(".mode-tab").forEach((tab) => tab.addEventListener("click", () => switchMode(tab.dataset.mode)));
  $("#review-form").addEventListener("submit", handleReviewSubmit);
  $("#reset-review").addEventListener("click", resetReviewForm);
  $("#code-sample-select").addEventListener("change", () => {
    const sample = state.codeSamples.find((item) => item.id === $("#code-sample-select").value);
    if (sample) {
      $("#code-snippet").value = sample.code;
      updateCodeEmptyState();
    }
  });
  $("#try-sample").addEventListener("click", () => {
    const sample = state.codeSamples.find((item) => item.category === "Clean example") || state.codeSamples[0];
    if (!sample) return showToast("No built-in Python examples are available.");
    $("#code-sample-select").value = sample.id;
    $("#code-snippet").value = sample.code;
    updateCodeEmptyState();
    $("#code-snippet").focus();
  });
  $("#code-snippet").addEventListener("input", updateCodeEmptyState);
  $("#severity-filters").addEventListener("click", (event) => {
    const button = event.target.closest("[data-filter]");
    if (!button) return;
    state.filter = button.dataset.filter;
    $$(".filter-chip", $("#severity-filters")).forEach((chip) => chip.classList.toggle("active", chip === button));
    renderFindings();
  });
  $("#finding-search").addEventListener("input", (event) => {
    state.search = event.target.value;
    renderFindings();
  });
  $("#export-report").addEventListener("click", exportReport);
  $("#diff-toggle").addEventListener("click", () => {
    const isHidden = $("#diff-view").classList.toggle("hidden");
    $("#diff-toggle").setAttribute("aria-expanded", String(!isHidden));
    $("#diff-toggle").innerHTML = `${isHidden ? "Show" : "Hide"} diff <span>${isHidden ? "⌄" : "⌃"}</span>`;
  });
  $("#history-search").addEventListener("input", (event) => renderHistory(event.target.value));
  $("#history-severity").addEventListener("change", () => renderHistory($("#history-search").value));
  $("#clear-history").addEventListener("click", async () => {
    if (!state.reviews.length) return showToast("There are no saved reviews to clear.");
    if (!window.confirm("Clear all locally saved review history? This cannot be undone.")) return;
    try {
      await api("/api/reviews", { method: "DELETE" });
      state.reviews = [];
      updateDashboard();
      renderActivity();
      renderHistory($("#history-search").value);
      showToast("Review history cleared.");
    } catch (error) {
      showToast(`Could not clear review history: ${error.message}`);
    }
  });
  try {
    const [samples, codeSamples] = await Promise.all([
      api("/api/samples"),
      api("/api/code-samples")
    ]);
    state.samples = samples;
    state.codeSamples = codeSamples;
    renderSampleOptions();
    renderCodeSampleOptions();
    await loadHistory();
    switchMode("code");
  } catch (error) {
    showToast(`Could not load workspace data: ${error.message}`);
    $("#activity-list").innerHTML = `<div class="empty-filter">Start the FastAPI backend to load demo pull requests.</div>`;
  }
  await loadSettings();
}

init();
