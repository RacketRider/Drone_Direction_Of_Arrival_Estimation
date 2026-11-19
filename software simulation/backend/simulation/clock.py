"""
Master Simulation Clock.
Provides deterministic timing, stepping, playback controls, and event logging.
"""

import time
from typing import Callable, List, Optional

class SimulationClock:
    """Deterministic simulation clock coordinating all subsystem updates."""
    
    def __init__(self, dt: float = 0.05, speed_multiplier: float = 1.0, seed: int = 42):
        self.dt: float = dt
        self.speed_multiplier: float = speed_multiplier
        self.seed: int = seed
        self.sim_time: float = 0.0
        self.frame_count: int = 0
        self.is_paused: bool = True
        self.single_step_requested: bool = False
        self._listeners: List[Callable[[float, int], None]] = []
        self._event_log: List[dict] = []

    def set_speed(self, multiplier: float) -> None:
        """Sets playback speed multiplier (e.g. 0.25x to 5.0x)."""
        self.speed_multiplier = max(0.1, min(10.0, multiplier))
        self.log_event("SPEED_CHANGE", f"Speed multiplier set to {self.speed_multiplier:.2f}x")

    def play(self) -> None:
        """Resumes/starts simulation execution."""
        self.is_paused = False
        self.log_event("PLAY", f"Simulation resumed at t={self.sim_time:.3f}s")

    def pause(self) -> None:
        """Pauses simulation execution."""
        self.is_paused = True
        self.log_event("PAUSE", f"Simulation paused at t={self.sim_time:.3f}s")

    def step(self) -> bool:
        """Requests single-step execution of one discrete burst cycle."""
        self.single_step_requested = True
        self.is_paused = False
        return self.tick()

    def reset(self, new_seed: Optional[int] = None) -> None:
        """Resets the clock to t=0.0."""
        self.sim_time = 0.0
        self.frame_count = 0
        self.is_paused = True
        self.single_step_requested = False
        if new_seed is not None:
            self.seed = new_seed
        self.log_event("RESET", f"Simulation clock reset. Seed={self.seed}")

    def tick(self) -> bool:
        """
        Advances the clock by dt * speed_multiplier if active.
        Returns True if a simulation step occurred, False if paused.
        """
        if self.is_paused and not self.single_step_requested:
            return False

        effective_dt = self.dt * self.speed_multiplier
        self.sim_time += effective_dt
        self.frame_count += 1

        for listener in self._listeners:
            listener(self.sim_time, self.frame_count)

        if self.single_step_requested:
            self.single_step_requested = False
            self.is_paused = True

        return True

    def register_listener(self, callback: Callable[[float, int], None]) -> None:
        """Registers a listener to be notified on each clock tick."""
        self._listeners.append(callback)

    def log_event(self, event_type: str, message: str) -> None:
        """Appends a timestamped event into the simulation log."""
        entry = {
            "timestamp": time.time(),
            "sim_time": round(self.sim_time, 4),
            "frame": self.frame_count,
            "type": event_type,
            "message": message
        }
        self._event_log.append(entry)
        if len(self._event_log) > 200:
            self._event_log.pop(0)

    @property
    def recent_events(self) -> List[dict]:
        """Returns the most recent event logs."""
        return list(self._event_log)

