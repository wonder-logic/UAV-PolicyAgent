from __future__ import annotations

from datetime import date

from policy_agent.db.models import ProfileCredential, UserPolicyProfile


def is_credential_expired(credential: ProfileCredential, *, on_date: date | None = None) -> bool:
    if credential.expiration_date is None:
        return False
    comparison_date = on_date or date.today()
    return credential.expiration_date < comparison_date


def profile_is_certificate_current(profile: UserPolicyProfile, *, on_date: date | None = None) -> bool:
    if profile.remote_pilot_certificate_expiration is None:
        return False
    comparison_date = on_date or date.today()
    return profile.remote_pilot_certificate_expiration >= comparison_date
