from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Protocol

import httpx

from policy_agent.config import Settings
from policy_agent.core.exceptions import ExternalServiceError
from policy_agent.schemas.mission import MissionDecision, MissionDetailsRead, MissionUpdate, MissionUpdateExtraction
from policy_agent.utils.datetime_utils import utcnow

ALTITUDE_PATTERN = re.compile(r"\b(\d{2,4})\s*(?:ft|feet|foot)\b", re.IGNORECASE)
PEOPLE_COUNT_PATTERN = re.compile(r"\b(\d+)\s+people\b", re.IGNORECASE)
TIME_PATTERN = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.IGNORECASE)
LOCATION_PATTERNS = (
    re.compile(r"\bnear\s+([^,.]+?)(?=,| and |$)", re.IGNORECASE),
    re.compile(r"\bfrom\s+([^,.]+?)(?=,| and |$)", re.IGNORECASE),
    re.compile(r"\bat\s+([^,.]+?)(?=,| and |$)", re.IGNORECASE),
)
AREA_PATTERN = re.compile(r"\bto\s+([^,.]+?)(?=,| and |$)", re.IGNORECASE)


class BaseLLMProvider(Protocol):
    def extract_mission_update(self, *, message: str, mission: MissionDetailsRead) -> MissionUpdateExtraction: ...

    def generate_decision_explanation(
        self,
        *,
        mission: MissionDetailsRead,
        decision: MissionDecision,
    ) -> str: ...


def _build_follow_up_question(missing_fields: list[str]) -> str | None:
    prompts = {
        "start_time": "What date and local time do you plan to start the mission?",
        "launch_location": "Where will the mission launch from?",
        "operational_area": "What area will the aircraft cover during the mission?",
        "maximum_altitude_agl_ft": "What maximum altitude above ground level do you plan to fly?",
        "visual_line_of_sight": "Will the aircraft remain within visual line of sight for the full mission?",
        "night_operation": "Will any part of this mission occur at night?",
        "operation_over_people": "Will the route pass over people who are not directly involved in the operation?",
        "operation_over_moving_vehicles": "Will the route include sustained flight over moving vehicles?",
        "pilot_certification": "Do you have a current remote pilot certificate recorded in your profile?",
        "remote_id": "Which Remote ID method is active on the selected aircraft?",
    }
    for field in missing_fields:
        if field in prompts:
            return prompts[field]
    return None


def _maybe_parse_datetime(message: str) -> datetime | None:
    lowered = message.lower()
    day_offset = None
    if "tomorrow" in lowered:
        day_offset = 1
    elif "today" in lowered or "tonight" in lowered:
        day_offset = 0

    match = TIME_PATTERN.search(message)
    if day_offset is None or match is None:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or "0")
    meridiem = match.group(3).lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0

    base = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    base += timedelta(days=day_offset)
    return base.replace(hour=hour, minute=minute)


def _extract_location_phrase(message: str) -> str | None:
    for pattern in LOCATION_PATTERNS:
        match = pattern.search(message)
        if match is None:
            continue
        candidate = match.group(1).strip(" .")
        if candidate and not TIME_PATTERN.fullmatch(candidate):
            return candidate
    return None


def _extract_operational_area_phrase(message: str) -> str | None:
    match = AREA_PATTERN.search(message)
    if match is None:
        return None
    candidate = match.group(1).strip(" .")
    return candidate or None


