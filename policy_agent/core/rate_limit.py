from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from policy_agent.core.exceptions import ForbiddenError
from policy_agent.utils.datetime_utils import utcnow


@dataclass(slots=True)
class RateLimitPolicy:
    limit: int
    interval_seconds: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[datetime]] = defaultdict(deque)

    def check(self, *, key: str, action: str, policy: RateLimitPolicy) -> None:
        now = utcnow()
        window_start = now - timedelta(seconds=policy.interval_seconds)
        bucket = self._events[(key, action)]

        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= policy.limit:
            raise ForbiddenError(f"Too many {action.replace('_', ' ')} requests. Please wait a moment and try again.")

        bucket.append(now)
