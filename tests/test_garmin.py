import subprocess

from running_coach.garmin import (
    make_activity_id,
    parse_duration_seconds,
    parse_garmin_csv_text,
)


def test_parse_duration_seconds_with_decimal_seconds():
    assert parse_duration_seconds("00:05:48.7") == 348.7
    assert parse_duration_seconds("00:50:39") == 3039.0


def test_activity_id_distinguishes_repeated_titles():
    first = make_activity_id(
        "2026-05-28 16:17:36", 7.47, 3039.0, "Santo Ângelo Corrida"
    )
    second = make_activity_id(
        "2026-05-28 17:14:17", 1.33, 348.7, "Santo Ângelo Corrida"
    )

    assert first != second
    assert first.startswith("garmin-20260528T161736")


def test_parse_garmin_csv_maps_physiology_to_matheus():
    csv_text = (
        "Tipo de atividade,Data,Título,Distância,Tempo,FC Média,FC máxima,"
        "Ritmo médio,Melhor ritmo,Cadência de corrida média,Potência média,"
        "Tempo médio de contato com o solo,Comprimento médio da passada\n"
        "Corrida,2026-05-28 16:17:36,Santo Ângelo - 3x10min,7.47,00:50:39,"
        "147,164,6:47,4:55,161,220,250,0.91\n"
    )

    rows = parse_garmin_csv_text(csv_text, source_file="Activities.csv")
    row = rows[0]

    assert row["activity_id"].startswith("garmin-20260528T161736")
    assert row["source_file"] == "Activities.csv"
    assert row["source_row_number"] == 2
    assert row["local_date"] == "2026-05-28"
    assert row["local_datetime"] == "2026-05-28 16:17:36"
    assert row["timezone"] == "America/Sao_Paulo"
    assert row["matheus_avg_hr"] == 147
    assert row["matheus_max_hr"] == 164
    assert row["matheus_cadence"] == 161
    assert row["matheus_power"] == 220
    assert row["matheus_ground_contact"] == 250.0
    assert row["matheus_stride_length"] == 0.91
    assert row["data_owner_hr"] == "matheus"
    assert row["data_owner_dynamics"] == "matheus"


def test_dash_dash_fields_become_none_for_integer_and_number_fields():
    csv_text = (
        "Tipo de atividade,Data,Título,Distância,Tempo,FC Média,FC máxima,"
        "Cadência de corrida média,Potência média,Tempo médio de contato com o solo,"
        "Comprimento médio da passada\n"
        "Corrida,2026-05-28 16:17:36,Santo Ângelo Corrida,7.47,00:50:39,"
        "--,--,--,--,--,--\n"
    )

    row = parse_garmin_csv_text(csv_text, source_file="Activities.csv")[0]

    assert row["matheus_avg_hr"] is None
    assert row["matheus_max_hr"] is None
    assert row["matheus_cadence"] is None
    assert row["matheus_power"] is None
    assert row["matheus_ground_contact"] is None
    assert row["matheus_stride_length"] is None


def test_utf8_sig_bom_text_parses_correctly():
    csv_text = (
        "\ufeffTipo de atividade,Data,Título,Distância,Tempo\n"
        "Corrida,2026-05-28 16:17:36,Santo Ângelo Corrida,7.47,00:50:39\n"
    )

    rows = parse_garmin_csv_text(csv_text, source_file="Activities.csv")

    assert rows[0]["activity_type"] == "Corrida"
    assert rows[0]["title"] == "Santo Ângelo Corrida"


def test_ingest_script_runs_from_repo_root(tmp_path):
    garmin_csv = tmp_path / "Activities.csv"
    output_csv = tmp_path / "activities.csv"
    garmin_csv.write_text(
        "Tipo de atividade,Data,Título,Distância,Tempo\n"
        "Corrida,2026-05-28 16:17:36,Santo Ângelo Corrida,7.47,00:50:39\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            "scripts/ingest_garmin.py",
            "--garmin",
            str(garmin_csv),
            "--output",
            str(output_csv),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "garmin-20260528T161736" in output_csv.read_text(encoding="utf-8")
