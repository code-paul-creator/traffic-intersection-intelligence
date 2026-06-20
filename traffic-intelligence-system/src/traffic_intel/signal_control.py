"""
Signal control for the Traffic Intersection Intelligence System.

Implements two controllers:
  - FixedTimer: classic round-robin fixed-duration phases (baseline).
  - SignalController: wraps either a fixed timer or an adaptive policy
    that extends/shortens green time based on live congestion -- this is
    the "smart" part of the smart-city system.

The adaptive policy is intentionally simple and explainable (a
congestion-weighted longest-queue heuristic) rather than a black-box
model, so the logic is auditable and easy to extend with real
reinforcement-learning or optimization-based controllers later.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Optional

from .models import Direction


class SignalState(str, Enum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"


class SignalPhase(str, Enum):
    """Two-phase intersection: NS pair gets green together, then EW pair."""

    NORTH_SOUTH = "north_south"
    EAST_WEST = "east_west"

    @property
    def directions(self) -> tuple[Direction, Direction]:
        if self == SignalPhase.NORTH_SOUTH:
            return (Direction.NORTH, Direction.SOUTH)
        return (Direction.EAST, Direction.WEST)

    @property
    def other(self) -> "SignalPhase":
        return SignalPhase.EAST_WEST if self == SignalPhase.NORTH_SOUTH else SignalPhase.NORTH_SOUTH


class SignalController:
    """Adaptive two-phase traffic signal controller.

    Default behavior is fixed-timing (min_green for each phase). Call
    `enable_adaptive(get_queue_fn)` to switch to congestion-aware control,
    where green duration for the active phase is extended (up to
    max_green) while its queue remains significantly longer than the
    waiting phase's queue, and a minimum green is always honored to
    avoid starving heavy directions.
    """

    def __init__(
        self,
        tick_seconds: float = 2.0,
        min_green_s: float = 15.0,
        max_green_s: float = 75.0,
        yellow_s: float = 3.0,
        all_red_s: float = 1.0,
    ) -> None:
        self.tick_seconds = tick_seconds
        self.min_green_s = min_green_s
        self.max_green_s = max_green_s
        self.yellow_s = yellow_s
        self.all_red_s = all_red_s

        self.active_phase: SignalPhase = SignalPhase.NORTH_SOUTH
        self._sub_state: SignalState = SignalState.GREEN
        self._elapsed_in_substate: float = 0.0
        self._elapsed_in_phase: float = 0.0

        self._adaptive = False
        self._get_queue_fn = None  # Callable[[Direction], int]
        self.phase_changes: int = 0
        self.history: list = []  # list[(phase, duration_s)]

    # ------------------------------------------------------------------ #
    # Public configuration
    # ------------------------------------------------------------------ #

    def enable_adaptive(self, get_queue_fn) -> None:
        """Switch to congestion-aware adaptive signal timing.

        get_queue_fn: Callable[[Direction], int] returning current queue
        length for a direction, used to decide whether to extend green.
        """
        self._adaptive = True
        self._get_queue_fn = get_queue_fn

    def disable_adaptive(self) -> None:
        self._adaptive = False
        self._get_queue_fn = None

    # ------------------------------------------------------------------ #
    # State query
    # ------------------------------------------------------------------ #

    def state_for(self, direction: Direction) -> SignalState:
        if direction in self.active_phase.directions:
            return self._sub_state
        if self._sub_state in (SignalState.GREEN, SignalState.YELLOW):
            return SignalState.RED
        # During the brief all-red clearance, every direction is red.
        return SignalState.RED

    # ------------------------------------------------------------------ #
    # Stepping logic
    # ------------------------------------------------------------------ #

    def advance(self, dt_s: float) -> None:
        self._elapsed_in_substate += dt_s
        self._elapsed_in_phase += dt_s

        if self._sub_state == SignalState.GREEN:
            if self._should_end_green():
                self._sub_state = SignalState.YELLOW
                self._elapsed_in_substate = 0.0

        elif self._sub_state == SignalState.YELLOW:
            if self._elapsed_in_substate >= self.yellow_s:
                self._sub_state = SignalState.RED  # all-red clearance window
                self._elapsed_in_substate = 0.0

        elif self._sub_state == SignalState.RED:
            if self._elapsed_in_substate >= self.all_red_s:
                self._switch_phase()

    def _should_end_green(self) -> bool:
        if self._elapsed_in_phase >= self.max_green_s:
            return True

        if not self._adaptive or self._get_queue_fn is None:
            # Fixed timing: end exactly at min_green
            return self._elapsed_in_phase >= self.min_green_s

        active_q = sum(self._get_queue_fn(d) for d in self.active_phase.directions)
        waiting_q = sum(self._get_queue_fn(d) for d in self.active_phase.other.directions)
        total_q = active_q + waiting_q

        # Absolute floor: always allow a short clearance window before
        # considering a switch, to avoid rapid signal flicker.
        absolute_floor_s = 6.0
        if self._elapsed_in_phase < absolute_floor_s:
            return False

        if total_q == 0:
            return True  # nothing waiting anywhere, no reason to hold green

        # Once the normal min_green has elapsed, use the proportional
        # congestion margin to decide whether to keep extending.
        if self._elapsed_in_phase >= self.min_green_s:
            margin_threshold = max(3, round(0.20 * total_q))
            congestion_margin = active_q - waiting_q
            return congestion_margin <= margin_threshold

        # Between the absolute floor and min_green: only cut short if the
        # waiting side is severely starved relative to the active side,
        # so a quiet direction doesn't hog green while a busy one backs up.
        if waiting_q > 0 and active_q < waiting_q * 0.35:
            return True

        return False

    def _switch_phase(self) -> None:
        self.history.append((self.active_phase.value, round(self._elapsed_in_phase, 1)))
        self.phase_changes += 1
        self.active_phase = self.active_phase.other
        self._sub_state = SignalState.GREEN
        self._elapsed_in_substate = 0.0
        self._elapsed_in_phase = 0.0

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #

    def status(self) -> Dict[str, object]:
        return {
            "active_phase": self.active_phase.value,
            "sub_state": self._sub_state.value,
            "elapsed_in_phase_s": round(self._elapsed_in_phase, 1),
            "adaptive_enabled": self._adaptive,
            "phase_changes": self.phase_changes,
        }
