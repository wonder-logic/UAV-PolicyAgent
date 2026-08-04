import assert from "node:assert/strict";
import test from "node:test";

import {
  buildPolicyReferenceCards,
  buildFactBadges,
  buildChatPayload,
  buildDecisionSections,
  buildKnowledgeBaseOverview,
  buildSimulatorNarrative,
  buildSimulatorGridSummary,
  formatArtifactJson,
  formatConfidenceScore,
  formatDecisionStatus,
  isResetMessage,
  normalizeApiError,
} from "../policy_agent/web/static/app.mjs";

test("chat payload trims natural language input and carries the current structured request", () => {
  assert.deepEqual(buildChatPayload("  Can I fly this at night?  ", { operation_type: "research" }), {
    message: "Can I fly this at night?",
    policy_request: { operation_type: "research" },
    include_decision_preview: true,
  });
});

test("decision rendering helpers expose sections and badge styles", () => {
  const response = {
    missing_attributes: ["anti_collision_lights"],
    next_question: "Does the drone have anti-collision lighting available for the planned night operation?",
    knowledge_warnings: ["High wind at launch."],
    preview_decision: {
      uavguard_status: "NEEDS_REVIEW",
      confidence: "MEDIUM",
      mission_score: 62,
      accuracy_score: 78,
      explanation: "Current policy status is NEEDS_REVIEW because one required night-operation detail is still missing.",
      warnings: ["Conservative review required because one or more required authorization attributes are missing."],
      obligations: ["Confirm the anti-collision lighting configuration."],
      citations: [
        {
          document: "14 CFR Part 107",
          section: "14 CFR 107.29(a)(2)",
          page: 8,
          text_snippet: "Night operations require anti-collision lighting.",
          relevance: "Retrieved policy evidence supporting the decision",
        },
      ],
    },
  };

  const badge = formatDecisionStatus(response);
  const sections = buildDecisionSections(response);
  const confidence = formatConfidenceScore(response);
  const references = buildPolicyReferenceCards(response);

  assert.equal(badge.label, "Needs a closer check");
  assert.equal(confidence.value, "62/100");
  assert.equal(confidence.detail, "Accuracy 78/100 | Medium confidence");
  assert.ok(sections.some((section) => section.title === "Things to watch"));
  assert.ok(sections.some((section) => section.title === "What to do next"));
  assert.ok(sections.some((section) => section.title === "Operational context"));
  assert.equal(references[0].title, "14 CFR 107.29(a)(2)");
  assert.match(references[0].meta, /14 CFR Part 107/);
});

test("fact badges return verified fact strings in display order", () => {
  const facts = buildFactBadges({
    verified_facts: ["Aircraft: DJI Mini 4 Pro", "Altitude: 280 ft", "Night operation"],
  });

  assert.deepEqual(facts, ["Aircraft: DJI Mini 4 Pro", "Altitude: 280 ft", "Night operation"]);
});

test("reset message detection supports short chat commands", () => {
  assert.equal(isResetMessage(" reset "), true);
  assert.equal(isResetMessage("start over"), true);
  assert.equal(isResetMessage("can I reset the mission?"), false);
});

test("error normalization prefers human-readable messages", () => {
  assert.equal(normalizeApiError({ message: "Friendly message" }), "Friendly message");
  assert.equal(normalizeApiError({ detail: "Unauthorized" }), "Unauthorized");
});

test("artifact helpers summarize the simulator grid and pretty-print JSON", () => {
  const response = {
    simulator_grid_preview: {
      simulator_recommendation: "REVIEW",
      total_cells: 3,
      allowed_cell_ids: ["launch"],
      review_cell_ids: ["destination"],
      no_fly_zone_cell_ids: ["restricted-1"],
    },
  };

  assert.deepEqual(buildSimulatorGridSummary(response), {
    recommendation: "REVIEW",
    totalCells: 3,
    allowedCells: 1,
    reviewCells: 1,
    blockedCells: 1,
  });
  assert.match(formatArtifactJson({ hello: "world" }), /"hello": "world"/);
  assert.equal(formatArtifactJson(null, "Waiting"), "Waiting");
});

test("knowledge base and simulator narratives explain returned artifacts in plain language", () => {
  const response = {
    knowledge_agent_called: true,
    knowledge_source: "MOCK",
    grounded_facts: ["Aircraft matched", "Route validated"],
    knowledge_request: { request_id: "kar-123" },
    knowledge_response: {
      mission_level_facts: ["Class G airspace", "No TFR found"],
      warnings: ["High wind at launch."],
      missing_information: ["site authorization"],
    },
    simulator_package: {
      overall_decision: "APPROVED",
      grid_cells: [{ cell_id: "launch" }, { cell_id: "destination" }],
    },
    simulator_grid_preview: {
      simulator_recommendation: "PROCEED",
      total_cells: 2,
    },
  };

  const knowledge = buildKnowledgeBaseOverview(response);
  const simulatorNarrative = buildSimulatorNarrative(response);

  assert.equal(knowledge.statusLabel, "Response ready");
  assert.equal(knowledge.sourceLabel, "MOCK");
  assert.equal(knowledge.factCount, 2);
  assert.match(knowledge.narrative, /Knowledge Base response loaded from MOCK/);
  assert.match(simulatorNarrative, /Simulator handoff is ready/);
  assert.match(simulatorNarrative, /Route recommendation: PROCEED/);
});
