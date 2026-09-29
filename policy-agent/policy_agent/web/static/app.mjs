const CHAT_STATE_KEY = "uavguard-policy-chat-v1";
const DEFAULT_ARTIFACT_TAB = "review";
const VALID_ARTIFACT_TABS = ["review", "grid", "knowledge"];
const LEGACY_ARTIFACT_TAB_MAP = {
  "knowledge-response": "knowledge",
};
const STARTER_COPY =
  "Tell me about the aircraft and the mission in plain language. I'll track only the details you actually provide, ask for the next missing fact when needed, and stay grounded in the policy rules.";

const INTERNAL_WARNING_PREFIXES = [
  "LLM evaluator not configured",
  "Deterministic Part 107 safeguards",
];

function normalizeArtifactTab(tab, availableTabs = VALID_ARTIFACT_TABS) {
  const mappedTab = LEGACY_ARTIFACT_TAB_MAP[tab] || tab || DEFAULT_ARTIFACT_TAB;
  return availableTabs.includes(mappedTab) ? mappedTab : DEFAULT_ARTIFACT_TAB;
}

export function buildChatPayload(message, policyRequest = {}, knowledgeContext = null) {
  const payload = {
    message: `${message ?? ""}`.trim(),
    policy_request: policyRequest,
    include_decision_preview: true,
  };
  if (knowledgeContext) {
    payload.knowledge_context = knowledgeContext;
  }
  return payload;
}

export function formatDecisionStatus(response) {
  const status = response?.decision?.status || response?.preview_decision?.uavguard_status;
  if (!status) {
    return { label: "Listening", className: "decision-badge decision-badge--neutral" };
  }
  if (status === "APPROVED") {
    return {
      label: response?.evaluation_stage === "FINAL" ? "Grounded approval" : "Looks approvable",
      className: "decision-badge decision-badge--approved",
    };
  }
  if (status === "DENIED") {
    return { label: "Blocked as described", className: "decision-badge decision-badge--denied" };
  }
  if (response?.evaluation_stage === "PRELIMINARY" || response?.evaluation_stage === "COLLECTING_INFORMATION") {
    return { label: "Preliminary review", className: "decision-badge decision-badge--review" };
  }
  return { label: "Needs a closer check", className: "decision-badge decision-badge--review" };
}

export function buildDecisionSections(response) {
  const decision = response?.decision || response?.preview_decision;
  const sections = [];
  const visibleWarnings = (decision?.warnings || []).filter(
    (warning) => !INTERNAL_WARNING_PREFIXES.some((prefix) => `${warning}`.startsWith(prefix)),
  );

  if (response?.missing_fields?.length) {
    sections.push({
      title: "Still needed",
      items: response.missing_fields,
    });
  }
  if (visibleWarnings.length) {
    sections.push({
      title: "Things to watch",
      items: visibleWarnings,
    });
  }
  if (decision?.obligations?.length) {
    sections.push({
      title: "What to do next",
      items: decision.obligations,
    });
  }
  if (decision?.advice?.length) {
    sections.push({
      title: "Helpful notes",
      items: decision.advice,
    });
  }
  if (response?.knowledge_warnings?.length) {
    sections.push({
      title: "Operational context",
      items: response.knowledge_warnings,
    });
  }
  if (response?.errors?.length) {
    sections.push({
      title: "Integration issues",
      items: response.errors,
    });
  }
  if (response?.final_decision_ready && response?.knowledge_follow_up_questions?.length) {
    sections.push({
      title: "If you want a tighter review",
      items: response.knowledge_follow_up_questions,
    });
  }

  return sections;
}

export function buildFactBadges(response) {
  return (response?.grounded_facts || response?.verified_facts || []).filter(Boolean);
}

