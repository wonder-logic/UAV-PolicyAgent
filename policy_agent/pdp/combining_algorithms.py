from __future__ import annotations

from collections.abc import Sequence


def deny_overrides(
    policy_decisions: Sequence[str],
    missing_attributes: Sequence[str],
    relevant_policy_count: int,
) -> str:
    if any(decision == "DENY" for decision in policy_decisions):
        return "DENY"
    if any(decision == "PERMIT" for decision in policy_decisions) and not missing_attributes:
        return "PERMIT"
    if relevant_policy_count > 0:
        return "INDETERMINATE"
    return "NOT_APPLICABLE"


def permit_overrides(*args, **kwargs):
    raise NotImplementedError


def first_applicable(*args, **kwargs):
    raise NotImplementedError
