"""Application settings for UAVGuard."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path


@dataclass(slots=True)
class Settings:
    """Simple environment-driven settings container."""

    project_name: str
    base_dir: Path
    data_dir: Path
    raw_data_dir: Path
    processed_data_dir: Path
    faa_docs_dir: Path
    sample_requests_dir: Path
    database_path: Path
    chroma_path: Path
    policy_collection: str
    open_meteo_url: str
    weather_timeout_seconds: float
    grid_cell_size_meters: int
    grid_target_span_cells: int
    weather_fallback_temperature_c: float
    weather_fallback_wind_speed_mps: float
    geocoder_user_agent: str

    @classmethod
    def from_env(cls) -> "Settings":
        base_dir = Path(__file__).resolve().parents[2]
        data_dir = base_dir / "data"
        processed_dir = data_dir / "processed"
        return cls(
            project_name="UAVGuard",
            base_dir=base_dir,
            data_dir=data_dir,
            raw_data_dir=data_dir / "raw",
            processed_data_dir=processed_dir,
            faa_docs_dir=data_dir / "faa_docs",
            sample_requests_dir=data_dir / "sample_requests",
            database_path=Path(
                os.getenv(
                    "UAVGUARD_DATABASE_PATH",
                    str(processed_dir / "uavguard.sqlite3"),
                )
            ),
            chroma_path=Path(
                os.getenv(
                    "UAVGUARD_CHROMA_PATH",
                    str(processed_dir / "chroma"),
                )
            ),
            policy_collection=os.getenv(
                "UAVGUARD_POLICY_COLLECTION",
                "faa_policy_chunks",
            ),
            open_meteo_url=os.getenv(
                "UAVGUARD_OPEN_METEO_URL",
                "https://api.open-meteo.com/v1/forecast",
            ),
            weather_timeout_seconds=float(
                os.getenv("UAVGUARD_WEATHER_TIMEOUT_SECONDS", "8")
            ),
            grid_cell_size_meters=int(
                os.getenv("UAVGUARD_GRID_CELL_SIZE_METERS", "20")
            ),
            grid_target_span_cells=int(
                os.getenv("UAVGUARD_GRID_TARGET_SPAN_CELLS", "14")
            ),
            weather_fallback_temperature_c=float(
                os.getenv("UAVGUARD_WEATHER_FALLBACK_TEMPERATURE_C", "20")
            ),
            weather_fallback_wind_speed_mps=float(
                os.getenv("UAVGUARD_WEATHER_FALLBACK_WIND_SPEED_MPS", "5")
            ),
            geocoder_user_agent=os.getenv(
                "UAVGUARD_GEOCODER_USER_AGENT",
                "uavguard-research-prototype",
            ),
        )

    def ensure_directories(self) -> None:
        """Create the data directories used by the app."""

        for path in (
            self.data_dir,
            self.raw_data_dir,
            self.processed_data_dir,
            self.faa_docs_dir,
            self.sample_requests_dir,
            self.chroma_path,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""

    settings = Settings.from_env()
    settings.ensure_directories()
    return settings
