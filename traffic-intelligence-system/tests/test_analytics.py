import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from traffic_intel.analytics import CongestionAnalyzer, CongestionLevel, classify_congestion
from traffic_intel.city_profiles import get_city_profile
from traffic_intel.simulator import IntersectionSimulator


def test_classify_congestion_boundaries():
    assert classify_congestion(0.0) == CongestionLevel.FREE_FLOW
    assert classify_congestion(0.14) == CongestionLevel.FREE_FLOW
    assert classify_congestion(0.20) == CongestionLevel.LIGHT
    assert classify_congestion(0.50) == CongestionLevel.MODERATE
    assert classify_congestion(0.70) == CongestionLevel.HEAVY
    assert classify_congestion(0.95) == CongestionLevel.SEVERE
    assert classify_congestion(1.0) == CongestionLevel.SEVERE


def test_analyze_raises_on_empty_history():
    analyzer = CongestionAnalyzer()
    with pytest.raises(ValueError):
        analyzer.analyze()


def _run_simulation(n_ticks=200, seed=42):
    profile = get_city_profile("mumbai")
    sim = IntersectionSimulator(city_profile=profile, seed=seed, start_hour=8.5)
    analyzer = CongestionAnalyzer(tick_seconds=sim.tick_seconds)
    for snap in sim.run(n_ticks=n_ticks):
        analyzer.ingest(snap)
    return sim, analyzer


def test_analyze_report_has_all_directions():
    _, analyzer = _run_simulation()
    report = analyzer.analyze()
    directions = {d.direction for d in report.per_direction}
    assert directions == {"north", "south", "east", "west"}


def test_analyze_report_fields_are_sane():
    _, analyzer = _run_simulation()
    report = analyzer.analyze()
    assert report.total_vehicles_crossed >= 0
    assert report.throughput_per_min >= 0
    assert 0 <= report.violation_rate_pct <= 100
    assert report.bottleneck_direction in {"north", "south", "east", "west"}


def test_analyze_with_window_uses_subset():
    _, analyzer = _run_simulation(n_ticks=200)
    full_report = analyzer.analyze()
    windowed_report = analyzer.analyze(last_n_ticks=50)
    assert windowed_report.window_ticks == 50
    assert full_report.window_ticks == 200


def test_hourly_breakdown_groups_by_hour():
    _, analyzer = _run_simulation(n_ticks=2000)
    breakdown = analyzer.hourly_breakdown()
    assert len(breakdown) >= 1
    for hour, stats in breakdown.items():
        assert 0 <= hour <= 23
        assert "avg_density" in stats
        assert "throughput_per_min" in stats


def test_compare_to_baseline_returns_pct_changes():
    _, analyzer_a = _run_simulation(seed=1)
    _, analyzer_b = _run_simulation(seed=1)
    comparison = analyzer_a.compare_to_baseline(analyzer_b)
    assert "throughput_per_min_change_pct" in comparison
    assert "avg_wait_time_change_pct" in comparison
    assert "violation_rate_change_pct" in comparison
    # Same seed, same conditions -> should be identical (0% change)
    assert comparison["throughput_per_min_change_pct"] == 0.0


def test_ingest_many_adds_all_snapshots():
    profile = get_city_profile("mumbai")
    sim = IntersectionSimulator(city_profile=profile, seed=1, start_hour=8.5)
    snapshots = sim.run(n_ticks=100)
    analyzer = CongestionAnalyzer()
    analyzer.ingest_many(snapshots)
    assert len(analyzer.history) == 100
