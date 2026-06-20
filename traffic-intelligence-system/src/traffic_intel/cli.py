"""
Command-line interface for the Traffic Intersection Intelligence System.

Usage examples
--------------
Run a quick simulation and print a congestion report:
    python -m traffic_intel.cli simulate --city mumbai --minutes 30

Compare fixed-timing vs adaptive signal control on the same traffic:
    python -m traffic_intel.cli compare --city delhi --minutes 30 --asymmetric

List available city profiles:
    python -m traffic_intel.cli cities

Export a tick-by-tick CSV log for external analysis / dashboards:
    python -m traffic_intel.cli simulate --city bangalore --minutes 15 --export out.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import asdict

from .analytics import CongestionAnalyzer
from .city_profiles import get_city_profile, list_city_profiles
from .models import Direction
from .simulator import IntersectionSimulator

ASYMMETRIC_MULTIPLIERS = {
    Direction.NORTH: 2.0,
    Direction.SOUTH: 2.0,
    Direction.EAST: 0.5,
    Direction.WEST: 0.5,
}


def _build_simulator(args) -> IntersectionSimulator:
    profile = get_city_profile(args.city)
    multipliers = ASYMMETRIC_MULTIPLIERS if getattr(args, "asymmetric", False) else None
    return IntersectionSimulator(
        city_profile=profile,
        lanes_per_direction=args.lanes,
        start_hour=args.start_hour,
        seed=args.seed,
        direction_arrival_multipliers=multipliers,
    )


def _print_report(label: str, sim: IntersectionSimulator, analyzer: CongestionAnalyzer) -> None:
    report = analyzer.analyze()
    wait_by_dir = sim.completed_wait_summary()

    print(f"\n=== {label} ===")
    print(f"City profile        : {sim.city_profile.name} ({sim.city_profile.state})")
    print(f"Simulated duration  : {report.window_ticks * sim.tick_seconds / 60:.1f} min")
    print(f"Vehicles crossed    : {report.total_vehicles_crossed}")
    print(f"Throughput          : {report.throughput_per_min} veh/min")
    print(f"Overall congestion  : {report.overall_congestion.value}")
    print(f"Bottleneck approach : {report.bottleneck_direction}")
    print(f"Signal violations   : {report.total_violations} ({report.violation_rate_pct}%)")
    print("Completed wait time by approach (s):")
    for direction, wait in wait_by_dir.items():
        print(f"  {direction:8s}: {wait}")
    print("Per-direction congestion:")
    for d in report.per_direction:
        print(
            f"  {d.direction:8s} avg_density={d.avg_density:.2f}  "
            f"avg_queue={d.avg_queue:5.1f}  level={d.congestion_level.value}"
        )


def cmd_simulate(args) -> None:
    sim = _build_simulator(args)
    analyzer = CongestionAnalyzer(tick_seconds=sim.tick_seconds)

    if args.adaptive:
        sim.signal.enable_adaptive(lambda d: sum(l.queue_length for l in sim.lanes[d]))

    n_ticks = int(args.minutes * 60 / sim.tick_seconds)
    rows = []
    for snap in sim.run(n_ticks=n_ticks):
        analyzer.ingest(snap)
        if args.export:
            row = asdict(snap)
            row["lane_queues"] = str(row["lane_queues"])
            row["lane_density"] = str(row["lane_density"])
            row["signal_state"] = str(row["signal_state"])
            rows.append(row)

    label = "ADAPTIVE SIGNAL CONTROL" if args.adaptive else "FIXED-TIMING SIGNAL CONTROL"
    _print_report(label, sim, analyzer)

    if args.export:
        with open(args.export, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nExported {len(rows)} tick records to {args.export}")


def cmd_compare(args) -> None:
    n_ticks = int(args.minutes * 60 / 2.0)  # tick_seconds default = 2.0

    sim_fixed = _build_simulator(args)
    analyzer_fixed = CongestionAnalyzer(tick_seconds=sim_fixed.tick_seconds)
    for snap in sim_fixed.run(n_ticks=n_ticks):
        analyzer_fixed.ingest(snap)

    sim_adaptive = _build_simulator(args)
    sim_adaptive.signal.enable_adaptive(
        lambda d: sum(l.queue_length for l in sim_adaptive.lanes[d])
    )
    analyzer_adaptive = CongestionAnalyzer(tick_seconds=sim_adaptive.tick_seconds)
    for snap in sim_adaptive.run(n_ticks=n_ticks):
        analyzer_adaptive.ingest(snap)

    _print_report("FIXED-TIMING (BASELINE)", sim_fixed, analyzer_fixed)
    _print_report("ADAPTIVE (SMART CONTROL)", sim_adaptive, analyzer_adaptive)

    comparison = analyzer_adaptive.compare_to_baseline(analyzer_fixed)
    print("\n=== ADAPTIVE vs FIXED: % CHANGE ===")
    for key, value in comparison.items():
        print(f"  {key:32s}: {value:+.2f}%")

    print("\nNote: a positive throughput change and negative wait-time")
    print("change indicate adaptive control is outperforming fixed timing.")
    print("Under asymmetric load, expect the busier approach's wait time")
    print("to drop noticeably, traded off against the lighter approach.")


def cmd_cities(args) -> None:
    print("Available city profiles:\n")
    for key in list_city_profiles():
        profile = get_city_profile(key)
        print(f"  {key:16s} -> {profile.name}, {profile.state}")
        print(f"                     {profile.notes}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="traffic_intel",
        description="Traffic Intersection Intelligence System -- Indian smart-city traffic simulation & analytics.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--city", default="generic_tier1", help="City profile key (see 'cities' command)")
    common.add_argument("--lanes", type=int, default=2, help="Lanes per approach direction")
    common.add_argument("--minutes", type=float, default=30.0, help="Simulated duration in minutes")
    common.add_argument("--start-hour", type=float, default=8.5, dest="start_hour", help="Simulation start hour (0-24)")
    common.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility")
    common.add_argument(
        "--asymmetric",
        action="store_true",
        help="Model an arterial-road scenario: N/S gets 2x traffic, E/W gets 0.5x",
    )

    p_sim = subparsers.add_parser("simulate", parents=[common], help="Run a single simulation and print a report")
    p_sim.add_argument("--adaptive", action="store_true", help="Use adaptive (congestion-aware) signal control")
    p_sim.add_argument("--export", metavar="FILE.csv", help="Export tick-by-tick data to a CSV file")
    p_sim.set_defaults(func=cmd_simulate)

    p_cmp = subparsers.add_parser(
        "compare", parents=[common], help="Run fixed-timing vs adaptive control side by side"
    )
    p_cmp.set_defaults(func=cmd_compare)

    p_cities = subparsers.add_parser("cities", help="List available Indian city traffic profiles")
    p_cities.set_defaults(func=cmd_cities)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