export function formatConfidenceScore(response) {
  const decision = response?.decision || response?.preview_decision || {};
  const missionScore = decision?.mission_score;
  const accuracyScore = decision?.accuracy_score;
  const confidence = decision?.confidence;
  if (Number.isFinite(missionScore)) {
    const detailParts = [];
    if (Number.isFinite(accuracyScore)) {
      detailParts.push(`Accuracy ${Math.round(accuracyScore)}/100`);
    }
    if (confidence === "HIGH") {
      detailParts.push("High confidence");
    } else if (confidence === "MEDIUM") {
      detailParts.push("Medium confidence");
    } else if (confidence === "LOW") {
      detailParts.push("Low confidence");
    }
    return {
      value: `${Math.round(missionScore)}/100`,
      detail: detailParts.join(" | ") || "Grounded decision score",
      className:
        confidence === "HIGH"
          ? "score-card score-card--high"
          : confidence === "MEDIUM"
            ? "score-card score-card--medium"
            : confidence === "LOW"
              ? "score-card score-card--low"
              : "score-card score-card--neutral",
    };
  }
  if (confidence === "HIGH") {
    return {
      value: "3/3",
      detail: "High confidence",
      className: "score-card score-card--high",
    };
  }
  if (confidence === "MEDIUM") {
    return {
      value: "2/3",
      detail: "Medium confidence",
      className: "score-card score-card--medium",
    };
  }
  if (confidence === "LOW") {
    return {
      value: "1/3",
      detail: "Low confidence",
      className: "score-card score-card--low",
    };
  }
  return {
    value: "No score yet",
    detail: "Waiting for enough grounded facts",
    className: "score-card score-card--neutral",
  };
}

export function buildPolicyReferenceCards(response) {
  const citations = response?.decision?.citations || response?.preview_decision?.citations || [];
  return citations.map((citation) => ({
    title: citation.section || citation.title || citation.document || "Policy reference",
    meta: [
      citation.document || citation.title || null,
      citation.page != null ? `Page ${citation.page}` : null,
      citation.relevance || citation.authority || null,
    ]
      .filter(Boolean)
      .join(" | "),
    snippet: `${citation.text_snippet || citation.excerpt || ""}`.replace(/\s+/g, " ").trim(),
  }));
}

export function buildSimulatorGridSummary(response) {
  const grid = response?.simulator_grid_preview;
  if (!grid) {
    return {
      recommendation: "Waiting",
      totalCells: 0,
      allowedCells: 0,
      reviewCells: 0,
      blockedCells: 0,
    };
  }

  return {
    recommendation: grid.simulator_recommendation || "Waiting",
    totalCells: Number(grid.total_cells) || 0,
    allowedCells: (grid.allowed_cell_ids || []).length,
    reviewCells: (grid.review_cell_ids || []).length,
    blockedCells: (grid.no_fly_zone_cell_ids || []).length,
  };
}

export function buildSimulatorNarrative(response) {
  const simulatorPackage = response?.simulator_package;
  const grid = response?.simulator_grid_preview;

  if (simulatorPackage) {
    const decision = simulatorPackage.overall_decision || "REVIEW";
    const recommendation = grid?.simulator_recommendation || "REVIEW";
    const cellCount =
      (Array.isArray(simulatorPackage.grid_cells) && simulatorPackage.grid_cells.length) || Number(grid?.total_cells) || 0;
    return `Simulator handoff is ready. Overall decision: ${decision}. Route recommendation: ${recommendation}. ${cellCount} validated grid cell${cellCount === 1 ? "" : "s"} prepared for the simulator.`;
  }

  if (grid) {
    const cellCount = Number(grid.total_cells) || 0;
    return `A simulator preview is available with ${cellCount} grid cell${cellCount === 1 ? "" : "s"}. The full handoff package will appear here after the grounded review reaches a final knowledge-backed state.`;
  }

  return "The simulator tab will show the route handoff package here once enough mission and knowledge data are available.";
}

