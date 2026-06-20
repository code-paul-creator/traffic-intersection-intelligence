import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from traffic_intel.models import Direction
from traffic_intel.signal_control import SignalController, SignalPhase, SignalState


def test_initial_state_north_south_green():
    sc = SignalController()
    assert sc.state_for(Direction.NORTH) == SignalState.GREEN
    assert sc.state_for(Direction.SOUTH) == SignalState.GREEN
    assert sc.state_for(Direction.EAST) == SignalState.RED
    assert sc.state_for(Direction.WEST) == SignalState.RED


def test_phase_directions_mapping():
    assert set(SignalPhase.NORTH_SOUTH.directions) == {Direction.NORTH, Direction.SOUTH}
    assert set(SignalPhase.EAST_WEST.directions) == {Direction.EAST, Direction.WEST}
    assert SignalPhase.NORTH_SOUTH.other == SignalPhase.EAST_WEST
    assert SignalPhase.EAST_WEST.other == SignalPhase.NORTH_SOUTH


def test_fixed_timing_cycles_through_yellow_and_red():
    sc = SignalController(tick_seconds=1.0, min_green_s=5.0, yellow_s=2.0, all_red_s=1.0)
    states_seen = set()
    for _ in range(15):
        sc.advance(1.0)
        states_seen.add(sc._sub_state)
    assert SignalState.GREEN in states_seen
    assert SignalState.YELLOW in states_seen
    assert SignalState.RED in states_seen


def test_fixed_timing_switches_phase_after_full_cycle():
    sc = SignalController(tick_seconds=1.0, min_green_s=5.0, yellow_s=2.0, all_red_s=1.0)
    assert sc.active_phase == SignalPhase.NORTH_SOUTH
    # 5 (green) + 2 (yellow) + 1 (all-red) = 8 ticks to switch phase
    for _ in range(8):
        sc.advance(1.0)
    assert sc.active_phase == SignalPhase.EAST_WEST
    assert sc.phase_changes == 1


def test_max_green_caps_extension_even_when_adaptive():
    sc = SignalController(tick_seconds=1.0, min_green_s=5.0, max_green_s=10.0, yellow_s=1.0, all_red_s=1.0)
    # Queue function always favors active phase heavily -> would extend forever without cap
    sc.enable_adaptive(lambda d: 100 if d in SignalPhase.NORTH_SOUTH.directions else 0)
    for _ in range(10):
        sc.advance(1.0)
    assert sc._sub_state == SignalState.YELLOW  # forced to end at max_green


def test_adaptive_extends_green_for_busier_phase():
    sc = SignalController(tick_seconds=1.0, min_green_s=5.0, max_green_s=60.0, yellow_s=1.0, all_red_s=1.0)
    # NS heavily busier than EW -> should extend past min_green
    sc.enable_adaptive(lambda d: 50 if d in SignalPhase.NORTH_SOUTH.directions else 2)
    for _ in range(20):
        sc.advance(1.0)
        if sc._sub_state != SignalState.GREEN:
            break
    assert sc._elapsed_in_phase > 5.0  # extended beyond min_green


def test_adaptive_can_be_disabled():
    sc = SignalController()
    sc.enable_adaptive(lambda d: 10)
    assert sc._adaptive is True
    sc.disable_adaptive()
    assert sc._adaptive is False
    assert sc._get_queue_fn is None


def test_status_reports_expected_keys():
    sc = SignalController()
    status = sc.status()
    assert "active_phase" in status
    assert "sub_state" in status
    assert "elapsed_in_phase_s" in status
    assert "adaptive_enabled" in status
    assert "phase_changes" in status
