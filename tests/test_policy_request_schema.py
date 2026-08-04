from __future__ import annotations

import pytest
from pydantic import ValidationError

from policy_agent.api.schemas import PolicyRequest


def test_policy_request_accepts_valid_payload():
    request = PolicyRequest(operation_type="research", altitude_ft=350, night_operation=True)
    assert request.operation_type == "research"
    assert request.altitude_ft == 350


def test_policy_request_rejects_invalid_operation_type():
    with pytest.raises(ValidationError):
        PolicyRequest(operation_type="delivery")