export function buildKnowledgeBaseOverview(response) {
  const request = response?.knowledge_request || response?.knowledge_request_preview;
  const knowledgeResponse = response?.knowledge_response || response?.verified_mission_context;
  const sourceLabel = response?.knowledge_source || "NONE";
  const knowledgeAgentCalled = Boolean(response?.knowledge_agent_called);
  const factCount = Array.isArray(knowledgeResponse?.mission_level_facts)
    ? knowledgeResponse.mission_level_facts.length
    : Array.isArray(response?.grounded_facts)
      ? response.grounded_facts.length
      : 0;
  const warningCount = Array.isArray(knowledgeResponse?.warnings)
    ? knowledgeResponse.warnings.length
    : Array.isArray(response?.knowledge_warnings)
      ? response.knowledge_warnings.length
      : 0;
  const missingCount = Array.isArray(knowledgeResponse?.missing_information)
    ? knowledgeResponse.missing_information.length
    : Array.isArray(response?.missing_fields)
      ? response.missing_fields.length
      : 0;

  let statusLabel = "Waiting";
  let statusDetail = "Need more mission details before building the Knowledge Agent request";
  let sourceDetail = "Knowledge Agent not called yet";
  let narrative =
    "The Knowledge Base tab will show the structured request and validated response once enough mission details are available.";

  if (request) {
    statusLabel = "Request ready";
    statusDetail = "Structured request built from the mission details collected in chat";
    narrative =
      "The Policy Agent has prepared the structured Knowledge Agent request. The request JSON is shown below so you can inspect exactly what the backend sends.";
  }

  if (knowledgeResponse) {
    statusLabel = "Response ready";
    statusDetail = "Validated knowledge context is available for grounded review";
    const detailParts = [];
    if (factCount) {
      detailParts.push(`${factCount} grounded fact${factCount === 1 ? "" : "s"}`);
    }
    if (warningCount) {
      detailParts.push(`${warningCount} warning${warningCount === 1 ? "" : "s"}`);
    }
    if (missingCount) {
      detailParts.push(`${missingCount} outstanding field${missingCount === 1 ? "" : "s"}`);
    }
    narrative = knowledgeAgentCalled
      ? `Knowledge Base response loaded from ${sourceLabel}. ${detailParts.length ? `It contains ${detailParts.join(", ")}.` : "The validated response is ready below."}`
      : `Supplied knowledge context is loaded${sourceLabel !== "NONE" ? ` from ${sourceLabel}` : ""}. ${detailParts.length ? `It contains ${detailParts.join(", ")}.` : "The validated context is ready below."}`;
  }

  if (knowledgeAgentCalled) {
    sourceDetail = "Knowledge Agent called for grounded review";
  } else if (sourceLabel === "SUPPLIED") {
    sourceDetail = "User-supplied knowledge context";
  }

  return {
    statusLabel,
    statusDetail,
    sourceLabel,
    sourceDetail,
    factCount,
    warningCount,
    missingCount,
    narrative,
  };
}

function formatEvaluationStageMeta(response) {
  const stage = response?.evaluation_stage || "PRELIMINARY";
  const source = response?.knowledge_source || "NONE";
  const called = response?.knowledge_agent_called ? "Knowledge Agent called" : "Knowledge Agent not called";
  const stageDetailMap = {
    COLLECTING_INFORMATION: "Collecting the remaining mission details",
    PRELIMINARY: "Mission details are still incomplete, so this is not a final decision",
    KNOWLEDGE_PENDING: "The grounded review is waiting on Knowledge Agent facts",
    FINAL: "Grounded decision based on validated knowledge and deterministic rules",
    ERROR: "A validation or integration issue blocked the final grounded review",
  };
  return {
    stage,
    stageDetail: stageDetailMap[stage] || "Grounded review status",
    source,
    called,
  };
}

function buildRuleResultCards(response) {
  const ruleResults = response?.decision?.rule_results || response?.preview_decision?.rule_results || [];
  return ruleResults.map((result) => ({
    title: result.rule_name || result.rule_id || "Rule result",
    status: `${result.result || "unknown"}`.replaceAll("_", " "),
    reason: result.reason || "",
  }));
}

export function formatArtifactJson(value, fallback = "Artifact preview will appear here.") {
  if (value == null) {
    return fallback;
  }
  return JSON.stringify(value, null, 2);
}

