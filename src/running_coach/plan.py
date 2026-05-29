from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from running_coach.csv_utils import decode_json_cell
from running_coach.models import Phase, PlannedWorkoutStatus


REQUIRED_PLANNED_WORKOUT_HEADERS = [
    "planned_workout_id",
    "week_number",
    "date",
    "phase",
    "slot",
    "intended_category",
    "purpose",
    "primary_athlete",
    "planned_distance_or_duration",
    "planned_intensity_range",
    "allowed_fallbacks",
    "contraindications",
    "status",
]


class PlanLoadError(ValueError):
    def __init__(
        self,
        path: Path,
        row_number: int,
        field: str,
        value: Any,
        reason: str,
    ) -> None:
        self.path = path
        self.row_number = row_number
        self.field = field
        self.value = value
        self.reason = reason
        super().__init__(
            f"{path}: row {row_number}: field {field!r} value {value!r}: {reason}"
        )


class PlannedWorkout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planned_workout_id: str = Field(min_length=1)
    week_number: int
    date: date
    phase: Phase
    slot: str = Field(min_length=1)
    intended_category: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    primary_athlete: Literal["matheus", "bruna"]
    planned_distance_or_duration: str = Field(min_length=1)
    planned_intensity_range: str = Field(min_length=1)
    allowed_fallbacks: list[str]
    contraindications: list[str]
    status: PlannedWorkoutStatus

    @field_validator("allowed_fallbacks", "contraindications")
    @classmethod
    def list_values_must_be_strings(cls, value: list[str]) -> list[str]:
        if not all(isinstance(item, str) for item in value):
            raise ValueError("must be a JSON list of strings")
        return value


class Cycle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    timezone: Literal["America/Sao_Paulo"]
    current_phase: Phase
    current_week_number: int
    target: dict[str, Any]
    weekly_baseline: dict[str, str]


class WorkoutTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: str = Field(min_length=1)
    allowed_intensity_range: str = Field(min_length=1)
    contraindications: list[str]
    science_tags: list[str]


def _decode_string_list_cell(
    path: Path, row_number: int, field: str, value: str | None
) -> list[str]:
    try:
        decoded = decode_json_cell(value)
    except ValueError as error:
        raise PlanLoadError(path, row_number, field, value, str(error)) from error
    if not all(isinstance(item, str) for item in decoded):
        raise PlanLoadError(
            path, row_number, field, value, "must be a JSON list of strings"
        )
    return decoded


def load_workout_template_keys(path: Path) -> set[str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    templates = data["templates"]
    return set(templates)


def load_planned_workouts(
    path: Path, allowed_categories: set[str] | None = None
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        for header in REQUIRED_PLANNED_WORKOUT_HEADERS:
            if header not in fieldnames:
                raise PlanLoadError(path, 1, header, None, "missing required header")

        for row_number, row in enumerate(reader, start=2):
            parsed = dict(row)
            try:
                parsed["week_number"] = int(row["week_number"])
            except ValueError as error:
                raise PlanLoadError(
                    path,
                    row_number,
                    "week_number",
                    row["week_number"],
                    "must be an integer",
                ) from error

            parsed["allowed_fallbacks"] = _decode_string_list_cell(
                path, row_number, "allowed_fallbacks", row["allowed_fallbacks"]
            )
            parsed["contraindications"] = _decode_string_list_cell(
                path, row_number, "contraindications", row["contraindications"]
            )

            try:
                workout = PlannedWorkout.model_validate(parsed)
            except ValidationError as error:
                first_error = error.errors()[0]
                field = str(first_error["loc"][0])
                raise PlanLoadError(
                    path,
                    row_number,
                    field,
                    parsed.get(field),
                    first_error["msg"],
                ) from error
            if (
                allowed_categories is not None
                and workout.intended_category not in allowed_categories
            ):
                raise PlanLoadError(
                    path,
                    row_number,
                    "intended_category",
                    workout.intended_category,
                    "unknown intended category",
                )
            rows.append(workout.model_dump(mode="json"))
    return rows
