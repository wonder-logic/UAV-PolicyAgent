from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Protocol

from policy_agent.db.models import DroneProfile, ProfileCredential, UserPolicyProfile
from policy_agent.schemas.common import PolicyEvaluationResult, PolicyRuleSeverity
from policy_agent.schemas.knowledge import KnowledgeAgentResponse, KnowledgeCellFact
from policy_agent.schemas.mission import MissionDetailsRead
from policy_agent.schemas.policy import PolicyEvaluation
from policy_agent.utils.datetime_utils import utcnow


@dataclass(slots=True)
class RuleContext:
    mission: MissionDetailsRead
    profile: UserPolicyProfile | None
    drone: DroneProfile | None
    knowledge_response: KnowledgeAgentResponse | None
    cell_fact: KnowledgeCellFact | None = None

    def fact_value(self, category: str):
        if self.cell_fact is not None:
            for fact in self.cell_fact.facts:
                if fact.category == category:
                    return fact.value
        if self.knowledge_response is None:
            return None
        for fact in self.knowledge_response.mission_level_facts:
            if fact.category == category:
                return fact.value
        return None

    def as_of_date(self) -> date:
        if self.mission.start_time is not None:
            return self.mission.start_time.date()
        return utcnow().date()

    def active_credentials(self, *, credential_kind: str) -> list[ProfileCredential]:
        if self.profile is None:
            return []
        comparison_date = self.as_of_date()
        matches = [
            credential
            for credential in self.profile.credentials
            if credential.credential_kind.strip().lower() == credential_kind
        ]
        active: list[ProfileCredential] = []
        for credential in matches:
            if credential.expiration_date is not None and credential.expiration_date < comparison_date:
                continue
            active.append(credential)
        return active

    def has_active_credential(self, *, credential_kind: str, keywords: Iterable[str] = ()) -> bool:
        keyword_set = {keyword.lower() for keyword in keywords}
        for credential in self.active_credentials(credential_kind=credential_kind):
            searchable = " ".join(
                filter(
                    None,
                    [
                        credential.credential_type,
                        credential.identifier,
                        credential.issuing_authority,
                        " ".join(credential.restrictions or []),
                    ],
                )
            ).lower()
            if not keyword_set:
                return True
            if any(keyword in searchable for keyword in keyword_set):
                return True
        return False


class PolicyRule(Protocol):
    rule_id: str
    rule_name: str
    severity: PolicyRuleSeverity
    query_tags: tuple[str, ...]

    def evaluate(self, context: RuleContext, citations: list) -> PolicyEvaluation: ...


def _evaluation(
    *,
    rule_id: str,
    rule_name: str,
    applicability: bool,
    result: PolicyEvaluationResult,
    severity: PolicyRuleSeverity,
    observed_facts: dict[str, object],
    required_conditions: list[str],
    reason: str,
    citations: list,
) -> PolicyEvaluation:
    return PolicyEvaluation(
        rule_id=rule_id,
        rule_name=rule_name,
        applicability=applicability,
        result=result,
        severity=severity,
        observed_facts=observed_facts,
        required_conditions=required_conditions,
        reason=reason,
        citations=citations,
    )


@dataclass(slots=True)
class MaximumAltitudeRule:
    rule_id: str = "maximum_altitude"
    rule_name: str = "Maximum altitude"
    severity: PolicyRuleSeverity = PolicyRuleSeverity.BLOCKING
    query_tags: tuple[str, ...] = ("altitude",)

    def evaluate(self, context: RuleContext, citations: list) -> PolicyEvaluation:
        altitude = context.mission.maximum_altitude_agl_ft
        if altitude is None:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.UNKNOWN,
                severity=self.severity,
                observed_facts={},
                required_conditions=["Provide the planned maximum altitude above ground level."],
                reason="The mission altitude was not provided.",
                citations=citations,
            )
        if altitude > 400:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.VIOLATED,
                severity=self.severity,
                observed_facts={"maximum_altitude_agl_ft": altitude},
                required_conditions=[
                    "Planned altitude must stay at or below 400 feet AGL unless a valid exception applies."
                ],
                reason="The planned altitude exceeds 400 feet above ground level.",
                citations=citations,
            )
        return _evaluation(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            applicability=True,
            result=PolicyEvaluationResult.SATISFIED,
            severity=self.severity,
            observed_facts={"maximum_altitude_agl_ft": altitude},
            required_conditions=[],
            reason="The planned altitude stays within the standard Part 107 limit.",
            citations=citations,
        )