export function normalizeApiError(error) {
  if (typeof error === "string") {
    return error;
  }
  if (error && typeof error === "object") {
    if (typeof error.message === "string") {
      return error.message;
    }
    if (typeof error.detail === "string") {
      return error.detail;
    }
    if (error.detail && typeof error.detail === "object") {
      return JSON.stringify(error.detail);
    }
  }
  return "An unexpected error occurred.";
}

export function isResetMessage(message) {
  const normalized = `${message ?? ""}`.trim().toLowerCase();
  return ["reset", "start over", "clear chat", "clear"].includes(normalized);
}

function escapeHtml(value) {
  return `${value ?? ""}`
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function createBaseState() {
  return {
    conversation: [],
    policyRequest: {},
    lastResponse: null,
    activeArtifactTab: normalizeArtifactTab(DEFAULT_ARTIFACT_TAB),
  };
}

function loadState() {
  try {
    const parsed = JSON.parse(localStorage.getItem(CHAT_STATE_KEY) || "null") || {};
    return {
      ...createBaseState(),
      ...parsed,
      activeArtifactTab: normalizeArtifactTab(parsed.activeArtifactTab),
    };
  } catch {
    return createBaseState();
  }
}

function saveState(state) {
  localStorage.setItem(CHAT_STATE_KEY, JSON.stringify(state));
}

function resetState(state) {
  state.conversation = [];
  state.policyRequest = {};
  state.lastResponse = null;
  state.activeArtifactTab = normalizeArtifactTab(DEFAULT_ARTIFACT_TAB);
  saveState(state);
}

function cacheElements() {
  return {
    serviceStatus: document.getElementById("serviceStatus"),
    decisionBadge: document.getElementById("decisionBadge"),
    clearChatButton: document.getElementById("clearChatButton"),
    chatFeed: document.getElementById("chatFeed"),
    groundingPanel: document.getElementById("groundingPanel"),
    chatForm: document.getElementById("chatForm"),
    chatInput: document.getElementById("chatInput"),
    chatMessage: document.getElementById("chatMessage"),
    decisionSummary: document.getElementById("decisionSummary"),
    decisionSections: document.getElementById("decisionSections"),
    nextQuestion: document.getElementById("nextQuestion"),
    statusScore: document.getElementById("statusScore"),
    confidenceCard: document.getElementById("confidenceCard"),
    confidenceScore: document.getElementById("confidenceScore"),
    confidenceDetail: document.getElementById("confidenceDetail"),
    evaluationStage: document.getElementById("evaluationStage"),
    evaluationStageDetail: document.getElementById("evaluationStageDetail"),
    knowledgeSource: document.getElementById("knowledgeSource"),
    knowledgeAgentStatus: document.getElementById("knowledgeAgentStatus"),
    policyHitCount: document.getElementById("policyHitCount"),
    policyReferences: document.getElementById("policyReferences"),
    verifiedFacts: document.getElementById("verifiedFacts"),
    ruleResultList: document.getElementById("ruleResultList"),
    artifactTabs: Array.from(document.querySelectorAll("[data-artifact-tab]")),
    artifactPanels: Array.from(document.querySelectorAll("[data-artifact-panel]")),
    gridSummaryCards: document.getElementById("gridSummaryCards"),
    gridCellList: document.getElementById("gridCellList"),
    simulatorNarrative: document.getElementById("simulatorNarrative"),
    gridJsonPreview: document.getElementById("gridJsonPreview"),
    knowledgeNarrative: document.getElementById("knowledgeNarrative"),
    knowledgeSummaryCards: document.getElementById("knowledgeSummaryCards"),
    knowledgeRequestPreview: document.getElementById("knowledgeRequestPreview"),
    knowledgeResponsePreview: document.getElementById("knowledgeResponsePreview"),
    promptButtons: Array.from(document.querySelectorAll("[data-prompt]")),
  };
}

async function apiFetch(path, { method = "GET", body } = {}) {
  const response = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });

  const text = await response.text();
  const payload = text
    ? (() => {
        try {
          return JSON.parse(text);
        } catch {
          return text;
        }
      })()
    : null;

  if (!response.ok) {
    throw payload;
  }
  return payload;
}

