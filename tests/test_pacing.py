from running_coach.pacing import Benchmark, zones_from_benchmark, prescribe_pace, predict_time, HALF_KM
from running_coach.periodization import SessionType


def test_bruna_5k_calibration_is_sane():
    z = zones_from_benchmark(Benchmark(5.0, 29 * 60 + 10))  # 5:50/km
    # HMP slower than 5K pace; easy slower than HMP; 5-10k intervals == race pace
    assert z["half_marathon"] == "6:33/km"
    assert z["intervals_5_10k"] == "5:50/km"
    assert z["easy"] == "7:48/km"
    assert "5K em 5:50/km" in z["calibrated_from"]


def test_riegel_half_slower_than_5k():
    t = predict_time(29 * 60 + 10, 5.0, HALF_KM)
    assert t / HALF_KM > (29 * 60 + 10) / 5.0  # half pace slower than 5k pace


def test_prescribe_pace_and_heat():
    z = zones_from_benchmark(Benchmark(5.0, 29 * 60 + 10))
    assert prescribe_pace(SessionType.EASY, z) == "7:48/km"
    assert "6:33/km" in prescribe_pace(SessionType.LONG_PROGRESSIVE, z)
    assert prescribe_pace(SessionType.TEMPO_HMP, z, heat=True) == "por esforço/PSE (calor)"
    assert prescribe_pace(SessionType.OFF, z) == "—"


def test_payload_exposes_calibrated_zones():
    from running_coach.frontend_data import build_frontend_payload
    from pathlib import Path
    z = build_frontend_payload(Path(".")).get("pace_zones", {})
    assert z.get("calibrated_from")  # benchmark present
    assert z.get("half_marathon")


def test_heat_and_invalid_benchmark_fail_to_effort():
    z = zones_from_benchmark(Benchmark(5.0, 1750, conditions="heat"))
    assert "calor" in z["calibrated_from"] and "half_marathon" not in z
    bad = zones_from_benchmark(Benchmark(0.0, 1750))
    assert "inválida" in bad["calibrated_from"]
    neg = zones_from_benchmark(Benchmark(5.0, -10))
    assert "inválida" in neg["calibrated_from"]


def test_heat_off_is_dash_not_effort():
    z = zones_from_benchmark(Benchmark(5.0, 1750))
    assert prescribe_pace(SessionType.OFF, z, heat=True) == "—"
    assert prescribe_pace(SessionType.EASY, z, heat=True) == "por esforço/PSE (calor)"
