import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from traffic_intel.models import (
    Direction,
    Lane,
    TurnIntent,
    Vehicle,
    VehicleType,
    make_intersection_lanes,
)


def test_direction_opposite_pairs():
    assert Direction.NORTH.opposite == Direction.SOUTH
    assert Direction.SOUTH.opposite == Direction.NORTH
    assert Direction.EAST.opposite == Direction.WEST
    assert Direction.WEST.opposite == Direction.EAST


def test_vehicle_speed_within_profile_range():
    for _ in range(50):
        v = Vehicle(
            vehicle_type=VehicleType.CAR,
            direction=Direction.NORTH,
            turn_intent=TurnIntent.STRAIGHT,
        )
        assert 30 <= v.speed_kmh <= 55


def test_vehicle_has_unique_id():
    v1 = Vehicle(VehicleType.CAR, Direction.NORTH, TurnIntent.STRAIGHT)
    v2 = Vehicle(VehicleType.CAR, Direction.NORTH, TurnIntent.STRAIGHT)
    assert v1.id != v2.id


def test_lane_density_ratio_empty():
    lane = Lane(direction=Direction.NORTH, lane_index=0)
    assert lane.density_ratio == 0.0
    assert lane.queue_length == 0


def test_lane_density_ratio_increases_with_queue():
    lane = Lane(direction=Direction.NORTH, lane_index=0, capacity_m=20.0)
    lane.queue.append(Vehicle(VehicleType.CAR, Direction.NORTH, TurnIntent.STRAIGHT))
    density_one = lane.density_ratio
    lane.queue.append(Vehicle(VehicleType.CAR, Direction.NORTH, TurnIntent.STRAIGHT))
    density_two = lane.density_ratio
    assert density_two > density_one


def test_lane_density_ratio_clamped_at_one():
    lane = Lane(direction=Direction.NORTH, lane_index=0, capacity_m=5.0)
    for _ in range(20):
        lane.queue.append(Vehicle(VehicleType.TRUCK, Direction.NORTH, TurnIntent.STRAIGHT))
    assert lane.density_ratio == 1.0


def test_make_intersection_lanes_default_two_per_direction():
    registry = make_intersection_lanes(lanes_per_direction=2)
    assert set(registry.keys()) == set(Direction)
    for direction in Direction:
        assert len(registry[direction]) == 2
        for i, lane in enumerate(registry[direction]):
            assert lane.lane_index == i
            assert lane.direction == direction


def test_make_intersection_lanes_custom_count():
    registry = make_intersection_lanes(lanes_per_direction=4)
    for direction in Direction:
        assert len(registry[direction]) == 4
