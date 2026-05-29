from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from running_coach.models import SourceType


class ScienceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    science_ref_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    authors: list[str] = Field(min_length=1)
    year: int = Field(ge=1800, le=2100)
    source_type: SourceType
    journal_or_publisher: str = Field(min_length=1)
    doi_or_url: str = Field(min_length=1)
    population: str = Field(min_length=1)
    finding: str = Field(min_length=1)
    practical_application: str = Field(min_length=1)
    limits: str = Field(min_length=1)
    tags: list[str] = Field(min_length=1)
    approved: bool
    approved_date: date | None = None
    notes: str = ""

    @field_validator("doi_or_url")
    @classmethod
    def doi_or_url_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("doi_or_url must be non-empty")
        return value

    @field_validator("tags")
    @classmethod
    def tags_must_not_be_blank(cls, value: list[str]) -> list[str]:
        normalized = [tag.strip() for tag in value]
        if any(not tag for tag in normalized):
            raise ValueError("tags must not contain blank values")
        if len(set(normalized)) != len(normalized):
            raise ValueError("tags must be unique")
        return normalized

    @model_validator(mode="after")
    def approved_refs_require_approval_date(self) -> ScienceRef:
        if self.approved and self.approved_date is None:
            raise ValueError("approved source requires approved_date")
        return self


def load_science_refs(path: Path) -> dict[str, ScienceRef]:
    with path.open(encoding="utf-8") as handle:
        raw_data = yaml.safe_load(handle) or {}

    raw_refs = raw_data.get("refs")
    if not isinstance(raw_refs, list):
        raise ValueError("science registry must contain top-level refs list")

    refs: dict[str, ScienceRef] = {}
    for raw_ref in raw_refs:
        ref = ScienceRef(**raw_ref)
        if ref.science_ref_id in refs:
            raise ValueError(f"duplicate science_ref_id: {ref.science_ref_id}")
        refs[ref.science_ref_id] = ref
    return refs


def validate_science_tags(
    refs: dict[str, ScienceRef],
    science_ref_ids: list[str],
    required_tags: set[str],
) -> None:
    if not required_tags:
        raise ValueError("required_tags must be non-empty")

    for science_ref_id in science_ref_ids:
        ref = refs.get(science_ref_id)
        if ref is None:
            raise ValueError(f"unknown science ref: {science_ref_id}")
        if not ref.approved:
            raise ValueError(f"science ref is unapproved: {science_ref_id}")
        if not set(ref.tags) & required_tags:
            raise ValueError(
                f"science ref {science_ref_id} has no intersection with required tags"
            )
