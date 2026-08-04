from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from policy_agent.db.models import ProfileCredential, UserPolicyProfile


class ProfileRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_profile(self, user_id: str) -> UserPolicyProfile | None:
        statement = (
            select(UserPolicyProfile)
            .options(selectinload(UserPolicyProfile.credentials))
            .where(UserPolicyProfile.user_id == user_id)
        )
        return self.session.scalar(statement)

    def create_profile(self, **payload) -> UserPolicyProfile:
        profile = UserPolicyProfile(**payload)
        self.session.add(profile)
        self.session.flush()
        return profile

    def update_profile(self, profile: UserPolicyProfile, **payload) -> UserPolicyProfile:
        for key, value in payload.items():
            setattr(profile, key, value)
        self.session.add(profile)
        self.session.flush()
        return profile

    def create_credential(self, **payload) -> ProfileCredential:
        credential = ProfileCredential(**payload)
        self.session.add(credential)
        self.session.flush()
        return credential

    def get_credential(self, user_id: str, credential_id: str) -> ProfileCredential | None:
        statement = select(ProfileCredential).where(
            ProfileCredential.user_id == user_id,
            ProfileCredential.id == credential_id,
        )
        return self.session.scalar(statement)

    def update_credential(self, credential: ProfileCredential, **payload) -> ProfileCredential:
        for key, value in payload.items():
            setattr(credential, key, value)
        self.session.add(credential)
        self.session.flush()
        return credential

    def delete_credential(self, credential: ProfileCredential) -> None:
        self.session.delete(credential)
        self.session.flush()
