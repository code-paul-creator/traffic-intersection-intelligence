"""
Congestion analysis and traffic-flow analytics for the Traffic
Intersection Intelligence System.

Consumes the stream of TickSnapshot objects produced by
IntersectionSimulator and derives higher-level metrics: congestion
levels, throughput, level-of-service classification, and rolling
trend statistics suitable for dashboards and reporting.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

from .simulator import TickSnapshot


class CongestionLevel(str, Enum):
    FREE_FLOW = "free_flow"
    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"
    SEVERE = "severe"


# Density-ratio thresholds mapping to qualitative congestion levels.
# These mirror the spirit of the US Highway Capacity Manual's
# Level-of-Service (LOS) bands, adapted to a 0-1 density scale.
_CONGESTION_THRESHOLDS = [
    (0.15, CongestionLevel.FREE_FLOW),
    (0.40, CongestionLevel.LIGHT),
    (0.65, CongestionLevel.MODERATE),
    (0.85, CongestionLevel.HEAVY),
    (1.01, CongestionLevel.SEVERE),
]


def classify_congestion(density_ratio: float) -> CongestionLevel:
    for threshold, level in _CONGESTION_THRESHOLDS:
        if density_ratio < threshold:
            return level
    return CongestionLevel.SEVERE


@dataclass
class DirectionSummary:
    direction: str
    avg_density: float
    max_density: float
    avg_queue: float
    max_queue: int
    congestion_level: CongestionLevel


@dataclass
class AnalysisReport:
    window_ticks: int
    total_vehicles_crossed: int
    throughput_per_min: float
    avg_wait_time_s: float
    max_wait_time_s: float
    total_violations: int
    violation_rate_pct: float
    overall_congestion: CongestionLevel
    per_direction: List[DirectionSummary]
    bottleneck_direction: str


class CongestionAnalyzer:
    """Computes rolling and windowed analytics over simulation snapshots."""

    def __init__(self, tick_seconds: float = 2.0) -> None:
        self.tick_seconds = tick_seconds
        self._history: List[TickSnapshot] = []

    def ingest(self, snapshot: TickSnapshot) -> None:
        self._history.append(snapshot)

    def ingest_many(self, snapshots: List[TickSnapshot]) -> None:
        self._history.extend(snapshots)

    @property
    def history(self) -> List[TickSnapshot]:
        return self._history

    def analyze(self, last_n_ticks: int = None) -> AnalysisReport:
        """Produce an AnalysisReport over the last N ticks (default: all)."""
        window = self._history if last_n_ticks is None else self._history[-last_n_ticks:]
        if not window:
            raise ValueError("No snapshot history to analyze. Call ingest() first.")

        directions = list(window[0].lane_queues.keys())
        per_direction: List[DirectionSummary] = []

        for d in directions:
            densities = [s.lane_density[d] for s in window]
            queues = [s.lane_queues[d] for s in window]
            avg_density = statistics.fmean(densities)
            per_direction.append(
                DirectionSummary(
                    direction=d,
                    avg_density=round(avg_density, 3),
                    max_density=round(max(densities), 3),
                    avg_queue=round(statistics.fmean(queues), 2),
                    max_queue=max(queues),
                    congestion_level=classify_congestion(avg_density),
                )
            )

        total_crossed = sum(s.vehicles_crossed_this_tick for s in window)
        elapsed_min = (len(window) * self.tick_seconds) / 60.0
        throughput = total_crossed / elapsed_min if elapsed_min > 0 else 0.0

        wait_samples = [s.avg_wait_time_s for s in window if s.avg_wait_time_s > 0]
        avg_wait = statistics.fmean(wait_samples) if wait_samples else 0.0
        max_wait = max(wait_samples) if wait_samples else 0.0

        total_violations = sum(s.violations_this_tick for s in window)
        violation_rate = (total_violations / total_crossed * 100) if total_crossed else 0.0

        overall_density = statistics.fmean([d.avg_density for d in per_direction])
        bottleneck = max(per_direction, key=lambda d: d.avg_density)

        return AnalysisReport(
            window_ticks=len(window),
            total_vehicles_crossed=total_crossed,
            throughput_per_min=round(throughput, 2),
            avg_wait_time_s=round(avg_wait, 1),
            max_wait_time_s=round(max_wait, 1),
            total_violations=total_violations,
            violation_rate_pct=round(violation_rate, 2),
            overall_congestion=classify_congestion(overall_density),
            per_direction=per_direction,
            bottleneck_direction=bottleneck.direction,
        )

    def hourly_breakdown(self) -> Dict[int, Dict[str, float]]:
        """Group history by hour-of-day and report avg density + throughput."""
        buckets: Dict[int, List[TickSnapshot]] = {}
        for s in self._history:
            hour = int(s.hour_of_day)
            buckets.setdefault(hour, []).append(s)

        result: Dict[int, Dict[str, float]] = {}
        for hour, snaps in sorted(buckets.items()):
            avg_density = statistics.fmean(
                [statistics.fmean(list(s.lane_density.values())) for s in snaps]
            )
            crossed = sum(s.vehicles_crossed_this_tick for s in snaps)
            elapsed_min = (len(snaps) * self.tick_seconds) / 60.0
            result[hour] = {
                "avg_density": round(avg_density, 3),
                "throughput_per_min": round(crossed / elapsed_min, 2) if elapsed_min else 0.0,
                "samples": len(snaps),
            }
        return result

    def compare_to_baseline(self, baseline: "CongestionAnalyzer") -> Dict[str, float]:
        """Compare this analyzer's full-history report against a baseline run.

        Useful for quantifying improvement of adaptive signal control vs.
        fixed-timing control on identical traffic conditions.
        """
        this_report = self.analyze()
        base_report = baseline.analyze()

        def pct_change(new: float, old: float) -> float:
            if old == 0:
                return 0.0
            return round((new - old) / old * 100, 2)

        return {
            "throughput_per_min_change_pct": pct_change(
                this_report.throughput_per_min, base_report.throughput_per_min
            ),
            "avg_wait_time_change_pct": pct_change(
                this_report.avg_wait_time_s, base_report.avg_wait_time_s
            ),
            "violation_rate_change_pct": pct_change(
                this_report.violation_rate_pct, base_report.violation_rate_pct
            ),
        }
