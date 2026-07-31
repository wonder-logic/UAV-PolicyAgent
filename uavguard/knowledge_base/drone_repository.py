"""Repository layer for stored drone specifications."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from contextlib import closing

from ..api.schemas import DroneProfile, DroneSearchMatch
from ..config.settings import Settings, get_settings
from .cache import LocalLookupCache
from .db import get_connection, initialize_database
from .fuzzy_matcher import normalize_text, score_candidates


@dataclass(slots=True)
class DroneLookupResult:
    profile: DroneProfile
    match_type: str
    warnings: list[str]


class DroneRepository:
    """SQLite-backed repository with exact and fuzzy model lookup."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        initialize_database(self.settings.database_path)
        self._cache: LocalLookupCache[str, DroneProfile] = LocalLookupCache()

    @staticmethod
    def _cache_key(manufacturer: str, model: str) -> str:
        return f"{normalize_text(manufacturer)}::{normalize_text(model)}"

    @staticmethod
    def _row_to_profile(
        row: sqlite3.Row,
        match_type: str = "exact",
        confidence: float = 100.0,
    ) -> DroneProfile:
        return DroneProfile(
            manufacturer=row["manufacturer"],
            model=row["model"],
            weight_grams=row["weight_grams"],
            max_flight_time_minutes=row["max_flight_time_minutes"],
            max_range_meters=row["max_range_meters"],
            max_speed_mps=row["max_speed_mps"],
            source=row["source"] or "unknown",
            match_type=match_type,
            confidence=confidence,
        )

    def _fetch_all_rows(self) -> list[sqlite3.Row]:
        with closing(get_connection(self.settings.database_path)) as connection:
            return connection.execute(
                """
                SELECT manufacturer, model, weight_grams, max_flight_time_minutes,
                       max_range_meters, max_speed_mps, source
                FROM drones
                """
            ).fetchall()

    def exact_lookup(self, manufacturer: str, model: str) -> DroneProfile | None:
        """Resolve a drone via exact manufacturer/model lookup."""

        cached = self._cache.get(self._cache_key(manufacturer, model))
        if cached is not None:
            return cached

        manufacturer_norm = normalize_text(manufacturer)
        model_norm = normalize_text(model)
        with closing(get_connection(self.settings.database_path)) as connection:
            row = connection.execute(
                """
                SELECT manufacturer, model, weight_grams, max_flight_time_minutes,
                       max_range_meters, max_speed_mps, source
                FROM drones
                WHERE lower(trim(manufacturer)) = ? AND lower(trim(model)) = ?
                LIMIT 1
                """,
                (manufacturer_norm, model_norm),
            ).fetchone()
            if row is None:
                row = connection.execute(
                    """
                    SELECT manufacturer, model, weight_grams, max_flight_time_minutes,
                           max_range_meters, max_speed_mps, source
                    FROM drones
                    WHERE lower(trim(model)) = ?
                    LIMIT 1
                    """,
                    (model_norm,),
                ).fetchone()
        if row is None:
            return None

        match_type = "exact" if normalize_text(row["manufacturer"]) == manufacturer_norm else "model_exact"
        profile = self._row_to_profile(row, match_type=match_type, confidence=100.0)
        self._cache.set(self._cache_key(manufacturer, model), profile)
        return profile

    def fuzzy_lookup(self, manufacturer: str, model: str) -> DroneProfile | None:
        """Resolve the closest drone profile using fuzzy search."""

        rows = self._fetch_all_rows()
        if not rows:
            return None
        query = f"{manufacturer} {model}".strip()
        candidate_map = {
            f"{row['manufacturer']} {row['model']}": row
            for row in rows
        }
        best_matches = score_candidates(query, candidate_map.keys(), limit=5)
        if not best_matches:
            return None
        best_name, best_score = best_matches[0]
        if best_score < 60:
            return None
        match_type = "fuzzy" if best_score >= 85 else "fuzzy_low_confidence"
        profile = self._row_to_profile(
            candidate_map[best_name],
            match_type=match_type,
            confidence=best_score,
        )
        if best_score < 85:
            profile.warnings.append(
                "Drone match confidence is low; review the selected model manually."
            )
        self._cache.set(self._cache_key(manufacturer, model), profile)
        return profile

    def lookup(self, manufacturer: str, model: str) -> DroneLookupResult:
        """Try exact lookup first, then fuzzy fallback."""

        warnings: list[str] = []
        exact = self.exact_lookup(manufacturer, model)
        if exact is not None:
            if exact.match_type != "exact":
                warnings.append(
                    "Manufacturer did not match exactly; using the best exact model match."
                )
            return DroneLookupResult(
                profile=exact,
                match_type=exact.match_type,
                warnings=warnings + exact.warnings,
            )

        fuzzy = self.fuzzy_lookup(manufacturer, model)
        if fuzzy is not None:
            warnings.append("Exact drone lookup failed; fuzzy match fallback was used.")
            return DroneLookupResult(
                profile=fuzzy,
                match_type=fuzzy.match_type,
                warnings=warnings + fuzzy.warnings,
            )

        unresolved = DroneProfile(
            manufacturer=manufacturer,
            model=model,
            source="unresolved",
            match_type="unresolved",
            confidence=0.0,
            warnings=["No drone profile was found in the local repository."],
        )
        return DroneLookupResult(
            profile=unresolved,
            match_type="unresolved",
            warnings=list(unresolved.warnings),
        )

    def search(self, query: str, manufacturer: str | None = None, limit: int = 5) -> list[DroneSearchMatch]:
        """Return fuzzy search results for the API."""

        rows = self._fetch_all_rows()
        if manufacturer:
            manufacturer_norm = normalize_text(manufacturer)
            rows = [
                row
                for row in rows
                if normalize_text(row["manufacturer"]) == manufacturer_norm
            ]
        candidate_map = {
            f"{row['manufacturer']} {row['model']}": row
            for row in rows
        }
        matches = score_candidates(query, candidate_map.keys(), limit=limit)
        return [
            DroneSearchMatch(
                manufacturer=candidate_map[name]["manufacturer"],
                model=candidate_map[name]["model"],
                score=score,
                source=candidate_map[name]["source"] or "unknown",
            )
            for name, score in matches
        ]
