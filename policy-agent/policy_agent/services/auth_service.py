from __future__ import annotations

from sqlalchemy.orm import Session

from policy_agent.config import Settings
from policy_agent.core.exceptions import ConflictError, ForbiddenError
from policy_agent.core.security import (
    build_session_expiry,
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from policy_agent.repositories import AuthRepository
from policy_agent.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from policy_agent.services.mappers import user_to_schema
from policy_agent.utils.datetime_utils import utcnow


class AuthService:
    def __init__(self, session: Session, settings: Settings):
        self.session = session
        self.settings = settings
        self.repository = AuthRepository(session)

    def register(self, payload: RegisterRequest) -> AuthResponse:
        if len(payload.password) < self.settings.auth_password_min_length:
            raise ForbiddenError(
                f"Passwords must be at least {self.settings.auth_password_min_length} characters long."
            )

        existing = self.repository.get_user_by_email(payload.email)
        if existing is not None:
            raise ConflictError("An account with that email already exists.")

        user = self.repository.create_user(
            full_name=payload.full_name.strip(),
            email=payload.email,
            password_hash=hash_password(payload.password),
            organization=payload.organization.strip() if payload.organization else None,
        )
        token = generate_session_token()
        auth_session = self.repository.create_session(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=build_session_expiry(self.settings.auth_token_ttl_hours),
        )
        self.session.commit()
        return AuthResponse(
            access_token=token,
            expires_at=auth_session.expires_at,
            user=user_to_schema(user),
        )

    def login(self, payload: LoginRequest) -> AuthResponse:
        user = self.repository.get_user_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.password_hash):
            raise ForbiddenError("Invalid email or password.")

        token = generate_session_token()
        auth_session = self.repository.create_session(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=build_session_expiry(self.settings.auth_token_ttl_hours),
        )
        self.session.commit()
        return AuthResponse(
            access_token=token,
            expires_at=auth_session.expires_at,
            user=user_to_schema(user),
        )

    def authenticate_token(self, token: str):
        auth_session = self.repository.get_session(hash_session_token(token))
        if auth_session is None:
            raise ForbiddenError("Your session is invalid. Please sign in again.")
        if auth_session.expires_at <= utcnow():
            raise ForbiddenError("Your session has expired. Please sign in again.")

        self.repository.touch_session(auth_session)
        self.session.commit()
        return auth_session.user
