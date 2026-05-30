from running_coach.pacing import Benchmark, zones_from_benchmark, prescribe_pace, predict_time, HALF_KM
from running_coach.periodization import SessionType


def test_bruna_5k_calibration_is_sane():
    z = zones_from_benchmark(Benchmark(5.0, 29 * 60 + 10))  # 5:50/km
    # Anchored on race pace: easy near race pace (endurance profile), intervals == 5K.
    assert z["intervals_5_10k"] == "5:50/km"
    assert z["tempo_hmp"] == "6:10/km"
    assert z["easy"] == "6:38/km"
    assert z["long_easy"] == "6:40/km"
    assert z["half_projection"] == "6:33/km"
    assert "5K em 5:50/km" in z["calibrated_from"]


def test_riegel_half_slower_than_5k():
    t = predict_time(29 * 60 + 10, 5.0, HALF_KM)
    assert t / HALF_KM > (29 * 60 + 10) / 5.0  # half pace slower than 5k pace


def test_prescribe_pace_and_heat():
    z = zones_from_benchmark(Benchmark(5.0, 29 * 60 + 10))
    assert prescribe_pace(SessionType.EASY, z) == "6:38/km"
    assert "6:10/km" in prescribe_pace(SessionType.LONG_PROGRESSIVE, z)
    assert prescribe_pace(SessionType.TEMPO_HMP, z, heat=True) == "por esforço/PSE (calor)"
    assert prescribe_pace(SessionType.OFF, z) == "—"


def test_payload_exposes_calibrated_zones():
    from running_coach.frontend_data import build_frontend_payload
    from pathlib import Path
    z = build_frontend_payload(Path(".")).get("pace_zones", {})
    assert z.get("calibrated_from")  # benchmark present
    assert z.get("half_projection")


def test_heat_and_invalid_benchmark_fail_to_effort():
    z = zones_from_benchmark(Benchmark(5.0, 1750, conditions="heat"))
    assert "calor" in z["calibrated_from"] and "half_projection" not in z
    bad = zones_from_benchmark(Benchmark(0.0, 1750))
    assert "inválida" in bad["calibrated_from"]
    neg = zones_from_benchmark(Benchmark(5.0, -10))
    assert "inválida" in neg["calibrated_from"]


def test_heat_off_is_dash_not_effort():
    z = zones_from_benchmark(Benchmark(5.0, 1750))
    assert prescribe_pace(SessionType.OFF, z, heat=True) == "—"
    assert prescribe_pace(SessionType.EASY, z, heat=True) == "por esforço/PSE (calor)"


def test_select_best_picks_fastest_and_auto_tightens():
    from running_coach.pacing import select_best
    # a faster 5K wins; heat + invalid are ignored
    best = select_best([
        Benchmark(5.0, 29 * 60 + 10),
        Benchmark(5.0, 27 * 60 + 30),
        Benchmark(5.0, 25 * 60, conditions="heat"),
        Benchmark(0.0, 1000),
    ])
    assert best.time_seconds == 27 * 60 + 30
    z = zones_from_benchmark(best)
    assert z["intervals_5_10k"] == "5:30/km" and z["long_easy"] == "6:20/km"
    # a 10K effort can outrank a 5K if the normalized 5K is faster
    mixed = select_best([Benchmark(5.0, 29 * 60 + 10), Benchmark(10.0, 58 * 60)])
    assert mixed.distance_km == 10.0  # 58:00/10K ~ stronger than 29:10/5K
    assert select_best([]) is None


def test_hard_training_effort_calibrates(tmp_path):
    from running_coach.frontend_data import _benchmark_candidates
    proc = tmp_path / "data/processed"; proc.mkdir(parents=True)
    (tmp_path / "data/plan").mkdir(parents=True)
    from datetime import date
    today = date.today().isoformat()
    (proc / "workouts.csv").write_text(
        "local_date,category,distance_km,avg_pace,all_out_race,shared_run,bruna_present,athlete_context\n"
        f"{today},quality,6.0,5:55,,true,true,shared\n"            # qualifies
        f"{today},easy,8.0,6:50,,true,true,shared\n"              # easy: NO
        f"{today},quality,6.0,4:30,,false,false,matheus_garmin_only\n"  # Matheus-only: NO
        f"{today},quality,4.0,5:00,,true,true,shared\n"          # <5km: NO
    )
    cands = _benchmark_candidates(tmp_path)
    assert len(cands) == 1 and abs(cands[0].distance_km - 6.0) < 1e-6