@dataclass(slots=True)
class PilotCertificationRule:
    rule_id: str = "pilot_certification"
    rule_name: str = "Pilot certification presence and validity"
    severity: PolicyRuleSeverity = PolicyRuleSeverity.BLOCKING
    query_tags: tuple[str, ...] = ("pilot", "certificate")

    def evaluate(self, context: RuleContext, citations: list) -> PolicyEvaluation:
        if context.profile is None:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.UNKNOWN,
                severity=self.severity,
                observed_facts={},
                required_conditions=["Create a pilot policy profile and record a current remote pilot certificate."],
                reason="No pilot policy profile is available for this mission.",
                citations=citations,
            )
        if not context.profile.remote_pilot_certificate_number:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.UNKNOWN,
                severity=self.severity,
                observed_facts={},
                required_conditions=["Record the remote pilot certificate number in the policy profile."],
                reason="The pilot certificate number is missing from the profile.",
                citations=citations,
            )
        expiration = context.profile.remote_pilot_certificate_expiration
        if expiration is not None and expiration < context.as_of_date():
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.VIOLATED,
                severity=self.severity,
                observed_facts={"certificate_expiration": expiration.isoformat()},
                required_conditions=["Pilot certification must be current on the mission date."],
                reason="The recorded remote pilot certificate is expired.",
                citations=citations,
            )
        return _evaluation(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            applicability=True,
            result=PolicyEvaluationResult.SATISFIED,
            severity=self.severity,
            observed_facts={"certificate_number_present": True},
            required_conditions=[],
            reason="A current remote pilot certificate is recorded on the profile.",
            citations=citations,
        )


@dataclass(slots=True)
class NightOperationsRule:
    rule_id: str = "night_operations"
    rule_name: str = "Night operations training"
    severity: PolicyRuleSeverity = PolicyRuleSeverity.BLOCKING
    query_tags: tuple[str, ...] = ("night", "training")

    def evaluate(self, context: RuleContext, citations: list) -> PolicyEvaluation:
        if context.mission.night_operation is None:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.UNKNOWN,
                severity=self.severity,
                observed_facts={},
                required_conditions=["Confirm whether the mission will occur at night."],
                reason="Night-operation status is not yet known.",
                citations=citations,
            )
        if context.mission.night_operation is False:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=False,
                result=PolicyEvaluationResult.NOT_APPLICABLE,
                severity=self.severity,
                observed_facts={"night_operation": False},
                required_conditions=[],
                reason="The mission is not planned for night operations.",
                citations=citations,
            )
        if context.profile is None or not context.profile.recurrent_training_completed:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.VIOLATED,
                severity=self.severity,
                observed_facts={"night_operation": True},
                required_conditions=["Night operations require current FAA recurrent training evidence."],
                reason="Night flight training is not recorded as complete in the profile.",
                citations=citations,
            )
        return _evaluation(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            applicability=True,
            result=PolicyEvaluationResult.SATISFIED,
            severity=self.severity,
            observed_facts={"night_operation": True, "training_completed": True},
            required_conditions=[],
            reason="Night-operation training is recorded as complete.",
            citations=citations,
        )


