import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from traffic_intel.city_profiles import get_city_profile
from traffic_intel.models import Direction
from traffic_intel.simulator import IntersectionSimulator


def make_sim(seed=42, **kwargs):
    profile = get_city_profile("mumbai")
    return IntersectionSimulator(city_profile=profile, seed=seed, start_hour=8.5, **kwargs)


def test_simulator_initializes_empty_lanes():
    sim = make_sim()
    for direction in Direction:
        for lane in sim.lanes[direction]:
            assert lane.queue_length == 0


def test_step_advances_tick_and_time():
    sim = make_sim()
    snap = sim.step()
    assert snap.tick == 1
    assert sim.tick == 1
    assert sim.sim_time_s > 8.5 * 3600.0


def test_run_returns_correct_number_of_snapshots():
    sim = make_sim()
    snapshots = sim.run(n_ticks=50)
    assert len(snapshots) == 50
    assert snapshots[-1].tick == 50


def test_deterministic_with_same_seed():
    sim1 = make_sim(seed=7)
    sim2 = make_sim(seed=7)
    snaps1 = sim1.run(n_ticks=100)
    snaps2 = sim2.run(n_ticks=100)
    assert [s.total_vehicles_crossed for s in snaps1] == [s.total_vehicles_crossed for s in snaps2]
    assert [s.lane_queues for s in snaps1] == [s.lane_queues for s in snaps2]


def test_different_seeds_produce_different_outcomes():
    sim1 = make_sim(seed=1)
    sim2 = make_sim(seed=2)
    snaps1 = sim1.run(n_ticks=200)
    snaps2 = sim2.run(n_ticks=200)
    totals1 = [s.total_vehicles_crossed for s in snaps1]
    totals2 = [s.total_vehicles_crossed for s in snaps2]
    assert totals1 != totals2


def test_vehicles_eventually_cross():
    sim = make_sim()
    snapshots = sim.run(n_ticks=300)
    assert snapshots[-1].total_vehicles_crossed > 0


def test_lane_never_exceeds_capacity_significantly():
    sim = make_sim()
    for _ in range(500):
        sim.step()
        for direction in Direction:
            for lane in sim.lanes[direction]:
                assert lane.density_ratio <= 1.0


def test_direction_arrival_multipliers_affect_queue_balance():
    mult = {Direction.NORTH: 3.0, Direction.SOUTH: 3.0, Direction.EAST: 0.2, Direction.WEST: 0.2}
    sim = make_sim(seed=11, direction_arrival_multipliers=mult)
    for _ in range(300):
        sim.step()
    ns_queue = sum(l.queue_length for l in sim.lanes[Direction.NORTH]) + sum(
        l.queue_length for l in sim.lanes[Direction.SOUTH]
    )
    ew_queue = sum(l.queue_length for l in sim.lanes[Direction.EAST]) + sum(
        l.queue_length for l in sim.lanes[Direction.WEST]
    )
    assert ns_queue > ew_queue


def test_completed_wait_summary_has_all_directions():
    sim = make_sim()
    sim.run(n_ticks=300)
    summary = sim.completed_wait_summary()
    assert set(summary.keys()) == {d.value for d in Direction}


def test_hour_of_day_wraps_correctly():
    sim = make_sim()
    sim.sim_time_s = 25 * 3600.0  # 25 hours -> should wrap to hour 1
    assert sim.hour_of_day == 1.0


def test_is_peak_hour_detection():
    profile = get_city_profile("mumbai")
    sim = IntersectionSimulator(city_profile=profile, seed=1, start_hour=9.0)
    assert sim.is_peak_hour is True  # 9am is within mumbai's (8,11) peak window

    sim2 = IntersectionSimulator(city_profile=profile, seed=1, start_hour=14.0)
    assert sim2.is_peak_hour is False