async function checkService(els) {
  try {
    const payload = await apiFetch("/health");
    els.serviceStatus.textContent = `${payload.service} ready`;
  } catch {
    els.serviceStatus.textContent = "Service unavailable";
  }
}

function renderConversation(state, els) {
  const conversation = state.conversation.length
    ? state.conversation
    : [{ role: "assistant", content: STARTER_COPY }];

  els.chatFeed.innerHTML = conversation
    .map(
      (entry) => `
        <article class="chat-bubble chat-bubble--${entry.role}">
          <span class="chat-role">${entry.role === "assistant" ? "Policy Agent" : "Operator"}</span>
          <p>${escapeHtml(entry.content)}</p>
        </article>
      `,
    )
    .join("");

  els.chatFeed.scrollTop = els.chatFeed.scrollHeight;
}

function renderArtifactTabState(state, els) {
  const availableTabs = els.artifactTabs.map((button) => button.dataset.artifactTab).filter(Boolean);
  const activeTab = normalizeArtifactTab(state.activeArtifactTab, availableTabs);
  state.activeArtifactTab = activeTab;
  els.artifactTabs.forEach((button) => {
    const isActive = button.dataset.artifactTab === activeTab;
    button.classList.toggle("artifact-tab--active", isActive);
    button.setAttribute("aria-selected", `${isActive}`);
  });
  els.artifactPanels.forEach((panel) => {
    panel.hidden = panel.dataset.artifactPanel !== activeTab;
  });
}

function gridCardClassName(status) {
  if (status === "APPROVED") {
    return "grid-cell-card grid-cell-card--approved";
  }
  if (status === "DENIED") {
    return "grid-cell-card grid-cell-card--denied";
  }
  return "grid-cell-card grid-cell-card--review";
}

function renderArtifactPreviews(state, els) {
  const grid = state.lastResponse?.simulator_grid_preview;
  const gridSummary = buildSimulatorGridSummary(state.lastResponse);
  const simulatorPackage = state.lastResponse?.simulator_package;
  const knowledgeOverview = buildKnowledgeBaseOverview(state.lastResponse);

  els.simulatorNarrative.textContent = buildSimulatorNarrative(state.lastResponse);
  els.gridSummaryCards.innerHTML = `
    <article class="score-card">
      <span class="score-card__label">Simulator recommendation</span>
      <strong class="score-card__value">${escapeHtml(gridSummary.recommendation)}</strong>
      <span class="score-card__meta">Overall route recommendation for the simulator handoff</span>
    </article>
    <article class="score-card">
      <span class="score-card__label">Grid cells</span>
      <strong class="score-card__value">${escapeHtml(`${gridSummary.totalCells}`)}</strong>
      <span class="score-card__meta">Validated simulator cells</span>
    </article>
    <article class="score-card">
      <span class="score-card__label">Allowed / Review / Blocked</span>
      <strong class="score-card__value">${escapeHtml(
        `${gridSummary.allowedCells} / ${gridSummary.reviewCells} / ${gridSummary.blockedCells}`,
      )}</strong>
      <span class="score-card__meta">Cell-by-cell policy status</span>
    </article>
  `;

  const gridCells = grid?.cells || [];
  els.gridCellList.innerHTML = gridCells.length
    ? gridCells
        .map((cell) => {
          const highlights = [cell.explanation, ...(cell.warnings || []).slice(0, 1)].filter(Boolean);
          return `
            <article class="${gridCardClassName(cell.uavguard_status)}">
              <strong>${escapeHtml(cell.location_label || cell.cell_id)}</strong>
              <span class="grid-cell-card__meta">
                ${escapeHtml(cell.cell_id)} | ${escapeHtml(cell.uavguard_status)} | Cost ${escapeHtml(`${cell.cost}`)}
              </span>
              <ul class="grid-cell-card__list">
                ${highlights.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
              </ul>
            </article>
          `;
        })
        .join("")
    : `<p class="policy-empty">Simulator grid cells will appear here once the mission state is available.</p>`;

  els.gridJsonPreview.textContent = formatArtifactJson(
    simulatorPackage || grid,
    "Simulator package will appear here once the grounded mission review completes.",
  );
  els.knowledgeNarrative.textContent = knowledgeOverview.narrative;
  els.knowledgeSummaryCards.innerHTML = `
    <article class="score-card">
      <span class="score-card__label">Knowledge status</span>
      <strong class="score-card__value">${escapeHtml(knowledgeOverview.statusLabel)}</strong>
      <span class="score-card__meta">${escapeHtml(knowledgeOverview.statusDetail)}</span>
    </article>
    <article class="score-card">
      <span class="score-card__label">Knowledge source</span>
      <strong class="score-card__value">${escapeHtml(knowledgeOverview.sourceLabel)}</strong>
      <span class="score-card__meta">${escapeHtml(knowledgeOverview.sourceDetail)}</span>
    </article>
    <article class="score-card">
      <span class="score-card__label">Facts / Warnings / Missing</span>
      <strong class="score-card__value">${escapeHtml(
        `${knowledgeOverview.factCount} / ${knowledgeOverview.warningCount} / ${knowledgeOverview.missingCount}`,
      )}</strong>
      <span class="score-card__meta">Validated knowledge summary</span>
    </article>
  `;
  els.knowledgeRequestPreview.textContent = formatArtifactJson(
    state.lastResponse?.knowledge_request || state.lastResponse?.knowledge_request_preview,
    "Knowledge-agent request preview will appear here once mission details are available.",
  );
  els.knowledgeResponsePreview.textContent = formatArtifactJson(
    state.lastResponse?.knowledge_response || state.lastResponse?.verified_mission_context,
    "Knowledge-agent response will appear here after the grounded review uses validated knowledge.",
  );
}

