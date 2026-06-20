import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from traffic_intel.city_profiles import CITY_PROFILES, get_city_profile, list_city_profiles
from traffic_intel.models import VehicleType


def test_all_profiles_have_valid_vehicle_mix():
    for key, profile in CITY_PROFILES.items():
        assert len(profile.vehicle_mix) > 0
        for vtype, weight in profile.vehicle_mix.items():
            assert isinstance(vtype, VehicleType)
            assert weight > 0


def test_all_profiles_have_positive_arrival_rate():
    for key, profile in CITY_PROFILES.items():
        assert profile.base_arrival_rate > 0
        assert profile.peak_multiplier >= 1.0


def test_get_city_profile_case_insensitive():
    p1 = get_city_profile("Mumbai")
    p2 = get_city_profile("mumbai")
    p3 = get_city_profile("MUMBAI")
    assert p1.name == p2.name == p3.name


def test_get_city_profile_handles_spaces():
    profile = get_city_profile("generic tier1")
    assert profile is not None


def test_get_city_profile_raises_on_unknown():
    with pytest.raises(KeyError):
        get_city_profile("atlantis")


def test_list_city_profiles_returns_sorted_list():
    profiles = list_city_profiles()
    assert profiles == sorted(profiles)
    assert "mumbai" in profiles
    assert "delhi" in profiles


def test_vehicle_mix_weights_sum_reasonable():
    # Mix doesn't need to sum exactly to 1, but should be in a sane range
    for key, profile in CITY_PROFILES.items():
        total = sum(profile.vehicle_mix.values())
        assert 0.9 <= total <= 1.1, f"{key} vehicle_mix sums to {total}"
