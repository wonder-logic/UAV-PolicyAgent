from __future__ import annotations

from policy_agent.api.routes import create_app
from policy_agent.config import get_settings
from policy_agent.utils.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
app = create_app(settings)
