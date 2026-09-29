from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from policy_agent.db.models import AuthSession, UserAccount
from policy_agent.utils.datetime_utils import utcnow


class AuthRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_user_by_email(self, email: str) -> UserAccount | None:
        return self.session.scalar(select(UserAccount).where(UserAccount.email == email.lower()))

    def get_user_by_id(self, user_id: str) -> UserAccount | None:
        return self.session.get(UserAccount, user_id)

    def create_user(
        self,
        *,
        full_name: str,
        email: str,
        password_hash: str,
        organization: str | None,
    ) -> UserAccount:
        user = UserAccount(
            full_name=full_name,
            email=email.lower(),
            password_hash=password_hash,
            organization=organization,
        )
        self.session.add(user)
        self.session.flush()
        return user

    def create_session(
        self,
        *,
        user_id: str,
        token_hash: str,
        expires_at: datetime,
    ) -> AuthSession:
        auth_session = AuthSession(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(auth_session)
        self.session.flush()
        return auth_session

    def get_session(self, token_hash: str) -> AuthSession | None:
        return self.session.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))

    def touch_session(self, auth_session: AuthSession) -> AuthSession:
        auth_session.last_used_at = utcnow()
        self.session.add(auth_session)
        self.session.flush()
        return auth_session