function renderPolicyState(state, els) {
  const hasResponse = Boolean(state.lastResponse);
  const badge = formatDecisionStatus(state.lastResponse);
  els.decisionBadge.className = badge.className;
  els.decisionBadge.textContent = badge.label;
  els.groundingPanel.hidden = !hasResponse;
  els.statusScore.textContent = badge.label;

  const confidence = formatConfidenceScore(state.lastResponse);
  els.confidenceCard.className = confidence.className;
  els.confidenceScore.textContent = confidence.value;
  els.confidenceDetail.textContent = confidence.detail;

  const evaluationMeta = formatEvaluationStageMeta(state.lastResponse);
  els.evaluationStage.textContent = evaluationMeta.stage;
  els.evaluationStageDetail.textContent = evaluationMeta.stageDetail;
  els.knowledgeSource.textContent = evaluationMeta.source;
  els.knowledgeAgentStatus.textContent = evaluationMeta.called;

  const policyHits =
    state.lastResponse?.decision?.matched_policies?.length ||
    state.lastResponse?.decision?.citations?.length ||
    state.lastResponse?.preview_decision?.matched_policies?.length ||
    0;
  els.policyHitCount.textContent = `${policyHits}`;

  const facts = buildFactBadges(state.lastResponse);
  els.verifiedFacts.innerHTML = facts.length
    ? facts.map((fact) => `<article class="fact-chip">${escapeHtml(fact)}</article>`).join("")
    : `<article class="fact-chip fact-chip--muted">No verified mission facts yet</article>`;

  els.nextQuestion.textContent =
    state.lastResponse?.next_question ||
    "I have enough detail for the next grounded review step right now.";

  const decision = state.lastResponse?.decision || state.lastResponse?.preview_decision;
  els.decisionSummary.textContent =
    decision?.explanation ||
    decision?.summary ||
    "This panel keeps the policy score, verified facts, and supporting references outside the chat reply.";

  const ruleCards = buildRuleResultCards(state.lastResponse);
  els.ruleResultList.innerHTML = ruleCards.length
    ? ruleCards
        .map(
          (rule) => `
            <article class="${gridCardClassName(
              `${rule.status}`.includes("violated")
                ? "DENIED"
                : `${rule.status}`.includes("satisfied")
                  ? "APPROVED"
                  : "NEEDS_REVIEW",
            )}">
              <strong>${escapeHtml(rule.title)}</strong>
              <span class="grid-cell-card__meta">${escapeHtml(rule.status)}</span>
              <p class="policy-empty">${escapeHtml(rule.reason)}</p>
            </article>
          `,
        )
        .join("")
    : `<p class="policy-empty">Rule-level deterministic results will appear here after evaluation.</p>`;

  const references = buildPolicyReferenceCards(state.lastResponse);
  els.policyReferences.innerHTML = references.length
    ? references
        .map(
          (reference) => `
            <article class="reference-card">
              <strong>${escapeHtml(reference.title)}</strong>
              ${reference.meta ? `<span>${escapeHtml(reference.meta)}</span>` : ""}
              <p>${escapeHtml(reference.snippet)}</p>
            </article>
          `,
        )
        .join("")
    : `<p class="policy-empty">Policy references will appear here when the engine finds grounded support.</p>`;

  const sections = buildDecisionSections(state.lastResponse);
  els.decisionSections.innerHTML = sections.length
    ? sections
        .map(
          (section) => `
            <details open>
              <summary>${escapeHtml(section.title)}</summary>
              <ul>${section.items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
            </details>
          `,
        )
        .join("")
    : `<p class="policy-empty">Missing fields, follow-up actions, and integration issues will appear here when they matter.</p>`;

  renderArtifactPreviews(state, els);
  renderArtifactTabState(state, els);
}

