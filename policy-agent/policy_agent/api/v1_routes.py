from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from policy_agent.api.dependencies import get_current_user, get_db_session, get_settings
from policy_agent.core import NotFoundError
from policy_agent.core.rate_limit import RateLimitPolicy
from policy_agent.integrations import create_knowledge_agent_client, create_llm_provider
from policy_agent.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, SessionUser
from policy_agent.schemas.chat import ConversationMessage, MissionChatRequest, MissionChatResponse
from policy_agent.schemas.drone import DroneProfileCreate, DroneProfileRead, DroneProfileUpdate
from policy_agent.schemas.mission import (
    MissionCreate,
    MissionDecision,
    MissionDetailsRead,
    MissionEvaluationRequest,
    MissionHistoryItem,
    MissionSubmissionStatus,
    MissionUpdateRequest,
    SimulatorPolicyPackage,
)
from policy_agent.schemas.profile import (
    CredentialRecordCreate,
    CredentialRecordRead,
    CredentialRecordUpdate,
    UserPolicyProfileCreate,
    UserPolicyProfileRead,
    UserPolicyProfileUpdate,
)
from policy_agent.services import (
    AuthService,
    ChatService,
    DroneService,
    EvaluationService,
    MissionService,
    ProfileService,
)
from policy_agent.services.mappers import conversation_to_schema, user_to_schema

router = APIRouter(prefix="/api")


def _apply_rate_limit(request: Request, *, key: str, action: str, limit: int, seconds: int) -> None:
    request.app.state.rate_limiter.check(
        key=key,
        action=action,
        policy=RateLimitPolicy(limit=limit, interval_seconds=seconds),
    )


@router.post("/auth/register", response_model=AuthResponse)
def register_account(payload: RegisterRequest, request: Request, session=Depends(get_db_session)) -> AuthResponse:
    service = AuthService(session, request.app.state.settings)
    return service.register(payload)


@router.post("/auth/login", response_model=AuthResponse)
def login_account(payload: LoginRequest, request: Request, session=Depends(get_db_session)) -> AuthResponse:
    service = AuthService(session, request.app.state.settings)
    return service.login(payload)


@router.get("/auth/me", response_model=SessionUser)
def read_current_user(user=Depends(get_current_user)) -> SessionUser:
    return user_to_schema(user)


