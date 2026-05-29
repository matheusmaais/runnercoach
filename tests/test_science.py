from pathlib import Path

import pytest
from pydantic import ValidationError

from running_coach.models import SourceType
from running_coach.science import ScienceRef, load_science_refs, validate_science_tags


def science_ref(**overrides):
    values = {
        "science_ref_id": "source-1",
        "title": "Example source",
        "authors": ["Researcher A", "Researcher B"],
        "year": 2024,
        "source_type": SourceType.PEER_REVIEWED_STUDY,
        "journal_or_publisher": "Journal of Running Evidence",
        "doi_or_url": "https://doi.org/10.1234/example",
        "population": "Recreational runners",
        "finding": "Training decisions should match athlete state.",
        "practical_application": "Use evidence tags to gate recommendations.",
        "limits": "Example-only fixture.",
        "tags": ["threshold"],
        "approved": True,
        "approved_date": "2026-05-29",
        "notes": "Fixture for validation tests.",
    }
    values.update(overrides)
    return ScienceRef(**values)


def test_recommendation_cannot_use_unapproved_source():
    refs = {
        "source-1": science_ref(approved=False, approved_date=None),
    }

    with pytest.raises(ValueError, match="unapproved"):
        validate_science_tags(refs, ["source-1"], {"threshold"})


def test_recommendation_requires_matching_tag():
    refs = {"source-1": science_ref(tags=["threshold"])}

    with pytest.raises(ValueError, match="required tags"):
        validate_science_tags(refs, ["source-1"], {"achilles"})


def test_registry_has_minimum_coverage():
    refs = load_science_refs(Path("data/knowledge/science_refs.yaml"))
    approved_refs = [ref for ref in refs.values() if ref.approved]
    approved_tags = {tag for ref in approved_refs for tag in ref.tags}

    assert len(approved_refs) >= 8
    assert {
        "easy_run",
        "long_run",
        "threshold",
        "polarized",
        "load_management",
        "achilles",
        "strength",
        "sleep_recovery",
        "race_calibration",
    } <= approved_tags


def test_science_ref_requires_doi_or_url():
    with pytest.raises(ValidationError):
        science_ref(doi_or_url="")


def test_science_ref_rejects_non_doi_or_url():
    with pytest.raises(ValidationError, match="doi_or_url must be an http URL or DOI"):
        science_ref(doi_or_url="not-a-doi-or-url")


def test_science_ref_accepts_url():
    ref = science_ref(doi_or_url=" https://doi.org/10.1136/bjsports-2016-096581 ")

    assert ref.doi_or_url == "https://doi.org/10.1136/bjsports-2016-096581"


def test_science_ref_accepts_doi():
    ref = science_ref(doi_or_url="10.1136/bjsports-2016-096581")

    assert ref.doi_or_url == "10.1136/bjsports-2016-096581"


@pytest.mark.parametrize(
    "doi_or_url",
    [
        "doi:10.",
        "doi:10.abc",
        "doi:10.123/no-space-ok",
    ],
)
def test_science_ref_rejects_invalid_prefixed_doi(doi_or_url):
    with pytest.raises(ValidationError, match="doi_or_url must be an http URL or DOI"):
        science_ref(doi_or_url=doi_or_url)


def test_science_ref_accepts_prefixed_doi():
    ref = science_ref(doi_or_url="doi:10.1136/bjsports-2016-096581")

    assert ref.doi_or_url == "doi:10.1136/bjsports-2016-096581"


def test_unknown_source_type_rejected():
    with pytest.raises(ValidationError):
        science_ref(source_type="blog")


def test_approved_source_requires_approved_date():
    with pytest.raises(ValidationError):
        science_ref(approved=True, approved_date=None)
