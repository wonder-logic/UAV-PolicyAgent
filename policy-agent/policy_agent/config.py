from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse


def _env(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value != "":
            return value
    return default


def _env_float(*names: str, default: float) -> float:
    value = _env(*names)
    return float(value) if value is not None else default


def _env_int(*names: str, default: int) -> int:
    value = _env(*names)
    return int(value) if value is not None else default


def _env_list(*names: str) -> tuple[str, ...]:
    value = _env(*names)
    if value is None:
        return tuple()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _env_path(*names: str, default: str) -> Path:
    value = _env(*names, default=default)
    assert value is not None
    return Path(value).resolve()


def _load_project_dotenv(project_root: Path) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - optional at runtime
        return
    load_dotenv(project_root / ".env", override=False)


@dataclass(slots=True)
class Settings:
    project_root: Path
    data_dir: Path
    policy_docs_dir: Path
    drone_catalog_dir: Path
    processed_dir: Path
    sample_requests_dir: Path
    sample_policies_dir: Path
    drone_catalog_path: Path
    policy_chunks_path: Path
    vector_store_path: Path
    chroma_dir: Path
    uploads_dir: Path
    temp_dir: Path
    database_url: str
    app_env: str
    auth_token_ttl_hours: int
    auth_password_min_length: int
    knowledge_agent_mode: str
    knowledge_agent_base_url: str | None
    knowledge_agent_timeout_seconds: float
    knowledge_agent_max_retries: int
    simulator_base_url: str | None
    policy_store_path: Path
    policy_version: str
    cors_origins: tuple[str, ...]
    project_name: str = "UAVGuard Policy Agent"
    service_name: str = "uavguard-policy-agent"
    vector_backend: str = "json"
    retrieval_top_k: int = 5
    llm_provider: str = "mock"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 1
    log_level: str = "INFO"

    def ensure_directories(self) -> None:
        for path in (
            self.data_dir,
            self.policy_docs_dir,
            self.drone_catalog_dir,
            self.processed_dir,
            self.sample_requests_dir,
            self.sample_policies_dir,
            self.chroma_dir,
            self.uploads_dir,
            self.temp_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    @property
    def sqlite_path(self) -> Path | None:
        parsed = urlparse(self.database_url)
        if parsed.scheme != "sqlite":
            return None

        if parsed.path in {"", ":memory:"}:
            return None

        if self.database_url.startswith("sqlite:///"):
            raw_path = self.database_url.removeprefix("sqlite:///")
            return Path(raw_path).resolve()
        return None

    @property
    def alembic_database_url(self) -> str:
        return self.database_url

    def validate_startup(self) -> None:
        if self.knowledge_agent_mode == "remote" and not self.knowledge_agent_base_url:
            raise ValueError("KNOWLEDGE_AGENT_BASE_URL must be set when KNOWLEDGE_AGENT_MODE is 'remote'.")
        if self.llm_provider == "http" and not self.llm_base_url:
            raise ValueError("LLM_BASE_URL must be set when LLM_PROVIDER is 'http'.")


def build_settings(project_root: Path | None = None) -> Settings:
    resolved_root = Path(
        project_root or os.getenv("UAVGUARD_PROJECT_ROOT") or Path(__file__).resolve().parents[1]
    ).resolve()

    _load_project_dotenv(resolved_root)

    data_dir = _env_path("DATA_DIR", "UAVGUARD_DATA_DIR", default=str(resolved_root / "data"))
    processed_dir = _env_path("UAVGUARD_PROCESSED_DIR", default=str(data_dir / "processed"))
    database_path = _env_path("POLICY_AGENT_DB_PATH", default=str(data_dir / "uavguard_policy_agent.sqlite3"))
    default_database_url = f"sqlite:///{database_path.as_posix()}"
    database_url = _env("DATABASE_URL", default=default_database_url) or default_database_url
    uploads_dir = _env_path("UPLOADS_DIR", default=str(data_dir / "uploads"))
    temp_dir = _env_path("TEMP_DIR", default=str(resolved_root / ".tmp"))

    settings = Settings(
        project_root=resolved_root,
        data_dir=data_dir,
        policy_docs_dir=_env_path("UAVGUARD_POLICY_DOCS_DIR", default=str(data_dir / "policy_docs")),
        drone_catalog_dir=_env_path("UAVGUARD_DRONE_CATALOG_DIR", default=str(data_dir / "drone_catalog")),
        processed_dir=processed_dir,
        sample_requests_dir=_env_path("UAVGUARD_SAMPLE_REQUESTS_DIR", default=str(data_dir / "sample_requests")),
        sample_policies_dir=_env_path("UAVGUARD_SAMPLE_POLICIES_DIR", default=str(data_dir / "sample_policies")),
        drone_catalog_path=_env_path(
            "UAVGUARD_DRONE_CATALOG_PATH", default=str(data_dir / "drone_catalog" / "drone_models.json")
        ),
        policy_chunks_path=_env_path("UAVGUARD_POLICY_CHUNKS_PATH", default=str(processed_dir / "policy_chunks.json")),
        vector_store_path=_env_path("UAVGUARD_VECTOR_STORE_PATH", default=str(processed_dir / "vector_store.json")),
        chroma_dir=_env_path("UAVGUARD_CHROMA_DIR", default=str(processed_dir / "chromadb")),
        uploads_dir=uploads_dir,
        temp_dir=temp_dir,
        database_url=database_url,
        app_env=(_env("APP_ENV", default="development") or "development").strip().lower(),
        auth_token_ttl_hours=_env_int("AUTH_TOKEN_TTL_HOURS", default=24),
        auth_password_min_length=_env_int("AUTH_PASSWORD_MIN_LENGTH", default=10),
        knowledge_agent_mode=(_env("KNOWLEDGE_AGENT_MODE", default="mock") or "mock").strip().lower(),
        knowledge_agent_base_url=_env("KNOWLEDGE_AGENT_BASE_URL"),
        knowledge_agent_timeout_seconds=_env_float("KNOWLEDGE_AGENT_TIMEOUT_SECONDS", default=15.0),
        knowledge_agent_max_retries=_env_int("KNOWLEDGE_AGENT_MAX_RETRIES", default=1),
        simulator_base_url=_env("SIMULATOR_BASE_URL"),
        policy_store_path=_env_path("POLICY_STORE_PATH", default=str(processed_dir / "policy_records.json")),
        policy_version=_env("POLICY_VERSION", default="2026.07-part107-baseline") or "2026.07-part107-baseline",
        cors_origins=_env_list("CORS_ORIGINS"),
        vector_backend=(_env("UAVGUARD_VECTOR_BACKEND", default="json") or "json").strip().lower(),
        retrieval_top_k=_env_int("UAVGUARD_TOP_K", default=5),
        llm_provider=(_env("LLM_PROVIDER", default="mock") or "mock").strip().lower(),
        llm_base_url=_env("LLM_BASE_URL", "UAVGUARD_LLM_BASE_URL"),
        llm_api_key=_env("LLM_API_KEY", "UAVGUARD_LLM_API_KEY"),
        llm_model=_env("LLM_MODEL", "UAVGUARD_LLM_MODEL", default="gpt-4o-mini") or "gpt-4o-mini",
        llm_timeout_seconds=_env_float("LLM_TIMEOUT_SECONDS", "UAVGUARD_LLM_TIMEOUT", default=30.0),
        llm_max_retries=_env_int("LLM_MAX_RETRIES", default=1),
        log_level=(_env("LOG_LEVEL", "UAVGUARD_LOG_LEVEL", default="INFO") or "INFO").upper(),
    )
    settings.validate_startup()
    return settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = build_settings()
    settings.ensure_directories()
    return settings