@dataclass(slots=True)
class AntiCollisionLightingRule:
    rule_id: str = "anti_collision_lighting"
    rule_name: str = "Night anti-collision lighting"
    severity: PolicyRuleSeverity = PolicyRuleSeverity.BLOCKING
    query_tags: tuple[str, ...] = ("night", "lighting")

    def evaluate(self, context: RuleContext, citations: list) -> PolicyEvaluation:
        if context.mission.night_operation is not True:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=False,
                result=PolicyEvaluationResult.NOT_APPLICABLE,
                severity=self.severity,
                observed_facts={},
                required_conditions=[],
                reason="The anti-collision lighting rule applies only to night operations.",
                citations=citations,
            )
        if context.drone is None:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.UNKNOWN,
                severity=self.severity,
                observed_facts={},
                required_conditions=["Select a drone profile with verified night-lighting information."],
                reason="No drone profile is available for lighting verification.",
                citations=citations,
            )
        if context.drone.anti_collision_lighting is False:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.VIOLATED,
                severity=self.severity,
                observed_facts={"anti_collision_lighting": False},
                required_conditions=["Night operations require anti-collision lighting."],
                reason="The selected drone does not record anti-collision lighting.",
                citations=citations,
            )
        if context.drone.anti_collision_lighting is None or context.drone.light_visibility_statute_miles is None:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.UNKNOWN,
                severity=self.severity,
                observed_facts={"anti_collision_lighting": context.drone.anti_collision_lighting},
                required_conditions=["Verify anti-collision lighting and its visibility distance."],
                reason="Lighting visibility information is incomplete for night operations.",
                citations=citations,
            )
        if context.drone.light_visibility_statute_miles < 3:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.VIOLATED,
                severity=self.severity,
                observed_facts={"light_visibility_statute_miles": context.drone.light_visibility_statute_miles},
                required_conditions=["Night anti-collision lighting must be visible for at least 3 statute miles."],
                reason="The recorded anti-collision lighting visibility is below 3 statute miles.",
                citations=citations,
            )
        return _evaluation(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            applicability=True,
            result=PolicyEvaluationResult.SATISFIED,
            severity=self.severity,
            observed_facts={"light_visibility_statute_miles": context.drone.light_visibility_statute_miles},
            required_conditions=[],
            reason="The selected drone records night lighting visible for at least 3 statute miles.",
            citations=citations,
        )


@dataclass(slots=True)
class ControlledAirspaceRule:
    rule_id: str = "controlled_airspace"
    rule_name: str = "Controlled airspace requirements"
    severity: PolicyRuleSeverity = PolicyRuleSeverity.REVIEW
    query_tags: tuple[str, ...] = ("airspace", "authorization")

    def evaluate(self, context: RuleContext, citations: list) -> PolicyEvaluation:
        controlled = context.fact_value("controlled_airspace")
        if controlled is None:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.UNKNOWN,
                severity=self.severity,
                observed_facts={},
                required_conditions=["Verify whether the mission area enters controlled airspace."],
                reason="Controlled-airspace status could not be verified from the available facts.",
                citations=citations,
            )
        if controlled is False:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.SATISFIED,
                severity=self.severity,
                observed_facts={"controlled_airspace": False},
                required_conditions=[],
                reason="The Knowledge Agent did not identify controlled airspace in the mission area.",
                citations=citations,
            )
        return _evaluation(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            applicability=True,
            result=PolicyEvaluationResult.AUTHORIZATION_REQUIRED,
            severity=self.severity,
            observed_facts={"controlled_airspace": True},
            required_conditions=["Provide a valid authorization for the controlled-airspace portion of the mission."],
            reason="The mission area includes controlled airspace and requires authorization review.",
            citations=citations,
        )


@dataclass(slots=True)
class AuthorizationValidityRule:
    rule_id: str = "authorization_validity"
    rule_name: str = "Controlled airspace authorization validity"
    severity: PolicyRuleSeverity = PolicyRuleSeverity.REVIEW
    query_tags: tuple[str, ...] = ("authorization", "airspace")

    def evaluate(self, context: RuleContext, citations: list) -> PolicyEvaluation:
        controlled = context.fact_value("controlled_airspace")
        if controlled is not True:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=False,
                result=PolicyEvaluationResult.NOT_APPLICABLE,
                severity=self.severity,
                observed_facts={"controlled_airspace": controlled},
                required_conditions=[],
                reason="Authorization validity matters only when the mission enters controlled airspace.",
                citations=citations,
            )
        if context.has_active_credential(
            credential_kind="authorization", keywords=("laanc", "airspace", "atc", "class")
        ):
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.SATISFIED,
                severity=self.severity,
                observed_facts={"authorization_present": True},
                required_conditions=[],
                reason="An active authorization record appears to match the controlled-airspace mission.",
                citations=citations,
            )
        return _evaluation(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            applicability=True,
            result=PolicyEvaluationResult.AUTHORIZATION_REQUIRED,
            severity=self.severity,
            observed_facts={"authorization_present": False},
            required_conditions=["Upload or select the applicable controlled-airspace authorization."],
            reason="No valid controlled-airspace authorization could be verified in the profile.",
            citations=citations,
        )


