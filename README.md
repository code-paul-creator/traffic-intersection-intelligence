# 🚦 Traffic Intersection Intelligence System

A simulation and analytics engine for **smart-city traffic management** at signalized intersections, calibrated to common Indian urban traffic patterns (Mumbai, Delhi, Bangalore, Chennai, Pune, and two generic city tiers).

It models vehicle arrivals, lane congestion, and an **adaptive, congestion-aware traffic signal controller** that makes autonomous, real-time decisions about which approach gets green light priority — and measures how much that actually helps compared to a traditional fixed-timing signal.

> Built as a fully synthetic, deterministic simulation (no real camera feeds or proprietary traffic data required) so it's easy to run, test, and extend.

---

## What it does

- **Simulates vehicle flow** at a 4-way signalized intersection, tracking individual vehicles (two-wheelers, cars, autos, buses, trucks, cycles) with realistic Indian-traffic vehicle-mix ratios.
- **Models congestion** per lane/direction using a density-ratio metric, classified into Free-Flow / Light / Moderate / Heavy / Severe levels.
- **Runs an adaptive signal controller** — an autonomous agent that watches live queue lengths on all four approaches and decides, every tick, whether to extend or end the current green phase, instead of using a fixed timer.
- **Quantifies the improvement** of adaptive vs. fixed-timing control on identical traffic conditions (same seed, same arrival pattern), reporting throughput, wait-time, and violation-rate deltas.
- **Models 7 Indian city traffic profiles** (vehicle mix, peak hours, arrival rates) that are fully configurable and easy to extend with your own city.

## Why this matters

Indian intersections are usually run on **fixed-cycle signals** that give every direction the same green time regardless of how much traffic is actually waiting. An arterial road and a quiet side street get treated identically. This project demonstrates — with reproducible, seeded simulations — that a simple, explainable, congestion-aware policy can meaningfully cut wait times on the busier approach without needing a black-box model, expensive sensors, or real-time camera infrastructure beyond a queue-length estimate.

## Quick start

```bash
git clone https://github.com/<your-username>/traffic-intersection-intelligence.git
cd traffic-intersection-intelligence
pip install -r requirements.txt

# List available Indian city traffic profiles
python -m traffic_intel.cli cities

# Run a 20-minute simulation for Mumbai
python -m traffic_intel.cli simulate --city mumbai --minutes 20

# Compare fixed-timing vs adaptive signal control under arterial-road load
python -m traffic_intel.cli compare --city mumbai --minutes 50 --asymmetric --seed 1
```

### As a library

```python
from traffic_intel import IntersectionSimulator, CongestionAnalyzer
from traffic_intel.city_profiles import get_city_profile

profile = get_city_profile("mumbai")
sim = IntersectionSimulator(city_profile=profile, seed=42)
sim.signal.enable_adaptive(lambda d: sum(l.queue_length for l in sim.lanes[d]))

analyzer = CongestionAnalyzer(tick_seconds=sim.tick_seconds)
for snapshot in sim.run(n_ticks=900):
    analyzer.ingest(snapshot)

report = analyzer.analyze()
print(report.overall_congestion, report.throughput_per_min)
```

## Architecture

```
src/traffic_intel/
├── models.py          # Vehicle, Lane, Direction — core data structures
├── city_profiles.py   # Indian city traffic-pattern configs (vehicle mix, peak hours, arrival rates)
├── simulator.py        # Tick-based intersection simulation engine (vehicle spawning + movement)
├── signal_control.py   # Fixed-timing + adaptive congestion-aware signal controller
├── analytics.py         # Congestion classification, throughput, wait-time, hourly breakdown
└── cli.py                # Command-line interface (simulate / compare / cities)

tests/                   # 42 pytest unit tests covering all modules
notebooks/                # Demo notebook: city comparison + adaptive vs fixed benchmark
```

## How the adaptive controller works

The signal controller is a small **autonomous decision-making agent**: every simulation tick, it observes the current queue length on each of the four approaches and decides whether to keep the active phase green or switch. The logic is intentionally simple and auditable rather than a black box:

1. A minimum green time is always honored (no flickering, no starving a direction completely).
2. Once the minimum has elapsed, it compares the active phase's total queue against the waiting phase's queue.
3. If the active phase is meaningfully busier (a margin that scales with total traffic present), it extends green. Otherwise it yields.
4. A hard maximum green time prevents one direction from monopolizing the signal indefinitely.

### Measured result (Mumbai profile, arterial-road scenario, 50 min simulated, seed=1)

| Metric | Fixed-Timing | Adaptive | Change |
|---|---|---|---|
| Busy approach (N/S) wait time | 14.4s | 13.0s | **−9.7%** |
| Side-street (E/W) wait time | 17.9s | 21.9s | +22% (traded off) |
| Signal violations | 32 | 31 | −3% |

This is an honest trade-off, not a free win: the adaptive controller reallocates green time toward the busier direction, which is exactly what a real-world demand-responsive signal does. Run `python -m traffic_intel.cli compare --asymmetric` yourself to reproduce this with any city profile and seed.

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

42/42 tests pass, covering vehicle models, city profiles, signal control (fixed + adaptive), the simulation engine, and analytics.

## Extending this project

- **Add a new city**: add a `CityProfile` entry in `city_profiles.py` with your own vehicle mix and arrival rates.
- **Add a CV pipeline**: swap the simulated `Vehicle` spawner for a real object-tracking pipeline (e.g. YOLO + a tracker) feeding the same `Lane`/`Vehicle` data structures — the analytics and signal-control layers don't need to change.
- **Add a smarter controller**: implement an alternative policy (e.g. reinforcement learning) against the same `SignalController` interface and benchmark it with `CongestionAnalyzer.compare_to_baseline`.

## Disclaimer

All city traffic figures (vehicle mix, arrival rates, peak hours, violation rates) are **illustrative approximations** meant to produce realistic-feeling simulations, not measured municipal data. This is a simulation and decision-policy research tool, not a deployed traffic-control system.

## License

MIT — see [LICENSE](LICENSE).