class MockLLMProvider:
    def extract_mission_update(self, *, message: str, mission: MissionDetailsRead) -> MissionUpdateExtraction:
        lowered = message.lower()
        update = MissionUpdate()
        uncertain_fields: list[str] = []

        altitude_match = ALTITUDE_PATTERN.search(message)
        if altitude_match:
            update.maximum_altitude_agl_ft = float(altitude_match.group(1))

        if "night" in lowered or "after sunset" in lowered:
            update.night_operation = True
        if "daytime" in lowered or "during the day" in lowered:
            update.night_operation = False
        if (
            "bvlos" in lowered
            or "beyond visual line of sight" in lowered
            or "not within visual line of sight" in lowered
        ):
            update.visual_line_of_sight = False
        elif "stay within visual line of sight" in lowered or "remain within visual line of sight" in lowered:
            update.visual_line_of_sight = True
        elif "vlos" in lowered or "visual line of sight" in lowered:
            update.visual_line_of_sight = True
        if "over people" in lowered or "crowd" in lowered or "spectators" in lowered:
            update.operation_over_people = "not over people" not in lowered
        if "over moving vehicles" in lowered or "traffic" in lowered or "cars" in lowered:
            update.operation_over_moving_vehicles = "not over moving vehicles" not in lowered
        if "controlled ground area" in lowered:
            update.controlled_ground_area = True

        people_match = PEOPLE_COUNT_PATTERN.search(message)
        if people_match:
            update.expected_people_count = int(people_match.group(1))

        parsed_time = _maybe_parse_datetime(message)
        if parsed_time is not None:
            update.start_time = parsed_time
            if update.night_operation is None and (parsed_time.hour >= 21 or parsed_time.hour < 6):
                update.night_operation = True

        location_phrase = _extract_location_phrase(message)
        if location_phrase:
            update.launch_location = {
                "type": "Feature",
                "geometry": None,
                "properties": {"label": location_phrase, "source": "user_message"},
            }

        area_phrase = _extract_operational_area_phrase(message)
        if area_phrase:
            update.operational_area = {
                "type": "Feature",
                "geometry": None,
                "properties": {"label": area_phrase, "source": "user_message"},
            }

        if any(token in lowered for token in ("survey", "inspection", "research", "mapping", "training")):
            if "research" in lowered:
                update.purpose = "Research mission"
            elif "inspection" in lowered:
                update.purpose = "Inspection mission"
            elif "mapping" in lowered:
                update.purpose = "Mapping mission"
            elif "training" in lowered:
                update.purpose = "Training mission"
            else:
                update.purpose = "Survey mission"

        if "around campus" in lowered or "near campus" in lowered:
            uncertain_fields.append("launch_location")
            uncertain_fields.append("operational_area")

        missing_fields = [
            field
            for field in (
                "start_time",
                "launch_location",
                "operational_area",
                "maximum_altitude_agl_ft",
                "visual_line_of_sight",
                "night_operation",
                "operation_over_people",
                "operation_over_moving_vehicles",
            )
            if getattr(update, field) is None and getattr(mission, field, None) is None
        ]

        follow_up_question = _build_follow_up_question(missing_fields)
        return MissionUpdateExtraction(
            updates=update,
            uncertain_fields=uncertain_fields,
            missing_fields=missing_fields,
            follow_up_question=follow_up_question,
            reasoning_summary="Structured mission fields were extracted conservatively from the user's message.",
        )

    def generate_decision_explanation(
        self,
        *,
        mission: MissionDetailsRead,
        decision: MissionDecision,
    ) -> str:
        if decision.decision == "APPROVED":
            return (
                "The mission can proceed based on the currently verified facts. "
                "All applicable blocking checks were satisfied, and no unresolved authorization or waiver gaps remain."
            )
        if decision.decision == "DENIED":
            reasons = "; ".join(decision.blocking_reasons[:2]) or decision.concise_summary
            return (
                f"The mission is denied because {reasons.lower()} "
                "Update the blocked conditions or provide the required waiver before reevaluation."
            )
        reasons = "; ".join((decision.review_reasons or decision.missing_information)[:2]) or decision.concise_summary
        return (
            f"The mission needs review because {reasons.lower()} "
            "Provide the missing verification or authorization details and reevaluate the mission."
        )


class HttpLLMProvider:
    def __init__(self, settings: Settings):
        if not settings.llm_base_url:
            raise ExternalServiceError("LLM_BASE_URL is not configured.")
        self.settings = settings
        self.base_url = settings.llm_base_url

    def _request(self, payload: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"

        last_error: Exception | None = None
        for _ in range(self.settings.llm_max_retries + 1):
            try:
                with httpx.Client(timeout=self.settings.llm_timeout_seconds) as client:
                    response = client.post(self.base_url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # pragma: no cover - network dependent
                last_error = exc
        raise ExternalServiceError(f"LLM request failed: {last_error}")  # pragma: no cover

    def extract_mission_update(self, *, message: str, mission: MissionDetailsRead) -> MissionUpdateExtraction:
        payload = {
            "task": "extract_mission_update",
            "model": self.settings.llm_model,
            "message": message,
            "mission": mission.model_dump(mode="json"),
        }
        response = self._request(payload)
        return MissionUpdateExtraction.model_validate(response)

    def generate_decision_explanation(
        self,
        *,
        mission: MissionDetailsRead,
        decision: MissionDecision,
    ) -> str:
        payload = {
            "task": "generate_decision_explanation",
            "model": self.settings.llm_model,
            "mission": mission.model_dump(mode="json"),
            "decision": decision.model_dump(mode="json"),
        }
        response = self._request(payload)
        explanation = response.get("explanation")
        if not explanation:
            raise ExternalServiceError("LLM response did not include an explanation.")
        return str(explanation)


def create_llm_provider(settings: Settings) -> BaseLLMProvider:
    if settings.llm_provider == "http":
        return HttpLLMProvider(settings)
    return MockLLMProvider()
