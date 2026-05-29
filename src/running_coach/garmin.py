from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import datetime
from typing import Any

from running_coach.models import TIMEZONE


def parse_duration_seconds(value: str) -> float:
    hours, minutes, seconds = value.split(":")
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
    output: list[dict[str, Any]] = []
    for row_number, row in enumerate(reader, start=2):
        local_datetime = _required_text(row, "Data")
        local_date = local_datetime.split(" ")[0]
        title = row.get("Título", "") or ""
        distance_km = parse_number(row.get("Distância")) or 0.0
        duration_seconds = parse_duration_seconds(_required_text(row, "Tempo"))

        activity_type = row.get("Tipo de atividade", "") or ""
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
                "matheus_avg_hr": parse_int(row.get("FC Média")),
                "matheus_max_hr": parse_int(row.get("FC máxima")),
                "avg_pace": _optional_text(row, "Ritmo médio"),
                "best_pace": _optional_text(row, "Melhor ritmo"),
                "matheus_cadence": parse_int(row.get("Cadência de corrida média")),
                "matheus_power": parse_int(row.get("Potência média")),
                "matheus_ground_contact": parse_number(
                    row.get("Tempo médio de contato com o solo")
                ),
                "matheus_stride_length": parse_number(
                    row.get("Comprimento médio da passada")
                ),
                "data_owner_hr": "matheus",
                "data_owner_dynamics": "matheus",
                "is_shared_run_candidate": activity_type == "Corrida",
            }
        )
    return output


def _required_text(row: dict[str, str], field: str) -> str:
    value = row.get(field)
    if value is None or value == "":
        raise ValueError(f"missing required Garmin field: {field}")
    return value


def _optional_text(row: dict[str, str], field: str) -> str | None:
    value = row.get(field)
    if value is None or value.strip() in {"", "--"}:
        return None
    return value