@dataclass(slots=True)
class OperationsOverPeopleRule:
    rule_id: str = "operations_over_people"
    rule_name: str = "Operations over people"
    severity: PolicyRuleSeverity = PolicyRuleSeverity.BLOCKING
    query_tags: tuple[str, ...] = ("people", "waiver")

    def evaluate(self, context: RuleContext, citations: list) -> PolicyEvaluation:
        value = context.mission.operation_over_people
        if value is None:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.UNKNOWN,
                severity=self.severity,
                observed_facts={},
                required_conditions=["Confirm whether the route includes flight over people."],
                reason="The mission does not yet specify whether it involves operations over people.",
                citations=citations,
            )
        if value is False:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=False,
                result=PolicyEvaluationResult.NOT_APPLICABLE,
                severity=self.severity,
                observed_facts={"operation_over_people": False},
                required_conditions=[],
                reason="The mission does not include operations over people.",
                citations=citations,
            )
        if context.has_active_credential(credential_kind="waiver", keywords=("people", "107.39")):
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.SATISFIED,
                severity=self.severity,
                observed_facts={"operation_over_people": True},
                required_conditions=[],
                reason="A waiver record appears to cover operations over people.",
                citations=citations,
            )
        return _evaluation(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            applicability=True,
            result=PolicyEvaluationResult.WAIVER_REQUIRED,
            severity=self.severity,
            observed_facts={"operation_over_people": True},
            required_conditions=[
                "Provide a waiver or mission configuration that lawfully supports flight over people."
            ],
            reason="The mission proposes flight over people without a matching waiver record.",
            citations=citations,
        )


@dataclass(slots=True)
class OperationsOverMovingVehiclesRule:
    rule_id: str = "operations_over_moving_vehicles"
    rule_name: str = "Operations over moving vehicles"
    severity: PolicyRuleSeverity = PolicyRuleSeverity.BLOCKING
    query_tags: tuple[str, ...] = ("vehicles", "waiver")

    def evaluate(self, context: RuleContext, citations: list) -> PolicyEvaluation:
        value = context.mission.operation_over_moving_vehicles
        if value is None:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.UNKNOWN,
                severity=self.severity,
                observed_facts={},
                required_conditions=["Confirm whether the route includes sustained flight over moving vehicles."],
                reason="The mission does not yet specify whether it includes operations over moving vehicles.",
                citations=citations,
            )
        if value is False:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=False,
                result=PolicyEvaluationResult.NOT_APPLICABLE,
                severity=self.severity,
                observed_facts={"operation_over_moving_vehicles": False},
                required_conditions=[],
                reason="The mission does not include operations over moving vehicles.",
                citations=citations,
            )
        if context.has_active_credential(credential_kind="waiver", keywords=("vehicle", "107.145")):
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.SATISFIED,
                severity=self.severity,
                observed_facts={"operation_over_moving_vehicles": True},
                required_conditions=[],
                reason="A waiver record appears to address operations over moving vehicles.",
                citations=citations,
            )
        return _evaluation(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            applicability=True,
            result=PolicyEvaluationResult.WAIVER_REQUIRED,
            severity=self.severity,
            observed_facts={"operation_over_moving_vehicles": True},
            required_conditions=[
                "Provide a waiver or mission design that avoids sustained flight over moving vehicles."
            ],
            reason="The mission proposes flight over moving vehicles without a matching waiver record.",
            citations=citations,
        )


@dataclass(slots=True)
class RemoteIdRule:
    rule_id: str = "remote_id"
    rule_name: str = "Remote ID availability"
    severity: PolicyRuleSeverity = PolicyRuleSeverity.REVIEW
    query_tags: tuple[str, ...] = ("remote_id",)

    def evaluate(self, context: RuleContext, citations: list) -> PolicyEvaluation:
        if context.drone is None:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.UNKNOWN,
                severity=self.severity,
                observed_facts={},
                required_conditions=["Select a drone profile with Remote ID information."],
                reason="No drone profile is available to verify Remote ID details.",
                citations=citations,
            )
        if context.drone.remote_id_serial_number or context.drone.remote_id_type:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.SATISFIED,
                severity=self.severity,
                observed_facts={"remote_id_type": context.drone.remote_id_type},
                required_conditions=[],
                reason="The selected drone profile records Remote ID information.",
                citations=citations,
            )
        return _evaluation(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            applicability=True,
            result=PolicyEvaluationResult.UNKNOWN,
            severity=self.severity,
            observed_facts={"remote_id_type": context.drone.remote_id_type},
            required_conditions=["Add verified Remote ID information to the drone profile."],
            reason="Remote ID details are missing from the selected drone profile.",
            citations=citations,
        )