@router.post("/profiles", response_model=UserPolicyProfileRead)
def create_profile(
    payload: UserPolicyProfileCreate,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> UserPolicyProfileRead:
    return ProfileService(session).create_profile(user, payload)


@router.get("/profiles/me", response_model=UserPolicyProfileRead)
def get_profile(
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> UserPolicyProfileRead:
    return ProfileService(session).get_profile(user)


@router.patch("/profiles/me", response_model=UserPolicyProfileRead)
def patch_profile(
    payload: UserPolicyProfileUpdate,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> UserPolicyProfileRead:
    return ProfileService(session).update_profile(user, payload)


@router.post("/profiles/me/certifications", response_model=CredentialRecordRead)
def create_credential(
    payload: CredentialRecordCreate,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> CredentialRecordRead:
    return ProfileService(session).create_credential(user, payload)


@router.patch("/profiles/me/certifications/{credential_id}", response_model=CredentialRecordRead)
def patch_credential(
    credential_id: str,
    payload: CredentialRecordUpdate,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> CredentialRecordRead:
    return ProfileService(session).update_credential(user, credential_id, payload)


@router.delete("/profiles/me/certifications/{credential_id}", status_code=204, response_class=Response)
def delete_credential(
    credential_id: str,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> Response:
    ProfileService(session).delete_credential(user, credential_id)
    return Response(status_code=204)


@router.post("/drones", response_model=DroneProfileRead)
def create_drone(
    payload: DroneProfileCreate,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> DroneProfileRead:
    return DroneService(session).create_drone(user, payload)


@router.get("/drones", response_model=list[DroneProfileRead])
def list_drones(
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> list[DroneProfileRead]:
    return DroneService(session).list_drones(user)


@router.get("/drones/{drone_id}", response_model=DroneProfileRead)
def get_drone(
    drone_id: str,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> DroneProfileRead:
    return DroneService(session).get_drone(user, drone_id)


@router.patch("/drones/{drone_id}", response_model=DroneProfileRead)
def patch_drone(
    drone_id: str,
    payload: DroneProfileUpdate,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> DroneProfileRead:
    return DroneService(session).update_drone(user, drone_id, payload)


@router.delete("/drones/{drone_id}", status_code=204, response_class=Response)
def delete_drone(
    drone_id: str,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> Response:
    DroneService(session).delete_drone(user, drone_id)
    return Response(status_code=204)


@router.post("/missions", response_model=MissionDetailsRead)
def create_mission(
    payload: MissionCreate,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> MissionDetailsRead:
    return MissionService(session).create_mission(user, payload)


@router.get("/missions", response_model=list[MissionHistoryItem])
def list_missions(
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> list[MissionHistoryItem]:
    return MissionService(session).list_missions(user)


@router.get("/missions/{mission_id}", response_model=MissionDetailsRead)
def get_mission(
    mission_id: str,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> MissionDetailsRead:
    return MissionService(session).get_mission(user, mission_id)


@router.patch("/missions/{mission_id}", response_model=MissionDetailsRead)
def patch_mission(
    mission_id: str,
    payload: MissionUpdateRequest,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> MissionDetailsRead:
    return MissionService(session).update_mission(user, mission_id, payload)


@router.post("/missions/{mission_id}/submit", response_model=MissionSubmissionStatus)
def submit_mission(
    mission_id: str,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> MissionSubmissionStatus:
    service = MissionService(session)
    mission = service.submit_mission(user, mission_id)
    readiness = service.evaluate_readiness(user, mission_id)
    return MissionSubmissionStatus(
        mission=mission,
        missing_fields=readiness.missing_fields,
        ready_for_evaluation=readiness.ready_for_evaluation,
    )


@router.post("/missions/{mission_id}/evaluate", response_model=MissionDecision)
def evaluate_mission(
    mission_id: str,
    payload: MissionEvaluationRequest,
    request: Request,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> MissionDecision:
    _apply_rate_limit(request, key=user.id, action="mission_evaluate", limit=10, seconds=60)
    settings = get_settings(request)
    service = EvaluationService(
        session,
        settings,
        create_knowledge_agent_client(settings),
        create_llm_provider(settings),
    )
    decision, _ = service.evaluate(user=user, mission_id=mission_id, payload=payload)
    return decision


@router.get("/missions/{mission_id}/decision", response_model=MissionDecision)
def get_mission_decision(
    mission_id: str,
    request: Request,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> MissionDecision:
    settings = get_settings(request)
    service = EvaluationService(
        session,
        settings,
        create_knowledge_agent_client(settings),
        create_llm_provider(settings),
    )
    return service.get_latest_decision(user=user, mission_id=mission_id)


@router.get("/missions/{mission_id}/simulator-package", response_model=SimulatorPolicyPackage)
def get_simulator_package(
    mission_id: str,
    request: Request,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> SimulatorPolicyPackage:
    settings = get_settings(request)
    service = EvaluationService(
        session,
        settings,
        create_knowledge_agent_client(settings),
        create_llm_provider(settings),
    )
    return service.get_latest_simulator_package(user=user, mission_id=mission_id)


@router.post("/missions/{mission_id}/chat", response_model=MissionChatResponse)
def chat_about_mission(
    mission_id: str,
    payload: MissionChatRequest,
    request: Request,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> MissionChatResponse:
    _apply_rate_limit(request, key=user.id, action="mission_chat", limit=30, seconds=60)
    settings = get_settings(request)
    evaluation_service = EvaluationService(
        session,
        settings,
        create_knowledge_agent_client(settings),
        create_llm_provider(settings),
    )
    decision_preview = None
    try:
        decision_preview = evaluation_service.get_latest_decision(user=user, mission_id=mission_id)
    except NotFoundError:
        decision_preview = None
    return ChatService(session, create_llm_provider(settings)).chat(
        user=user,
        mission_id=mission_id,
        message=payload.message,
        decision_preview=decision_preview,
    )


@router.get("/missions/{mission_id}/conversation", response_model=list[ConversationMessage])
def get_mission_conversation(
    mission_id: str,
    user=Depends(get_current_user),
    session=Depends(get_db_session),
) -> list[ConversationMessage]:
    mission = MissionService(session).get_mission_record(user, mission_id)
    return [conversation_to_schema(item) for item in mission.conversations]
