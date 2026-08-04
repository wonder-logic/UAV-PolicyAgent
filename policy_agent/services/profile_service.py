from __future__ import annotations

from sqlalchemy.orm import Session

from policy_agent.core.exceptions import ConflictError, NotFoundError
from policy_agent.db.models import UserAccount
from policy_agent.repositories import ProfileRepository
from policy_agent.schemas.profile import (
    CredentialRecordCreate,
    CredentialRecordRead,
    CredentialRecordUpdate,
    UserPolicyProfileCreate,
    UserPolicyProfileRead,
    UserPolicyProfileUpdate,
)
from policy_agent.services.mappers import credential_to_schema, profile_to_schema


class ProfileService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = ProfileRepository(session)

    def create_profile(self, user: UserAccount, payload: UserPolicyProfileCreate) -> UserPolicyProfileRead:
        if self.repository.get_profile(user.id) is not None:
            raise ConflictError("A policy profile already exists for this account.")

        profile = self.repository.create_profile(user_id=user.id, **payload.model_dump())
        self.session.commit()
        return profile_to_schema(profile)

    def get_profile(self, user: UserAccount) -> UserPolicyProfileRead:
        profile = self.repository.get_profile(user.id)
        if profile is None:
            raise NotFoundError("Create your policy profile to continue.")
        return profile_to_schema(profile)

    def update_profile(self, user: UserAccount, payload: UserPolicyProfileUpdate) -> UserPolicyProfileRead:
        profile = self.repository.get_profile(user.id)
        if profile is None:
            raise NotFoundError("Create your policy profile before editing it.")

        updated = self.repository.update_profile(profile, **payload.model_dump(exclude_none=True))
        self.session.commit()
        return profile_to_schema(updated)

    def create_credential(self, user: UserAccount, payload: CredentialRecordCreate) -> CredentialRecordRead:
        profile = self.repository.get_profile(user.id)
        if profile is None:
            raise NotFoundError("Create your policy profile before adding credentials.")

        credential = self.repository.create_credential(
            user_id=user.id,
            profile_id=profile.id,
            **payload.model_dump(),
        )
        self.session.commit()
        return credential_to_schema(credential)

    def update_credential(
        self,
        user: UserAccount,
        credential_id: str,
        payload: CredentialRecordUpdate,
    ) -> CredentialRecordRead:
        credential = self.repository.get_credential(user.id, credential_id)
        if credential is None:
            raise NotFoundError("Credential record not found.")

        updated = self.repository.update_credential(credential, **payload.model_dump(exclude_none=True))
        self.session.commit()
        return credential_to_schema(updated)

    def delete_credential(self, user: UserAccount, credential_id: str) -> None:
        credential = self.repository.get_credential(user.id, credential_id)
        if credential is None:
            raise NotFoundError("Credential record not found.")

        self.repository.delete_credential(credential)
        self.session.commit()