@dataclass(slots=True)
class VisualLineOfSightRule:
    rule_id: str = "visual_line_of_sight"
    rule_name: str = "Visual line of sight"
    severity: PolicyRuleSeverity = PolicyRuleSeverity.BLOCKING
    query_tags: tuple[str, ...] = ("vlos", "waiver")

    def evaluate(self, context: RuleContext, citations: list) -> PolicyEvaluation:
        value = context.mission.visual_line_of_sight
        if value is None:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.UNKNOWN,
                severity=self.severity,
                observed_facts={},
                required_conditions=["Confirm whether the aircraft will remain within visual line of sight."],
                reason="Visual line-of-sight status is not yet known.",
                citations=citations,
            )
        if value is True:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.SATISFIED,
                severity=self.severity,
                observed_facts={"visual_line_of_sight": True},
                required_conditions=[],
                reason="The mission states the aircraft will remain within visual line of sight.",
                citations=citations,
            )
        if context.has_active_credential(credential_kind="waiver", keywords=("bvlos", "vlos", "107.31")):
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.SATISFIED,
                severity=self.severity,
                observed_facts={"visual_line_of_sight": False},
                required_conditions=[],
                reason="A waiver record appears to address the mission's visual line-of-sight exception.",
                citations=citations,
            )
        return _evaluation(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            applicability=True,
            result=PolicyEvaluationResult.WAIVER_REQUIRED,
            severity=self.severity,
            observed_facts={"visual_line_of_sight": False},
            required_conditions=["Provide a waiver if the aircraft will operate beyond visual line of sight."],
            reason="The mission indicates the aircraft will not remain within visual line of sight.",
            citations=citations,
        )


@dataclass(slots=True)
class WaiverRequirementRule:
    rule_id: str = "waiver_requirements"
    rule_name: str = "Additional waiver requirements"
    severity: PolicyRuleSeverity = PolicyRuleSeverity.BLOCKING
    query_tags: tuple[str, ...] = ("waiver", "exception")

    def evaluate(self, context: RuleContext, citations: list) -> PolicyEvaluation:
        triggered_conditions: list[str] = []
        if context.mission.operation_over_people is True:
            triggered_conditions.append("operations over people")
        if context.mission.operation_over_moving_vehicles is True:
            triggered_conditions.append("operations over moving vehicles")
        if context.mission.visual_line_of_sight is False:
            triggered_conditions.append("operations beyond visual line of sight")

        if not triggered_conditions:
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=False,
                result=PolicyEvaluationResult.NOT_APPLICABLE,
                severity=self.severity,
                observed_facts={},
                required_conditions=[],
                reason="No waiver-triggering mission conditions were identified.",
                citations=citations,
            )
        if context.has_active_credential(credential_kind="waiver"):
            return _evaluation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                applicability=True,
                result=PolicyEvaluationResult.SATISFIED,
                severity=self.severity,
                observed_facts={"triggered_conditions": triggered_conditions},
                required_conditions=[],
                reason="The profile contains at least one active waiver record for a waiver-triggering mission condition.",
                citations=citations,
            )
        return _evaluation(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            applicability=True,
            result=PolicyEvaluationResult.WAIVER_REQUIRED,
            severity=self.severity,
            observed_facts={"triggered_conditions": triggered_conditions},
            required_conditions=[
                "Provide the applicable FAA waiver before proceeding with the triggered mission condition."
            ],
            reason=f"The mission triggers waiver review for {', '.join(triggered_conditions)}.",
            citations=citations,
        )


def build_default_rules() -> list[PolicyRule]:
    return [
        MaximumAltitudeRule(),
        PilotCertificationRule(),
        NightOperationsRule(),
        AntiCollisionLightingRule(),
        ControlledAirspaceRule(),
        AuthorizationValidityRule(),
        OperationsOverPeopleRule(),
        OperationsOverMovingVehiclesRule(),
        RemoteIdRule(),
        VisualLineOfSightRule(),
        WaiverRequirementRule(),
    ]
