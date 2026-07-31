"""Shared test helpers for UAVGuard."""

from __future__ import annotations

from pathlib import Path

from uavguard.config.settings import Settings


def build_test_settings(base_dir: Path) -> Settings:
    data_dir = base_dir / "data"
    processed_dir = data_dir / "processed"
    settings = Settings(
        project_name="UAVGuard Test",
        base_dir=base_dir,
        data_dir=data_dir,
        raw_data_dir=data_dir / "raw",
        processed_data_dir=processed_dir,
        faa_docs_dir=data_dir / "faa_docs",
        sample_requests_dir=data_dir / "sample_requests",
        database_path=processed_dir / "uavguard.sqlite3",
        chroma_path=processed_dir / "chroma",
        policy_collection="test_policy_chunks",
        open_meteo_url="https://api.open-meteo.com/v1/forecast",
        weather_timeout_seconds=1.0,
        grid_cell_size_meters=20,
        grid_target_span_cells=14,
        weather_fallback_temperature_c=20.0,
        weather_fallback_wind_speed_mps=5.0,
        geocoder_user_agent="uavguard-test",
    )
    settings.ensure_directories()
    return settings