function renderAll(state, els) {
  renderConversation(state, els);
  renderPolicyState(state, els);
}

function showMessage(els, message, isError = false) {
  els.chatMessage.textContent = message;
  els.chatMessage.classList.toggle("message-box--error", isError);
}

async function handleChatSubmit(event, state, els) {
  event.preventDefault();
  const message = `${els.chatInput.value ?? ""}`.trim();
  if (!message) {
    return;
  }

  if (isResetMessage(message)) {
    resetState(state);
    els.chatInput.value = "";
    showMessage(els, "Conversation cleared. Start with a fresh mission description.");
    renderAll(state, els);
    return;
  }

  state.conversation.push({ role: "user", content: message });
  renderConversation(state, els);
  showMessage(els, "");

  try {
    const response = await apiFetch("/policy-agent/chat", {
      method: "POST",
      body: buildChatPayload(message, state.policyRequest),
    });
    state.policyRequest = response.policy_request || {};
    state.lastResponse = response;
    state.conversation.push({ role: "assistant", content: response.assistant_message });
    saveState(state);
    els.chatInput.value = "";
    renderAll(state, els);
  } catch (error) {
    state.conversation.pop();
    renderConversation(state, els);
    showMessage(els, normalizeApiError(error), true);
  }
}

function bindEvents(state, els) {
  els.chatForm.addEventListener("submit", (event) => handleChatSubmit(event, state, els));
  els.clearChatButton.addEventListener("click", () => {
    resetState(state);
    showMessage(els, "Conversation cleared. Start with a fresh mission description.");
    renderAll(state, els);
  });
  els.artifactTabs.forEach((button) => {
    button.addEventListener("click", () => {
      state.activeArtifactTab = normalizeArtifactTab(button.dataset.artifactTab);
      saveState(state);
      renderArtifactTabState(state, els);
    });
  });
  els.promptButtons.forEach((button) => {
    button.addEventListener("click", () => {
      els.chatInput.value = button.textContent.trim();
      els.chatInput.focus();
    });
  });
}

async function initBrowserApp() {
  const state = loadState();
  const els = cacheElements();
  bindEvents(state, els);
  renderAll(state, els);
  await checkService(els);
}

if (typeof document !== "undefined") {
  initBrowserApp();
}
