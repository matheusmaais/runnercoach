from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import datetime
from typing import Any

from running_coach.models import TIMEZONE


GARMIN_ACTIVITY_FIELDS = [
    "activity_id",
    "source_file",
    "source_row_number",
    "local_date",
    "local_datetime",
    "timezone",
    "activity_type",
    "title",
    "distance_km",
    "duration_seconds",
    "matheus_avg_hr",
    "matheus_max_hr",
    "avg_pace",
    "best_pace",
    "matheus_cadence",
    "matheus_power",
    "matheus_ground_contact",
    "matheus_stride_length",
    "data_owner_hr",
    "data_owner_dynamics",
    "is_shared_run_candidate",
]

REQUIRED_GARMIN_FIELDS = [
    "Data",
    "Tipo de atividade",
    "Título",
    "Distância",
    "Tempo",
]


class GarminParseError(Exception):
    def __init__(
        self,
        *,
        source_file: str,
        row_number: int,
        field: str,
        value: Any,
        reason: str,
    ) -> None:
        self.source_file = source_file
        self.row_number = row_number
        self.field = field
        self.value = value
        self.reason = reason
        super().__init__(
            f"{source_file}: row {row_number}, field {field}, value {value!r}: {reason}"
        )


def parse_duration_seconds(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    if not (hours and minutes and seconds):
        raise ValueError("duration must use HH:MM:SS")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if normalized in {"", "--"}:
        return None
    return float(normalized.replace(",", "."))


def parse_int(value: str | None) -> int | None:
    number = parse_number(value)
    if number is None:
        return None
    return int(number)


def make_activity_id(
    local_datetime: str, distance_km: float, duration_seconds: float, title: str
) -> str:
    activity_datetime = datetime.strptime(local_datetime, "%Y-%m-%d %H:%M:%S")
    normalized_title = re.sub(r"\s+", " ", title.strip().lower())
    digest_source = (
        f"{activity_datetime.isoformat()}|{distance_km:.2f}|"
        f"{duration_seconds:.1f}|{normalized_title}"
    )
    digest = hashlib.sha1(digest_source.encode("utf-8")).hexdigest()[:8]
    distance_token = f"{distance_km:.2f}".replace(".", "p")
    duration_token = str(int(round(duration_seconds)))
    return (
        f"garmin-{activity_datetime:%Y%m%dT%H%M%S}-"
        f"{distance_token}km-{duration_token}s-{digest}"
    )


def parse_garmin_csv_text(csv_text: str, source_file: str) -> list[dict[str, Any]]:
    text = csv_text.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(text))
    _validate_required_headers(reader.fieldnames, source_file)
    output: list[dict[str, Any]] = []
    for row_number, row in enumerate(reader, start=2):
        local_datetime = _required_text(row, "Data", source_file, row_number)
        local_date = local_datetime.split(" ")[0]
        title = _required_text(row, "Título", source_file, row_number)
        distance_km = _parse_number_field(row, "Distância", source_file, row_number)
        duration_seconds = _parse_duration_field(row, "Tempo", source_file, row_number)

        activity_type = _required_text(
            row, "Tipo de atividade", source_file, row_number
        )
        output.append(
            {
                "activity_id": make_activity_id(
                    local_datetime, distance_km, duration_seconds, title
                ),
                "source_file": source_file,
                "source_row_number": row_number,
                "local_date": local_date,
                "local_datetime": local_datetime,
                "timezone": TIMEZONE,
                "activity_type": activity_type,
                "title": title,
                "distance_km": distance_km,
                "duration_seconds": duration_seconds,
                "matheus_avg_hr": _parse_int_field(
                    row, "FC Média", source_file, row_number
                ),
                "matheus_max_hr": _parse_int_field(
                    row, "FC máxima", source_file, row_number
                ),
                "avg_pace": _optional_text(row, "Ritmo médio"),
                "best_pace": _optional_text(row, "Melhor ritmo"),
                "matheus_cadence": _parse_int_field(
                    row, "Cadência de corrida média", source_file, row_number
                ),
                "matheus_power": _parse_int_field(
                    row, "Potência média", source_file, row_number
                ),
                "matheus_ground_contact": _parse_number_field(
                    row,
                    "Tempo médio de contato com o solo",
                    source_file,
                    row_number,
                    required=False,
                ),
                "matheus_stride_length": _parse_number_field(
                    row,
                    "Comprimento médio da passada",
                    source_file,
                    row_number,
                    required=False,
                ),
                "data_owner_hr": "matheus",
                "data_owner_dynamics": "matheus",
                "is_shared_run_candidate": activity_type.strip().casefold()
                == "corrida",
            }
        )
    return output


def _validate_required_headers(fieldnames: list[str] | None, source_file: str) -> None:
    headers = set(fieldnames or [])
    for field in REQUIRED_GARMIN_FIELDS:
        if field not in headers:
            raise GarminParseError(
                source_file=source_file,
                row_number=1,
                field=field,
                value="",
                reason="missing required Garmin field",
            )


def _required_text(
    row: dict[str, str], field: str, source_file: str, row_number: int
) -> str:
    value = row.get(field)
    if value is None or value == "":
        raise GarminParseError(
            source_file=source_file,
            row_number=row_number,
            field=field,
            value=value or "",
            reason="missing required Garmin field",
        )
    return value


def _optional_text(row: dict[str, str], field: str) -> str | None:
    value = row.get(field)
    if value is None or value.strip() in {"", "--"}:
        return None
    return value


def _parse_duration_field(
    row: dict[str, str], field: str, source_file: str, row_number: int
) -> float:
    value = _required_text(row, field, source_file, row_number)
    try:
        return parse_duration_seconds(value)
    except (TypeError, ValueError) as error:
        raise GarminParseError(
            source_file=source_file,
            row_number=row_number,
            field=field,
            value=value,
            reason=str(error),
        ) from error


def _parse_number_field(
    row: dict[str, str],
    field: str,
    source_file: str,
    row_number: int,
    *,
    required: bool = True,
) -> float | None:
    value = row.get(field)
    if required:
        _required_text(row, field, source_file, row_number)
    try:
        return parse_number(value)
    except (TypeError, ValueError) as error:
        raise GarminParseError(
            source_file=source_file,
            row_number=row_number,
            field=field,
            value=value,
            reason=str(error),
        ) from error


def _parse_int_field(
    row: dict[str, str], field: str, source_file: str, row_number: int
) -> int | None:
    value = row.get(field)
    try:
        return parse_int(value)
    except (TypeError, ValueError) as error:
        raise GarminParseError(
            source_file=source_file,
            row_number=row_number,
            field=field,
            value=value,
            reason=str(error),
        ) from error