def test_classify_effort_detects_strong_and_ignores_easy():
    from running_coach.pacing import classify_effort
    z = zones_from_benchmark(Benchmark(5.0, 29 * 60 + 10))  # race 5:50, tempo 6:10
    assert classify_effort(350, z) == "race"          # 5:50 == 5K pace
    assert classify_effort(370, z, pse=7) == "threshold"  # 6:10 threshold band
    assert classify_effort(400, z) == "easy"          # 6:40 easy
    assert classify_effort(0, z) == "easy"            # invalid
    assert classify_effort(350, {}) == "easy"         # no zones -> safe


def test_readiness_levels():
    from running_coach.frontend_data import _readiness
    assert _readiness([])["level"] == "indefinido"
    assert _readiness([{"local_date": "2026-06-01", "matheus_achilles_after": "6"}])["level"] == "recuperar"
    assert _readiness([{"local_date": "2026-06-01", "bruna_pse": "8"}])["level"] == "cautela"
    assert _readiness([{"local_date": "2026-06-01", "bruna_pse": "5"}])["level"] == "boa"


def test_heat_adjusted_pace():
    from running_coach.pacing import heat_adjusted_pace
    assert heat_adjusted_pace(360, 15) == 360       # no change at/below 15C
    assert heat_adjusted_pace(360, 30) == 360 + 45  # +3s/km * 15C
    assert heat_adjusted_pace(360, 100) == 360 + 90 # capped
    assert heat_adjusted_pace(0, 30) == 0           # invalid safe


def test_fast_easy_run_does_not_auto_calibrate(tmp_path):
    """A fast easy/low-PSE run (downhill/GPS glitch) must NOT tighten zones."""
    from running_coach.frontend_data import _benchmark_candidates
    (tmp_path / "data/plan").mkdir(parents=True)
    (tmp_path / "data/processed").mkdir(parents=True)
    from datetime import date
    today = date.today().isoformat()
    (tmp_path / "data/plan/races.yaml").write_text(
        "schema_version: 1\nraces:\n"
        f"  - race_id: 5k-x\n    date: '{today}'\n    distance_km: 5.0\n    time_seconds: 1750\n    status: done\n")
    (tmp_path / "data/processed/workouts.csv").write_text(
        "local_date,category,distance_km,avg_pace,bruna_pse,shared_run,bruna_present,all_out_race\n"
        f"{today},easy,5.5,5:30,3,true,true,\n")       # fast but EASY + low PSE
    cands = _benchmark_candidates(tmp_path)
    # only the race remains; the fast-easy run is rejected
    assert all(abs(c.distance_km - 5.5) > 1e-6 for c in cands)


def test_hard_corroborated_run_does_auto_calibrate(tmp_path):
    from running_coach.frontend_data import _benchmark_candidates
    (tmp_path / "data/plan").mkdir(parents=True)
    (tmp_path / "data/processed").mkdir(parents=True)
    from datetime import date
    today = date.today().isoformat()
    (tmp_path / "data/plan/races.yaml").write_text(
        "schema_version: 1\nraces:\n"
        f"  - race_id: 5k-x\n    date: '{today}'\n    distance_km: 5.0\n    time_seconds: 1750\n    status: done\n")
    (tmp_path / "data/processed/workouts.csv").write_text(
        "local_date,category,distance_km,avg_pace,bruna_pse,shared_run,bruna_present,all_out_race\n"
        f"{today},,6.0,5:48,8,true,true,\n")            # threshold-ish + PSE 8
    cands = _benchmark_candidates(tmp_path)
    assert any(abs(c.distance_km - 6.0) < 1e-6 for c in cands)


def test_readiness_dated_without_evidence_is_indefinido():
    from running_coach.frontend_data import _readiness
    assert _readiness([{"local_date": "2026-06-01"}])["level"] == "indefinido"


def test_prescribe_workout_is_concrete():
    from running_coach.pacing import prescribe_workout
    z = zones_from_benchmark(Benchmark(5.0, 1750))
    iv = prescribe_workout(SessionType.INTERVALS_5_10K, z)
    assert "5 × 1 km" in iv and "@5:50/km" in iv and "trote" in iv  # reps, pace, recovery
    assert "min" in prescribe_workout(SessionType.EASY, z)          # duration
    assert "14 km" in prescribe_workout(SessionType.LONG_EASY, z, long_km=14.0)
    assert prescribe_workout(SessionType.OFF, z).startswith("Folga")
    tempo = prescribe_workout(SessionType.TEMPO_HMP, z)
    assert "Aquecer" in tempo and "ritmo de meia" in tempo and "soltar" in tempo
    assert "esforço/PSE" in prescribe_workout(SessionType.EASY, z, heat=True)
